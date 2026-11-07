"""Classificação de ΔT pelo critério validado do sistema termográfico (2.3.2.2).

Limites sintéticos de teste; não são faixas de ΔT normativas.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.cadastros.models import Area, Cliente, Equipamento, Instrumento, Setor
from apps.preditiva.models import LimiteAlarmeSerie, Validacao

from .analise_preditiva import replay_medicao
from .models import Inspecao, MedicaoTermografia
from .rules import classificar_termografia


class ClassificarTermografiaFuncaoTest(TestCase):
    def test_sem_limites_fica_pendente(self):
        r = classificar_termografia(Decimal("35"), Decimal("20"))
        self.assertEqual(r.criticidade, "")
        self.assertIn("pendente", r.diagnostico)

    def test_com_limites_classifica_em_sentido_superior(self):
        limites = {"ALERTA": Decimal("10"), "CRITICO": Decimal("20")}
        self.assertEqual(classificar_termografia(Decimal("35"), Decimal("20"), limites).criticidade, "ALERTA")
        self.assertEqual(classificar_termografia(Decimal("45"), Decimal("20"), limites).criticidade, "CRITICO")
        self.assertEqual(classificar_termografia(Decimal("22"), Decimal("20"), limites).criticidade, "NORMAL")


class TermografiaCriterioTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cliente = Cliente.objects.create(nome="Cliente TC", cnpj="21.111.111/0001-12")
        cls.tec = get_user_model().objects.create_user(email="tc@t.test", nome="T", perfil="TECNICO", nivel="JUNIOR")
        cls.portal_outro = get_user_model().objects.create_user(
            email="tc-outro@t.test", nome="O", perfil="CLIENTE_PCM",
            cliente=Cliente.objects.create(nome="Outro TC", cnpj="22.222.222/0001-22"))
        area = Area.objects.create(nome="A", cliente=cls.cliente)
        setor = Setor.objects.create(nome="S", area=area)
        cls.eq = Equipamento.objects.create(nome="Redutor TC", tag="RTC-1", setor=setor)
        cls.instr = Instrumento.objects.create(tipo="Termovisor", modelo="T", numero_serie="TC-1")
        cls.base = timezone.make_aware(timezone.datetime(2026, 9, 1, 9))

    def medicao(self, sistema, delta, ponto="Mancal"):
        inspecao = Inspecao.objects.create(cliente=self.cliente, tecnico=self.tec, data=date(2026, 9, 1),
                                           tipo_analise="TERMOGRAFIA")
        return MedicaoTermografia.objects.create(
            inspecao=inspecao, equipamento=self.eq, instrumento=self.instr, ponto_medicao=ponto, sistema=sistema,
            temperatura_ponto=Decimal("20") + Decimal(str(delta)), temperatura_referencia=Decimal("20"),
            data_hora=self.base,
        )

    def criterio(self, sistema="", alerta="10", critico="20", sentido="SUPERIOR",
                 validacao=Validacao.VALIDADA, cliente=None):
        return LimiteAlarmeSerie.objects.create(
            modalidade="TERMOGRAFIA", grandeza="delta_t", unidade="°C", sistema=sistema, sentido=sentido,
            cliente=cliente if cliente is not None else self.cliente,
            valor_alerta=Decimal(alerta), valor_critico=Decimal(critico), origem="RESPONSAVEL_TECNICO",
            fonte="QA sintético", validacao=validacao,
        )

    def test_sem_criterio_continua_pendente_com_motor_anterior(self):
        m = self.medicao("ELETRICO", 15)
        self.assertEqual((m.criticidade, m.classificacao_status), ("", "PENDENTE"))
        self.assertEqual(m.criterio_aplicado["motor"], "termografia_delta_v2")

    def test_criterio_validado_classifica_e_congela_limites(self):
        self.criterio()
        m = self.medicao("ELETRICO", 15)
        self.assertEqual((m.criticidade, m.classificacao_status), ("ALERTA", "CLASSIFICADA"))
        self.assertEqual(m.criterio_aplicado["motor"], "termografia_criterio_v1")
        self.assertEqual(m.criterio_aplicado["limites_congelados"], {"ALERTA": "10.0000", "CRITICO": "20.0000"})

    def test_criterio_especifico_do_sistema_so_vale_para_o_sistema(self):
        self.criterio(sistema="MEC_DINAMICO", alerta="5", critico="8")
        self.assertEqual(self.medicao("MEC_DINAMICO", 15).criticidade, "CRITICO")
        self.assertEqual(self.medicao("ELETRICO", 15).classificacao_status, "PENDENTE")

    def test_especifico_do_sistema_prevalece_sobre_o_generico(self):
        self.criterio(sistema="", alerta="10", critico="20")
        self.criterio(sistema="PROCESSO", alerta="3", critico="6")
        self.assertEqual(self.medicao("PROCESSO", 15).criticidade, "CRITICO")
        self.assertEqual(self.medicao("ELETRICO", 15).criticidade, "ALERTA")

    def test_criterio_inferior_ou_nao_validado_nao_classifica(self):
        self.criterio(sentido="INFERIOR")
        self.assertEqual(self.medicao("ELETRICO", 15).classificacao_status, "PENDENTE")
        LimiteAlarmeSerie.objects.all().delete()
        self.criterio(validacao=Validacao.PROVISORIA)
        self.assertEqual(self.medicao("ELETRICO", 15).classificacao_status, "PENDENTE")

    def test_snapshot_reexecuta_com_limites_congelados(self):
        self.criterio()
        m = self.medicao("ELETRICO", 15)
        LimiteAlarmeSerie.objects.all().update(valor_alerta=Decimal("50"), valor_critico=Decimal("80"))
        replay = replay_medicao(m.criterio_aplicado)
        self.assertEqual(replay["criticidade"], "ALERTA")

    def test_alterar_o_cadastro_nao_reclassifica_medicao_ja_gravada(self):
        self.criterio()
        m = self.medicao("ELETRICO", 15)
        LimiteAlarmeSerie.objects.all().update(valor_alerta=Decimal("50"), valor_critico=Decimal("80"))
        m.refresh_from_db()
        self.assertEqual(m.criticidade, "ALERTA")

    def test_api_mostra_criticidade_do_criterio_e_respeita_tenant(self):
        self.criterio()
        m = self.medicao("ELETRICO", 25)
        api = APIClient()
        api.force_authenticate(self.tec)
        self.assertEqual(api.get(f"/api/medicoes-termografia/{m.pk}/").data["criticidade"], "CRITICO")
        api.force_authenticate(self.portal_outro)
        self.assertEqual(api.get(f"/api/medicoes-termografia/{m.pk}/").status_code, 404)
