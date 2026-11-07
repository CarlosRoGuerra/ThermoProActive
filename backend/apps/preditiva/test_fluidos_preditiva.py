"""Projeção de fluidos: série com contexto comparável e limite fixo vigente. Valores sintéticos."""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.cadastros.models import Area, Cliente, Equipamento, Setor
from apps.coletas.models import Carregamento, ItemInspecao, TecnologiaAnalise
from apps.ensaios.models import (
    Ensaio, OrigemReferencia, ParametroEnsaio, ReferenciaParametro, ResultadoEnsaio,
    SituacaoResultado, TipoReferencia, ValorParametro,
)

from .fluidos import analisar_valor_fluido


class TendenciaFluidoTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cliente = Cliente.objects.create(nome="Cliente F", cnpj="41.111.111/0001-41")
        cls.outro = Cliente.objects.create(nome="Cliente G", cnpj="42.222.222/0001-42")
        cls.tec = TecnologiaAnalise.objects.create(nome="Fluidos QA")
        analista = get_user_model().objects.create_user(email="fluido-pred@t.test", nome="A", perfil="TECNICO", nivel="JUNIOR")
        cls.analista = analista
        area = Area.objects.create(nome="Á", cliente=cls.cliente)
        setor = Setor.objects.create(nome="S", area=area)
        cls.eq = Equipamento.objects.create(nome="Compressor F", tag="CMP-F", setor=setor)
        cls.ensaio = Ensaio.objects.create(nome="Fluidos QA", sigla="FQX", modulo="FLUIDOS", titulo_ficha="QA")
        cls.param = ParametroEnsaio.objects.create(ensaio=cls.ensaio, codigo="VISC", nome="Viscosidade", unidade="cSt")
        cls.contexto = {"comparacao_fluido": {"instrumento_id": 1, "ponto_coleta_id": 2, "produto_id": 3,
                                              "condicao_operacional": "REGIME", "equipamento_id": cls.eq.pk}}

    def campanha(self, dias, valor, contexto=True, eq=None, cliente=None):
        cliente = cliente or self.cliente
        carr = Carregamento.objects.create(cliente=cliente, tecnologia=self.tec, analista=self.analista,
                                           data_coleta=date(2026, 1, 1) + timedelta(days=dias))
        item = ItemInspecao.objects.create(carregamento=carr, equipamento=eq or self.eq)
        res = ResultadoEnsaio.objects.create(
            item=item, ensaio=self.ensaio, situacao=SituacaoResultado.REALIZADO,
            contexto_tecnico=self.contexto if contexto else {},
        )
        ValorParametro.objects.create(resultado=res, parametro=self.param, valor=Decimal(str(valor)), estado="MEDIDO")
        return res

    def limite(self, alerta="40", critico="50"):
        return ReferenciaParametro.objects.create(
            parametro=self.param, cliente=self.cliente, tipo=TipoReferencia.MAXIMO,
            limite_alerta=Decimal(alerta), limite_critico=Decimal(critico),
            origem=OrigemReferencia.RESPONSAVEL_TECNICO, fonte="QA sintético", vigencia_inicio=date(2025, 1, 1),
        )

    def test_sem_contexto_registrado_fica_inconclusiva(self):
        for dias, v in [(0, 30), (60, 32), (120, 35), (180, 38), (240, 41)]:
            self.campanha(dias, v, contexto=False)
        atual = self.campanha(300, 44, contexto=False)
        r = analisar_valor_fluido(atual, "VISC")
        self.assertEqual(r["serie"]["status"], "INSUFICIENTE")
        self.assertEqual(r["serie"]["motivo"], "contexto_historico_nao_registrado")

    def test_limite_maximo_vigente_estima_cruzamento(self):
        self.limite()
        for dias, v in [(0, 30.0), (60, 32.5), (120, 35.1), (180, 37.4), (240, 40.2)]:
            self.campanha(dias, v)
        atual = self.campanha(300, 42.9)
        r = analisar_valor_fluido(atual, "VISC")
        self.assertTrue(r["limite"]["validado"])
        self.assertEqual(r["serie"]["status"], "TENDENCIA")
        niveis = {p["nivel"]: p["estado"] for p in r["serie"]["projecoes"]}
        self.assertEqual(niveis["ALERTA"], "ATINGIDO")  # 42,9 já supera o alerta de 40

    def test_sem_referencia_fixa_nao_projeta(self):
        for dias, v in [(0, 30.0), (60, 32.5), (120, 35.1), (180, 37.4), (240, 40.2)]:
            self.campanha(dias, v)
        atual = self.campanha(300, 42.9)
        r = analisar_valor_fluido(atual, "VISC")
        self.assertEqual(r["limite"]["motivo"], "sem_limite_fixo_para_projetar")
        self.assertEqual(r["serie"]["projecoes"], [])

    def test_campanha_de_outro_cliente_nao_aparece_no_endpoint(self):
        atual = self.campanha(300, 42.9)
        user = get_user_model().objects.create_user(email="fluido-portal@t.test", nome="P", perfil="CLIENTE_PCM",
                                                    cliente=self.outro)
        api = APIClient()
        api.force_authenticate(user)
        r = api.get(f"/api/preditiva/tendencias/fluidos/{atual.pk}/VISC/")
        self.assertEqual(r.status_code, 404)
