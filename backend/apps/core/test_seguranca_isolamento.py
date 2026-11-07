"""
Auditoria de segurança de pré-homologação — isolamento entre clientes (IDOR) e RBAC de escrita,
varrendo TODAS as rotas registradas (não uma lista escrita à mão).

Dados: o cenário de exemplo (`seed_relatorios_exemplo`) é o "cliente-vítima"; um segundo cliente,
sem dado nenhum, é o "intruso". Duas varreduras:

1. Leitura (GET) — para cada rota de lista e de detalhe/ação (com ids reais tirados da API como
   interno), o intruso e o usuário órfão (perfil cliente sem `cliente_id`) NÃO podem receber nenhum
   identificador da vítima (nome, CNPJ, TAG, nº de OSP/relatório/laudo). Um "oráculo" só vale se
   enxergar o dado: o teste confere que o dono legítimo o encontra em várias rotas.
2. Escrita — usuários de cliente só escrevem onde o produto permite (retorno da OSP e
   notificações próprias); nas demais rotas qualquer POST/PUT/PATCH/DELETE precisa ser barrado
   (401/403/404/405) ANTES de validar o corpo. Técnico não-Master não pode agir como Admin.

Rota nova que aparecer sem classificação cai na varredura sozinha — é o objetivo.
"""
import io
import re

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import URLPattern, URLResolver, get_resolver
from rest_framework.test import APIClient

from apps.cadastros.models import Area, Cliente, Equipamento, Setor
from apps.coletas.models import Relatorio
from apps.core.management.commands.seed_relatorio_completo import CNPJ_DEMO
from apps.laudos.models import Laudo
from apps.osp.models import OrdemServico

User = get_user_model()

#: Rotas sem escopo de cliente por desenho (autenticação, mídia tem teste próprio).
IGNORAR_PREFIXOS = ("api/auth/", "api/media/", "api/schema/", "api/docs/", "django-admin/")

#: Escritas que o Portal PODE fazer (permissão decidida no recurso, escopo no queryset).
ESCRITA_CLIENTE_PERMITIDA = (
    r"^api/osps/\d+/$",                # PATCH: campos de retorno
    r"^api/osps/\d+/status/$",         # PATCH: máquina de estados (permissão por perfil no service)
    r"^api/notificacoes/",             # só as próprias
    # Assinatura do cliente (Anexo I 2.6.2.6): só perfis aprovadores, só OSP do próprio cliente.
    # Permissão, 404 fora do escopo e imutabilidade têm testes próprios em apps/osp/test_execucao.py.
    r"^api/osp-assinaturas/$",
)

_GRUPO = re.compile(r"\(\?P<(\w+)>(?:[^()]|\([^()]*\))*\)")
_CONVERSOR = re.compile(r"<(?:\w+:)?(\w+)>")


def _coletar(padroes, prefixo=""):
    for p in padroes:
        trecho = str(p.pattern).replace("^", "").replace("$", "")
        if isinstance(p, URLResolver):
            yield from _coletar(p.url_patterns, prefixo + trecho)
        elif isinstance(p, URLPattern):
            yield (prefixo + trecho).lstrip("/")


def _modelos_de_rota():
    """Moldes `api/xxx/{pk}/acao/` já sem regex; descarta sufixo de formato e rotas ignoradas."""
    saida = set()
    for bruto in _coletar(get_resolver().url_patterns):
        if "format" in bruto or not bruto.startswith("api/"):
            continue
        molde = _CONVERSOR.sub(r"{\1}", _GRUPO.sub(lambda m: "{" + m.group(1) + "}", bruto))
        molde = molde.replace("\\.", ".").replace("/?", "/")
        if "\\" in molde or molde.startswith(IGNORAR_PREFIXOS):
            continue
        saida.add(molde)
    return sorted(saida)


def _lista(resposta):
    dados = getattr(resposta, "data", None)
    if isinstance(dados, dict):
        dados = dados.get("results", [])
    return dados if isinstance(dados, list) else []


