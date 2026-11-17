"""Alinhamento no relatório: origem do critério, pendências e cadastro do critério pela API (Master).

Valores sintéticos de teste; não são tolerâncias de fabricante nem normativas.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.cadastros.models import Area, Cliente, Equipamento, Instrumento, Setor
from apps.preditiva.models import LimiteAlarmeSerie, Validacao

from .models import Inspecao, MedicaoTecnica
from .relatorio_tecnico.alinhamento import ultimo_alinhamento


class AlinhamentoCriterioNoRelatorioTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cliente = Cliente.objects.create(nome="Cliente CR", cnpj="41.111.111/0001-41")
        cls.outro = Cliente.objects.create(nome="Cliente CR 2", cnpj="42.222.222/0001-42")
        cls.master = get_user_model().objects.create_user(email="cr-master@t.test", nome="M", perfil="TECNICO",
                                                          nivel="MASTER")
        cls.tec = get_user_model().objects.create_user(email="cr-tec@t.test", nome="T", perfil="TECNICO",
                                                       nivel="JUNIOR")
        setor = Setor.objects.create(nome="S", area=Area.objects.create(nome="A", cliente=cls.cliente))
        cls.eq = Equipamento.objects.create(nome="Motor CR", tag="MCR-1", setor=setor)
        cls.instr = Instrumento.objects.create(tipo="Laser", modelo="L", numero_serie="CR-1")
        cls.insp = Inspecao.objects.create(cliente=cls.cliente, tecnico=cls.tec, data=date(2026, 10, 1),
                                           tipo_analise="CORRETIVA")
        cls.base = timezone.make_aware(timezone.datetime(2026, 10, 1, 9))

    def registro(self, fase, ang, par, minutos):
        parametros = {"fase": fase, "vertical_paralelo_mm": par, "vertical_angular_mm_100mm": ang,
                      "horizontal_paralelo_mm": par, "horizontal_angular_mm_100mm": ang, "rpm": 1800}
        return MedicaoTecnica.objects.create(
            inspecao=self.insp, equipamento=self.eq, instrumento=self.instr, tipo="CORRETIVA",
            subtipo="ALINHAMENTO_EIXOS", ponto_medicao="Acoplamento", grandeza="Desalinhamento angular",
            unidade="mm/100mm", valor=Decimal(str(ang)), parametros=parametros,
            data_hora=self.base + timedelta(minutes=minutos),
        )

    def par(self):
        self.registro("antes", "0.40", "0.10", 0)
        self.registro("depois", "0.04", "0.03", 60)

    def criterio(self, grandeza, unidade, alerta, critico, cliente=None, validacao=Validacao.VALIDADA,
                 fonte="Acordo de demonstração (teste)"):
        return LimiteAlarmeSerie.objects.create(
            modalidade="CORRETIVA", grandeza=grandeza, unidade=unidade, cliente=cliente or self.cliente,
            sentido="SUPERIOR", valor_alerta=Decimal(alerta), valor_critico=Decimal(critico),
            origem="ACORDO_CLIENTE", fonte=fonte, validacao=validacao,
        )

    def test_sem_criterio_fica_pendente_e_diz_o_que_falta(self):
        self.par()
        r = ultimo_alinhamento(self.cliente.pk, self.eq.pk, None, "ALINHAMENTO_EIXOS")
        self.assertEqual(r["condicao"], "PENDENTE")
        self.assertFalse(r["criterio_validado"])
        self.assertIsNone(r["criterio"]["angular"])
        self.assertEqual(len(r["pendencias"]), 2)
        self.assertIn("angular", r["pendencias"][0])
        self.assertIn("paralelo", r["pendencias"][1])

    def test_criterio_validado_sai_com_origem_e_fonte(self):
        self.par()
        self.criterio("Desalinhamento angular", "mm/100mm", "0.05", "0.10")
        self.criterio("Desalinhamento paralelo", "mm", "0.05", "0.10")
        r = ultimo_alinhamento(self.cliente.pk, self.eq.pk, None, "ALINHAMENTO_EIXOS")
        self.assertEqual(r["condicao"], "NORMAL")
        self.assertTrue(r["criterio_validado"])
        self.assertEqual(r["criterio"]["angular"]["origem"], "ACORDO_CLIENTE")
        self.assertEqual(r["criterio"]["angular"]["origem_display"], "Acordo com o cliente / contrato")
        self.assertEqual(r["criterio"]["angular"]["fonte"], "Acordo de demonstração (teste)")
        self.assertEqual(r["limites"]["angular"], {"ALERTA": "0.05", "CRITICO": "0.1"})
        self.assertEqual(r["pendencias"], [])

    def test_so_angular_validado_mantem_pendente(self):
        self.par()
        self.criterio("Desalinhamento angular", "mm/100mm", "0.05", "0.10")
        r = ultimo_alinhamento(self.cliente.pk, self.eq.pk, None, "ALINHAMENTO_EIXOS")
        self.assertEqual(r["condicao_angular"], "NORMAL")
        self.assertEqual(r["condicao_paralelo"], "PENDENTE")
        self.assertEqual(r["condicao"], "PENDENTE")
        self.assertEqual(len(r["pendencias"]), 1)
        self.assertIn("paralelo", r["pendencias"][0])

    def test_criterio_provisorio_nao_classifica(self):
        self.par()
        self.criterio("Desalinhamento angular", "mm/100mm", "0.05", "0.10", validacao=Validacao.PROVISORIA)
        r = ultimo_alinhamento(self.cliente.pk, self.eq.pk, None, "ALINHAMENTO_EIXOS")
        self.assertEqual(r["condicao"], "PENDENTE")
        self.assertIsNone(r["criterio"]["angular"])

    def test_criterio_de_outro_cliente_nao_vale(self):
        self.par()
        self.criterio("Desalinhamento angular", "mm/100mm", "0.05", "0.10", cliente=self.outro)
        self.criterio("Desalinhamento paralelo", "mm", "0.05", "0.10", cliente=self.outro)
        r = ultimo_alinhamento(self.cliente.pk, self.eq.pk, None, "ALINHAMENTO_EIXOS")
        self.assertEqual(r["condicao"], "PENDENTE")

    def test_classificacao_acima_do_critico(self):
        self.registro("antes", "0.40", "0.10", 0)
        self.registro("depois", "0.20", "0.03", 60)
        self.criterio("Desalinhamento angular", "mm/100mm", "0.05", "0.10")
        self.criterio("Desalinhamento paralelo", "mm", "0.05", "0.10")
        r = ultimo_alinhamento(self.cliente.pk, self.eq.pk, None, "ALINHAMENTO_EIXOS")
        self.assertEqual(r["condicao_angular"], "CRITICO")
        self.assertEqual(r["condicao"], "CRITICO")


class CriterioAlinhamentoPelaTelaTest(TestCase):
    """O Master cadastra e valida o critério pela API que a tela de cadastros usa."""

    @classmethod
    def setUpTestData(cls):
        cls.cliente = Cliente.objects.create(nome="Cliente API AL", cnpj="43.333.333/0001-43")
        cls.master = get_user_model().objects.create_user(email="api-al-master@t.test", nome="M", perfil="TECNICO",
                                                          nivel="MASTER")
        cls.tec = get_user_model().objects.create_user(email="api-al-tec@t.test", nome="T", perfil="TECNICO",
                                                       nivel="JUNIOR")

    def corpo(self, **extra):
        base = {"modalidade": "CORRETIVA", "grandeza": "Desalinhamento angular", "unidade": "mm/100mm",
                "sistema": "", "sentido": "SUPERIOR", "valor_alerta": "0.05", "valor_critico": "0.10",
                "origem": "RESPONSAVEL_TECNICO", "fonte": "Critério do RT (teste)", "validacao": "VALIDADA",
                "cliente": self.cliente.pk}
        base.update(extra)
        return base

    def api(self, usuario):
        c = APIClient()
        c.force_authenticate(usuario)
        return c

    def test_master_cadastra_e_valida(self):
        r = self.api(self.master).post("/api/preditiva/limites-alarme/", self.corpo(), format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["validacao_display"], "Validada pelo responsável técnico")
        self.assertEqual(r.data["modalidade_display"], "Manutenção Corretiva")
        self.assertEqual(r.data["cliente_nome"], "Cliente API AL")

    def test_tecnico_nao_altera_o_criterio(self):
        r = self.api(self.tec).post("/api/preditiva/limites-alarme/", self.corpo(), format="json")
        self.assertEqual(r.status_code, 403)

    def test_validar_sem_fonte_e_recusado(self):
        r = self.api(self.master).post("/api/preditiva/limites-alarme/", self.corpo(fonte=""), format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("fonte", str(r.data))

    def test_alerta_maior_que_critico_e_recusado(self):
        r = self.api(self.master).post("/api/preditiva/limites-alarme/",
                                       self.corpo(valor_alerta="0.20", valor_critico="0.10"), format="json")
        self.assertEqual(r.status_code, 400)

    def test_lista_traz_os_campos_da_tabela(self):
        LimiteAlarmeSerie.objects.create(
            modalidade="CORRETIVA", grandeza="Desalinhamento angular", unidade="mm/100mm", cliente=self.cliente,
            sentido="SUPERIOR", valor_alerta=Decimal("0.05"), valor_critico=Decimal("0.10"),
            origem="RESPONSAVEL_TECNICO", fonte="teste", validacao=Validacao.VALIDADA,
        )
        r = self.api(self.tec).get("/api/preditiva/limites-alarme/")
        self.assertEqual(r.status_code, 200)
        linha = (r.data["results"] if isinstance(r.data, dict) else r.data)[0]
        for campo in ("modalidade_display", "sistema_display", "sentido_display", "origem_display",
                      "validacao_display", "cliente_nome"):
            self.assertIn(campo, linha)
