r"""Integração opt-in: Chromium imprime os dois layouts existentes, sem mock.

Requer frontend local já compilado/servido. Exemplo PowerShell:
$env:LAUDOS_TEST_RENDER_URL='http://127.0.0.1:3100'
.\.venv\Scripts\python.exe manage.py test apps.laudos.test_pdf_layout --noinput

Artefatos vão a LAUDOS_TEST_ARTIFACT_DIR ou backend/test-artifacts/laudos.
"""
import hashlib
import io
import os
from datetime import date, timedelta
from pathlib import Path
from unittest import skipUnless

from django.conf import settings
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image, ImageDraw, ImageStat

from apps.cadastros.models import Equipamento
from apps.coletas.models import Achado, AchadoImagem, Inspecao, ItemInspecao, MedicaoTermografia

from . import test_conformidade_documentos as qa
from .models import AnexoLaudo, Laudo
from .pdf import congelar_imagens, gerar_pdf
from .services import gerar_laudo_de_inspecao
from .snapshots import montar_snapshot

RENDER_URL = os.environ.get("LAUDOS_TEST_RENDER_URL")


@skipUnless(RENDER_URL, "Defina LAUDOS_TEST_RENDER_URL para testar Chromium/layout real.")
@override_settings(LAUDOS_FRONTEND_URL=RENDER_URL or "http://127.0.0.1:3100")
class PDFLayoutRealTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Reaproveita somente a preparação dos dados, sem herdar testes/patches.
        qa.ConformidadeDocumentosTest.setUpTestData.__func__(cls)

    @staticmethod
    def imagem_qa():
        imagem = Image.new("RGB", (800, 600), color=(245, 240, 230))
        desenho = ImageDraw.Draw(imagem)
        desenho.rectangle((40, 60, 380, 540), fill=(170, 40, 30))
        desenho.rectangle((420, 60, 760, 540), fill=(20, 70, 170))
        desenho.line((40, 60, 760, 540), fill=(0, 0, 0), width=12)
        buffer = io.BytesIO()
        imagem.save(buffer, format="PNG")
        return buffer.getvalue()

    def configurar_documento(self, laudo):
        laudo.status = "EMITIDO"  # snapshot de teste em memória; não burla serviço operacional.
        laudo.data_emissao = timezone.now()
        laudo.assinatura = {"metodo": "APROVACAO_ELETRONICA_INTERNA", "usuario_id": self.responsavel.pk,
            "nome": self.responsavel.nome, "conselho": self.responsavel.conselho_classe,
            "assinatura_criptografica": False, "data_hora": laudo.data_emissao.isoformat()}
        laudo.diagnostico += "\nAção técnica QA: inspeção e medição. ΔT em °C; resistência em MΩ; deslocamento em µm."
        laudo.recomendacoes = "Recomendação QA: conferir o contexto e a evidência com o responsável técnico."
        laudo.conclusao = "Conclusão QA: avaliação registrada; causa de falha não confirmada. MARCADOR-FIM-DOCUMENTAL"
        imagem = self.imagem_qa()
        # O anexo só é adicionado ao rascunho persistido; status acima é só em memória.
        persistido = Laudo.objects.get(pk=laudo.pk)
        AnexoLaudo.objects.create(laudo=persistido, nome="evidencia-layout-qa.png",
            legenda="Evidência fotográfica QA — carcaça e ponto medido", mime="image/png",
            sha256=hashlib.sha256(imagem).hexdigest(), tamanho=len(imagem), conteudo=imagem,
            criado_por=self.responsavel)
        return congelar_imagens(montar_snapshot(laudo))

    def validar_pdf_e_gravar(self, nome, snapshot, minimo_paginas):
        from pypdf import PdfReader
        import pypdfium2 as pdfium

        conteudo = gerar_pdf(snapshot)
        self.assertTrue(conteudo.startswith(b"%PDF-"))
        leitor = PdfReader(io.BytesIO(conteudo))
        texto = "\n".join(p.extract_text() or "" for p in leitor.pages)
        for marcador in ("Cliente documental QA", "DOC-QA-01", "Ação técnica QA", "ΔT", "MΩ", "µm",
                         "MARCADOR-FIM-DOCUMENTAL", "Evidência fotográfica QA"):
            self.assertIn(marcador, texto, f"Conteúdo ausente no PDF {nome}: {marcador}")
        self.assertGreaterEqual(len(leitor.pages), minimo_paginas)
        self.assertGreater(sum(len(p.images) for p in leitor.pages), 0, "Nenhuma imagem raster incorporada ao PDF.")
        pasta = Path(os.environ.get("LAUDOS_TEST_ARTIFACT_DIR", Path(settings.BASE_DIR) / "test-artifacts" / "laudos"))
        pasta.mkdir(parents=True, exist_ok=True)
        (pasta / f"{nome}.pdf").write_bytes(conteudo)
        (pasta / f"{nome}.txt").write_text(texto, encoding="utf-8")
        documento = pdfium.PdfDocument(conteudo)
        try:
            for indice in sorted({0, 1, len(documento) - 1}):
                pagina = documento[indice]
                imagem = pagina.render(scale=1).to_pil()
                self.assertGreater(max(ImageStat.Stat(imagem.convert("RGB")).stddev), 3,
                                   f"Página {indice + 1} aparentemente vazia em {nome}.")
                imagem.save(pasta / f"{nome}-pagina-{indice + 1:02d}.png")
                pagina.close()
        finally:
            documento.close()
        return texto

    def test_layout_direto_unicode_medicoes_anexo_e_muitas_paginas(self):
        inspecao = Inspecao.objects.create(cliente=self.cliente, tecnico=self.responsavel,
            tipo_analise="TERMOGRAFIA", data=date(2026, 10, 20))
        instante = timezone.make_aware(timezone.datetime(2026, 10, 20, 12))
        for indice in range(3):
            MedicaoTermografia.objects.create(inspecao=inspecao, equipamento=self.equipamento,
                instrumento=self.instrumento, ponto_medicao="PONTO-TERMICO-QA-000", sistema="ELETRICO",
                temperatura_ponto=30 + indice * 5, temperatura_referencia=20,
                temperatura_ambiente=25, emissividade="0.90", carga_percentual=80,
                data_hora=instante - timedelta(days=3 - indice))
        for indice in range(65):
            MedicaoTermografia.objects.create(inspecao=inspecao, equipamento=self.equipamento,
                instrumento=self.instrumento, ponto_medicao=f"PONTO-TERMICO-QA-{indice:03d}",
                sistema="ELETRICO", temperatura_ponto=45 + indice, temperatura_referencia=20,
                temperatura_ambiente=25, emissividade="0.90", carga_percentual=80,
                data_hora=instante + timedelta(seconds=indice))
        laudo = gerar_laudo_de_inspecao(inspecao, self.responsavel)
        snapshot = self.configurar_documento(laudo)
        self.assertEqual(len(snapshot["medicoes"]), 68)
        self.assertTrue(snapshot["graficos"], "A série térmica comparável precisa alimentar os dados gráficos reais.")
        texto = self.validar_pdf_e_gravar("qa-laudo-direto", snapshot, minimo_paginas=6)
        self.assertIn("PONTO-TERMICO-QA-000", texto)
        self.assertIn("PONTO-TERMICO-QA-064", texto)

    def test_layout_modular_unicode_medicoes_fotografia_e_muitas_paginas(self):
        origem, achado = qa.ConformidadeDocumentosTest.origem_por_rota(self)
        carregamento = achado.item.carregamento
        for indice in range(1, 65):
            equipamento = Equipamento.objects.create(setor=self.equipamento.setor,
                tag=f"TAG-ROTA-QA-{indice:03d}", nome=f"Máquina de inspeção QA {indice}")
            item = ItemInspecao.objects.create(carregamento=carregamento, equipamento=equipamento,
                ordem=indice + 1, condicao=achado.item.condicao)
            Achado.objects.create(item=item, anomalia_texto=f"Observação técnica QA {indice}", confirmada=True)
        imagem = self.imagem_qa()
        from django.core.files.base import ContentFile
        achado_imagem = AchadoImagem(achado=achado, legenda="Imagem da medição QA — ponto inspecionado")
        # Storage em memória evita deixar dados de teste na mídia operacional.
        with override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.InMemoryStorage"}}):
            achado_imagem.arquivo.save("medicao-qa.png", ContentFile(imagem), save=True)
            laudo = Laudo.objects.create(relatorio_origem=origem, responsavel=self.responsavel,
                titulo="Laudo modular QA", diagnostico="Inspeção modular QA e observações sensoriais")
            snapshot = self.configurar_documento(laudo)
        self.assertGreaterEqual(len(snapshot["evidencias"]), 2)
        texto = self.validar_pdf_e_gravar("qa-laudo-modular", snapshot, minimo_paginas=6)
        self.assertIn("TAG-ROTA-QA-064", texto)
        self.assertIn("Imagem da medição QA", texto)
