"""
Pré-homologação (QA) — isolamento entre clientes (multi-tenant).

Dois clientes, A e B, com dados completos (parque, coleta, OSP automática, laudo emitido,
relatório de rotas, ensaio de fluido, corretiva com economia, notificação). Cada perfil de
cliente de A (CORP, LOCAL, PCM, MANUT) tenta alcançar B por:

  * troca de ID na URL (GET/PATCH/PUT/DELETE e ações de detalhe: PDF/DOCX, histórico, dossiê...);
  * filtros e parâmetros (?cliente=, ?equipamento=, ?search=, ids em relatório/exportação);
  * criação apontando para FK de B (inspeção/medição/OSP/equipamento/laudo...);
  * listagens, painéis, portal, relatórios (json/csv/xlsx/pdf), notificações.

Esperado: 404 (ou 403) e NENHUM rastro de B no corpo da resposta. Como a equipe interna
legitimamente pode apontar qualquer FK, há também testes de INTEGRIDADE do cadastro interno
(OSP/rota/item/serviço de A apontando para equipamento de B), que vazariam o TAG de B no
Portal de A — esses testes falham enquanto o cadastro aceitar o vínculo cruzado.

Execução: cd backend && python manage.py test apps.core.test_homologacao_isolamento --parallel 1
"""
import io

from django.core.cache import cache
from django.test import TestCase
from openpyxl import load_workbook
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente
from apps.coletas.models import Achado, Carregamento, Inspecao, ItemInspecao, MedicaoVibracao
from apps.laudos.models import Laudo
from apps.notificacoes.models import EventoPreditivo, Notificacao
from apps.osp.models import OrdemServico
from apps.servicos.models import ServicoCampo

from .test_homologacao_base import construir_cliente, criar_internos
from .test_homologacao_fluxo import texto_pdf

PERFIS_CLIENTE = ["CLIENTE_CORP", "CLIENTE_LOCAL", "CLIENTE_PCM", "CLIENTE_MANUT"]
NEGADO = (403, 404)  # recusa legítima


class IsolamentoBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.internos = criar_internos()
        tec, ges = cls.internos["TECNICO"], cls.internos["GESTOR"]
        cls.a = construir_cliente("A", "11.111.111/0001-11", tec, ges)
        cls.b = construir_cliente("B", "22.222.222/0001-22", tec, ges)
        cls.evento_b = EventoPreditivo.objects.filter(inspecao__cliente=cls.b.cliente).first()
        cls.evento_a = EventoPreditivo.objects.filter(inspecao__cliente=cls.a.cliente).first()
        b = cls.b
        #: Tudo que identifica B: se aparecer na resposta de um usuário de A, houve vazamento.
        cls.marcadores_b = [
            "TAG-B-0", "Bomba Sigilosa B", "Ventilador Sigiloso B", "Area Secreta B", "Setor Secreto B",
            "Rota Secreta B", "Industria B QA", "Unidade B", "Contato Gestor B", "Observacao reservada B",
            "Mancal Sigiloso B", "RT-QA-B", "RT-QA-FB", "Anomalia reservada B", "Componente reservado B",
            "Servico reservado B", "Aviso reservado B", "Oleo Reservado B", "Ruido anormal B", "Plano B",
            "22.222.222/0001-22", "Painel B", "Ponto sensitivo B", b.osp.numero, b.laudo.numero,
            b.usuarios["CLIENTE_PCM"].email, b.usuarios["CLIENTE_CORP"].email,
        ]

    def setUp(self):
        cache.clear()
        self.api = APIClient()

    def como(self, perfil, de=None):
        d = de or self.a
        self.api.force_authenticate(d.usuarios[perfil])
        return self.api

    # ------------------------------------------------------------------ inspeção do corpo
    def texto(self, resposta) -> str:
        tipo = resposta.get("Content-Type", "") if hasattr(resposta, "get") else ""
        conteudo = getattr(resposta, "content", b"")
        if "spreadsheetml" in tipo:
            ws = load_workbook(io.BytesIO(conteudo)).active
            return str([[c.value for c in row] for row in ws.iter_rows()])
        if "pdf" in tipo and conteudo.startswith(b"%PDF") and b"QA homologacao" not in conteudo:
            return texto_pdf(conteudo)
        if "wordprocessingml" in tipo:
            import zipfile
            with zipfile.ZipFile(io.BytesIO(conteudo)) as z:
                return "".join(z.read(n).decode("utf-8", "ignore") for n in z.namelist() if n.endswith(".xml"))
        return conteudo.decode("utf-8-sig", "ignore")

    def sem_rastro_de_b(self, resposta, contexto):
        texto = self.texto(resposta)
        for marcador in self.marcadores_b:
            self.assertNotIn(marcador, texto, f"VAZAMENTO ({contexto}): '{marcador}' no corpo da resposta")

    def ids(self, resposta):
        corpo = resposta.data
        itens = corpo["results"] if isinstance(corpo, dict) and "results" in corpo else corpo
        return {i["id"] for i in itens if isinstance(i, dict) and "id" in i}


