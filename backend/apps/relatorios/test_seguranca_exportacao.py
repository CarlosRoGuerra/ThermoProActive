"""Regressão: texto de dado nunca vira marcação do ReportLab (SSRF/leitura de arquivo) nem fórmula de planilha."""
from unittest import mock

from django.test import SimpleTestCase

from .exporters import to_csv, to_pdf, to_xlsx
from .reports import Relatorio


class ExportacaoSegura(SimpleTestCase):
    def test_pdf_nao_interpreta_marcacao_nem_busca_url_remota(self):
        rel = Relatorio(titulo="<img src='http://127.0.0.1:9/t.png'/>", colunas=["<b>x</b>"],
                        linhas=[["<img src='http://127.0.0.1:9/ssrf.png'/>"], ["a & b < c"]])
        with mock.patch("reportlab.lib.utils.open_for_read") as abrir:
            pdf = to_pdf(rel)
        abrir.assert_not_called()
        self.assertTrue(pdf.startswith(b"%PDF"))

    def test_csv_e_xlsx_neutralizam_formula(self):
        rel = Relatorio(titulo="t", colunas=["a"], linhas=[["=HYPERLINK(\"http://x\")"], ["+1+1"], ["@SUM(1)"]])
        self.assertIn("'=HYPERLINK", to_csv(rel).decode("utf-8-sig"))
        self.assertTrue(to_xlsx(rel).startswith(b"PK"))
