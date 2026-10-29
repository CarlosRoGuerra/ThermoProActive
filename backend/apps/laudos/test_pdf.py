"""Limites operacionais, imagens congeladas e falhas controladas do renderer."""
import base64
import io
import subprocess
import tempfile
from unittest.mock import patch

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.test import SimpleTestCase, override_settings
from PIL import Image

from .pdf import ErroGeracaoPDF, congelar_imagens, gerar_pdf


def imagem_png():
    arquivo = io.BytesIO()
    Image.new("RGB", (80, 60), "orange").save(arquivo, format="PNG")
    return arquivo.getvalue()


class CongelamentoImagemTest(SimpleTestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.addCleanup(self.pasta.cleanup)
        self.config = override_settings(MEDIA_ROOT=self.pasta.name, MEDIA_URL="media/")
        self.config.enable()
        self.addCleanup(self.config.disable)

    def test_media_relativa_absoluta_e_bytes_preservados(self):
        dados = imagem_png()
        nome = default_storage.save("laudos/foto.png", ContentFile(dados))
        original = {"imagens": [{"url": "/media/" + nome}, {"arquivo": "https://api.exemplo.test/media/" + nome}]}
        congelado = congelar_imagens(original)
        self.assertEqual(congelado["imagens"][0]["url"], congelado["imagens"][1]["arquivo"])
        default_storage.delete(nome)
        self.assertEqual(base64.b64decode(congelado["imagens"][0]["url"].split(",")[1]), dados)
        self.assertTrue(original["imagens"][0]["url"].startswith("/media/"))

    def test_imagem_incorporada_validada_e_idempotente(self):
        uri = "data:image/png;base64," + base64.b64encode(imagem_png()).decode()
        snapshot = {"evidencias": [{"data_uri": uri}], "texto": "Inspeção — ΔT e µm"}
        self.assertEqual(congelar_imagens(snapshot), snapshot)

    def test_imagem_ausente_corrompida_externa_ou_traversal_bloqueia(self):
        casos = ["/media/ausente.png", "/media/../segredo.png", "/media/%2E%2E/segredo.png",
                 "https://externo.test/foto.png", "data:image/png;base64,%%%%",
                 "data:image/png;base64," + base64.b64encode(b"nao e imagem").decode()]
        for caso in casos:
            with self.subTest(caso=caso), self.assertRaises(ErroGeracaoPDF):
                congelar_imagens({"imagem": caso})

    @override_settings(LAUDOS_MAX_IMAGEM_BYTES=10)
    def test_limite_individual(self):
        uri = "data:image/png;base64," + base64.b64encode(imagem_png()).decode()
        with self.assertRaisesMessage(ErroGeracaoPDF, "limite"):
            congelar_imagens({"foto": uri})

    def test_limite_total_conta_dados_unicos(self):
        dados = imagem_png()
        uri = "data:image/png;base64," + base64.b64encode(dados).decode()
        with override_settings(LAUDOS_MAX_IMAGENS_BYTES=len(dados)):
            self.assertEqual(congelar_imagens({"foto": uri, "imagem": uri})["foto"], uri)
        with override_settings(LAUDOS_MAX_IMAGENS_BYTES=len(dados)-1):
            with self.assertRaisesMessage(ErroGeracaoPDF, "Conjunto"):
                congelar_imagens({"foto": uri})

    @override_settings(LAUDOS_MAX_SNAPSHOT_NOS=3)
    def test_complexidade_limitada(self):
        with self.assertRaisesMessage(ErroGeracaoPDF, "complexidade"):
            congelar_imagens({"itens": [1, 2, 3]})


class RendererLayoutTest(SimpleTestCase):
    @patch("apps.laudos.pdf.subprocess.run")
    def test_bytes_pdf_sem_reconstrucao_em_outro_design(self, executar):
        executar.return_value = subprocess.CompletedProcess([], 0, b"%PDF-layout-original", b"")
        self.assertEqual(gerar_pdf({"schema": "laudo_v1"}), b"%PDF-layout-original")
        args, kwargs = executar.call_args
        self.assertIn("render-layout.cjs", args[0][1])
        self.assertNotIn("shell", kwargs)
        self.assertIn(b'"snapshot"', kwargs["input"])

    @patch("apps.laudos.pdf.subprocess.run")
    def test_falha_timeout_e_bytes_invalidos_bloqueiam_emissao(self, executar):
        for retorno in [subprocess.CompletedProcess([], 1, b"", b"erro"),
                        subprocess.CompletedProcess([], 0, b"HTML inesperado", b"")]:
            executar.return_value = retorno
            with self.assertRaises(ErroGeracaoPDF):
                gerar_pdf({})
        executar.side_effect = subprocess.TimeoutExpired("node", 1)
        with self.assertRaises(ErroGeracaoPDF):
            gerar_pdf({})

    @override_settings(LAUDOS_FRONTEND_URL="https://externo.test")
    @patch("apps.laudos.pdf.subprocess.run")
    def test_origem_externa_recusada_sem_rede(self, executar):
        with self.assertRaises(ErroGeracaoPDF):
            gerar_pdf({})
        executar.assert_not_called()

    @override_settings(LAUDOS_MAX_PDF_BYTES=5)
    @patch("apps.laudos.pdf.subprocess.run")
    def test_pdf_excessivo_bloqueado(self, executar):
        executar.return_value = subprocess.CompletedProcess([], 0, b"%PDF-excessivo", b"")
        with self.assertRaisesMessage(ErroGeracaoPDF, "tamanho"):
            gerar_pdf({})
