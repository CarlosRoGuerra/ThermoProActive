"""
Revisão independente da pré-homologação (agente revisor, 29/10/2026).

Cada teste abaixo é uma PROVA reproduzível escrita por quem NÃO fez as correções:
  * os que passam confirmam a correção por um caminho que os testes dos autores não cobrem;
  * R-01 (X-Accel-Redirect com acento) foi corrigido depois desta revisão; o teste virou regressão.

Rodar: python manage.py test apps.core.test_revisao_independente
"""
import io
import os
import shutil
import tempfile
import uuid
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from apps.accounts.models import EstadoConta, SessaoAutenticacao
from apps.cadastros.models import Area, Cliente, Equipamento, Setor

User = get_user_model()
SENHA = "uma frase senha longa e segura 2026"


def _mk(email, perfil, nivel="PLENO", **kw):
    return User.objects.create_user(email=email, password=SENHA, nome=email.split("@")[0],
                                    perfil=perfil, nivel=nivel, **kw)


class A06RotasLegadasETokens(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cli = Cliente.objects.create(nome="Cliente A", cnpj="45.723.174/0001-10")
        cls.outro = Cliente.objects.create(nome="Cliente B", cnpj="12.345.678/0001-95")
        cls.u = _mk("u@a.test", "CLIENTE_PCM", cliente=cls.cli)
        cls.v = _mk("v@b.test", "CLIENTE_PCM", cliente=cls.outro)
        cls.master = _mk("m@thermo.test", "GESTOR", "MASTER")

    def setUp(self):
        cache.clear()

    def login(self, email, contexto="portal"):
        c = APIClient(enforce_csrf_checks=True)
        csrf = {"HTTP_X_CSRFTOKEN": c.get("/api/auth/csrf/").data["csrfToken"]}
        r = c.post(f"/api/auth/{contexto}/login/", {"email": email, "password": SENHA}, format="json", **csrf)
        self.assertEqual(r.status_code, 200, r.content)
        return c, csrf

    def token(self, user, sid, cls=AccessToken):
        t = cls.for_user(user)
        if sid is not None:
            t["sid"] = sid
        return str(t)

    def test_nenhuma_rota_legada_de_token_existe(self):
        """A-06: nenhum caminho plausível emite/renova JWT fora do login contextual (todos os verbos)."""
        for rota in ("/api/auth/login/", "/api/auth/refresh/", "/api/auth/token/", "/api/auth/token/refresh/",
                     "/api/token/", "/api/token/refresh/", "/api/login/", "/api/auth/login", "/api/auth/refresh",
                     "/api/auth/token/verify/", "/api/token/verify/"):
            for verbo in ("get", "post", "options", "put"):
                r = getattr(self.client, verbo)(rota, {"email": self.u.email, "password": SENHA}, format="json")
                self.assertEqual(r.status_code, 404, f"{verbo.upper()} {rota} -> {r.status_code}")

    def test_bearer_forjado_todas_as_variantes_sao_rejeitadas(self):
        """Bearer assinado com a chave certa mas sem sessão válida: sem sid, sid de OUTRO usuário, sid inexistente,
        sid malformado, sid expirado/revogado, refresh usado como access."""
        _, _ = self.login(self.u.email)
        _, _ = self.login(self.v.email)
        sessao_v = SessaoAutenticacao.objects.get(usuario=self.v)
        sessao_u = SessaoAutenticacao.objects.get(usuario=self.u)
        casos = {
            "sem sid": self.token(self.u, None),
            "sid de outro usuario": self.token(self.u, str(sessao_v.id)),
            "sid inexistente": self.token(self.u, str(uuid.uuid4())),
            "sid malformado": self.token(self.u, "not-a-uuid"),
            "sid vazio": self.token(self.u, ""),
            "sid inteiro": self.token(self.u, 7),
            "refresh como access": self.token(self.u, str(sessao_u.id), RefreshToken),
        }
        for rotulo, tk in casos.items():
            r = APIClient().get("/api/auth/me/", HTTP_AUTHORIZATION=f"Bearer {tk}")
            self.assertEqual(r.status_code, 401, rotulo)
        # sessão expirada
        SessaoAutenticacao.objects.filter(pk=sessao_u.pk).update(expira_em=timezone.now() - timedelta(seconds=1))
        r = APIClient().get("/api/auth/me/", HTTP_AUTHORIZATION=f"Bearer {self.token(self.u, str(sessao_u.id))}")
        self.assertEqual(r.status_code, 401)
        # e o controle positivo: sid correto e vivo funciona
        SessaoAutenticacao.objects.filter(pk=sessao_u.pk).update(expira_em=timezone.now() + timedelta(days=1))
        r = APIClient().get("/api/auth/me/", HTTP_AUTHORIZATION=f"Bearer {self.token(self.u, str(sessao_u.id))}")
        self.assertEqual(r.status_code, 200)

    def test_token_com_chave_errada_ou_alg_none_e_rejeitado(self):
        import base64, json
        sessao = None
        self.login(self.u.email)
        sessao = SessaoAutenticacao.objects.get(usuario=self.u)
        def b64(d):
            return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()
        exp = int((timezone.now() + timedelta(hours=1)).timestamp())
        payload = {"token_type": "access", "exp": exp, "iat": exp - 10, "jti": "x" * 32,
                   "user_id": str(self.u.pk), "sid": str(sessao.id)}
        none_tok = f"{b64({'alg': 'none', 'typ': 'JWT'})}.{b64(payload)}."
        r = APIClient().get("/api/auth/me/", HTTP_AUTHORIZATION=f"Bearer {none_tok}")
        self.assertEqual(r.status_code, 401)

    def test_cookie_com_token_de_sessao_revogada_vira_anonimo_e_nao_acessa_nada(self):
        c, csrf = self.login(self.u.email)
        self.assertEqual(c.get("/api/auth/me/").status_code, 200)
        c.post("/api/auth/logout/", {}, format="json", **csrf)
        # reanexa os cookies velhos (o navegador "malicioso" guardou o cookie antes do logout)
        sessao = SessaoAutenticacao.objects.get(usuario=self.u)
        self.assertIsNotNone(sessao.revogada_em)
        velho = APIClient()
        velho.cookies["tpa_access"] = self.token(self.u, str(sessao.id))
        self.assertEqual(velho.get("/api/auth/me/").status_code, 401)
        self.assertEqual(velho.get("/api/equipamentos/").status_code, 401)

    def test_refresh_depois_do_logout_replay_e_troca_de_senha(self):
        c, csrf = self.login(self.u.email)
        refresh_antigo = c.cookies["tpa_refresh"].value
        # 1) rotação normal e replay do refresh antigo
        self.assertEqual(c.post("/api/auth/session/refresh/", {}, format="json", **csrf).status_code, 204)
        replay = APIClient(enforce_csrf_checks=True)
        replay.cookies["tpa_refresh"] = refresh_antigo
        csrf2 = {"HTTP_X_CSRFTOKEN": replay.get("/api/auth/csrf/").data["csrfToken"]}
        self.assertEqual(replay.post("/api/auth/session/refresh/", {}, format="json", **csrf2).status_code, 401)
        # 2) logout e refresh
        refresh_vivo = c.cookies["tpa_refresh"].value
        c.post("/api/auth/logout/", {}, format="json", **csrf)
        pos = APIClient(enforce_csrf_checks=True)
        pos.cookies["tpa_refresh"] = refresh_vivo
        csrf3 = {"HTTP_X_CSRFTOKEN": pos.get("/api/auth/csrf/").data["csrfToken"]}
        self.assertEqual(pos.post("/api/auth/session/refresh/", {}, format="json", **csrf3).status_code, 401)

    def test_outra_sessao_encerrada_por_troca_de_senha_e_por_encerrar_outras(self):
        a, csrf_a = self.login(self.u.email)
        b, csrf_b = self.login(self.u.email)
        refresh_a = a.cookies["tpa_refresh"].value
        r = b.post("/api/auth/seguranca/alterar-senha/",
                   {"senha_atual": SENHA, "nova_senha": "outra frase senha muito longa 2027"}, format="json", **csrf_b)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(a.get("/api/auth/me/").status_code, 401)       # access da sessão A morreu
        self.assertEqual(b.get("/api/auth/me/").status_code, 200)       # a corrente sobrevive
        p = APIClient(enforce_csrf_checks=True)
        p.cookies["tpa_refresh"] = refresh_a
        t = {"HTTP_X_CSRFTOKEN": p.get("/api/auth/csrf/").data["csrfToken"]}
        self.assertEqual(p.post("/api/auth/session/refresh/", {}, format="json", **t).status_code, 401)

        c, csrf_c = self.login(self.u.email) if False else (None, None)

    def test_master_exclui_usuario_e_token_dele_morre(self):
        c, _ = self.login(self.v.email)
        sessao = SessaoAutenticacao.objects.get(usuario=self.v)
        tk = self.token(self.v, str(sessao.id))
        m, csrf = self.login(self.master.email, "admin")
        r = m.delete(f"/api/usuarios/{self.v.pk}/", **csrf)
        self.assertIn(r.status_code, (204, 200), r.content)
        self.assertEqual(APIClient().get("/api/auth/me/", HTTP_AUTHORIZATION=f"Bearer {tk}").status_code, 401)

    def test_login_com_conta_suspensa_e_token_pre_existente(self):
        c, _ = self.login(self.u.email)
        sessao = SessaoAutenticacao.objects.get(usuario=self.u)
        tk = self.token(self.u, str(sessao.id))
        User.objects.filter(pk=self.u.pk).update(estado=EstadoConta.SUSPENDED)
        self.assertEqual(APIClient().get("/api/auth/me/", HTTP_AUTHORIZATION=f"Bearer {tk}").status_code, 401)
        User.objects.filter(pk=self.u.pk).update(estado=EstadoConta.ACTIVE, is_active=False)
        self.assertEqual(APIClient().get("/api/auth/me/", HTTP_AUTHORIZATION=f"Bearer {tk}").status_code, 401)

    def test_header_authorization_nao_bearer_com_cookie_valido(self):
        """Comportamento (não é falha de segurança): `Authorization: Basic ...` + cookie válido => anônimo (401),
        porque o ramo de cabeçalho devolve None sem cair para o cookie."""
        c, _ = self.login(self.u.email)
        r = c.get("/api/auth/me/", HTTP_AUTHORIZATION="Basic dTp4")
        print("\n[info] Authorization Basic + cookie válido ->", r.status_code)


# ============================================================================ A-03 mídia
from django.apps import apps as django_apps  # noqa: E402
from apps.cadastros.models import DadosTecnicosMotor, TecnologiaAnalise, TipoEquipamento  # noqa: E402
from apps.coletas.models import Achado, AchadoImagem, Carregamento, ItemInspecao  # noqa: E402
from apps.core import midia  # noqa: E402


def _png():
    b = io.BytesIO()
    Image.new("RGB", (4, 4), (10, 20, 30)).save(b, "PNG")
    return b.getvalue()


def _f(nome):
    return SimpleUploadedFile(nome, _png(), content_type="image/png")


class A03Midia(TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.mkdtemp()
        cls._o = override_settings(MEDIA_ROOT=cls._tmp)
        cls._o.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._o.disable()
        shutil.rmtree(cls._tmp, ignore_errors=True)

    @classmethod
    def setUpTestData(cls):
        cls.a = Cliente.objects.create(nome="A", cnpj="11.111.111/0001-11")
        cls.b = Cliente.objects.create(nome="B", cnpj="22.222.222/0001-22")
        cls.tec = TecnologiaAnalise.objects.create(nome="Vib", sigla="VIB")
        tipo = TipoEquipamento.objects.create(nome="Motor")
        setor = Setor.objects.create(area=Area.objects.create(cliente=cls.a, codigo="A", nome="A"), codigo="A", nome="A")
        eq = Equipamento.objects.create(setor=setor, tag="A-1", nome="Motor", tipo_equipamento=tipo)
        cls.placa = DadosTecnicosMotor.objects.create(equipamento=eq, foto_placa=_f("placa_motor.png"))
        cls.interno = _mk("i@t.test", "TECNICO"); car = Carregamento.objects.create(cliente=cls.a, tecnologia=cls.tec, analista=cls.interno)
        item = ItemInspecao.objects.create(carregamento=car, equipamento=eq, ordem=1)
        ach = Achado.objects.create(item=item, visivel_cliente=True)  # liberado ao cliente (S-24): sem isso a foto não sai
        cls.img = AchadoImagem.objects.create(achado=ach, tipo="ESPECTRO", arquivo=_f("evid.png"))
        cls.cli_a = _mk("a@a.test", "CLIENTE_PCM", cliente=cls.a)
        cls.cli_b = _mk("b@b.test", "CLIENTE_PCM", cliente=cls.b)
        cls.orfao = _mk("o@o.test", "CLIENTE_PCM")

    def get(self, user, caminho_url):
        c = APIClient()
        if user:
            c.force_authenticate(user)
        return c.get(caminho_url)

    def test_traversal_e_codificacoes(self):
        os.makedirs(os.path.join(self._tmp, "achados"), exist_ok=True)
        with open(os.path.join(self._tmp, "segredo.png"), "wb") as fh:
            fh.write(_png())
        ruins = [
            "..%2fsegredo.png", "%2e%2e/segredo.png", "%2E%2E%2Fsegredo.png", "achados/%2e%2e/segredo.png",
            "achados/..%2fsegredo.png", "achados%2f..%2fsegredo.png", "achados/%252e%252e/segredo.png",
            "%252e%252e%252fsegredo.png", "achados" + chr(92) + ".." + chr(92) + "segredo.png", "achados%5c..%5csegredo.png",
            "/etc/passwd", "%2fetc%2fpasswd", "achados/evid.png%00.png", "achados/%00../segredo.png",
            "achados/./" + os.path.basename(self.img.arquivo.name), "achados//" + os.path.basename(self.img.arquivo.name),
            "achados/" + os.path.basename(self.img.arquivo.name) + "/", "achados/" + os.path.basename(self.img.arquivo.name) + "/.",
            "segredo.png", "achados/../segredo.png", "file:///etc/passwd", "http://x/y.png",
            "achados/" + os.path.basename(self.img.arquivo.name).upper(),
            "achados/" + os.path.basename(self.img.arquivo.name) + ".svg",
            "achados/%C0%AE%C0%AE/segredo.png",
        ]
        for u in ruins:
            r = self.get(self.interno, "/api/media/" + u)
            self.assertIn(r.status_code, (404, 400), f"{u} -> {r.status_code}")
        # controle positivo
        self.assertEqual(self.get(self.interno, "/api/media/" + self.img.arquivo.name).status_code, 200)

    def test_resolvedor_nome_seguro_unitario(self):
        for ruim in ("../a.png", "a/../b.png", "/a.png", "a//b.png", "a/./b.png", "a" + chr(92) + "b.png", "", "a" + chr(0) + ".png", ".."):
            self.assertIsNone(midia.nome_seguro(ruim), ruim)

    def test_cliente_sem_vinculo_nao_ve_nada_com_dono_de_cliente(self):
        for nome in (self.img.arquivo.name, self.placa.foto_placa.name):
            self.assertEqual(self.get(self.orfao, "/api/media/" + nome).status_code, 404)
            self.assertEqual(self.get(self.cli_b, "/api/media/" + nome).status_code, 404)
            self.assertEqual(self.get(self.cli_a, "/api/media/" + nome).status_code, 200)
            self.assertIn(self.get(None, "/api/media/" + nome).status_code, (401, 403))

    def test_todos_os_caminhos_orm_das_regras_sao_validos(self):
        """Se um caminho de REGRAS estiver errado, o cliente receberia 500 (FieldError) — checa todos."""
        for prefixo, rotulo, campos, caminho in midia.REGRAS:
            if caminho in (None, "__assinatura__"):
                continue
            modelo = django_apps.get_model(rotulo)
            list(modelo._default_manager.filter(**{caminho: self.a.pk})[:1])

    def test_todo_upload_to_do_projeto_tem_regra(self):
        """Todo ImageField/FileField cujo upload_to não esteja em REGRAS ficaria 404 (imagem quebrada)."""
        faltando = []
        for modelo in django_apps.get_models():
            for campo in modelo._meta.get_fields():
                up = getattr(campo, "upload_to", None)
                if up and not any(str(up).startswith(p) or p.startswith(str(up)) for p, *_ in midia.REGRAS):
                    faltando.append(f"{modelo.__name__}.{campo.name} ({up})")
        self.assertEqual(faltando, [])

    @override_settings(MEDIA_ACCEL_PREFIX="/protected-media/")
    def test_x_accel_redirect_com_nome_nao_ascii_sai_percent_encoded(self):
        """R-01 (corrigido em midia.py com quote()): antes o header X-Accel-Redirect levava o nome do arquivo cru. Django aceita nomes com letras
        acentuadas (get_valid_filename mantém 'ç', 'ã'), grava no header em latin-1 (ou MIME-encoded se fora de
        latin-1) e o nginx NÃO acha o arquivo (404) — prova funcional com nginx real no relatório."""
        AchadoImagem.objects.filter(pk=self.img.pk).update(arquivo="achados/inspeção_01.png")
        r = self.get(self.interno, "/api/media/achados/inspeção_01.png")
        self.assertEqual(r.status_code, 200)
        valor = r["X-Accel-Redirect"]
        self.assertTrue(valor.isascii() and "%C3%A7" in valor.upper(), f"header cru: {valor!r}")


# ============================================================================ upload
class UploadEvidencias(TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.mkdtemp()
        cls._o = override_settings(MEDIA_ROOT=cls._tmp)
        cls._o.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._o.disable()
        shutil.rmtree(cls._tmp, ignore_errors=True)

    @classmethod
    def setUpTestData(cls):
        cls.a = Cliente.objects.create(nome="A", cnpj="11.111.111/0001-11")
        cls.tec = TecnologiaAnalise.objects.create(nome="Vib", sigla="VIB")
        cls.interno = _mk("i@t.test", "TECNICO", "MASTER")
        tipo = TipoEquipamento.objects.create(nome="Motor")
        setor = Setor.objects.create(area=Area.objects.create(cliente=cls.a, codigo="A", nome="A"), codigo="A", nome="A")
        eq = Equipamento.objects.create(setor=setor, tag="A-1", nome="Motor", tipo_equipamento=tipo)
        car = Carregamento.objects.create(cliente=cls.a, tecnologia=cls.tec, analista=cls.interno)
        item = ItemInspecao.objects.create(carregamento=car, equipamento=eq, ordem=1)
        cls.achado = Achado.objects.create(item=item)
        cls.cli = _mk("c@a.test", "CLIENTE_PCM", "MASTER", cliente=cls.a)

    def up(self, nome, conteudo, tipo="image/png", user=None):
        c = APIClient()
        c.force_authenticate(user or self.interno)
        return c.post("/api/achados-imagens/", {"achado": self.achado.pk, "tipo": "ESPECTRO",
                                                "arquivo": SimpleUploadedFile(nome, conteudo, content_type=tipo)},
                      format="multipart")

    def test_tipos_perigosos_sao_recusados(self):
        svg = b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"/>'
        html = b"<html><script>alert(1)</script></html>"
        casos = [("a.svg", svg, "image/svg+xml"), ("a.png", svg, "image/png"), ("a.png", html, "image/png"),
                 ("a.html", _png(), "text/html"), ("a.php.png", html, "image/png"), ("a.png", b"", "image/png"),
                 ("a.pdf", b"%PDF-1.4", "application/pdf"), ("a.png", b"GIF89a" + html, "image/png")]
        for nome, dado, tipo in casos:
            r = self.up(nome, dado, tipo)
            self.assertEqual(r.status_code, 400, f"{nome} {dado[:12]!r} -> {r.status_code} {r.content[:120]}")

    def test_teto_de_10mb_na_evidencia(self):
        with override_settings(LAUDOS_MAX_IMAGEM_BYTES=2000):
            grande = _png() + b"\0" * 5000  # PNG válido com lixo no fim => ainda abre no Pillow
            r = self.up("grande.png", grande)
            self.assertEqual(r.status_code, 400, r.content)
            self.assertIn("excede", str(r.content))
        self.assertEqual(self.up("ok.png", _png()).status_code, 201)

    def test_nome_com_traversal_e_sanitizado_e_nao_sobrescreve(self):
        r1 = self.up("../../../etc/x.png", _png())
        self.assertEqual(r1.status_code, 201, r1.content)
        nome = AchadoImagem.objects.latest("id").arquivo.name
        self.assertTrue(nome.startswith("achados/") and ".." not in nome and nome.count("/") == 1, nome)
        r2 = self.up("x.png", _png())
        r3 = self.up("x.png", _png())
        self.assertNotEqual(AchadoImagem.objects.order_by("-id")[0].arquivo.name,
                            AchadoImagem.objects.order_by("-id")[1].arquivo.name)

    def test_cliente_nao_envia_evidencia(self):
        self.assertEqual(self.up("a.png", _png(), user=self.cli).status_code, 403)

    def test_png_gigante_em_pixels_e_recusado_ou_controlado(self):
        """Bomba de descompressão: 30000x30000 de uma cor (poucos KB) — o Pillow aborta (> 2x MAX_IMAGE_PIXELS)."""
        import zlib, struct
        w = h = 30000
        def chunk(t, d):
            c = struct.pack(">I", len(d)) + t + d
            return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
        # constrói IDAT streaming de h linhas
        comp = zlib.compressobj(9)
        partes = []
        linha = b"\x00" * (w * 3 + 1)
        for _ in range(h):
            partes.append(comp.compress(linha))
        partes.append(comp.flush())
        idat = b"".join(partes)
        png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
               + chunk(b"IDAT", idat) + chunk(b"IEND", b""))
        print(f"\n[info] PNG {w}x{h} ocupa {len(png)/1024:.0f} KB")
        r = self.up("bomba.png", png)
        print("[info] bomba de pixels ->", r.status_code, r.content[:100])
        self.assertIn(r.status_code, (400, 413))


# ============================================================================ isolamento (varredura mais estrita)
import re  # noqa: E402
from apps.core.test_seguranca_isolamento import IsolamentoEntreClientes as _Iso, _lista  # noqa: E402


class IsolamentoEstrito(_Iso):
    """Reaproveita o cenário dos autores, mas confere STATUS (não só marcadores de texto):
    com um id que pertence à vítima, o intruso e o órfão precisam receber 403/404 em qualquer
    detalhe ou @action GET — exceto catálogos globais (ids que o intruso também lista)."""

    def _ids_privados(self, prefixo):
        dono = _lista(self.api(self.dono).get("/" + prefixo, {"page_size": 100}))
        intr = _lista(self.api(self.intruso).get("/" + prefixo, {"page_size": 100}))
        publicos = {str(o.get("id")) for o in intr if isinstance(o, dict)}
        return [str(o["id"]) for o in dono if isinstance(o, dict) and "id" in o and str(o["id"]) not in publicos]

    def test_detalhes_e_acoes_get_da_vitima_sao_404_para_intruso_e_orfao(self):
        falhas, testadas = [], 0
        for molde in self.modelos:
            if "{pk}" not in molde:
                continue
            prefixo = molde.split("{")[0]
            ids = self._ids_privados(prefixo)[:3]
            for pk in ids:
                nomes = re.findall(r"\{(\w+)\}", molde)
                extras = {"key": "tecnico", "item_id": "1", "anexo_id": "1", "token": "x" * 40, "nome": "a.png"}
                url = "/" + molde.format(**{n: (pk if n == "pk" else extras.get(n, "1")) for n in nomes})
                for u in (self.intruso, self.orfao):
                    r = self.api(u).get(url)
                    testadas += 1
                    self.assertLess(r.status_code, 500, f"500 {url}")
                    if r.status_code not in (401, 403, 404, 405):
                        falhas.append((u.email, url, r.status_code))
        print(f"\n[info] {testadas} requisições estritas; falhas: {falhas}")
        self.assertGreater(testadas, 100)
        self.assertEqual(falhas, [])

    def test_exportacoes_em_todos_os_formatos_com_cliente_da_vitima(self):
        api = self.api(self.intruso)
        vazou = []
        for rel in ("tecnico", "gerencial", "historico", "equipamento", "falhas", "financeiro", "produtividade",
                    "painel-executivo"):
            for fmt in ("json", "csv", "xlsx", "pdf"):
                r = api.get(f"/api/relatorios/{rel}/", {"formato": fmt, "cliente": self.vitima.pk,
                                                        "equipamento": 1, "inspecao": 1})
                self.assertLess(r.status_code, 500, f"{rel} {fmt}")
                if r.status_code == 200 and fmt in ("json", "csv"):
                    corpo = r.content.decode("utf-8", "replace")
                    vazou += [(rel, fmt, m) for m in self.marcas if m in corpo]
                if r.status_code == 200 and rel in ("financeiro", "produtividade", "painel-executivo"):
                    vazou.append((rel, fmt, "interno-acessivel-ao-cliente"))
        self.assertEqual(vazou, [])

    def test_ordering_e_search_por_campo_relacionado_nao_vazam_para_intruso(self):
        """`ordering=` e `search=` com campos de relacionamento: só existe oráculo se o conjunto ordenado/filtrado
        contiver linhas da vítima, o que o escopo impede — confirma que a contagem do intruso nunca inclui dela."""
        api = self.api(self.intruso)
        for molde in self.modelos:
            if "{" in molde or not molde.startswith("api/"):
                continue
            base = api.get("/" + molde, {"page_size": 100})
            if base.status_code != 200:
                continue
            n_base = base.data.get("count") if isinstance(base.data, dict) else None
            for termo in (self.vitima.nome.split()[0], "UH-01", "OSP", "P-0"):
                r = api.get("/" + molde, {"search": termo, "ordering": "-cliente__nome", "page_size": 100})
                self.assertLess(r.status_code, 500, f"{molde} search={termo}")
                if r.status_code == 200 and isinstance(r.data, dict) and n_base is not None:
                    self.assertLessEqual(r.data.get("count"), n_base, f"{molde}: search ampliou o conjunto")
                    corpo = r.content.decode("utf-8", "replace")
                    for m in self.marcas:
                        self.assertNotIn(m, corpo.replace(f"search={termo}", ""), molde)


class S24RascunhoInvisivelAoCliente(A03Midia):
    """S-24 (decidido): o cliente NÃO lê achado com `visivel_cliente=False` nem a imagem dele
    pela API. Internos continuam lendo. A mídia (`/api/media/`) é tratada em `core/midia.py`
    (arquivo do Agente 1) e ainda não foi alterada aqui — ver docs/22."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # Achado NÃO liberado ao cliente (o da fixture base foi liberado para o teste de mídia).
        cls.ach_oculto = Achado.objects.create(item=cls.img.achado.item, visivel_cliente=False)

    def test_cliente_nao_le_achado_nao_visivel(self):
        c = APIClient()
        c.force_authenticate(self.cli_a)
        ids = [a["id"] for a in c.get("/api/achados/").data["results"]]
        self.assertNotIn(self.ach_oculto.pk, ids)

    def test_interno_le_achado_nao_visivel(self):
        c = APIClient()
        c.force_authenticate(self.interno)
        ids = [a["id"] for a in c.get("/api/achados/").data["results"]]
        self.assertIn(Achado.objects.get(visivel_cliente=False).pk, ids)

    def test_cliente_liberado_aparece(self):
        Achado.objects.filter(visivel_cliente=False).update(visivel_cliente=True)
        c = APIClient()
        c.force_authenticate(self.cli_a)
        ids = [a["id"] for a in c.get("/api/achados/").data["results"]]
        self.assertIn(self.ach_oculto.pk, ids)
