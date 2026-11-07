"""Estatística e projeção puras. Casos sintéticos: não são limites normativos nem dados reais."""
import math
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from django.test import SimpleTestCase

from .estatistica import (
    ajuste_exponencial,
    ajuste_linear,
    atipicos,
    escolher_modelo,
    inclinacao_significativa,
    inverter_para,
    primeiro_x_que_atinge,
    t_critico,
)
from .risco import calcular_indice, validar_matriz
from .tendencia import PARAMETROS_PADRAO, TEXTO_LIMITE, projetar_serie

ORIGEM = datetime(2026, 1, 1, tzinfo=timezone.utc)


def instantes(dias):
    return [ORIGEM + timedelta(days=d) for d in dias]


class EstatisticaTest(SimpleTestCase):
    def test_reta_exata_tem_inclinacao_e_r2_unitarios(self):
        xs = [0, 1, 2, 3, 4]
        ajuste = ajuste_linear(xs, [1 + 2 * x for x in xs])
        self.assertAlmostEqual(ajuste["b"], 2)
        self.assertAlmostEqual(ajuste["a"], 1)
        self.assertAlmostEqual(ajuste["r2"], 1)

    def test_valores_conhecidos_da_regressao(self):
        # x = 1..4, y = 2, 4, 5, 4: Sxy = 3,5; Sxx = 5 → b = 0,7; a = 2,0 (cálculo manual)
        # SST = 4,75; SSE = 2,3 → R² = 1 − 2,3/4,75
        ajuste = ajuste_linear([1, 2, 3, 4], [2, 4, 5, 4])
        self.assertAlmostEqual(ajuste["b"], 0.7)
        self.assertAlmostEqual(ajuste["a"], 2.0)
        self.assertAlmostEqual(ajuste["r2"], 1 - 2.3 / 4.75)

    def test_serie_curta_nao_ajusta(self):
        self.assertIsNone(ajuste_linear([0, 1], [1, 2]))
        self.assertIsNone(ajuste_exponencial([0, 1], [1, 2]))

    def test_x_sem_variacao_nao_divide_por_zero(self):
        self.assertIsNone(ajuste_linear([5, 5, 5], [1, 2, 3]))

    def test_exponencial_exige_valores_positivos(self):
        self.assertIsNone(ajuste_exponencial([0, 1, 2], [1, 0, 2]))
        self.assertIsNone(ajuste_exponencial([0, 1, 2], [1, -1, 2]))

    def test_serie_exponencial_escolhe_o_modelo_exponencial(self):
        xs = [0, 1, 2, 3, 4, 5, 6]
        ys = [math.exp(0.4 * x) for x in xs]
        ajuste, comparacao = escolher_modelo(xs, ys)
        self.assertEqual(ajuste["modelo"], "exponencial")
        self.assertEqual(comparacao["escolhido"], "exponencial")

    def test_serie_linear_mantem_o_modelo_linear(self):
        xs = [0, 1, 2, 3, 4, 5]
        ys = [1 + 0.5 * x + (0.05 if i % 2 else -0.05) for i, x in enumerate(xs)]
        ajuste, comparacao = escolher_modelo(xs, ys)
        self.assertEqual(ajuste["modelo"], "linear")
        self.assertEqual(comparacao["escolhido"], "linear")

    def test_inclinacao_nula_nao_e_significativa(self):
        xs = [0, 1, 2, 3, 4, 5]
        ys = [3, 5, 3, 5, 3, 5]
        t, significativa = inclinacao_significativa(ajuste_linear(xs, ys))
        self.assertFalse(significativa)
        self.assertLess(abs(t), t_critico(4))

    def test_t_critico_conservador_acima_de_30_gl(self):
        self.assertEqual(t_critico(0), None)
        self.assertEqual(t_critico(1), 12.706)
        self.assertEqual(t_critico(500), t_critico(30))

    def test_inverter_para_linear_e_exponencial(self):
        linear = ajuste_linear([0, 1, 2, 3], [1, 3, 5, 7])  # y = 1 + 2x
        self.assertAlmostEqual(inverter_para(linear, 9), 4)
        exp = ajuste_exponencial([0, 1, 2, 3], [1, 2, 4, 8])  # y = 2^x
        self.assertAlmostEqual(inverter_para(exp, 16), 4, places=6)
        self.assertIsNone(inverter_para(exp, 0))

    def test_primeiro_x_que_atinge_bisseciona(self):
        x = primeiro_x_que_atinge(lambda v: 2 * v, 10, 0, 100, sobe=True)
        self.assertAlmostEqual(x, 5, places=6)
        self.assertIsNone(primeiro_x_que_atinge(lambda v: 2 * v, 1000, 0, 100, sobe=True))
        self.assertEqual(primeiro_x_que_atinge(lambda v: 2 * v, -1, 0, 100, sobe=True), 0)

    def test_atipico_pelo_z_modificado_sem_remover(self):
        self.assertEqual(atipicos([1, 1.1, 0.9, 1.05, 9.0]), [4])
        self.assertEqual(atipicos([2, 2, 2, 2]), [])
        self.assertEqual(atipicos([1, 2]), [])