def recursos(b):
    """(rótulo, rota da lista, objeto de B) — o objeto de B é alcançado trocando o ID na URL."""
    return [
        ("clientes", "/api/clientes/", b.cliente),
        ("areas", "/api/areas/", b.area),
        ("setores", "/api/setores/", b.setor),
        ("equipamentos", "/api/equipamentos/", b.equipamento),
        ("componentes", "/api/componentes/", b.componente),
        ("rotas", "/api/rotas/", b.rota),
        ("inspecoes", "/api/inspecoes/", b.inspecao),
        ("medicoes-vibracao", "/api/medicoes-vibracao/", b.vibracao),
        ("medicoes-termografia", "/api/medicoes-termografia/", b.termografia),
        ("medicoes-tecnicas", "/api/medicoes-tecnicas/", b.tecnica),
        ("relatorios-inspecao", "/api/relatorios-inspecao/", b.relatorio),
        ("carregamentos", "/api/carregamentos/", b.carregamento),
        ("itens-inspecao", "/api/itens-inspecao/", b.item),
        ("achados", "/api/achados/", b.achado),
        ("coletas-fluido", "/api/coletas-fluido/", b.coleta_fluido),
        ("resultados-ensaio", "/api/resultados-ensaio/", b.resultado_ensaio),
        ("fluidos-inspecao", "/api/fluidos-inspecao/", b.item_fluido),
        ("servicos", "/api/servicos/", b.servico),
        ("balanceamento-planos", "/api/balanceamento-planos/", b.plano),
        ("economias", "/api/economias/", b.economia),
        ("osps", "/api/osps/", b.osp),
        ("laudos", "/api/laudos/", b.laudo),
        ("notificacoes", "/api/notificacoes/", b.notificacao),
    ]


LISTAS_EXTRAS = [
    "/api/eventos-preditivos/", "/api/transformadores-inspecao/", "/api/atividades-corretivas/",
    "/api/dados-tecnicos-motor/", "/api/dados-tecnicos-transformador/", "/api/achados-imagens/",
    "/api/balanceamento-pontos/", "/api/coletas-oleo/", "/api/registros-ensaio-eletrico/",
    "/api/fluidos-historico/", "/api/minha-equipe/", "/api/minha-equipe/convites/",
]


# ======================================================================== LISTAGENS E FILTROS
class ListagensEFiltros(IsolamentoBase):
    def test_listagens_nao_contem_nada_de_b(self):
        urls = [(r, u, o) for r, u, o in recursos(self.b)] + [(u, u, None) for u in LISTAS_EXTRAS]
        for perfil in PERFIS_CLIENTE:
            for rotulo, url, objeto_b in urls:
                with self.subTest(perfil=perfil, lista=rotulo):
                    r = self.como(perfil).get(f"{url}?page_size=500")
                    self.assertEqual(r.status_code, 200, (url, getattr(r, "data", None)))
                    self.sem_rastro_de_b(r, f"{perfil} lista {url}")
                    if objeto_b is not None and hasattr(r, "data"):
                        self.assertNotIn(objeto_b.pk, self.ids(r) if r.data else set(),
                                         f"{perfil}: {url} lista o id {objeto_b.pk} de B")

    def test_listagens_trazem_dados_do_proprio_cliente(self):
        """Contraprova: o escopo filtra, não zera — A vê o que é dele."""
        for perfil in PERFIS_CLIENTE:
            api = self.como(perfil)
            with self.subTest(perfil=perfil):
                self.assertIn(self.a.equipamento.pk, self.ids(api.get("/api/equipamentos/?page_size=500")))
                self.assertIn(self.a.osp.pk, self.ids(api.get("/api/osps/")))
                self.assertIn(self.a.laudo.pk, self.ids(api.get("/api/laudos/")))
                self.assertIn(self.a.inspecao.pk, self.ids(api.get("/api/inspecoes/")))
                self.assertEqual(self.ids(api.get("/api/clientes/")), {self.a.cliente.pk})

    def test_filtros_e_busca_nao_atravessam_clientes(self):
        b = self.b
        parametros = [
            f"cliente={b.cliente.pk}", f"cliente__id={b.cliente.pk}", f"equipamento={b.equipamento.pk}",
            f"inspecao={b.inspecao.pk}", f"setor={b.setor.pk}", f"area={b.area.pk}",
            f"setor__area__cliente={b.cliente.pk}", f"inspecao__cliente={b.cliente.pk}",
            f"item={b.item.pk}", f"carregamento={b.carregamento.pk}", f"relatorio={b.relatorio.pk}",
            f"servico={b.servico.pk}", f"osp={b.osp.pk}", f"achado={b.achado.pk}", f"rota={b.rota.pk}",
            f"item__carregamento__cliente={b.cliente.pk}", "search=TAG-B", "search=Sigil", "search=Industria B",
            f"search={b.osp.numero}", f"search={b.laudo.numero}", "ordering=-id&page_size=1000",
            f"id={b.equipamento.pk}", f"pk={b.osp.pk}", f"destinatario={b.usuarios['CLIENTE_PCM'].pk}",
        ]
        urls = [u for _, u, _ in recursos(self.b)] + LISTAS_EXTRAS
        for perfil in ("CLIENTE_CORP", "CLIENTE_MANUT"):
            api = self.como(perfil)
            for url in urls:
                for p in parametros:
                    with self.subTest(perfil=perfil, url=url, parametro=p):
                        r = api.get(f"{url}?{p}")
                        self.assertIn(r.status_code, (200, 400, 404), (r.status_code, getattr(r, "data", None)))
                        self.sem_rastro_de_b(r, f"{perfil} {url}?{p}")

    def test_cliente_orfao_sem_vinculo_nao_ve_nada_de_ninguem(self):
        from .test_homologacao_base import criar_usuario

        orfao = criar_usuario("orfao@cliente.qa", "CLIENTE_PCM", "PLENO", cliente=None)
        self.api.force_authenticate(orfao)
        urls = [u for _, u, _ in recursos(self.b)] + [u for u in LISTAS_EXTRAS if "minha-equipe" not in u]
        for url in urls:
            with self.subTest(lista=url):
                r = self.api.get(f"{url}?page_size=500")
                self.assertEqual(r.status_code, 200, url)
                texto = self.texto(r)
                for m in ("TAG-A-0", "TAG-B-0", "Industria A QA", "Industria B QA", "Secreta"):
                    self.assertNotIn(m, texto, f"órfão enxerga '{m}' em {url}")
                self.assertEqual(self.ids(r), set(), f"órfão recebeu registros em {url}")


