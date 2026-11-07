"""Resistência de isolação de motores (2.3.2.5.1.1): índices, ficha, critério ausente → PENDENTE, API e isolamento.

Valores sintéticos de teste; não são limites normativos.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.cadastros.models import Area, Cliente, Equipamento, Instrumento, Setor, TecnologiaAnalise
from apps.preditiva.models import LimiteAlarmeSerie, Validacao

from .models import Inspecao, MedicaoTecnica
from .motor_rxi import classificar_indice, indices, pior_condicao, validar_ficha
from .relatorio_tecnico.modulos import modulo_da_tecnologia
from .relatorio_tecnico.motor_rxi import MODULO_MOTOR_RXI, ultimo_motor_rxi


class IndicesMotorTest(SimpleTestCase):
    def test_dar_e_ip_por_razao(self):
        dar, ip = indices(100, 150, 300)
        self.assertEqual(dar, Decimal("1.50"))
        self.assertEqual(ip, Decimal("2.00"))

    def test_divisor_zero_ou_leitura_faltando_nao_inventa(self):
        self.assertEqual(indices(0, 150, 300), (None, Decimal("2.00")))
        self.assertEqual(indices(100, 0, 300), (Decimal("0.00"), None))
        self.assertEqual(indices(100, 150, None), (Decimal("1.50"), None))

    def test_classificacao_com_sentido_inferior(self):
        limites = {"ALERTA": Decimal("2"), "CRITICO": Decimal("1.5")}
        self.assertEqual(classificar_indice(1.4, limites), "CRITICO")
        self.assertEqual(classificar_indice(1.8, limites), "ALERTA")
        self.assertEqual(classificar_indice(2.5, limites), "NORMAL")
        self.assertEqual(classificar_indice(2.5, {}), "PENDENTE")
        self.assertEqual(classificar_indice(None, limites), "PENDENTE")

    def test_pior_condicao_fica_pendente_se_algum_indice_sem_criterio(self):
        self.assertEqual(pior_condicao(["NORMAL", "PENDENTE"]), "PENDENTE")
        self.assertEqual(pior_condicao(["NORMAL", "ALERTA"]), "ALERTA")

    def test_ficha_exige_tempo_tensao_e_temperatura(self):
        erros = validar_ficha({})
        self.assertEqual(set(erros), {"tempo_leitura_s", "tensao_ensaio_v", "temperatura_c"})
        self.assertIn("tempo_leitura_s", validar_ficha({"tempo_leitura_s": 45, "tensao_ensaio_v": 500, "temperatura_c": 25}))
        self.assertEqual(validar_ficha({"tempo_leitura_s": "60", "tensao_ensaio_v": "500", "temperatura_c": "25.5"}), {})
        self.assertIn("umidade_pct", validar_ficha({"tempo_leitura_s": 60, "tensao_ensaio_v": 500,
                                                    "temperatura_c": 25, "umidade_pct": 120}))


class MotorRxiApiTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cliente = Cliente.objects.create(nome="Cliente Motor", cnpj="71.111.111/0001-71")
        cls.outro = Cliente.objects.create(nome="Cliente Motor 2", cnpj="72.222.222/0001-72")
        cls.tec = get_user_model().objects.create_user(email="motor@t.test", nome="T", perfil="TECNICO", nivel="JUNIOR")
        cls.portal_outro = get_user_model().objects.create_user(email="motor-outro@t.test", nome="O",
                                                                perfil="CLIENTE_PCM", cliente=cls.outro)
        area = Area.objects.create(nome="A", cliente=cls.cliente)
        setor = Setor.objects.create(nome="S", area=area)
        cls.eq = Equipamento.objects.create(nome="Motor 1", tag="MOT-1", setor=setor)
        cls.instr = Instrumento.objects.create(tipo="Megôhmetro", modelo="M", numero_serie="MOT-1")
        cls.insp = Inspecao.objects.create(cliente=cls.cliente, tecnico=cls.tec, data=date(2026, 6, 1),
                                           tipo_analise="ENSAIO_ELETRICO")
        cls.base = timezone.make_aware(timezone.datetime(2026, 6, 1, 10))

    def api(self, usuario=None):
        c = APIClient()
        c.force_authenticate(usuario or self.tec)
        return c

    def leitura(self, tempo, valor, **extra):
        parametros = {"tempo_leitura_s": tempo, "tensao_ensaio_v": 500, "temperatura_c": 25, **extra}
        return MedicaoTecnica.objects.create(
            inspecao=self.insp, equipamento=self.eq, instrumento=self.instr, tipo="ENSAIO_ELETRICO",
            subtipo="MOTOR_RI", ponto_medicao="Enrolamento", grandeza="Resistência de isolação", unidade="MΩ",
            valor=Decimal(str(valor)), parametros=parametros, data_hora=self.base + timedelta(seconds=tempo),
        )

    def grupo(self):
        return [self.leitura(30, 100), self.leitura(60, 150), self.leitura(600, 300)]

    def criterio_ip(self, alerta="2", critico="1.5", validado=True):
        return LimiteAlarmeSerie.objects.create(
            modalidade="ENSAIO_ELETRICO", grandeza="IP", unidade="", cliente=self.cliente, sentido="INFERIOR",
            valor_alerta=Decimal(alerta), valor_critico=Decimal(critico), origem="RESPONSAVEL_TECNICO",
            fonte="QA sintético", validacao=Validacao.VALIDADA if validado else Validacao.PROVISORIA,
        )

    def test_api_recusa_ficha_sem_tensao(self):
        corpo = {"inspecao": self.insp.pk, "equipamento": self.eq.pk, "instrumento": self.instr.pk,
                 "tipo": "ENSAIO_ELETRICO", "subtipo": "MOTOR_RI", "ponto_medicao": "Enrolamento",
                 "grandeza": "Resistência de isolação", "unidade": "MΩ", "valor": "100",
                 "parametros": {"tempo_leitura_s": 30, "temperatura_c": 25}}
        r = self.api().post("/api/medicoes-tecnicas/", corpo, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("tensao_ensaio_v", str(r.data))

    def test_sem_criterio_validado_ip_fica_pendente(self):
        self.criterio_ip(validado=False)
        leitura = self.grupo()[1]
        r = self.api().get(f"/api/preditiva/motor-rxi/{leitura.pk}/")
        self.assertEqual(r.data["DAR"], "1.50")
        self.assertEqual(r.data["IP"], "2.00")
        self.assertEqual(r.data["condicao_IP"], "PENDENTE")
        self.assertEqual(r.data["condicao"], "PENDENTE")

    def test_criterio_validado_classifica_ip(self):
        self.criterio_ip(alerta="2.5", critico="1.5")
        leitura = self.grupo()[0]
        r = self.api().get(f"/api/preditiva/motor-rxi/{leitura.pk}/")
        self.assertEqual(r.data["IP"], "2.00")
        self.assertEqual(r.data["condicao_IP"], "ALERTA")  # 1.5 < 2.00 <= 2.5 → ALERTA (sentido inferior)

    def test_grupos_de_tensao_diferente_nao_se_misturam(self):
        self.criterio_ip()
        a = self.grupo()
        self.leitura(600, 999, tensao_ensaio_v=1000)  # outro grupo, sem R30/R60
        r = self.api().get(f"/api/preditiva/motor-rxi/{a[2].pk}/")
        self.assertEqual(r.data["IP"], "2.00")

    def test_outro_cliente_nao_ve_o_ensaio(self):
        leitura = self.leitura(30, 100)
        self.assertEqual(self.api(self.portal_outro).get(f"/api/preditiva/motor-rxi/{leitura.pk}/").status_code, 404)

    def test_modulo_motor_resolve_e_relatorio_le_o_ultimo_grupo(self):
        modulo = modulo_da_tecnologia(TecnologiaAnalise(nome="Motor QA", modulo_tecnico="MOTOR_RXI"))
        self.assertIs(modulo, MODULO_MOTOR_RXI)
        self.grupo()
        r = ultimo_motor_rxi(self.cliente.pk, self.eq.pk, date(2026, 12, 31))
        self.assertEqual((Decimal(r["R30"]), Decimal(r["R60"]), Decimal(r["R600"])),
                         (Decimal("100"), Decimal("150"), Decimal("300")))
        self.assertIsNone(ultimo_motor_rxi(self.outro.pk, self.eq.pk, None))