class ProjetarSerieTest(SimpleTestCase):
    def cfg(self, **extra):
        return {**PARAMETROS_PADRAO, **extra}

    def test_pontos_insuficientes(self):
        r = projetar_serie(instantes([0, 10]), [1, 2], [], self.cfg())
        self.assertEqual((r["status"], r["motivo"]), ("INSUFICIENTE", "pontos_insuficientes"))
        self.assertEqual(r["projecoes"], [])

    def test_serie_constante(self):
        r = projetar_serie(instantes([0, 1, 2, 3]), [2, 2, 2, 2], [], self.cfg())
        self.assertEqual(r["status"], "SERIE_CONSTANTE")

    def test_ruido_sem_tendencia_nao_gera_data(self):
        dias = [0, 10, 20, 30, 40, 50]
        ys = [3, 5, 3, 5, 3, 5]
        limite = [{"nivel": "ALERTA", "valor": Decimal("6"), "sentido": "SUPERIOR"}]
        r = projetar_serie(instantes(dias), ys, limite, self.cfg())
        self.assertEqual(r["status"], "SEM_TENDENCIA")
        self.assertEqual(r["projecoes"], [])
        self.assertEqual(r["motivo"], "inclinacao_nao_significativa_95")

    def test_tendencia_crescente_estima_data_com_intervalo(self):
        # 1,0 mm/s por 10 dias, com pequena oscilação
        dias = [0, 10, 20, 30, 40, 50]
        ys = [2.0, 3.1, 3.9, 5.1, 5.9, 7.2]
        limite = [{"nivel": "ALERTA", "valor": Decimal("9.0"), "sentido": "SUPERIOR"}]
        r = projetar_serie(instantes(dias), ys, limite, self.cfg(horizonte_dias=3650))
        self.assertEqual(r["status"], "TENDENCIA")
        self.assertEqual(r["sentido"], "SOBE")
        proj = r["projecoes"][0]
        self.assertEqual(proj["estado"], "ESTIMADO")
        self.assertEqual(proj["limite"], "9.0")
        inicio, fim = (datetime.fromisoformat(x) for x in proj["intervalo_confianca"])
        estimada = datetime.fromisoformat(proj["data_estimada"])
        self.assertLessEqual(inicio, estimada)
        self.assertLessEqual(estimada, fim)
        self.assertIn("não probabilidade de falha", TEXTO_LIMITE)

    def test_tendencia_descendente_nao_converge_ao_limite_superior(self):
        dias = [0, 10, 20, 30, 40, 50]
        ys = [9.0, 8.1, 7.2, 6.0, 5.1, 4.2]
        limite = [{"nivel": "ALERTA", "valor": Decimal("12"), "sentido": "SUPERIOR"}]
        r = projetar_serie(instantes(dias), ys, limite, self.cfg())
        self.assertEqual(r["sentido"], "DESCE")
        self.assertEqual(r["projecoes"][0]["estado"], "NAO_CONVERGE")

    def test_limite_inferior_com_tendencia_descendente_estima(self):
        dias = [0, 10, 20, 30, 40, 50]
        ys = [9.0, 8.1, 7.2, 6.0, 5.1, 4.2]
        limite = [{"nivel": "CRITICO", "valor": Decimal("2"), "sentido": "INFERIOR"}]
        r = projetar_serie(instantes(dias), ys, limite, self.cfg(horizonte_dias=3650))
        self.assertEqual(r["projecoes"][0]["estado"], "ESTIMADO")

    def test_limite_ja_atingido_pela_ultima_medicao(self):
        dias = [0, 10, 20, 30, 40]
        ys = [1.0, 2.0, 3.0, 4.0, 5.0]
        limite = [{"nivel": "ALERTA", "valor": Decimal("4.5"), "sentido": "SUPERIOR"}]
        r = projetar_serie(instantes(dias), ys, limite, self.cfg())
        self.assertEqual(r["projecoes"][0]["estado"], "ATINGIDO")
        self.assertIsNone(r["projecoes"][0]["data_estimada"])

    def test_alem_do_horizonte_nao_da_data(self):
        dias = [0, 10, 20, 30, 40, 50]
        ys = [1.0, 1.5, 2.2, 2.6, 3.4, 3.9]
        limite = [{"nivel": "ALERTA", "valor": Decimal("1000"), "sentido": "SUPERIOR"}]
        r = projetar_serie(instantes(dias), ys, limite, self.cfg(horizonte_dias=30))
        self.assertEqual(r["projecoes"][0]["estado"], "FORA_DO_HORIZONTE")
        self.assertIsNone(r["projecoes"][0]["data_estimada"])

    def test_sem_limite_cadastrado_so_descreve(self):
        dias = [0, 10, 20, 30, 40, 50]
        ys = [1.0, 1.5, 2.2, 2.6, 3.4, 3.9]
        r = projetar_serie(instantes(dias), ys, [], self.cfg())
        self.assertEqual(r["status"], "TENDENCIA")
        self.assertEqual(r["motivo"], "tendencia_sem_limite_cadastrado")
        self.assertEqual(r["projecoes"], [])

    def test_datas_desiguais_usam_dias_reais(self):
        # mesma reta, espaçamentos diferentes: a inclinação por dia deve coincidir
        r1 = projetar_serie(instantes([0, 1, 2, 3, 4]), [0, 1, 2, 3, 4], [], self.cfg())
        r2 = projetar_serie(instantes([0, 2, 4, 6, 8]), [0, 2, 4, 6, 8], [], self.cfg())
        self.assertAlmostEqual(r1["estatisticas"]["inclinacao_por_dia"], 1)
        self.assertAlmostEqual(r2["estatisticas"]["inclinacao_por_dia"], 1)