# ======================================================================== DETALHE POR TROCA DE ID
class DetalheEEscritaPorTrocaDeId(IsolamentoBase):
    def test_detalhe_de_b_e_404_para_todos_os_perfis_de_a(self):
        for perfil in PERFIS_CLIENTE:
            api = self.como(perfil)
            for rotulo, url, objeto in recursos(self.b):
                with self.subTest(perfil=perfil, recurso=rotulo):
                    r = api.get(f"{url}{objeto.pk}/")
                    self.assertIn(r.status_code, NEGADO, f"{perfil} GET {url}{objeto.pk}/ -> {r.status_code}")
                    self.sem_rastro_de_b(r, f"{perfil} GET {url}{objeto.pk}/")

    def test_alterar_ou_excluir_recurso_de_b_e_recusado_e_nao_altera(self):
        for perfil in PERFIS_CLIENTE:
            api = self.como(perfil)
            for rotulo, url, objeto in recursos(self.b):
                if rotulo == "notificacoes":
                    continue  # sem escrita por API (405)
                antes = type(objeto).objects.filter(pk=objeto.pk).values().first()
                for metodo in ("patch", "put", "delete"):
                    with self.subTest(perfil=perfil, recurso=rotulo, metodo=metodo):
                        corpo = {"observacoes": "INVADIDO", "nome": "INVADIDO", "titulo": "INVADIDO",
                                 "descricao_corretiva": "INVADIDO", "custo_real": "1.00"}
                        r = getattr(api, metodo)(f"{url}{objeto.pk}/", corpo, format="json") if metodo != "delete" \
                            else api.delete(f"{url}{objeto.pk}/")
                        self.assertIn(r.status_code, (403, 404, 405), f"{perfil} {metodo.upper()} {url}{objeto.pk}/ -> {r.status_code}")
                        self.sem_rastro_de_b(r, f"{perfil} {metodo} {url}{objeto.pk}/")
                depois = type(objeto).objects.filter(pk=objeto.pk).values().first()
                self.assertEqual(antes, depois, f"{perfil}: {rotulo} de B foi alterado/excluído")

    def test_acoes_de_detalhe_de_b(self):
        b = self.b
        acoes = [
            ("get", f"/api/laudos/{b.laudo.pk}/pdf/"), ("get", f"/api/laudos/{b.laudo.pk}/documento/"),
            ("get", f"/api/laudos/{b.laudo.pk}/previa/"), ("get", f"/api/laudos/{b.laudo.pk}/relatorio-tecnico/"),
            ("get", f"/api/laudos/{b.laudo.pk}/versoes/"), ("get", f"/api/laudos/{b.laudo.pk}/eventos/"),
            ("get", f"/api/laudos/{b.laudo.pk}/historico/"), ("get", f"/api/laudos/{b.laudo.pk}/anexos/"),
            ("get", f"/api/laudos/{b.laudo_rascunho.pk}/pdf/"), ("get", f"/api/laudos/{b.laudo_rascunho.pk}/documento/"),
            ("post", f"/api/laudos/{b.laudo.pk}/cancelar/"), ("post", f"/api/laudos/{b.laudo.pk}/revisar/"),
            ("post", f"/api/laudos/{b.laudo_rascunho.pk}/emitir/"), ("post", f"/api/laudos/{b.laudo.pk}/anexos/"),
            ("get", f"/api/osps/{b.osp.pk}/historico/"), ("patch", f"/api/osps/{b.osp.pk}/status/"),
            ("get", f"/api/relatorios-inspecao/{b.relatorio.pk}/secao-c/"),
            ("get", f"/api/relatorios-inspecao/{b.relatorio.pk}/dossie/"),
            ("get", f"/api/relatorios-inspecao/{b.relatorio.pk}/carta-docx/"),
            ("get", f"/api/medicoes-vibracao/{b.vibracao.pk}/analise-preditiva/"),
            ("get", f"/api/servicos/{b.servico.pk}/relatorio/"),
            ("post", f"/api/carregamentos/{b.carregamento.pk}/transferir/"),
            ("post", f"/api/carregamentos/{b.carregamento.pk}/descartar/"),
            ("post", f"/api/carregamentos/{b.carregamento.pk}/definir-condicao/"),
            ("post", f"/api/notificacoes/{b.notificacao.pk}/lida/"),
            ("get", f"/api/fluidos-historico/?equipamento={b.equipamento.pk}"),
            ("get", f"/api/atividades-corretivas/{b.carregamento.pk}/"),
        ]
        corpo = {"status": "CANCELADA", "motivo": "invasao", "itens": [b.item.pk]}
        for perfil in PERFIS_CLIENTE:
            api = self.como(perfil)
            for metodo, url in acoes:
                with self.subTest(perfil=perfil, acao=f"{metodo.upper()} {url}"):
                    r = getattr(api, metodo)(url) if metodo == "get" else getattr(api, metodo)(url, corpo, format="json")
                    self.assertIn(r.status_code, NEGADO, f"{perfil} {metodo.upper()} {url} -> {r.status_code}")
                    self.sem_rastro_de_b(r, f"{perfil} {metodo} {url}")
        b.osp.refresh_from_db()
        self.assertEqual(b.osp.status, "ABERTA", "OSP de B teve o status alterado por usuário de A")
        b.laudo.refresh_from_db()
        self.assertEqual(b.laudo.status, "EMITIDO", "laudo de B foi cancelado por usuário de A")

    def test_download_do_laudo_proprio_funciona_e_o_de_b_nao(self):
        for perfil in PERFIS_CLIENTE:
            api = self.como(perfil)
            proprio = api.get(f"/api/laudos/{self.a.laudo.pk}/pdf/")
            self.assertEqual(proprio.status_code, 200, perfil)
            self.assertEqual(proprio["Content-Type"], "application/pdf")
            self.assertEqual(api.get(f"/api/laudos/{self.b.laudo.pk}/pdf/").status_code, 404, perfil)

    def test_dossie_e_carta_docx_do_proprio_relatorio_so_tem_dados_de_a(self):
        for perfil in PERFIS_CLIENTE:
            api = self.como(perfil)
            for acao in ("dossie", "secao-c", "carta-docx"):
                r = api.get(f"/api/relatorios-inspecao/{self.a.relatorio.pk}/{acao}/")
                with self.subTest(perfil=perfil, acao=acao):
                    self.assertIn(r.status_code, (200, 409), (acao, getattr(r, "data", None)))
                    self.sem_rastro_de_b(r, f"{perfil} {acao} do próprio relatório")

    def test_cliente_de_a_nao_reatribui_osp_propria_para_b(self):
        """PATCH na OSP de A tentando apontar para cliente/equipamento/executor de B."""
        for perfil in PERFIS_CLIENTE:
            api = self.como(perfil)
            osp = self.a.osp
            antes = OrdemServico.objects.filter(pk=osp.pk).values("cliente_id", "equipamento_id", "responsavel_id").first()
            r = api.patch(f"/api/osps/{osp.pk}/", {
                "cliente": self.b.cliente.pk, "equipamento": self.b.equipamento.pk,
                "responsavel": self.internos["GESTOR"].pk, "inspecao": self.b.inspecao.pk,
            }, format="json")
            with self.subTest(perfil=perfil, campo="cliente/equipamento"):
                self.assertIn(r.status_code, (200, 400, 403))
                self.sem_rastro_de_b(r, f"{perfil} PATCH OSP -> FK de B")
                self.assertEqual(
                    OrdemServico.objects.filter(pk=osp.pk).values("cliente_id", "equipamento_id", "responsavel_id").first(),
                    antes)
            if perfil == "CLIENTE_MANUT":
                continue
            for campo in ("planejado_por", "executado_por", "finalizado_por"):
                with self.subTest(perfil=perfil, campo=campo):
                    r = api.patch(f"/api/osps/{osp.pk}/", {campo: self.b.usuarios["CLIENTE_PCM"].pk}, format="json")
                    self.assertEqual(r.status_code, 400, f"{campo} apontando para usuário de B -> {r.status_code}")
                    self.sem_rastro_de_b(r, f"{perfil} PATCH OSP {campo}")


