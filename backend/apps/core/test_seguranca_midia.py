"""
Regressão A-03 — a mídia (uploads) só sai para quem tem direito.

Antes: o nginx servia `/media/` direto do volume, sem login, com o nome original do arquivo na
URL (fotos de achados, placas de identificação, assinatura digital do RT, logomarcas de cliente).
Agora: `/api/media/<arquivo>` (apps.core.midia.MidiaView) exige login, resolve o registro dono do
arquivo e aplica o escopo do cliente; o nginx só entrega via X-Accel-Redirect (location interna).
"""
import io
import os
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework.test import APIClient

from apps.cadastros.models import (
    Area, Cliente, DadosTecnicosMotor, Empresa, Equipamento, Setor, TecnologiaAnalise, TipoEquipamento,
)
from apps.coletas.models import Achado, AchadoImagem, Carregamento, ItemInspecao

User = get_user_model()


def png(cor=(200, 30, 30)):
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), cor).save(buf, "PNG")
    return buf.getvalue()


def arquivo(nome):
    return SimpleUploadedFile(nome, png(), content_type="image/png")


class MidiaAutenticadaTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.mkdtemp()
        cls._override = override_settings(MEDIA_ROOT=cls._tmp)
        cls._override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._override.disable()
        shutil.rmtree(cls._tmp, ignore_errors=True)

    @classmethod
    def setUpTestData(cls):
        cls.a = Cliente.objects.create(nome="Cliente A", cnpj="11.111.111/0001-11", logomarca=arquivo("logoA.png"))
        cls.b = Cliente.objects.create(nome="Cliente B", cnpj="22.222.222/0001-22", logomarca=arquivo("logoB.png"))
        cls.empresa = Empresa.objects.create(nome="Prestadora", cnpj="39.923.567/0001-75",
                                             logomarca=arquivo("timbre.png"))
        mk = lambda e, p, **kw: User.objects.create_user(email=e, password="x", nome=e, perfil=p, **kw)  # noqa: E731
        cls.analista = mk("analista@thermo.test", "TECNICO")
        cls.analista.assinatura_digital = arquivo("assinatura_secreta.png")
        cls.analista.save()
        cls.outro_analista = mk("outro@thermo.test", "TECNICO")
        cls.outro_analista.assinatura_digital = arquivo("assinatura_outro.png")
        cls.outro_analista.save()
        cls.cli_a = mk("a@a.test", "CLIENTE_PCM", cliente=cls.a)
        cls.cli_b = mk("b@b.test", "CLIENTE_PCM", cliente=cls.b)
        cls.orfao = mk("o@o.test", "CLIENTE_PCM")

        tec = TecnologiaAnalise.objects.create(nome="Vibração", sigla="VIB", imagem=arquivo("tec.png"))
        tipo = TipoEquipamento.objects.create(nome="Motor")
        setor = Setor.objects.create(area=Area.objects.create(cliente=cls.a, codigo="A", nome="A"), codigo="A", nome="A")
        eq = Equipamento.objects.create(setor=setor, tag="A-001", nome="Motor A", tipo_equipamento=tipo)
        cls.placa = DadosTecnicosMotor.objects.create(equipamento=eq, foto_placa=arquivo("placa.png"))
        carreg = Carregamento.objects.create(cliente=cls.a, tecnologia=tec, analista=cls.analista)
        item = ItemInspecao.objects.create(carregamento=carreg, equipamento=eq, ordem=1)
        # Liberado ao cliente (S-24): sem isso a foto não sai para o cliente (ver midia.FILTRO_EXTRA_CLIENTE).
        achado = Achado.objects.create(item=item, visivel_cliente=True)
        cls.imagem = AchadoImagem.objects.create(achado=achado, tipo="ESPECTRO", arquivo=arquivo("evidencia.png"))
        cls.tec = tec

    def get(self, usuario, nome):
        api = APIClient()
        if usuario:
            api.force_authenticate(usuario)
        return api.get(f"/api/media/{nome}")

    def test_sem_login_nao_baixa_nada(self):
        for nome in (self.imagem.arquivo.name, self.analista.assinatura_digital.name, self.a.logomarca.name):
            self.assertIn(self.get(None, nome).status_code, (401, 403), nome)

    def test_foto_de_achado_respeita_o_cliente(self):
        nome = self.imagem.arquivo.name
        self.assertEqual(self.get(self.analista, nome).status_code, 200)
        r = self.get(self.cli_a, nome)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(b"".join(r.streaming_content)[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(r["X-Content-Type-Options"], "nosniff")
        self.assertIn("sandbox", r["Content-Security-Policy"])
        self.assertEqual(self.get(self.cli_b, nome).status_code, 404)
        self.assertEqual(self.get(self.orfao, nome).status_code, 404)  # falha fechada

    def test_placa_de_identificacao_respeita_o_cliente(self):
        nome = self.placa.foto_placa.name
        self.assertEqual(self.get(self.cli_a, nome).status_code, 200)
        self.assertEqual(self.get(self.cli_b, nome).status_code, 404)

    def test_logomarca_de_cliente_so_do_proprio_cliente_e_do_interno(self):
        self.assertEqual(self.get(self.cli_a, self.a.logomarca.name).status_code, 200)
        self.assertEqual(self.get(self.cli_a, self.b.logomarca.name).status_code, 404)
        self.assertEqual(self.get(self.analista, self.b.logomarca.name).status_code, 200)

    def test_assinatura_so_para_interno_ou_cliente_que_recebeu_trabalho_do_analista(self):
        nome = self.analista.assinatura_digital.name
        self.assertEqual(self.get(self.outro_analista, nome).status_code, 200)
        self.assertEqual(self.get(self.cli_a, nome).status_code, 200)   # analista de uma rota do cliente A
        self.assertEqual(self.get(self.cli_b, nome).status_code, 404)
        self.assertEqual(self.get(self.orfao, nome).status_code, 404)
        # assinatura de quem nunca trabalhou para o cliente A
        self.assertEqual(self.get(self.cli_a, self.outro_analista.assinatura_digital.name).status_code, 404)

    def test_identidade_visual_do_prestador_e_catalogos_para_qualquer_logado(self):
        self.assertEqual(self.get(self.cli_b, self.empresa.logomarca.name).status_code, 200)
        self.assertEqual(self.get(self.cli_b, self.tec.imagem.name).status_code, 200)

    def test_nega_por_padrao(self):
        # arquivo na pasta de mídia sem registro dono, prefixo desconhecido, extensão não-imagem,
        # e tentativas de sair da pasta
        os.makedirs(os.path.join(self._tmp, "achados"), exist_ok=True)
        with open(os.path.join(self._tmp, "achados", "orfao.png"), "wb") as f:
            f.write(png())
        with open(os.path.join(self._tmp, "segredo.txt"), "w") as f:
            f.write("x")
        for nome in ("achados/orfao.png", "segredo.txt", "achados/../segredo.txt", "../segredo.txt",
                     "achados/%2e%2e/segredo.txt", "achados\\..\\x.png", "achados//evidencia.png", "/etc/passwd",
                     "achados/inexistente.png", "tecnologias/x.svg", "achados/x.html"):
            self.assertEqual(self.get(self.analista, nome).status_code, 404, nome)

    @override_settings(MEDIA_ACCEL_PREFIX="/protected-media/")
    def test_com_proxy_responde_x_accel_redirect_sem_corpo(self):
        nome = self.imagem.arquivo.name
        r = self.get(self.cli_a, nome)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["X-Accel-Redirect"], f"/protected-media/{nome}")
        self.assertEqual(r.content, b"")
        self.assertEqual(self.get(self.cli_b, nome).status_code, 404)  # nunca emite o redirect para quem não pode

    def test_url_publica_antiga_nao_e_mais_servida_e_nova_esta_sob_api(self):
        self.assertTrue(self.imagem.arquivo.url.startswith("/api/media/"))
        self.assertEqual(APIClient().get(f"/media/{self.imagem.arquivo.name}").status_code, 404)