class MatrizRiscoTest(SimpleTestCase):
    def matriz(self, **extra):
        base = {"nome": "t", "peso_severidade": Decimal("0.6"), "peso_tendencia": Decimal("0.4"),
                "consequencia": {"A": 3, "B": 2, "C": 1},
                "faixas": [{"ate": 50, "rotulo": "BAIXO"}, {"ate": 100, "rotulo": "ALTO"}]}
        base.update(extra)
        return base

    def test_matriz_valida(self):
        validar_matriz(self.matriz())

    def test_pesos_devem_somar_um(self):
        with self.assertRaises(ValueError):
            validar_matriz(self.matriz(peso_tendencia=Decimal("0.5")))

    def test_consequencia_exige_a_b_c(self):
        with self.assertRaises(ValueError):
            validar_matriz(self.matriz(consequencia={"A": 3, "B": 2}))
        with self.assertRaises(ValueError):
            validar_matriz(self.matriz(consequencia={"A": 3, "B": 2, "C": True}))

    def test_faixas_crescentes_e_terminando_em_cem(self):
        with self.assertRaises(ValueError):
            validar_matriz(self.matriz(faixas=[{"ate": 60, "rotulo": "x"}, {"ate": 50, "rotulo": "y"}]))
        with self.assertRaises(ValueError):
            validar_matriz(self.matriz(faixas=[{"ate": 50, "rotulo": "x"}]))

    def test_indice_completo_e_decomposto(self):
        m = {"id": 1, "nome": "t", "origem": "cadastro", "validacao": "PROVISORIA", "fonte": "",
             "peso_severidade": 0.6, "peso_tendencia": 0.4,
             "consequencia": {"A": 3, "B": 2, "C": 1}, "faixas": [{"ate": 100, "rotulo": "X"}]}
        r = calcular_indice("CRITICO", "ESTIMADO", "A", m)
        # p = 0,6·1 + 0,4·1 = 1; c = 3/3 = 1; índice = 100
        self.assertEqual(r["indice"], 100.0)
        self.assertTrue(r["completo"])
        self.assertIn("priorização", r["aviso"])

    def test_componente_ausente_nao_vira_zero(self):
        m = {"peso_severidade": 0.6, "peso_tendencia": 0.4, "consequencia": {"A": 3, "B": 2, "C": 1},
             "faixas": [{"ate": 100, "rotulo": "X"}], "nome": "t", "origem": "reserva_do_sistema",
             "validacao": "PROVISORIA"}
        r = calcular_indice("NORMAL", None, "B", m)
        self.assertIsNone(r["indice"])
        self.assertFalse(r["completo"])
        self.assertIn("sem_tendencia_avaliada", r["pendencias"])
        r2 = calcular_indice(None, "SEM_TENDENCIA", "B", m)
        self.assertIn("sem_condicao_classificada", r2["pendencias"])

    def test_criticidade_sem_consequencia_fica_incompleto(self):
        m = {"peso_severidade": 0.6, "peso_tendencia": 0.4, "consequencia": {"A": 3, "B": 2, "C": 1},
             "faixas": [{"ate": 100, "rotulo": "X"}], "nome": "t", "origem": "x", "validacao": "PROVISORIA"}
        r = calcular_indice("ALERTA", "TENDENCIA", "", m)
        self.assertIsNone(r["indice"])
        self.assertIn("criticidade_do_ativo_nao_informada", r["pendencias"])
