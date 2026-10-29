"""Séries laboratoriais: histórico visível não é comparabilidade presumida."""
from datetime import date

from django.test import TestCase

from apps.cadastros.models import Instrumento

from .contexto import registrar_contexto
from .models import ColetaFluido, PontoColeta, ProdutoFluido
from .relatorio_fluidos import avaliar_resultado_fluido
from .test_fluidos import CenarioFluidos


class ComparacaoFluidosPreditivaTest(CenarioFluidos, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.criar()
        cls.instrumento = Instrumento.objects.create(tipo="Laboratório QA", numero_serie="LAB-QA")
        cls.outro_instrumento = Instrumento.objects.create(tipo="Laboratório QA2", numero_serie="LAB-QA2")
        cls.ponto = PontoColeta.objects.create(nome="Ponto da amostra QA", modulo="FLUIDO_LUBRIFICANTE")

    def amostra(self, dia, valor, *, instrumento=True, produto=None, metodo="", contexto=True, **coleta_extras):
        _, (item,) = self.rota(date(2026, 10, dia), [self.redutor])
        coleta = dict(item=item, aplicacao="LUBRIFICANTE", produto=produto or self.produto,
                      data_coleta=date(2026, 10, dia))
        if contexto:
            coleta.update(ponto_coleta=self.ponto, condicao_operacional="EM_OPERACAO")
        coleta.update(coleta_extras)
        ColetaFluido.objects.create(**coleta)
        resultado = self.resultado(item, "EF", {"FE": valor},
                                   instrumento=self.instrumento if instrumento is True else instrumento or None)
        if metodo:
            resultado.valores.update(metodo=metodo)
        registrar_contexto(resultado, self.tecnico)
        return resultado

    def linha(self, resultado):
        return next(l for l in avaliar_resultado_fluido(resultado)["linhas"] if l["codigo"] == "FE")

    def test_tendencia_compara_so_contexto_registrado_e_datas_anteriores(self):
        anterior = self.amostra(1, 10)
        atual = self.amostra(2, 20)
        self.amostra(3, 999)
        linha = self.linha(atual)
        self.assertEqual(linha["tendencia"]["direcao"], "SOBE")
        self.assertEqual(linha["comparacao"]["resultado_ids"], [anterior.pk, atual.pk])
        self.assertEqual(linha["comparacao"]["versao"], "comparacao_fluido_v1")

    def test_troca_instrumento_interrompe_tendencia_mas_preserva_historico(self):
        anterior = self.amostra(1, 10)
        atual = self.amostra(2, 20, instrumento=self.outro_instrumento)
        linha = self.linha(atual)
        self.assertIsNone(linha["tendencia"])
        self.assertEqual(linha["comparacao"]["excluidos"], [anterior.pk])
        self.assertEqual(len(linha["valores"]), 2)

    def test_troca_produto_nao_mistura_oleos(self):
        self.amostra(1, 10)
        outro_produto = ProdutoFluido.objects.create(nome="Outro óleo QA", aplicacao="LUBRIFICANTE")
        atual = self.amostra(2, 20, produto=outro_produto)
        self.assertIsNone(self.linha(atual)["tendencia"])

    def test_ausencia_instrumento_ou_contexto_e_inconclusiva(self):
        self.amostra(1, 10)
        for dia, extras in ((2, {"instrumento": False}), (3, {"contexto": False})):
            with self.subTest(extras=extras):
                linha = self.linha(self.amostra(dia, 20, **extras))
                self.assertIsNone(linha["tendencia"])
                self.assertEqual(linha["comparacao"]["motivo"], "instrumento_ou_contexto_operacional_ausente")

    def test_metodo_ou_intervencao_diferentes_nao_formam_tendencia(self):
        self.amostra(1, 10, metodo="Método A")
        metodo_b = self.amostra(2, 20, metodo="Método B")
        self.assertIsNone(self.linha(metodo_b)["tendencia"])
        troca = self.amostra(3, 30, metodo="Método A", data_ultima_troca=date(2026, 10, 3))
        self.assertIsNone(self.linha(troca)["tendencia"])

    def test_sem_numero_medido_nao_usa_censura_como_zero(self):
        self.amostra(1, 10)
        atual = self.amostra(2, 20)
        atual.valores.update(valor=None, estado="ABAIXO_LD", limite_deteccao="1")
        linha = self.linha(atual)
        self.assertIsNone(linha["tendencia"])
        self.assertEqual(linha["comparacao"]["motivo"], "leitura_atual_ausente_ou_invalida")

    def test_saneamento_coleta_posterior_nao_reescreve_contexto_congelado(self):
        anterior = self.amostra(1, 10)
        atual = self.amostra(2, 20)
        antes = self.linha(atual)["comparacao"]
        ColetaFluido.objects.filter(item=anterior.item).update(condicao_operacional="PARADO")
        ColetaFluido.objects.filter(item=atual.item).update(condicao_operacional="APOS_PARADA")
        self.assertEqual(self.linha(atual)["comparacao"], antes)
