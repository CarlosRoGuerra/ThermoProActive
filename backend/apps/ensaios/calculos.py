"""
Cálculos dos ensaios de transformador — funções puras, sem banco.

Cada fórmula tem a fonte (norma ou guia) e reproduz os números dos relatórios de
referência do cliente (2025-12_TRF-001_Óleo.pdf e 2025-12_TRF-001_ENDe.pdf) —
ver apps/ensaios/tests.py. Valor ausente devolve None, nunca zero.
"""
from decimal import ROUND_DOWN, Decimal

# IEEE C57.104: TDCG (TGC) = H2 + CH4 + C2H6 + C2H4 + C2H2 + CO. TG soma também os
# gases não combustíveis (O2, N2, CO2). PDF: TG 60.044,5 → "60.044"; TGC 544,5 → "544".
GASES_COMBUSTIVEIS = ("H2", "CH4", "CO", "C2H4", "C2H6", "C2H2")
GASES_TODOS = GASES_COMBUSTIVEIS + ("O2", "N2", "CO2")

# IEEE C57.12.90 / NBR 5356-1: correção da resistência ôhmica à temperatura de
# referência; constante do material do enrolamento (cobre 234,5; alumínio 225).
TK_COBRE = Decimal("234.5")
TK_ALUMINIO = Decimal("225")
TEMPERATURA_REFERENCIA_C = Decimal("75")

# De Pablo: GP = 7100 / (8,88 + 2-FAL), 2-FAL em ppm (mg/kg) — citada na nota 3 da ficha 2-FAL.
DE_PABLO_A = Decimal("7100")
DE_PABLO_B = Decimal("8.88")

_CEM = Decimal("100")


def soma_gases(valores: dict, codigos=GASES_TODOS):
    """Soma dos gases com valor; None se nenhum foi medido. Trunca como no relatório de referência."""
    presentes = [valores[c] for c in codigos if valores.get(c) is not None]
    if not presentes:
        return None
    return sum(presentes, Decimal("0")).quantize(Decimal("1"), rounding=ROUND_DOWN)


def _tensao_enrolamento(tensao_linha, tensao_fase, estrela: bool):
    if tensao_linha is None:
        return None
    if not estrela:
        return Decimal(tensao_linha)
    if tensao_fase is not None:
        return Decimal(tensao_fase)
    return Decimal(tensao_linha) / Decimal(3).sqrt()


def relacao_nominal(tensao_at_v, tensao_bt_v, tensao_bt_fase_v, grupo_ligacao: str):
    """
    Relação entre as tensões dos enrolamentos AT e BT (a que o TTR mede por fase).

    Triângulo (D/d) usa a tensão de linha; estrela (Y/y, Z/z) a de fase — a de placa
    quando existe (ex.: 220 V em 380/220 V). PDF: Dyn1, TAP 11.400 V e BT 380/220 V →
    11.400 ÷ 220 = 51,818.
    """
    g = (grupo_ligacao or "").strip()
    if len(g) < 2 or tensao_at_v is None or tensao_bt_v is None:
        return None
    at = _tensao_enrolamento(tensao_at_v, None, g[0] in "YZyz")
    bt = _tensao_enrolamento(tensao_bt_v, tensao_bt_fase_v, g[1] in "YZyz")
    if not at or not bt:
        return None
    return at / bt


def erro_relacao_pct(medido, nominal):
    """Erro da relação medida (%). NETA ATS: tolerância de ±0,5%."""
    if medido is None or not nominal:
        return None
    return (Decimal(medido) - Decimal(nominal)) / Decimal(nominal) * _CEM


def resistencia_fase(medido, triangulo: bool, com_neutro: bool):
    """
    Resistência por fase a partir da leitura entre terminais.

    Triângulo medido entre linhas: a leitura é R·2R/3R → fase = 1,5 × leitura.
    Estrela medida do neutro à linha: a leitura já é a fase. Estrela entre linhas: ÷ 2.
    PDF: H1|H2 = 3,51 Ω → 5,27 Ω (calculado).
    """
    if medido is None:
        return None
    medido = Decimal(medido)
    if triangulo:
        return medido * Decimal("1.5")
    return medido if com_neutro else medido / 2


def corrigir_temperatura(resistencia, temperatura_medicao_c, tk=TK_COBRE,
                         temperatura_referencia_c=TEMPERATURA_REFERENCIA_C):
    """R corrigida = R × (Tk + Tref) ÷ (Tk + Tmedição). PDF: 5,265 Ω a 45 °C → 5,83 Ω a 75 °C."""
    if resistencia is None or temperatura_medicao_c is None:
        return None
    return Decimal(resistencia) * (tk + temperatura_referencia_c) / (tk + Decimal(temperatura_medicao_c))


def indice_polarizacao(r600, r60):
    """IP = R(10 min) ÷ R(1 min). NETA ATS: maior que 1,0."""
    if r600 is None or not r60:
        return None
    return Decimal(r600) / Decimal(r60)


def indice_absorcao(r60, r30):
    """Índice de absorção (DAR) = R(60 s) ÷ R(30 s)."""
    if r60 is None or not r30:
        return None
    return Decimal(r60) / Decimal(r30)


def grau_polimerizacao_de_pablo(furfural_mg_kg):
    """Grau de polimerização estimado pelo 2-Furfural (equação de De Pablo)."""
    if furfural_mg_kg is None or Decimal(furfural_mg_kg) < 0:
        return None
    return DE_PABLO_A / (DE_PABLO_B + Decimal(furfural_mg_kg))


def percentual_do_limite(valor, limite):
    """Valor em % da referência (eixo dos gráficos). Referência zero não tem percentual."""
    if valor is None or limite is None or Decimal(limite) == 0:
        return None
    return Decimal(valor) / Decimal(limite) * _CEM


def avaliar(*, valor, texto, estado, tipo_limite, limite, limite_superior, referencia_texto):
    """
    True = dentro do limite, False = fora, None = sem critério ou sem valor.

    Abaixo do LD/LQ ou não detectado conta como dentro de um máximo e fora de um
    mínimo. Indisponível não é avaliado.
    """
    abaixo = estado in ("ABAIXO_LD", "ABAIXO_LQ", "NAO_DETECTADO")
    if tipo_limite == "QUALITATIVO":
        if not texto or not referencia_texto:
            return None
        return texto.strip().casefold() == referencia_texto.strip().casefold()
    if tipo_limite == "INFORMATIVO" or estado == "INDISPONIVEL":
        return None
    if abaixo:
        return {"MAXIMO": True, "MINIMO": False}.get(tipo_limite)
    if valor is None or limite is None:
        return None
    valor, limite = Decimal(valor), Decimal(limite)
    if tipo_limite == "MAXIMO":
        return valor <= limite
    if tipo_limite == "MINIMO":
        return valor >= limite
    if tipo_limite == "FAIXA":
        return limite_superior is not None and limite <= valor <= Decimal(limite_superior)
    return None
