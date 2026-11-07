"""Ultrassom elétrico e mecânico (2.3.2.6): ficha, classificação superior, grandeza por subtipo,
critério ausente → PENDENTE, API, isolamento e registro do módulo de relatório.

Valores sintéticos de teste; não são limites normativos.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.cadastros.models import Area, Cliente, Componente, Equipamento, Instrumento, Setor, TecnologiaAnalise
from apps.preditiva.models import LimiteAlarmeSerie, Validacao

from .models import Inspecao, MedicaoTecnica
from .relatorio_tecnico.modulos import modulo_da_tecnologia
from .relatorio_tecnico.ultrassom import MODULO_ULTRASSOM, ultimo_ultrassom
from .ultrassom import GRANDEZA_POR_SUBTIPO, classificar_superior, validar_ficha


class FichaEClassificacaoTest(SimpleTestCase):
    def test_ficha_exige_ganho_e_distancia(self):
        erros = validar_ficha({})
        self.assertEqual(set(erros), {"ganho_db", "distancia_cm"})
        self.assertEqual(validar_ficha({"ganho_db": "40", "distancia_cm": "0"}), {})
        self.assertIn("distancia_cm", validar_ficha({"ganho_db": 40, "distancia_cm": -1}))
        self.assertIn("frequencia_khz", validar_ficha({"ganho_db": 40, "distancia_cm": 30, "frequencia_khz": 0}))

    def test_classificacao_com_sentido_superior(self):
        limites = {"ALERTA": Decimal("50"), "CRITICO": Decimal("70")}
        self.assertEqual(classificar_superior(75, limites), "CRITICO")
        self.assertEqual(classificar_superior(55, limites), "ALERTA")
        self.assertEqual(classificar_superior(40, limites), "NORMAL")
        self.assertEqual(classificar_superior(40, {}), "PENDENTE")
        self.assertEqual(classificar_superior(None, limites), "PENDENTE")

    def test_grandeza_separa_eletrico_de_mecanico(self):
        self.assertNotEqual(GRANDEZA_POR_SUBTIPO["ELETRICO"], GRANDEZA_POR_SUBTIPO["MECANICO"])


class UltrassomApiTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cliente = Cliente.objects.create(nome="Cliente US", cnpj="81.111.111/0001-81")
        cls.outro = Cliente.objects.create(nome="Cliente US 2", cnpj="82.222.222/0001-82")
        cls.tec = get_user_model().objects.create_user(email="us@t.test", nome="T", perfil="TECNICO", nivel="JUNIOR")
        cls.portal_outro = get_user_model().objects.create_user(email="us-outro@t.test", nome="O",
                                                                perfil="CLIENTE_PCM", cliente=cls.outro)
        area = Area.objects.create(nome="A", cliente=cls.cliente)
        setor = Setor.objects.create(nome="S", area=area)
        cls.eq = Equipamento.objects.create(nome="Quadro", tag="QDR-1", setor=setor)
        cls.comp = Componente.objects.create(equipamento=cls.eq, nome="Painel")
        cls.instr = Instrumento.objects.create(tipo="Ultrassom", modelo="U", numero_serie="US-1")
        cls.insp = Inspecao.objects.create(cliente=cls.cliente, tecnico=cls.tec, data=date(2026, 7, 1),
                                           tipo_analise="ULTRASSOM")
        cls.base = timezone.make_aware(timezone.datetime(2026, 7, 1, 10))

    def api(self, usuario=None):
        c = APIClient()
        c.force_authenticate(usuario or self.tec)
        return c

    def leitura(self, valor, subtipo="ELETRICO", grandeza="Nível de ultrassom elétrico", **extra):
        parametros = {"ganho_db": 40, "distancia_cm": 30, **extra}
        return MedicaoTecnica.objects.create(
            inspecao=self.insp, equipamento=self.eq, componente=self.comp, instrumento=self.instr,
            tipo="ULTRASSOM", subtipo=subtipo, ponto_medicao="Painel", grandeza=grandeza, unidade="dB",
            valor=Decimal(str(valor)), parametros=parametros, data_hora=self.base,
        )

    def criterio(self, alerta="50", critico="70", grandeza="Nível de ultrassom elétrico"):
        return LimiteAlarmeSerie.objects.create(
            modalidade="ULTRASSOM", grandeza=grandeza, unidade="dB", cliente=self.cliente, sentido="SUPERIOR",
            valor_alerta=Decimal(alerta), valor_critico=Decimal(critico), origem="RESPONSAVEL_TECNICO",
            fonte="QA sintético", validacao=Validacao.VALIDADA,
        )

    def test_api_recusa_ficha_sem_ganho(self):
        corpo = {"inspecao": self.insp.pk, "equipamento": self.eq.pk, "componente": self.comp.pk,
                 "instrumento": self.instr.pk, "tipo": "ULTRASSOM", "subtipo": "ELETRICO",
                 "ponto_medicao": "Painel", "grandeza": "Nível de ultrassom elétrico", "unidade": "dB",
                 "valor": "55", "parametros": {"distancia_cm": 30}}
        r = self.api().post("/api/medicoes-tecnicas/", corpo, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("ganho_db", str(r.data))

    def test_api_recusa_grandeza_de_outro_subtipo(self):
        corpo = {"inspecao": self.insp.pk, "equipamento": self.eq.pk, "instrumento": self.instr.pk,
                 "tipo": "ULTRASSOM", "subtipo": "MECANICO", "ponto_medicao": "Mancal",
                 "grandeza": "Nível de ultrassom elétrico", "unidade": "dB", "valor": "55",
                 "parametros": {"ganho_db": 40, "distancia_cm": 30}}
        r = self.api().post("/api/medicoes-tecnicas/", corpo, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("grandeza", str(r.data))

    def test_sem_criterio_validado_fica_pendente(self):
        leitura = self.leitura(75)
        r = self.api().get(f"/api/preditiva/ultrassom/{leitura.pk}/")
        self.assertEqual(r.data["classificacao"], "PENDENTE")
        self.assertFalse(r.data["limite"]["validado"])

    def test_criterio_validado_classifica_em_sentido_superior(self):
        self.criterio()
        leitura = self.leitura(55)
        r = self.api().get(f"/api/preditiva/ultrassom/{leitura.pk}/")
        self.assertEqual(r.data["classificacao"], "ALERTA")

    def test_criterio_de_eletrico_nao_vale_para_mecanico(self):
        self.criterio()  # só para a grandeza elétrica
        mecanico = self.leitura(75, subtipo="MECANICO", grandeza="Nível de ultrassom mecânico")
        r = self.api().get(f"/api/preditiva/ultrassom/{mecanico.pk}/")
        self.assertEqual(r.data["classificacao"], "PENDENTE")

    def test_outro_cliente_nao_ve_a_leitura(self):
        leitura = self.leitura(55)
        self.assertEqual(self.api(self.portal_outro).get(f"/api/preditiva/ultrassom/{leitura.pk}/").status_code, 404)

    def test_modulo_resolve_e_relatorio_le_a_ultima_leitura(self):
        modulo = modulo_da_tecnologia(TecnologiaAnalise(nome="US QA", modulo_tecnico="ULTRASSOM"))
        self.assertIs(modulo, MODULO_ULTRASSOM)
        self.leitura(55)
        r = ultimo_ultrassom(self.cliente.pk, self.eq.pk, date(2026, 12, 31))
        self.assertEqual(r["condicao"], "PENDENTE")
        self.assertEqual(r["ganho_db"], "40")
        self.assertIsNone(ultimo_ultrassom(self.outro.pk, self.eq.pk, None))