# ======================================================================== CRIAÇÃO APONTANDO PARA B
class CriacaoApontandoParaB(IsolamentoBase):
    CONTADORES = (Inspecao, MedicaoVibracao, OrdemServico, Laudo, Achado, ItemInspecao, Carregamento, ServicoCampo)

    def contagens(self):
        from apps.cadastros.models import Area, Equipamento, Rota, Setor
        modelos = self.CONTADORES + (Cliente, Area, Setor, Equipamento, Rota, Notificacao)
        return {m.__name__: m.objects.count() for m in modelos}

    def test_usuario_de_a_nao_cria_nada_apontando_para_b(self):
        b, a = self.b, self.a
        tentativas = [
            ("inspecao em cliente B", "/api/inspecoes/", {"cliente": b.cliente.pk, "tipo_analise": "VIBRACAO", "data": "2026-10-28"}),
            ("medicao em equipamento de B", "/api/medicoes-vibracao/", {"inspecao": b.inspecao.pk, "equipamento": b.equipamento.pk, "ponto_medicao": "X", "direcao": "H", "velocidade_rms": "9.0", "rotacao_rpm": 1800}),
            ("medicao propria com equipamento de B", "/api/medicoes-vibracao/", {"inspecao": a.inspecao.pk, "equipamento": b.equipamento.pk, "ponto_medicao": "X", "direcao": "H", "velocidade_rms": "9.0", "rotacao_rpm": 1800}),
            ("medicao tecnica em B", "/api/medicoes-tecnicas/", {"inspecao": b.inspecao_sens.pk, "equipamento": b.equipamento2.pk, "ponto_medicao": "X", "grandeza": "x", "subtipo": "SENSITIVA", "parametros": {"criticidade": "CRITICO"}}),
            ("OSP em equipamento de B", "/api/osps/", {"cliente": b.cliente.pk, "equipamento": b.equipamento.pk, "titulo": "invasao", "inspecao": b.inspecao.pk}),
            ("OSP de A com equipamento de B", "/api/osps/", {"cliente": a.cliente.pk, "equipamento": b.equipamento.pk, "titulo": "invasao", "inspecao": a.inspecao.pk}),
            ("equipamento em setor de B", "/api/equipamentos/", {"setor": b.setor.pk, "tag": "INVASOR", "nome": "Invasor"}),
            ("area em cliente B", "/api/areas/", {"cliente": b.cliente.pk, "nome": "Invasora"}),
            ("setor em area de B", "/api/setores/", {"area": b.area.pk, "nome": "Invasor"}),
            ("rota para cliente B", "/api/rotas/", {"cliente": b.cliente.pk, "nome": "Invasora"}),
            ("rota de A com equipamento de B", "/api/rotas/", {"cliente": a.cliente.pk, "nome": "Invasora", "equipamentos": [b.equipamento.pk]}),
            ("componente em equipamento de B", "/api/componentes/", {"equipamento": b.equipamento.pk, "nome": "Invasor"}),
            ("laudo gerado da inspecao de B", "/api/laudos/gerar/", {"inspecao": b.inspecao.pk}),
            ("laudo gerado do relatorio de B", "/api/laudos/gerar/", {"relatorio_origem": b.relatorio.pk}),
            ("laudo manual sobre inspecao de B", "/api/laudos/", {"inspecao": b.inspecao.pk, "titulo": "invasao", "responsavel": self.internos["GESTOR"].pk}),
            ("achado em item de B", "/api/achados/", {"item": b.item.pk, "componente_texto": "x", "anomalia_texto": "y"}),
            ("item na rota de B", "/api/itens-inspecao/", {"carregamento": b.carregamento.pk, "equipamento": b.equipamento2.pk, "ordem": 9}),
            ("servico em equipamento de B", "/api/servicos/", {"cliente": b.cliente.pk, "equipamento": b.equipamento.pk, "tipo": "BALANCEAMENTO", "data_execucao": "2026-10-28"}),
            ("economia sobre servico de B", "/api/economias/", {"servico": b.servico.pk, "tensao_v": "380", "corrente_antes_a": "10", "corrente_apos_a": "9", "fator_potencia": "0.9", "horas_dia": "10", "dias_ano": 300, "custo_kwh": "0.5", "investimento": "100"}),
            ("convite para cliente B", "/api/auth/convites/", {"nome": "Invasor", "email": "invasor@x.qa", "tipo": "portal", "perfil": "CLIENTE_PCM", "nivel": "PLENO", "cliente": b.cliente.pk}),
            ("coleta de fluido em item de B", "/api/coletas-fluido/", {"item": b.item_fluido.pk, "aplicacao": "LUBRIFICANTE", "data_coleta": "2026-10-28"}),
            ("resultado de ensaio em item de B", "/api/resultados-ensaio/", {"item": b.item_fluido.pk, "situacao": "REALIZADO"}),
        ]
        for perfil in PERFIS_CLIENTE:
            api = self.como(perfil)
            for rotulo, url, corpo in tentativas:
                with self.subTest(perfil=perfil, tentativa=rotulo):
                    antes = self.contagens()
                    r = api.post(url, corpo, format="json")
                    self.assertIn(r.status_code, (400, 403, 404), f"{perfil}: {rotulo} -> {r.status_code} {getattr(r, 'data', '')}")
                    self.sem_rastro_de_b(r, f"{perfil} POST {rotulo}")
                    self.assertEqual(self.contagens(), antes, f"{perfil}: '{rotulo}' criou registro")

    def test_a_nao_envia_status_de_osp_de_b_nem_cancela_laudo_de_b(self):
        for perfil in PERFIS_CLIENTE:
            api = self.como(perfil)
            r = api.patch(f"/api/osps/{self.b.osp.pk}/status/", {"status": "CANCELADA", "motivo": "x"}, format="json")
            self.assertEqual(r.status_code, 404, perfil)

    # ---- Integridade do cadastro interno (o vínculo cruzado vazaria o TAG de B no portal de A) ----
    def interno(self, perfil="GESTOR"):
        self.api.force_authenticate(self.internos[perfil])
        return self.api

    def test_interno_nao_abre_osp_de_a_sobre_equipamento_de_b(self):
        r = self.interno().post("/api/osps/", {
            "cliente": self.a.cliente.pk, "equipamento": self.b.equipamento.pk, "titulo": "Vinculo cruzado",
            "inspecao": self.a.inspecao_sens.pk,
        }, format="json")
        self.assertEqual(r.status_code, 400, f"OSP do cliente A aceita equipamento do cliente B ({r.status_code})")
        # consequência visível: o portal de A mostraria o TAG de B
        if r.status_code == 201:
            portal = self.como("CLIENTE_PCM").get("/api/osps/")
            self.assertNotIn("TAG-B-01", self.texto(portal))

    def test_vinculo_cruzado_de_osp_vaza_o_tag_de_b_no_portal_de_a(self):
        """Consequência do vínculo cruzado: o PCM de A passa a ler TAG/nome do equipamento de B."""
        self.interno().post("/api/osps/", {
            "cliente": self.a.cliente.pk, "equipamento": self.b.equipamento.pk, "titulo": "Vinculo cruzado",
            "inspecao": self.a.inspecao_sens.pk,
        }, format="json")
        r = self.como("CLIENTE_PCM").get("/api/osps/?page_size=500")
        self.assertNotIn("TAG-B-01", self.texto(r), "o Portal de A exibe o TAG do equipamento de B")

    def test_vinculo_cruzado_de_folha_de_campo_vaza_o_tag_de_b_no_portal_de_a(self):
        self.interno().post("/api/itens-inspecao/", {
            "carregamento": self.a.carregamento.pk, "equipamento": self.b.equipamento2.pk, "ordem": 9,
        }, format="json")
        r = self.como("CLIENTE_PCM").get(f"/api/carregamentos/{self.a.carregamento.pk}/")
        self.assertNotIn("TAG-B-02", self.texto(r), "o Portal de A exibe o TAG do equipamento de B na folha de campo")

    def test_interno_nao_monta_rota_de_a_com_equipamento_de_b(self):
        r = self.interno().post("/api/rotas/", {
            "cliente": self.a.cliente.pk, "nome": "Rota cruzada", "equipamentos": [self.b.equipamento.pk],
        }, format="json")
        self.assertEqual(r.status_code, 400, f"Rota do cliente A aceita equipamento do cliente B ({r.status_code})")

    def test_interno_nao_inclui_equipamento_de_b_na_folha_de_campo_de_a(self):
        r = self.interno().post("/api/itens-inspecao/", {
            "carregamento": self.a.carregamento.pk, "equipamento": self.b.equipamento2.pk, "ordem": 9,
        }, format="json")
        self.assertEqual(r.status_code, 400, f"Folha de campo de A aceita equipamento de B ({r.status_code})")

    def test_interno_nao_registra_servico_de_a_em_equipamento_de_b(self):
        r = self.interno().post("/api/servicos/", {
            "cliente": self.a.cliente.pk, "equipamento": self.b.equipamento.pk, "tipo": "BALANCEAMENTO",
            "data_execucao": "2026-10-28",
        }, format="json")
        self.assertEqual(r.status_code, 400, f"Serviço do cliente A aceita equipamento do cliente B ({r.status_code})")

    def test_interno_nao_cria_medicao_de_a_em_equipamento_de_b(self):
        r = self.interno().post("/api/medicoes-vibracao/", {
            "inspecao": self.a.inspecao.pk, "equipamento": self.b.equipamento.pk, "ponto_medicao": "X",
            "direcao": "H", "velocidade_rms": "9.0", "rotacao_rpm": 1800,
        }, format="json")
        self.assertEqual(r.status_code, 400)

    def test_interno_nao_move_laudo_nem_inspecao_de_cliente(self):
        api = self.interno("ADMIN")
        r = api.patch(f"/api/inspecoes/{self.a.inspecao.pk}/", {"cliente": self.b.cliente.pk}, format="json")
        self.assertEqual(r.status_code, 400, "inspeção com medições mudou de cliente")
        r = api.patch(f"/api/laudos/{self.a.laudo_rascunho.pk}/", {"inspecao": self.b.inspecao.pk}, format="json")
        self.assertIn(r.status_code, (200, 400))
        self.a.laudo_rascunho.refresh_from_db()
        self.assertEqual(self.a.laudo_rascunho.inspecao_id, self.a.inspecao_termo.pk)


