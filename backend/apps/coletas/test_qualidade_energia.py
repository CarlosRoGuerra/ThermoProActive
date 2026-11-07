"""Qualidade de energia (2.3.2.10): ficha, grandezas, unidade, critério por grandeza, API e isolamento.

Valores sintéticos de teste; não são limites normativos nem de THD nem de desequilíbrio.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.cadastros.models import Area, Cliente, Equipamento, Instrumento, Setor, TecnologiaAnalise
from apps.preditiva.models import LimiteAlarmeSerie, Validacao

from .models import Inspecao, MedicaoTecnica
from .qualidade_energia import GRANDEZAS, classificar_superior, validar_ficha
from .relatorio_tecnico.modulos import modulo_da_tecnologia
from .relatorio_tecnico.qualidade_energia import MODULO_QUALIDADE_ENERGIA, ultimo_qualidade_energia


class FichaEClassificacaoTest(SimpleTestCase):
    def test_janela_de_agregacao_e_obrigatoria(self):
        self.assertIn("janela_agregacao", validar_ficha({}))
        self.assertIn("janela_agregacao", validar_ficha({"janela_agregacao": "   "}))
        self.assertEqual(validar_ficha({"janela_agregacao": "10 min"}), {})
        self.assertIn("tensao_nominal_v", validar_ficha({"janela_agregacao": "10 min", "tensao_nominal_v": 0}))

    def test_classificacao_superior(self):
        limites = {"ALERTA": Decimal("5"), "CRITICO": Decimal("8")}
        self.assertEqual(classificar_superior(9, limites), "CRITICO")
        self.assertEqual(classificar_superior(6, limites), "ALERTA")
        self.assertEqual(classificar_superior(2, limites), "NORMAL")
        self.assertEqual(classificar_superior(2, {}), "PENDENTE")

    def test_tres_grandezas_em_percentual(self):
        self.assertEqual(set(GRANDEZAS), {"THD de tensão", "THD de corrente", "Desequilíbrio de tensão"})


class QualidadeApiTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cliente = Cliente.objects.create(nome="Cliente QE", cnpj="91.111.111/0001-91")
        cls.outro = Cliente.objects.create(nome="Cliente QE 2", cnpj="92.222.222/0001-92")
        cls.tec = get_user_model().objects.create_user(email="qe@t.test", nome="T", perfil="TECNICO", nivel="JUNIOR")
        cls.portal_outro = get_user_model().objects.create_user(email="qe-outro@t.test", nome="O",
                                                                perfil="CLIENTE_PCM", cliente=cls.outro)
        area = Area.objects.create(nome="A", cliente=cls.cliente)
        setor = Setor.objects.create(nome="S", area=area)
        cls.eq = Equipamento.objects.create(nome="CCM", tag="CCM-1", setor=setor)
        cls.instr = Instrumento.objects.create(tipo="Analisador", modelo="Q", numero_serie="QE-1")
        cls.insp = Inspecao.objects.create(cliente=cls.cliente, tecnico=cls.tec, data=date(2026, 8, 1),
                                           tipo_analise="QUALIDADE_ENERGIA")
        cls.base = timezone.make_aware(timezone.datetime(2026, 8, 1, 10))

    def api(self, usuario=None):
        c = APIClient()
        c.force_authenticate(usuario or self.tec)
        return c

    def leitura(self, grandeza, valor, **extra):
        parametros = {"janela_agregacao": "10 min", **extra}
        return MedicaoTecnica.objects.create(
            inspecao=self.insp, equipamento=self.eq, instrumento=self.instr, tipo="QUALIDADE_ENERGIA",
            subtipo="QUALIDADE_ENERGIA", ponto_medicao="Barramento", grandeza=grandeza, unidade="%",
            valor=Decimal(str(valor)), parametros=parametros, data_hora=self.base,
        )

    def criterio(self, grandeza, alerta="5", critico="8"):
        return LimiteAlarmeSerie.objects.create(
            modalidade="QUALIDADE_ENERGIA", grandeza=grandeza, unidade="%", cliente=self.cliente,
            sentido="SUPERIOR", valor_alerta=Decimal(alerta), valor_critico=Decimal(critico),
            origem="RESPONSAVEL_TECNICO", fonte="QA sintético", validacao=Validacao.VALIDADA,
        )

    def test_api_recusa_ficha_sem_janela(self):
        corpo = {"inspecao": self.insp.pk, "equipamento": self.eq.pk, "instrumento": self.instr.pk,
                 "tipo": "QUALIDADE_ENERGIA", "subtipo": "QUALIDADE_ENERGIA", "ponto_medicao": "B",
                 "grandeza": "THD de tensão", "unidade": "%", "valor": "3", "parametros": {}}
        r = self.api().post("/api/medicoes-tecnicas/", corpo, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("janela_agregacao", str(r.data))

    def test_api_recusa_grandeza_fora_da_lista_e_unidade_errada(self):
        base = {"inspecao": self.insp.pk, "equipamento": self.eq.pk, "instrumento": self.instr.pk,
                "tipo": "QUALIDADE_ENERGIA", "subtipo": "QUALIDADE_ENERGIA", "ponto_medicao": "B",
                "valor": "3", "parametros": {"janela_agregacao": "10 min"}}
        r1 = self.api().post("/api/medicoes-tecnicas/", {**base, "grandeza": "Frequência", "unidade": "%"}, format="json")
        r2 = self.api().post("/api/medicoes-tecnicas/", {**base, "grandeza": "THD de tensão", "unidade": "V"}, format="json")
        self.assertEqual(r1.status_code, 400)
        self.assertEqual(r2.status_code, 400)

    def test_sem_criterio_fica_pendente(self):
        leitura = self.leitura("THD de tensão", 9)
        r = self.api().get(f"/api/preditiva/qualidade-energia/{leitura.pk}/")
        self.assertEqual(r.data["classificacao"], "PENDENTE")
        self.assertFalse(r.data["limite"]["validado"])

    def test_criterio_de_uma_grandeza_nao_vale_para_outra(self):
        self.criterio("THD de tensão")
        desequilibrio = self.leitura("Desequilíbrio de tensão", 9)
        r = self.api().get(f"/api/preditiva/qualidade-energia/{desequilibrio.pk}/")
        self.assertEqual(r.data["classificacao"], "PENDENTE")

    def test_criterio_validado_classifica(self):
        self.criterio("THD de tensão")
        leitura = self.leitura("THD de tensão", 6)
        r = self.api().get(f"/api/preditiva/qualidade-energia/{leitura.pk}/")
        self.assertEqual(r.data["classificacao"], "ALERTA")

    def test_outro_cliente_nao_ve_a_leitura(self):
        leitura = self.leitura("THD de corrente", 4)
        self.assertEqual(self.api(self.portal_outro).get(f"/api/preditiva/qualidade-energia/{leitura.pk}/").status_code, 404)

    def test_modulo_resolve_e_relatorio_traz_cada_grandeza(self):
        modulo = modulo_da_tecnologia(TecnologiaAnalise(nome="QE QA", modulo_tecnico="QUALIDADE_ENERGIA"))
        self.assertIs(modulo, MODULO_QUALIDADE_ENERGIA)
        self.leitura("THD de tensão", 3)
        r = ultimo_qualidade_energia(self.cliente.pk, self.eq.pk, date(2026, 12, 31))
        self.assertEqual(set(r), set(GRANDEZAS))
        self.assertEqual(r["THD de tensão"]["condicao"], "PENDENTE")
        self.assertIsNone(r["THD de corrente"])
        self.assertIsNone(ultimo_qualidade_energia(self.outro.pk, self.eq.pk, None))
