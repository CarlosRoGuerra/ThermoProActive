"""
Testes do motor de cálculo de manutenção corretiva.

Critério de aceitação: reproduzir os números das planilhas que o Fabrício usa hoje.
Se um destes testes quebrar, o sistema deixou de bater com a planilha dele.

Fonte dos valores esperados:
  · `Planilha Balanceamentos.xlsx`  (abas Bal-1P e Bal-2P)
  · `Economia Geradas com Alinhamentos e Balanceamentos.xlsx`
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from apps.cadastros.models import Area, Cliente, Equipamento, Setor

from . import rules
from .models import (
    BalanceamentoPlano,
    BalanceamentoPonto,
    EconomiaEnergetica,
    ServicoCampo,
    TipoServico,
)


def arredondar(valor, casas="0.01") -> Decimal:
    return Decimal(valor).quantize(Decimal(casas))


class CurvaReducaoTest(SimpleTestCase):
    """Bloco `CURVA REDUÇÃO (x100%)` — colunas I/J das abas Bal-1P e Bal-2P."""

    def test_bal_1p_mancal_2(self):
        # 12,31 → 1,70 mm/s: planilha mostra 0,138 residual e 86,2% de ganho.
        residual, reducao = rules.calcular_reducao("12.31", "1.7")
        self.assertEqual(arredondar(residual, "0.1"), Decimal("13.8"))
        self.assertEqual(arredondar(reducao, "0.1"), Decimal("86.2"))

    def test_bal_2p_mancal_3(self):
        # 20,00 → 0,90 mm/s: planilha mostra 0,045 residual e 95,5% de ganho.
        residual, reducao = rules.calcular_reducao("20", "0.9")
        self.assertEqual(arredondar(residual, "0.1"), Decimal("4.5"))
        self.assertEqual(arredondar(reducao, "0.1"), Decimal("95.5"))

    def test_referencia_zero_e_erro(self):
        # Dividir por zero na planilha daria #DIV/0!; aqui a mensagem é explícita.
        with self.assertRaises(ValueError):
            rules.calcular_reducao(0, "1.7")

    def test_reducao_zero_quando_trim_igual_a_referencia(self):
        # Balanceamento não reduziu nada — resultado válido (0%), não "sem dado".
        residual, reducao = rules.calcular_reducao("10", "10")
        self.assertEqual(residual, Decimal("100"))
        self.assertEqual(reducao, Decimal("0"))

    def test_trim_maior_que_referencia_da_reducao_negativa_sem_levantar_erro(self):
        # A vibração piorou depois da correção — resultado real e válido (não é erro
        # de entrada), o sinal negativo é a informação.
        residual, reducao = rules.calcular_reducao("10", "15")
        self.assertEqual(residual, Decimal("150"))
        self.assertEqual(reducao, Decimal("-50"))


class AvaliacaoPontoTest(SimpleTestCase):
    """O veredito que a planilha não dá: o resultado final passa na norma?"""

    def test_trim_de_1_7_mms_e_zona_b_na_classe_ii(self):
        r = rules.avaliar_ponto(classe_iso="II", reference_mms="12.31", trim_mms="1.7")
        self.assertEqual(arredondar(r.reducao_pct, "0.1"), Decimal("86.2"))
        self.assertEqual(r.zona_iso, "B")
        self.assertEqual(r.criticidade, "NORMAL")
        self.assertTrue(r.eficaz)

    def test_reducao_insuficiente_marca_nao_eficaz(self):
        r = rules.avaliar_ponto(classe_iso="II", reference_mms="10", trim_mms="8")
        self.assertFalse(r.eficaz)
        self.assertIn("abaixo do mínimo", r.diagnostico)


class MostradorPolarTest(SimpleTestCase):
    """Abas `Graf-O`: ângulo = fase/360 × 2π, x = cos, y = sen."""

    def test_fase_110_graus_bate_com_graf_o_1p(self):
        # Planilha: Meta_X2 = -0,34 e Meta_Y2 = 0,94 para a fase de 110°.
        x, y = rules.vetor_polar(110)
        self.assertEqual(arredondar(x), Decimal("-0.34"))
        self.assertEqual(arredondar(y), Decimal("0.94"))

    def test_fase_210_graus_bate_com_graf_o_2p(self):
        # Planilha: Meta_X2 = -0,87 e Meta_Y2 = -0,50 para a fase de 210°.
        x, y = rules.vetor_polar(210)
        self.assertEqual(arredondar(x), Decimal("-0.87"))
        self.assertEqual(arredondar(y), Decimal("-0.50"))

    def test_raio_proporcional_a_amplitude(self):
        # O que a planilha não faz: vetor do trim (1,7 de 12,31) encolhe para ~14%.
        x, y = rules.vetor_polar(0, amplitude="1.7", amplitude_maxima="12.31")
        self.assertEqual(arredondar(x, "0.001"), Decimal("0.138"))
        self.assertEqual(arredondar(y, "0.001"), Decimal("0.000"))


class RotacaoTest(SimpleTestCase):
    def test_29_74_hz_vira_1784_rpm(self):
        self.assertEqual(rules.hz_para_rpm("29.74"), 1784)


class EconomiaEnergeticaTest(SimpleTestCase):
    """
    Planilha de economia — 380 V, 71,0 → 66,2 A, FP 0,93, 20 h, R$ 0,35/kWh,
    investimento R$ 1.606,00 (mesmos números do exemplo do Fabrício que ele não
    conseguiu reproduzir na tela — a fórmula não mudou, o campo é que não tinha UI).
    """

    def calcular(self, **alteracoes):
        base = dict(
            tensao_v=380,
            corrente_antes_a="71",
            corrente_apos_a="66.2",
            fator_potencia="0.93",
            horas_dia=20,
            dias_ano=365,
            custo_kwh="0.35",
            investimento="1606",
        )
        return rules.calcular_economia(**{**base, **alteracoes})

    def test_reducao_de_corrente_em_amperes(self):
        # ΔI = 71,0 − 66,2 = 4,8 A — hoje exposto como campo próprio (era só uma
        # variável interna, "redução de corrente" pedida explicitamente).
        self.assertEqual(self.calcular().reducao_corrente_a, Decimal("4.8"))

    def test_reducao_de_demanda_em_kw(self):
        # Planilha (B9): 2,9380262... com a constante 1,732.
        self.assertEqual(arredondar(self.calcular().reducao_kw, "0.001"), Decimal("2.938"))

    def test_economia_anual_em_reais(self):
        # Planilha (B11): R$ 7.506,66. Aqui dá R$ 7.506,88 — os R$ 0,22 de diferença
        # são √3 exato (1,7320508…) contra a constante 1,732 da planilha.
        economia = self.calcular().economia_rs_ano
        self.assertAlmostEqual(float(economia), 7506.66, delta=1.0)

    def test_economia_anual_em_kwh(self):
        # Número que a planilha não mostra e o cliente usa na meta de eficiência.
        self.assertEqual(arredondar(self.calcular().economia_kwh_ano, "1"), Decimal("21448"))

    def test_retorno_no_ano_reproduz_o_c11(self):
        # Planilha (C11): 4,674 — quantas vezes o serviço se paga em um ano.
        self.assertEqual(arredondar(self.calcular().retorno_ano, "0.01"), Decimal("4.67"))

    def test_payback_e_o_inverso_do_c11(self):
        # O que a planilha chama de "PayBack" (4,67) não é payback: o payback são
        # ~2,6 meses / ~78 dias. Reproduzido à mão em docs/04 (linha 132) antes de
        # existir qualquer código — o mesmo exemplo do cliente que "não bateu".
        r = self.calcular()
        self.assertEqual(arredondar(r.payback_meses, "0.1"), Decimal("2.6"))
        self.assertEqual(arredondar(r.payback_dias, "1"), Decimal("78"))

    def test_payback_escala_com_o_investimento(self):
        # Dobrando o investimento, dobra o tempo de retorno — proporcionalidade direta,
        # é a definição (investimento / economia periódica).
        r1 = self.calcular(investimento="1606")
        r2 = self.calcular(investimento="3212")
        self.assertAlmostEqual(float(r2.payback_meses), float(r1.payback_meses) * 2, delta=0.01)

    def test_investimento_zero_nao_gera_payback(self):
        r = self.calcular(investimento="0")
        self.assertIsNone(r.payback_meses)
        self.assertIsNone(r.retorno_ano)

    def test_custo_de_energia_diferente_escala_a_economia_financeira(self):
        # Mesma energia poupada (kWh), tarifa diferente — só a economia em R$ muda.
        r1 = self.calcular(custo_kwh="0.35")
        r2 = self.calcular(custo_kwh="0.70")
        self.assertEqual(r1.economia_kwh_ano, r2.economia_kwh_ano)
        self.assertAlmostEqual(float(r2.economia_rs_ano), float(r1.economia_rs_ano) * 2, delta=0.01)

    def test_regime_diario_diferente_escala_a_economia_anual(self):
        r1 = self.calcular(horas_dia=10)
        r2 = self.calcular(horas_dia=20)
        self.assertAlmostEqual(float(r2.economia_kwh_ano), float(r1.economia_kwh_ano) * 2, delta=0.01)

    def test_dias_por_ano_diferente_escala_a_economia_anual(self):
        # Planta que não opera 365 dias/ano (ex.: para em julho) — não pode ficar
        # hardcoded, é exatamente o que a migração da planilha corrigiu.
        r1 = self.calcular(dias_ano=200)
        r2 = self.calcular(dias_ano=365)
        self.assertAlmostEqual(
            float(r2.economia_kwh_ano), float(r1.economia_kwh_ano) * 365 / 200, delta=0.01
        )

    def test_corrente_maior_apos_o_servico_gera_economia_negativa(self):
        r = self.calcular(corrente_antes_a="66.2", corrente_apos_a="71")
        self.assertLess(r.reducao_kw, 0)
        self.assertIsNone(r.payback_meses)  # não há payback sem economia

    def test_ausencia_de_economia_corrente_igual_antes_e_depois(self):
        # A corrente não mudou — resultado válido de "zero economia", não erro nem
        # "sem dado". Distinto do caso em que a corrente piora (fica negativo).
        r = self.calcular(corrente_antes_a="66.2", corrente_apos_a="66.2")
        self.assertEqual(r.reducao_corrente_a, Decimal("0"))
        self.assertEqual(r.reducao_kw, Decimal("0"))
        self.assertEqual(r.economia_rs_ano, Decimal("0"))
        self.assertIsNone(r.payback_meses)

    def test_valores_decimais_nao_redondos(self):
        # A fórmula precisa se comportar bem com números "de campo" reais, não só os
        # exemplos didáticos da planilha.
        r = self.calcular(
            tensao_v="381.5", corrente_antes_a="70.37", corrente_apos_a="65.94",
            fator_potencia="0.917", horas_dia="18.5", dias_ano=312,
            custo_kwh="0.4123", investimento="1789.90",
        )
        esperado_kw = (Decimal("381.5") * (Decimal("70.37") - Decimal("65.94")) * Decimal("0.917") * rules.RAIZ_TRES) / 1000
        self.assertAlmostEqual(float(r.reducao_kw), float(esperado_kw), delta=0.0005)
        self.assertGreater(r.payback_meses, 0)

    def test_nenhum_argumento_tem_valor_padrao(self):
        # Decisão do Fabrício: tudo é coletado na hora. Omitir uma grandeza tem de
        # quebrar, nunca virar um número plausível que ninguém mediu.
        for faltando in (
            "tensao_v", "corrente_antes_a", "corrente_apos_a", "fator_potencia",
            "horas_dia", "dias_ano", "custo_kwh", "investimento",
        ):
            kwargs = dict(
                tensao_v=380, corrente_antes_a="71", corrente_apos_a="66.2",
                fator_potencia="0.93", horas_dia=20, dias_ano=365,
                custo_kwh="0.35", investimento="1606",
            )
            del kwargs[faltando]
            with self.subTest(faltando=faltando), self.assertRaises(TypeError):
                rules.calcular_economia(**kwargs)

    def test_premissas_acompanham_o_resultado(self):
        # Vão impressas no relatório — sem elas o número não se sustenta em auditoria.
        self.assertTrue(any("trifásica" in p for p in self.calcular().premissas))


class ServicoDaPlanilha1PTest(TestCase):
    """
    Monta no banco o serviço exato da aba `Bal-1P` + a planilha de economia e confere
    que os valores gravados batem com os da planilha. É o teste de ponta a ponta:
    modelo → rules → campo calculado.
    """

    @classmethod
    def setUpTestData(cls):
        cliente = Cliente.objects.create(nome="Cliente Teste", cnpj="00.000.000/0001-00")
        area = Area.objects.create(cliente=cliente, nome="Área 1")
        setor = Setor.objects.create(area=area, nome="Setor 1")
        cls.equipamento = Equipamento.objects.create(
            setor=setor, tag="VE-001", nome="Ventilador Espargidor", classe_iso="II"
        )
        cls.analista = get_user_model().objects.create_user(
            email="analista@teste.com", nome="Analista", password="x"
        )
        cls.cliente = cliente

    def montar_servico(self):
        servico = ServicoCampo.objects.create(
            cliente=self.cliente,
            equipamento=self.equipamento,
            tipo=TipoServico.BALANCEAMENTO,
            analista=self.analista,
            data_execucao="2026-09-08",
            rotacao_hz="29.74",
            custo_servico="1606",
        )
        BalanceamentoPlano.objects.create(
            servico=servico, numero=1,
            massa_teste_g="30", angulo_teste="0",
            massa_final_g="100", angulo_final="136",
        )
        BalanceamentoPonto.objects.create(
            servico=servico, numero_mancal=2, direcao="H",
            reference_mms="12.31", reference_fase="110",
            trial_mms="23.95", trial_fase="133",
            trim_mms="1.7", trim_fase="136",
        )
        return servico

    def test_rotacao_em_hz_grava_rpm(self):
        # Cabeçalho da planilha: 29,74 Hz.
        self.assertEqual(self.montar_servico().rotacao_rpm, 1784)

    def test_ponto_grava_reducao_e_veredito(self):
        ponto = self.montar_servico().pontos.get()
        self.assertEqual(arredondar(ponto.reducao_pct, "0.1"), Decimal("86.2"))
        self.assertEqual(arredondar(ponto.residual_pct, "0.1"), Decimal("13.8"))
        self.assertEqual(ponto.zona_iso, "B")          # a planilha não dizia isto
        self.assertEqual(ponto.criticidade, "NORMAL")
        self.assertTrue(ponto.eficaz)
        self.assertEqual(ponto.codigo_ponto, "2H")

    def test_servico_resume_planos_e_reducao(self):
        servico = self.montar_servico()
        self.assertEqual(servico.numero_planos, 1)     # era a escolha entre duas abas
        self.assertEqual(arredondar(servico.reducao_media_pct, "0.1"), Decimal("86.2"))
        self.assertEqual(servico.criticidade_final, "NORMAL")

    def test_economia_grava_os_numeros_da_planilha(self):
        servico = self.montar_servico()
        economia = EconomiaEnergetica.objects.create(
            servico=servico,
            tensao_v="380", corrente_antes_a="71", corrente_apos_a="66.2",
            fator_potencia="0.93", horas_dia="20", dias_ano=365, custo_kwh="0.35",
            investimento="1606",
        )
        self.assertEqual(economia.reducao_corrente_a, Decimal("4.8"))
        self.assertEqual(arredondar(economia.reducao_kw, "0.001"), Decimal("2.938"))
        self.assertAlmostEqual(float(economia.economia_rs_ano), 7506.66, delta=1.0)
        self.assertEqual(arredondar(economia.retorno_ano, "0.01"), Decimal("4.67"))
        self.assertEqual(arredondar(economia.payback_meses, "0.1"), Decimal("2.6"))

    def test_economia_sem_investimento_nao_inventa_payback(self):
        # investimento é opcional só no banco (registros antigos) — sem ele, o serviço
        # continua mostrando a economia de energia, só não há payback para calcular.
        servico = self.montar_servico()
        economia = EconomiaEnergetica.objects.create(
            servico=servico,
            tensao_v="380", corrente_antes_a="71", corrente_apos_a="66.2",
            fator_potencia="0.93", horas_dia="20", dias_ano=365, custo_kwh="0.35",
        )
        self.assertIsNotNone(economia.economia_rs_ano)
        self.assertIsNone(economia.payback_meses)
        self.assertIsNone(economia.retorno_ano)

    def test_ponto_sem_trim_fica_em_andamento_sem_resultado_parcial(self):
        # Fluxo real de campo: mede o reference, aplica a massa de teste, mede o trial —
        # e só uma hora depois mede o trim. Tem de dar para salvar no meio, sem que
        # apareça um resultado parcial que seria lido como final.
        servico = self.montar_servico()
        ponto = BalanceamentoPonto.objects.create(
            servico=servico, numero_mancal=3, direcao="H",
            reference_mms="20", reference_fase="210",
            trial_mms="50", trial_fase="235",
        )
        self.assertFalse(ponto.completo)
        self.assertIsNone(ponto.reducao_pct)
        self.assertEqual(ponto.zona_iso, "")
        self.assertFalse(ponto.eficaz)

        # Chega o trim run: aí sim o resultado é calculado.
        ponto.trim_mms = "0.9"
        ponto.trim_fase = "240"
        ponto.save()
        self.assertTrue(ponto.completo)
        self.assertEqual(arredondar(ponto.reducao_pct, "0.1"), Decimal("95.5"))
        self.assertEqual(ponto.zona_iso, "A")

    def test_servico_ignora_pontos_em_andamento_na_media(self):
        servico = self.montar_servico()
        BalanceamentoPonto.objects.create(
            servico=servico, numero_mancal=3, direcao="H",
            reference_mms="20", reference_fase="210",
        )
        # Só o ponto completo (86,2%) entra na média.
        self.assertEqual(arredondar(servico.reducao_media_pct, "0.1"), Decimal("86.2"))
