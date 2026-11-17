"""Termografia mecânica no relatório: glossário próprio e condição do ΔT só com critério validado.

Limites sintéticos de teste; não são faixas de ΔT normativas.
"""
from datetime import date
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from apps.cadastros.models import Area, Cliente, Equipamento, OrigemCriterio, Setor
from apps.preditiva.models import LimiteAlarmeSerie, Validacao

from .relatorio_tecnico.termografia_sistemas import (
    GLOSSARIO_TERMOGRAFIA_SISTEMAS,
    MODULO_TERMO_PROCESSOS,
    MODULO_TERMOGRAFIA_MECANICA,
    PENDENCIA_DELTA,
    criterio_delta_t,
)


class GlossarioMecanicoTest(SimpleTestCase):
    def test_sem_termos_eletricos(self):
        textos = " ".join(texto for _, _, texto in GLOSSARIO_TERMOGRAFIA_SISTEMAS)
        siglas = {sigla for _, sigla, _ in GLOSSARIO_TERMOGRAFIA_SISTEMAS}
        for proibido in ("Grandezas Elétricas", "Grau de Risco", "GR-", "I(t)", "I(n)", "U(t)", "IC"):
            self.assertNotIn(proibido, textos + " ".join(siglas), proibido)

    def test_modulos_usam_o_glossario_proprio(self):
        for modulo in (MODULO_TERMOGRAFIA_MECANICA, MODULO_TERMO_PROCESSOS):
            self.assertIs(modulo.carta_glossario, GLOSSARIO_TERMOGRAFIA_SISTEMAS)
            self.assertEqual(modulo.tabelas_normativas, ())


class CriterioDeltaTTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cliente = Cliente.objects.create(nome="Cliente DT", cnpj="51.111.111/0001-51")
        cls.outro = Cliente.objects.create(nome="Cliente DT 2", cnpj="52.222.222/0001-52")
        setor = Setor.objects.create(nome="S", area=Area.objects.create(nome="A", cliente=cls.cliente))
        cls.eq = Equipamento.objects.create(nome="Redutor DT", tag="RDT-1", setor=setor)

    def criterio(self, sistema="MEC_DINAMICO", cliente=None, validacao=Validacao.VALIDADA, alerta="10", critico="20",
                 fonte="Critério de demonstração (teste)"):
        return LimiteAlarmeSerie.objects.create(
            modalidade="TERMOGRAFIA", grandeza="delta_t", unidade="°C", sistema=sistema, sentido="SUPERIOR",
            valor_alerta=Decimal(alerta), valor_critico=Decimal(critico), origem=OrigemCriterio.RESPONSAVEL_TECNICO,
            fonte=fonte, validacao=validacao, cliente=cliente or self.cliente,
        )

    def classificar(self, delta, chave="TERMOGRAFIA_MECANICA"):
        return criterio_delta_t(self.cliente.pk, self.eq.pk, date(2026, 10, 1), chave, Decimal(str(delta)))

    def test_sem_criterio_fica_pendente_com_aviso(self):
        r = self.classificar(34)
        self.assertEqual(r["condicao"], "PENDENTE")
        self.assertIsNone(r["criterio"])
        self.assertEqual(r["pendencia"], PENDENCIA_DELTA)

    def test_criterio_validado_classifica_e_mostra_origem(self):
        self.criterio()
        self.assertEqual(self.classificar(34)["condicao"], "CRITICO")
        r = self.classificar(12)
        self.assertEqual(r["condicao"], "ALERTA")
        self.assertEqual(r["criterio"]["origem"], OrigemCriterio.RESPONSAVEL_TECNICO)
        self.assertEqual(r["criterio"]["fonte"], "Critério de demonstração (teste)")
        self.assertEqual(r["limites"], {"ALERTA": "10", "CRITICO": "20"})
        self.assertEqual(self.classificar(5)["condicao"], "NORMAL")

    def test_provisorio_nao_classifica(self):
        self.criterio(validacao=Validacao.PROVISORIA)
        self.assertEqual(self.classificar(34)["condicao"], "PENDENTE")

    def test_criterio_de_processo_nao_vale_para_mecanico(self):
        self.criterio(sistema="PROCESSO")
        self.assertEqual(self.classificar(34, chave="TERMOGRAFIA_MECANICA")["condicao"], "PENDENTE")
        self.assertEqual(self.classificar(34, chave="TERMO_PROCESSOS")["condicao"], "CRITICO")

    def test_criterio_de_outro_cliente_nao_vale(self):
        self.criterio(cliente=self.outro)
        self.assertEqual(self.classificar(34)["condicao"], "PENDENTE")

    def test_criterio_sem_sistema_vale_para_mecanico(self):
        self.criterio(sistema="")
        self.assertEqual(self.classificar(34, chave="TERMO_PROCESSOS")["condicao"], "CRITICO")

    def test_delta_ausente_nao_e_classificado(self):
        self.criterio()
        r = criterio_delta_t(self.cliente.pk, self.eq.pk, date(2026, 10, 1), "TERMOGRAFIA_MECANICA", None)
        self.assertEqual(r["condicao"], "PENDENTE")
        self.assertIn("não registrada", r["pendencia"])