class IsolamentoEntreClientes(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_relatorios_exemplo", stdout=io.StringIO())
        cls.vitima = Cliente.objects.get(cnpj=CNPJ_DEMO)
        cls.intruso_cliente = Cliente.objects.create(nome="Empresa Intrusa SA", cnpj="12.345.678/0001-95")
        area = Area.objects.create(cliente=cls.intruso_cliente, codigo="I1", nome="Area Intrusa")
        setor = Setor.objects.create(area=area, codigo="I1", nome="Setor Intruso")
        Equipamento.objects.create(setor=setor, tag="INTRUSO-001", nome="Equip Intruso")

        mk = lambda email, perfil, **kw: User.objects.create_user(  # noqa: E731
            email=email, password="x", nome=email.split("@")[0], perfil=perfil, **kw)
        cls.interno_master = mk("master@thermo.test", "GESTOR", nivel="MASTER")
        cls.tecnico = mk("tec@thermo.test", "TECNICO", nivel="PLENO")
        cls.intruso = mk("intruso@x.test", "CLIENTE_CORP", nivel="MASTER", cliente=cls.intruso_cliente)
        cls.orfao = mk("orfao@x.test", "CLIENTE_PCM")
        cls.dono = mk("dono@vitima.test", "CLIENTE_PCM", nivel="MASTER", cliente=cls.vitima)

        marcas = {cls.vitima.nome, cls.vitima.cnpj}
        marcas |= set(Equipamento.objects.filter(setor__area__cliente=cls.vitima).values_list("tag", flat=True))
        marcas |= set(OrdemServico.objects.filter(cliente=cls.vitima).values_list("numero", flat=True))
        marcas |= set(Relatorio.objects.filter(cliente=cls.vitima).values_list("numero", flat=True))
        marcas |= set(Laudo.objects.values_list("numero", flat=True))
        cls.marcas = {m for m in marcas if m and len(m) >= 5}
        cls.modelos = _modelos_de_rota()

    # ------------------------------------------------------------------ util
    def api(self, usuario):
        api = APIClient()
        api.force_authenticate(usuario)
        return api

    def ids_reais(self, molde):
        """ids existentes para o `{pk}` desta rota, tirados da lista (como interno)."""
        prefixo = molde.split("{")[0]
        r = self.api(self.interno_master).get("/" + prefixo, {"page_size": 3})
        return [str(o["id"]) for o in _lista(r) if isinstance(o, dict) and "id" in o][:3] or ["1"]

    def urls_get(self):
        extras = {"key": ["tecnico", "gerencial", "equipamento", "falhas", "historico", "painel-operacional"],
                  "item_id": ["1"], "anexo_id": ["1"], "token": ["x" * 40], "nome": ["achados/x.png"]}
        for molde in self.modelos:
            nomes = re.findall(r"\{(\w+)\}", molde)
            if not nomes:
                yield molde
                continue
            ids = self.ids_reais(molde) if "pk" in nomes else [None]
            for pk in ids:
                variantes = [{"pk": pk, **{n: v for n in nomes if n != "pk" for v in extras.get(n, ["1"])[:1]}}]
                if "key" in nomes:
                    variantes = [{"pk": pk, "key": k} for k in extras["key"]]
                for valores in variantes:
                    yield molde.format(**{n: valores.get(n) or extras.get(n, ["1"])[0] for n in nomes})

    def vazamentos(self, usuario):
        api = self.api(usuario)
        achados, consultadas = [], 0
        for url in self.urls_get():
            resposta = api.get("/" + url)
            consultadas += 1
            self.assertLess(resposta.status_code, 500, f"500 em GET /{url}")
            if resposta.status_code in (401, 403, 404, 405):
                continue
            corpo = resposta.content.decode("utf-8", "replace") if hasattr(resposta, "content") else ""
            for marca in self.marcas:
                if marca in corpo:
                    achados.append((url, marca))
                    break
        return achados, consultadas

    # --------------------------------------------------------------- leitura
    def test_oraculo_enxerga_o_dado_do_dono(self):
        """Sem isto o teste de vazamento seria vazio: o dono legítimo precisa achar os marcadores."""
        achados, consultadas = self.vazamentos(self.dono)
        self.assertGreater(consultadas, 60)
        self.assertGreater(len({url for url, _ in achados}), 10, "o oráculo quase não encontra o dado do dono")

    def test_intruso_nao_recebe_dado_da_vitima_em_nenhuma_rota_get(self):
        achados, consultadas = self.vazamentos(self.intruso)
        self.assertGreater(consultadas, 60)
        self.assertEqual(achados, [], "cliente intruso recebeu dado de outro cliente")

    def test_cliente_orfao_nao_recebe_dado_de_nenhum_cliente(self):
        achados, _ = self.vazamentos(self.orfao)
        self.assertEqual(achados, [], "perfil cliente sem cliente_id recebeu dado de cliente (falha aberta)")

    def test_filtro_cliente_na_querystring_nao_amplia_o_escopo(self):
        api = self.api(self.intruso)
        corpos = []
        for molde in self.modelos:
            if "{" in molde or molde.startswith(("api/relatorios/", "api/dashboard", "api/portal")):
                continue
            for param in ("cliente", "item__carregamento__cliente", "inspecao__cliente", "setor__area__cliente"):
                r = api.get("/" + molde, {param: self.vitima.pk, "page_size": 50})
                if r.status_code == 200:
                    corpos.append((molde, r.content.decode("utf-8", "replace")))
        for molde, corpo in corpos:
            for marca in self.marcas:
                self.assertNotIn(marca, corpo, f"?cliente=<vítima> vazou em /{molde}")

    def test_relatorios_e_paineis_nao_aceitam_cliente_de_outro_no_parametro(self):
        api = self.api(self.intruso)
        for url in ("/api/relatorios/tecnico/", "/api/relatorios/gerencial/", "/api/relatorios/historico/",
                    "/api/relatorios/equipamento/", "/api/relatorios/falhas/", "/api/dashboard/",
                    "/api/portal/visao-geral/"):
            for formato in ("json", "csv"):
                r = api.get(url, {"cliente": self.vitima.pk, "formato": formato})
                if r.status_code != 200:
                    continue
                corpo = r.content.decode("utf-8", "replace")
                for marca in self.marcas:
                    self.assertNotIn(marca, corpo, f"{url}?cliente=<vítima>&formato={formato}")

    # --------------------------------------------------------------- escrita
    def urls_escrita(self):
        ids_cache = {}
        for molde in self.modelos:
            nomes = re.findall(r"\{(\w+)\}", molde)
            if not nomes:
                yield molde
                continue
            if "pk" in nomes:
                ids_cache.setdefault(molde, self.ids_reais(molde))
            pk = ids_cache.get(molde, ["1"])[0]
            yield molde.format(**{n: (pk if n == "pk" else "tecnico" if n == "key" else "1") for n in nomes})

    def test_cliente_so_escreve_onde_o_produto_permite(self):
        permitidas = [re.compile(p) for p in ESCRITA_CLIENTE_PERMITIDA]
        indevidas = []
        for usuario in (self.dono, self.intruso, self.orfao):
            api = self.api(usuario)
            for url in self.urls_escrita():
                for metodo in ("post", "put", "patch", "delete"):
                    if any(p.search(url) for p in permitidas):
                        continue
                    r = getattr(api, metodo)("/" + url, {}, format="json")
                    self.assertLess(r.status_code, 500, f"500 em {metodo.upper()} /{url}")
                    if r.status_code not in (401, 403, 404, 405):
                        indevidas.append((usuario.email, metodo.upper(), url, r.status_code))
        self.assertEqual(indevidas, [], "perfil cliente conseguiu passar da permissão em rota de escrita")

    def test_cliente_nao_altera_osp_de_outro_cliente(self):
        osp = OrdemServico.objects.filter(cliente=self.vitima).first()
        for usuario in (self.intruso, self.orfao):
            api = self.api(usuario)
            for corpo in ({"descricao_corretiva": "pichado"}, {"custo_real": "1.00"}):
                self.assertEqual(api.patch(f"/api/osps/{osp.pk}/", corpo, format="json").status_code, 404)
            self.assertEqual(
                api.patch(f"/api/osps/{osp.pk}/status/", {"status": "CANCELADA", "motivo": "x"}, format="json")
                .status_code, 404)
        osp.refresh_from_db()
        self.assertNotEqual(osp.descricao_corretiva, "pichado")

    def test_tecnico_nao_age_como_admin(self):
        """Gestão de usuários, convites e dados de sistema: só Master interno."""
        api = self.api(self.tecnico)
        alvo = self.dono.pk
        proibidas = [
            ("get", "/api/usuarios/"), ("patch", f"/api/usuarios/{alvo}/"), ("delete", f"/api/usuarios/{alvo}/"),
            ("get", "/api/solicitacoes-acesso/"), ("post", "/api/auth/convites/"),
            ("post", "/api/templates-laudo/"), ("get", "/api/criterios-vibracao/"),
        ]
        for metodo, url in proibidas:
            r = getattr(api, metodo)(url, {}, format="json") if metodo != "get" else api.get(url)
            if url == "/api/criterios-vibracao/":
                self.assertEqual(r.status_code, 200)  # leitura interna é permitida; escrita abaixo não
                continue
            self.assertIn(r.status_code, (403, 404, 405), f"{metodo.upper()} {url} -> {r.status_code}")
        # Dados de sistema (catálogos): só Master escreve.
        for url in ("/api/normas/", "/api/tipos-equipamento/", "/api/condicoes/", "/api/instrumentos/",
                    "/api/criterios-vibracao/"):
            self.assertEqual(api.post(url, {}, format="json").status_code, 403, url)
        # Exclusão exige Master/Sênior (Pleno não apaga).
        self.assertEqual(api.delete(f"/api/clientes/{self.vitima.pk}/").status_code, 403)
        self.assertTrue(Cliente.objects.ativos().filter(pk=self.vitima.pk).exists())