# ======================================================================== RELATÓRIOS, EXPORTAÇÕES, PAINÉIS, PORTAL
class RelatoriosPaineisEPortal(IsolamentoBase):
    RELATORIOS = ["tecnico", "gerencial", "equipamento", "falhas", "historico", "painel-operacional"]
    FORMATOS = ["json", "csv", "xlsx", "pdf"]

    def test_relatorios_em_todos_os_formatos_com_ids_de_b_nos_parametros(self):
        b = self.b
        extras = [
            "", f"&cliente={b.cliente.pk}", f"&equipamento={b.equipamento.pk}", f"&area={b.area.pk}",
            f"&setor={b.setor.pk}", f"&cliente={b.cliente.pk}&equipamento={b.equipamento.pk}",
            f"&cliente={self.a.cliente.pk}&equipamento={b.equipamento.pk}", "&data_inicio=2020-01-01&data_fim=2030-12-31",
        ]
        for perfil in ("CLIENTE_CORP", "CLIENTE_MANUT"):
            api = self.como(perfil)
            for key in self.RELATORIOS:
                for formato in self.FORMATOS:
                    for extra in extras:
                        with self.subTest(perfil=perfil, relatorio=key, formato=formato, extra=extra):
                            r = api.get(f"/api/relatorios/{key}/?formato={formato}&page_size=500{extra}")
                            self.assertEqual(r.status_code, 200, (r.status_code, getattr(r, "data", None)))
                            self.sem_rastro_de_b(r, f"{perfil} relatório {key}.{formato}{extra}")

    def test_exportacao_contem_dados_de_a(self):
        """Contraprova do teste anterior: o arquivo tem conteúdo legível (senão 'sem rastro' seria vazio)."""
        for formato in self.FORMATOS:
            r = self.como("CLIENTE_PCM").get(f"/api/relatorios/equipamento/?formato={formato}&page_size=500")
            self.assertIn("TAG-A-01", self.texto(r), formato)

    def test_relatorios_internos_negados_com_ids_de_b(self):
        b = self.b
        for perfil in PERFIS_CLIENTE:
            api = self.como(perfil)
            for key in ("financeiro", "produtividade", "painel-executivo"):
                for formato in self.FORMATOS:
                    r = api.get(f"/api/relatorios/{key}/?formato={formato}&cliente={b.cliente.pk}")
                    self.assertEqual(r.status_code, 403, (perfil, key, formato))
            self.assertEqual(api.get(f"/api/dashboard/executivo/?cliente={b.cliente.pk}").status_code, 403)

    def test_paineis_e_portal_so_contam_o_proprio_cliente(self):
        b = self.b
        for perfil in PERFIS_CLIENTE:
            api = self.como(perfil)
            with self.subTest(perfil=perfil):
                visao = api.get("/api/portal/visao-geral/")
                self.assertEqual(visao.status_code, 200)
                self.sem_rastro_de_b(visao, "visão geral")
                ind = visao.data["indicadores"]
                self.assertEqual(ind["equipamentos_monitorados"], 2)
                self.assertEqual(ind["inspecoes"], 3)
                self.assertEqual(ind["laudos_disponiveis"], 1)
                self.assertEqual(visao.data["cliente"]["nome"], self.a.cliente.nome)
                for extra in ("", f"?cliente={b.cliente.pk}", f"?equipamento={b.equipamento.pk}", f"?area={b.area.pk}",
                              f"?setor={b.setor.pk}"):
                    r = api.get(f"/api/dashboard/{extra}")
                    self.assertEqual(r.status_code, 200)
                    self.sem_rastro_de_b(r, f"dashboard{extra}")
                    if extra:
                        self.assertEqual((r.data["total_inspecoes"], r.data["total_medicoes"], r.data["osps_total"]),
                                         (0, 0, 0), f"dashboard{extra} trouxe dados com parâmetro de B")

    def test_dashboard_proprio_bate_com_o_banco(self):
        r = self.como("CLIENTE_PCM").get("/api/dashboard/").data
        self.assertEqual(r["total_inspecoes"], Inspecao.objects.filter(cliente=self.a.cliente, ativo=True).count())
        self.assertEqual(r["total_medicoes"], 3)

    def test_interno_filtra_por_cliente_sem_misturar(self):
        self.api.force_authenticate(self.internos["GESTOR"])
        r = self.api.get(f"/api/relatorios/tecnico/?formato=csv&cliente={self.a.cliente.pk}")
        texto = self.texto(r)
        self.assertIn("TAG-A-01", texto)
        self.assertNotIn("TAG-B-01", texto)
        r = self.api.get("/api/relatorios/tecnico/?formato=csv")
        self.assertTrue("TAG-A-01" in self.texto(r) and "TAG-B-01" in self.texto(r))


