"""Termografia de sistemas mecânicos e de processos (2.3.2.2.2–4): registro dos módulos, ΔT e condição pendente.

Valores sintéticos de teste; não são limites de temperatura.
"""
from datetime import date
from decimal import Decimal

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.cadastros.models import Area, Cliente, Equipamento, Instrumento, Setor, TecnologiaAnalise

from .models import Inspecao, MedicaoTermografia
from .relatorio_tecnico.modulos import ModuloNaoImplementado, modulo_da_tecnologia
from .relatorio_tecnico.termografia_sistemas import MODULO_TERMO_PROCESSOS, MODULO_TERMOGRAFIA_MECANICA


class RegistroTest(SimpleTestCase):
    def test_mecanica_e_processos_resolvem_modulo(self):
        self.assertIs(modulo_da_tecnologia(TecnologiaAnalise(nome="TM", modulo_tecnico="TERMOGRAFIA_MECANICA")),
                      MODULO_TERMOGRAFIA_MECANICA)
        self.assertIs(modulo_da_tecnologia(TecnologiaAnalise(nome="TP", modulo_tecnico="TERMO_PROCESSOS")),
                      MODULO_TERMO_PROCESSOS)

    def test_ensaio_eletrico_tc_continua_planejado(self):
        with self.assertRaises(ModuloNaoImplementado):
            modulo_da_tecnologia(TecnologiaAnalise(nome="TC", modulo_tecnico="ENSAIO_ELETRICO_TC"))

    def test_modulos_sem_bloco_eletrico(self):
        for modulo in (MODULO_TERMOGRAFIA_MECANICA, MODULO_TERMO_PROCESSOS):
            self.assertEqual(modulo.tabelas_normativas, ())
            self.assertEqual(modulo.medias[0].chave, "temperatura")


class DeltaESemDiagnosticoTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cliente = Cliente.objects.create(nome="Cliente TS", cnpj="10.111.111/0001-10")
        from django.contrib.auth import get_user_model
        cls.tec = get_user_model().objects.create_user(email="ts@t.test", nome="T", perfil="TECNICO", nivel="JUNIOR")
        area = Area.objects.create(nome="A", cliente=cls.cliente)
        setor = Setor.objects.create(nome="S", area=area)
        cls.eq = Equipamento.objects.create(nome="Redutor", tag="RED-1", setor=setor)
        cls.instr = Instrumento.objects.create(tipo="Termovisor", modelo="T", numero_serie="TS-1")

    def medicao(self, sistema, ponto, tp, tr):
        inspecao = Inspecao.objects.create(cliente=self.cliente, tecnico=self.tec, data=date(2026, 9, 1),
                                           tipo_analise="TERMOGRAFIA")
        return MedicaoTermografia.objects.create(
            inspecao=inspecao, equipamento=self.eq, instrumento=self.instr, ponto_medicao=ponto, sistema=sistema,
            temperatura_ponto=Decimal(str(tp)), temperatura_referencia=Decimal(str(tr)),
            data_hora=timezone.make_aware(timezone.datetime(2026, 9, 1, 9)),
        )

    def test_processo_calcula_delta_e_fica_pendente(self):
        m = self.medicao("PROCESSO", "Forno", 180, 150)
        self.assertEqual(m.delta_t, Decimal("30.0"))
        self.assertEqual(m.criticidade, "")
        self.assertEqual(m.classificacao_status, "PENDENTE")

    def test_mecanico_dinamico_nao_classifica_por_limite_generico(self):
        m = self.medicao("MEC_DINAMICO", "Mancal LA", 70, 40)
        self.assertEqual(m.delta_t, Decimal("30.0"))
        self.assertEqual(m.classificacao_status, "PENDENTE")
        self.assertEqual(m.criticidade, "")
