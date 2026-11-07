"""Alinhamento a laser (2.3.2.8.1.1–2): ficha, redução, tolerância ausente → PENDENTE, par antes/depois, isolamento.

Valores sintéticos de teste; não são tolerâncias de fabricante nem normativas.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.cadastros.models import Area, Cliente, Equipamento, Instrumento, Setor, TecnologiaAnalise
from apps.preditiva.models import LimiteAlarmeSerie, Validacao

from .alinhamento import reducao_percentual, validar_ficha
from .models import Inspecao, MedicaoTecnica
from .relatorio_tecnico.alinhamento import MODULO_ALINHAMENTO_EIXOS, MODULO_ALINHAMENTO_POLIAS, ultimo_alinhamento
from .relatorio_tecnico.modulos import ModuloNaoImplementado, modulo_da_tecnologia


def ficha(fase, ang_v, ang_h, par_v=0.05, par_h=0.02, **extra):
    return {"fase": fase, "vertical_paralelo_mm": par_v, "vertical_angular_mm_100mm": ang_v,
            "horizontal_paralelo_mm": par_h, "horizontal_angular_mm_100mm": ang_h, "rpm": 1800, **extra}


class FichaEReducaoTest(SimpleTestCase):
    def test_valor_deve_ser_maior_angular_dos_dois_planos(self):
        erros = validar_ficha(ficha("depois", -0.10, 0.04), Decimal("0.05"))
        self.assertIn("valor", erros)
        self.assertEqual(validar_ficha(ficha("depois", -0.10, 0.04), Decimal("0.10")), {})

    def test_campos_obrigatorios(self):
        erros = validar_ficha({}, Decimal("1"))
        self.assertEqual(set(erros), {"fase", "vertical_paralelo_mm", "vertical_angular_mm_100mm",
                                      "horizontal_paralelo_mm", "horizontal_angular_mm_100mm", "rpm"})

    def test_reducao_aritmetica(self):
        self.assertEqual(reducao_percentual(Decimal("0.40"), Decimal("0.10")), Decimal("75.0"))
        self.assertIsNone(reducao_percentual(0, Decimal("0.10")))
        self.assertIsNone(reducao_percentual(Decimal("0.40"), None))


class AlinhamentoApiTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cliente = Cliente.objects.create(nome="Cliente AL", cnpj="11.111.111/0001-11")
        cls.outro = Cliente.objects.create(nome="Cliente AL 2", cnpj="12.222.222/0001-12")
        cls.tec = get_user_model().objects.create_user(email="al@t.test", nome="T", perfil="TECNICO", nivel="JUNIOR")
        cls.portal_outro = get_user_model().objects.create_user(email="al-outro@t.test", nome="O",
                                                                perfil="CLIENTE_PCM", cliente=cls.outro)
        area = Area.objects.create(nome="A", cliente=cls.cliente)
        setor = Setor.objects.create(nome="S", area=area)
        cls.eq = Equipamento.objects.create(nome="Bomba AL", tag="BAL-1", setor=setor)
        cls.instr = Instrumento.objects.create(tipo="Laser", modelo="L", numero_serie="AL-1")
        cls.insp = Inspecao.objects.create(cliente=cls.cliente, tecnico=cls.tec, data=date(2026, 10, 1),
                                           tipo_analise="CORRETIVA")
        cls.base = timezone.make_aware(timezone.datetime(2026, 10, 1, 9))

    def api(self, usuario=None):
        c = APIClient()
        c.force_authenticate(usuario or self.tec)
        return c

    def registro(self, parametros, valor, subtipo="ALINHAMENTO_EIXOS", minutos=0):
        return MedicaoTecnica.objects.create(
            inspecao=self.insp, equipamento=self.eq, componente=None, instrumento=self.instr,
            tipo="CORRETIVA", subtipo=subtipo, ponto_medicao="Acoplamento", grandeza="Desalinhamento angular",
            unidade="mm/100mm", valor=Decimal(str(valor)), parametros=parametros,
            data_hora=self.base + timedelta(minutes=minutos),
        )

    def criterio(self, grandeza, unidade, alerta, critico):
        return LimiteAlarmeSerie.objects.create(
            modalidade="CORRETIVA", grandeza=grandeza, unidade=unidade, cliente=self.cliente, sentido="SUPERIOR",
            valor_alerta=Decimal(alerta), valor_critico=Decimal(critico), origem="RESPONSAVEL_TECNICO",
            fonte="QA sintético (faixa de rpm 1800)", validacao=Validacao.VALIDADA,
        )

    def test_api_recusa_valor_que_nao_bate_com_os_planos(self):
        corpo = {"inspecao": self.insp.pk, "equipamento": self.eq.pk, "instrumento": self.instr.pk,
                 "tipo": "CORRETIVA", "subtipo": "ALINHAMENTO_EIXOS", "ponto_medicao": "Acoplamento",
                 "grandeza": "Desalinhamento angular", "unidade": "mm/100mm", "valor": "0.01",
                 "parametros": ficha("antes", 0.30, 0.10)}
        r = self.api().post("/api/medicoes-tecnicas/", corpo, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("valor", str(r.data))

    def test_sem_tolerancia_validada_fica_pendente(self):
        antes = self.registro(ficha("antes", 0.40, 0.10), 0.40, minutos=0)
        depois = self.registro(ficha("depois", 0.10, 0.05), 0.10, minutos=60)
        r = self.api().get(f"/api/preditiva/alinhamento/{depois.pk}/")
        self.assertEqual(r.data["condicao"], "PENDENTE")
        self.assertEqual(r.data["reducao_angular_pct"], "75.0")
        self.assertEqual(r.data["antes"]["medicao_id"], antes.pk)

    def test_tolerancia_validada_classifica_o_depois(self):
        self.criterio("Desalinhamento angular", "mm/100mm", "0.08", "0.20")
        self.criterio("Desalinhamento paralelo", "mm", "0.10", "0.20")
        self.registro(ficha("antes", 0.40, 0.10), 0.40, minutos=0)
        depois = self.registro(ficha("depois", 0.15, 0.05, par_v=0.04, par_h=0.02), 0.15, minutos=60)
        r = self.api().get(f"/api/preditiva/alinhamento/{depois.pk}/")
        self.assertEqual(r.data["condicao_angular"], "ALERTA")  # 0.08 < 0.15 <= 0.20 → ALERTA
        self.assertEqual(r.data["condicao_paralelo"], "NORMAL")
        self.assertEqual(r.data["condicao"], "ALERTA")

    def test_outro_cliente_nao_ve_o_registro(self):
        depois = self.registro(ficha("depois", 0.10, 0.05), 0.10)
        self.assertEqual(self.api(self.portal_outro).get(f"/api/preditiva/alinhamento/{depois.pk}/").status_code, 404)

    def test_modulos_resolvem_e_relatorio_une_antes_e_depois(self):
        self.assertIs(modulo_da_tecnologia(TecnologiaAnalise(nome="AE", modulo_tecnico="ALINHAMENTO_EIXOS")),
                      MODULO_ALINHAMENTO_EIXOS)
        self.assertIs(modulo_da_tecnologia(TecnologiaAnalise(nome="AP", modulo_tecnico="ALINHAMENTO_POLIAS")),
                      MODULO_ALINHAMENTO_POLIAS)
        with self.assertRaises(ModuloNaoImplementado):
            modulo_da_tecnologia(TecnologiaAnalise(nome="ENS", modulo_tecnico="ENSAIO_ELETRICO_TC"))
        self.registro(ficha("antes", 0.40, 0.10), 0.40, minutos=0)
        self.registro(ficha("depois", 0.10, 0.05), 0.10, minutos=60)
        r = ultimo_alinhamento(self.cliente.pk, self.eq.pk, date(2026, 12, 31), "ALINHAMENTO_EIXOS")
        self.assertEqual(Decimal(r["depois"]["angular_mm_100mm"]), Decimal("0.10"))
        self.assertIsNone(ultimo_alinhamento(self.outro.pk, self.eq.pk, None, "ALINHAMENTO_EIXOS"))
