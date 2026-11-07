"""Espessura (2.3.2.7): cálculos, ficha obrigatória, critério ausente → PENDENTE e isolamento.

Valores sintéticos de teste; não são limites normativos.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.cadastros.models import Area, Cliente, Componente, Equipamento, Instrumento, Setor
from apps.preditiva.models import LimiteAlarmeSerie, Validacao

from .espessura import classificar, dias_entre, perda_percentual, taxa_corrosao, validar_ficha
from .models import Inspecao, MedicaoTecnica


class CalculosEspessuraTest(TestCase):
    def test_perda_percentual_sobre_a_nominal(self):
        self.assertEqual(perda_percentual(10, 8), Decimal("20.00"))
        self.assertEqual(perda_percentual("12.5", "12.5"), Decimal("0.00"))

    def test_perda_sem_nominal_positiva_nao_divide_por_zero(self):
        self.assertIsNone(perda_percentual(0, 5))
        self.assertIsNone(perda_percentual(None, 5))
        self.assertIsNone(perda_percentual(10, None))

    def test_taxa_em_mm_por_ano(self):
        self.assertEqual(taxa_corrosao(10, 9, Decimal("365.25")), Decimal("1.0000"))
        self.assertEqual(taxa_corrosao(10, 9.5, Decimal("730.5")), Decimal("0.2500"))

    def test_taxa_negativa_indica_aumento_sinalizado_nao_corrigido(self):
        self.assertEqual(taxa_corrosao(9, 10, Decimal("365.25")), Decimal("-1.0000"))

    def test_taxa_sem_intervalo_positivo_ou_dado(self):
        self.assertIsNone(taxa_corrosao(10, 9, 0))
        self.assertIsNone(taxa_corrosao(10, 9, -5))
        self.assertIsNone(taxa_corrosao(None, 9, 100))

    def test_dias_entre_leituras_reais(self):
        a = timezone.make_aware(timezone.datetime(2026, 1, 1, 0))
        b = a + timedelta(days=2, hours=12)
        self.assertEqual(dias_entre(a, b), Decimal("2.5"))
        self.assertIsNone(dias_entre(None, b))

    def test_classificacao_so_com_limite(self):
        self.assertEqual(classificar(9, {}), "PENDENTE")
        self.assertEqual(classificar(9, {"ALERTA": 10, "CRITICO": 8}), "ALERTA")
        self.assertEqual(classificar(8, {"ALERTA": 10, "CRITICO": 8}), "CRITICO")  # fronteira inclusiva
        self.assertEqual(classificar(11, {"ALERTA": 10, "CRITICO": 8}), "NORMAL")
        self.assertEqual(classificar(None, {"ALERTA": 10}), "PENDENTE")

    def test_ficha_exige_material_e_nominal(self):
        self.assertEqual(set(validar_ficha({})), {"material", "espessura_nominal_mm"})
        self.assertEqual(validar_ficha({"material": "A36", "espessura_nominal_mm": 12.5}), {})
        self.assertIn("espessura_nominal_mm", validar_ficha({"material": "A36", "espessura_nominal_mm": 0}))


class EspessuraApiTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cliente = Cliente.objects.create(nome="Cliente Esp", cnpj="51.111.111/0001-51")
        cls.outro = Cliente.objects.create(nome="Cliente Esp 2", cnpj="52.222.222/0001-52")
        cls.tecnico = get_user_model().objects.create_user(email="esp@t.test", nome="T", perfil="TECNICO", nivel="JUNIOR")
        cls.portal_outro = get_user_model().objects.create_user(email="esp-outro@t.test", nome="O",
                                                                perfil="CLIENTE_PCM", cliente=cls.outro)
        area = Area.objects.create(nome="A", cliente=cls.cliente)
        setor = Setor.objects.create(nome="S", area=area)
        cls.eq = Equipamento.objects.create(nome="Tubulação", tag="TUB-1", setor=setor)
        cls.comp = Componente.objects.create(equipamento=cls.eq, nome="Trecho 1")
        cls.instr = Instrumento.objects.create(tipo="Ultrassom", modelo="E", numero_serie="ESP-1")
        cls.inspecao = Inspecao.objects.create(cliente=cls.cliente, tecnico=cls.tecnico, data=date(2026, 3, 1),
                                               tipo_analise="ESPESSURA")
        cls.parametros = {"material": "Aço carbono ASTM A106", "espessura_nominal_mm": "12.0", "malha": "A1"}

    def api(self, usuario=None):
        c = APIClient()
        c.force_authenticate(usuario or self.tecnico)
        return c

    def medicao(self, valor, dias=0, parametros=None, inspecao=None):
        return MedicaoTecnica.objects.create(
            inspecao=inspecao or self.inspecao, equipamento=self.eq, componente=self.comp, instrumento=self.instr,
            tipo="ESPESSURA", subtipo="ESPESSURA", ponto_medicao="Trecho 1", grandeza="Espessura", unidade="mm",
            valor=Decimal(str(valor)), parametros=parametros or self.parametros,
            data_hora=timezone.make_aware(timezone.datetime(2026, 3, 1, 12)) + timedelta(days=dias),
        )

    def test_api_recusa_ficha_sem_material(self):
        corpo = {"inspecao": self.inspecao.pk, "equipamento": self.eq.pk, "componente": self.comp.pk,
                 "instrumento": self.instr.pk, "tipo": "ESPESSURA", "subtipo": "ESPESSURA",
                 "ponto_medicao": "Trecho 1", "grandeza": "Espessura", "unidade": "mm", "valor": "11.2",
                 "parametros": {"espessura_nominal_mm": "12"}}
        r = self.api().post("/api/medicoes-tecnicas/", corpo, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("material", str(r.data))

    def test_sem_critério_fica_pendente_e_mostra_perda(self):
        m = self.medicao("10.8")
        r = self.api().get(f"/api/preditiva/espessura/{m.pk}/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["classificacao"], "PENDENTE")
        self.assertFalse(r.data["limite"]["validado"])
        self.assertEqual(r.data["perda_percentual"], "10.00")
        self.assertEqual(r.data["projecoes"], [])

    def test_criterio_validado_classifica_e_calcula_taxa(self):
        LimiteAlarmeSerie.objects.create(
            modalidade="ESPESSURA", grandeza="Espessura", unidade="mm", cliente=self.cliente,
            sentido="INFERIOR", valor_alerta=Decimal("10.0"), valor_critico=Decimal("9.0"),
            origem="RESPONSAVEL_TECNICO", fonte="QA sintético", validacao=Validacao.VALIDADA,
        )
        self.medicao("11.0", dias=0)
        atual = self.medicao("10.0", dias=365.25)  # um ano juliano exato
        r = self.api().get(f"/api/preditiva/espessura/{atual.pk}/")
        self.assertEqual(r.data["classificacao"], "ALERTA")
        self.assertEqual(r.data["taxa_corrosao_mm_ano"], "1.0000")
        self.assertEqual(r.data["anterior"]["valor"], "11.0")

    def test_leituras_de_parametros_diferentes_nao_comparam(self):
        self.medicao("11.0", dias=0, parametros={**self.parametros, "malha": "B9"})
        atual = self.medicao("10.0", dias=365)
        r = self.api().get(f"/api/preditiva/espessura/{atual.pk}/")
        self.assertIsNone(r.data["anterior"])
        self.assertIsNone(r.data["taxa_corrosao_mm_ano"])

    def test_outro_cliente_nao_ve_a_medicao(self):
        m = self.medicao("10.0")
        self.assertEqual(self.api(self.portal_outro).get(f"/api/preditiva/espessura/{m.pk}/").status_code, 404)