# ======================================================================== NOTIFICAÇÕES, EQUIPE E USUÁRIOS
class NotificacoesEquipeEUsuarios(IsolamentoBase):
    def test_notificacoes_so_do_proprio_usuario(self):
        alvo = self.b.notificacao
        for perfil in PERFIS_CLIENTE:
            api = self.como(perfil)
            with self.subTest(perfil=perfil):
                self.sem_rastro_de_b(api.get("/api/notificacoes/?page_size=500"), "lista de notificações")
                self.assertEqual(api.get(f"/api/notificacoes/{alvo.pk}/").status_code, 404)
                self.assertEqual(api.post(f"/api/notificacoes/{alvo.pk}/lida/").status_code, 404)
                api.post("/api/notificacoes/marcar-todas/")
        alvo.refresh_from_db()
        self.assertFalse(alvo.lida)

    def test_notificacao_de_colega_do_mesmo_cliente_tambem_e_privada(self):
        colega = self.a.notificacao  # pertence ao PCM de A
        for perfil in ("CLIENTE_CORP", "CLIENTE_LOCAL", "CLIENTE_MANUT"):
            self.assertEqual(self.como(perfil).get(f"/api/notificacoes/{colega.pk}/").status_code, 404, perfil)

    def test_eventos_preditivos_de_b(self):
        if self.evento_b is None:
            self.skipTest("a massa não gerou evento preditivo")  # pragma: no cover
        for perfil in PERFIS_CLIENTE:
            self.assertEqual(self.como(perfil).get(f"/api/eventos-preditivos/{self.evento_b.pk}/").status_code, 404)
            r = self.api.get(f"/api/eventos-preditivos/?inspecao={self.b.inspecao.pk}")
            self.assertEqual(self.ids(r), set())

    def test_equipe_so_lista_colegas_do_proprio_cliente(self):
        for perfil in PERFIS_CLIENTE:
            api = self.como(perfil)
            r = api.get("/api/minha-equipe/?page_size=500")
            self.assertEqual(r.status_code, 200)
            self.sem_rastro_de_b(r, "minha-equipe")
            self.assertEqual({u["cliente"] for u in r.data["results"]}, {self.a.cliente.pk})
            alheio = self.b.usuarios["CLIENTE_PCM"].pk
            self.assertEqual(api.get(f"/api/minha-equipe/{alheio}/").status_code, 404)
            self.assertEqual(api.get(f"/api/minha-equipe/?cliente={self.b.cliente.pk}&page_size=500").data["count"],
                             r.data["count"])

    def test_usuarios_da_plataforma_inacessiveis_ao_cliente(self):
        alheio = self.b.usuarios["CLIENTE_PCM"].pk
        for perfil in PERFIS_CLIENTE:
            api = self.como(perfil)
            for metodo, url in (("get", "/api/usuarios/"), ("get", f"/api/usuarios/{alheio}/"),
                                ("patch", f"/api/usuarios/{alheio}/"), ("delete", f"/api/usuarios/{alheio}/"),
                                ("get", "/api/solicitacoes-acesso/"), ("get", "/api/clientes/?search=Industria B")):
                r = getattr(api, metodo)(url) if metodo != "patch" else api.patch(url, {"is_active": False}, format="json")
                with self.subTest(perfil=perfil, acao=f"{metodo} {url}"):
                    self.assertIn(r.status_code, (200, 403, 404))
                    self.sem_rastro_de_b(r, f"{perfil} {metodo} {url}")
                    if "usuarios" in url or "solicitacoes" in url:
                        self.assertEqual(r.status_code, 403)
        self.b.usuarios["CLIENTE_PCM"].refresh_from_db()
        self.assertTrue(self.b.usuarios["CLIENTE_PCM"].is_active)

    def test_dados_proprios_do_usuario_nao_expoem_outros(self):
        for perfil in PERFIS_CLIENTE:
            r = self.como(perfil).get("/api/auth/me/")
            self.assertEqual(r.data["cliente"], self.a.cliente.pk)
            self.sem_rastro_de_b(r, "/auth/me")
            for url in ("/api/auth/seguranca/", "/api/auth/seguranca/sessoes/", "/api/auth/seguranca/eventos/"):
                self.sem_rastro_de_b(self.api.get(url), url)

    def test_b_ainda_enxerga_o_proprio_e_nao_o_de_a(self):
        """Simetria: o isolamento vale nos dois sentidos."""
        for perfil in PERFIS_CLIENTE:
            api = self.como(perfil, de=self.b)
            self.assertEqual(api.get(f"/api/osps/{self.a.osp.pk}/").status_code, 404)
            self.assertEqual(api.get(f"/api/laudos/{self.a.laudo.pk}/pdf/").status_code, 404)
            self.assertEqual(api.get(f"/api/equipamentos/{self.a.equipamento.pk}/").status_code, 404)
            self.assertEqual(api.get(f"/api/osps/{self.b.osp.pk}/").status_code, 200)
            texto = self.texto(api.get("/api/relatorios/tecnico/?formato=csv"))
            self.assertIn("TAG-B-01", texto)
            self.assertNotIn("TAG-A-0", texto)