class AjusteCatalogoTest(TestCase):
    """Comando idempotente: --dry-run não grava; a segunda execução não muda nada."""

    @classmethod
    def setUpTestData(cls):
        from apps.cadastros.models import TecnologiaAnalise
        TecnologiaAnalise.objects.create(nome="Termo SMD", sigla="TI-SMD", modulo_tecnico="TERMOGRAFIA")
        TecnologiaAnalise.objects.create(nome="Termo SME", sigla="TI-SME", modulo_tecnico="TERMOGRAFIA")
        TecnologiaAnalise.objects.create(nome="Termo PI", sigla="TI-PI", modulo_tecnico="TERMOGRAFIA")
        TecnologiaAnalise.objects.create(nome="Alinhamento eixos", sigla="ALEE",
                                         modulo_tecnico="ALINHAMENTO_EIXOS", tipo_corretiva="")

    def executar(self, *args):
        saida = StringIO()
        call_command("ajustar_catalogo_termo_alinhamento", *args, stdout=saida)
        return saida.getvalue()

    def test_dry_run_nao_grava(self):
        from apps.cadastros.models import TecnologiaAnalise
        saida = self.executar("--dry-run")
        self.assertIn("nada foi gravado", saida)
        self.assertEqual(TecnologiaAnalise.objects.get(sigla="TI-SMD").modulo_tecnico, "TERMOGRAFIA")
        self.assertFalse(TecnologiaAnalise.objects.filter(modulo_tecnico="ALINHAMENTO_POLIAS").exists())

    def test_aplica_e_e_idempotente(self):
        from apps.cadastros.models import TecnologiaAnalise
        self.executar()
        self.assertEqual(TecnologiaAnalise.objects.get(sigla="TI-SMD").modulo_tecnico, "TERMOGRAFIA_MECANICA")
        self.assertEqual(TecnologiaAnalise.objects.get(sigla="TI-SME").modulo_tecnico, "TERMOGRAFIA_MECANICA")
        self.assertEqual(TecnologiaAnalise.objects.get(sigla="TI-PI").modulo_tecnico, "TERMO_PROCESSOS")
        polias = TecnologiaAnalise.objects.get(modulo_tecnico="ALINHAMENTO_POLIAS")
        self.assertEqual(polias.sigla, "ALEP")
        self.assertEqual(polias.tipo_corretiva, TecnologiaAnalise.objects.get(sigla="ALEE").tipo_corretiva)
        self.assertIn("Catálogo já está ajustado", self.executar())
        self.assertEqual(TecnologiaAnalise.objects.filter(modulo_tecnico="ALINHAMENTO_POLIAS").count(), 1)
