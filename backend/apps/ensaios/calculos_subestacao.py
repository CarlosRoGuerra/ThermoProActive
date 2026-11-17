"""
Cálculos dos ensaios elétricos de subestação (TC, TP, DJ, CS, RP) — funções puras, sem banco.

Cada fórmula tem a fonte. Nenhum limite é constante escondida aqui:

  - erro de relação de TC e TP: o admissível vem da CLASSE DE EXATIDÃO da placa, pela
    tabela da própria norma (IEC 61869-2 para TC, IEC 61869-3 para TP). Classe que não
    está na tabela = sem critério definido (nunca "conforme" por suposição);
  - erro de pickup e de tempo de relé: a tolerância é informada no lançamento (ajuste do
    ensaio, método e norma de referência ficam no catálogo; o valor é do técnico);
  - tempos de DJ, resistências de contato e de isolação: sem limite universal — critério
    do fabricante ou do cliente, informado no cadastro de referência.

Valor ausente devolve None, nunca zero.
"""
from decimal import ROUND_HALF_UP, Decimal

from .calculos import erro_relacao_pct

_CEM = Decimal("100")

# Erro de relação admissível por classe de exatidão (% da relação nominal).
# TC — IEC 61869-2 (medição 0,1 a 5 — erro de relação igual à classe; proteção 5P = ±1 %, 10P = ±3 %).
# TP — IEC 61869-3 (medição 0,1 a 3 — erro de relação igual à classe; proteção 3P = ±3 %, 6P = ±6 %).
ERRO_RELACAO_ADMISSIVEL = {
    "TC": {
        "0.1": Decimal("0.1"), "0.2": Decimal("0.2"), "0.5": Decimal("0.5"), "1": Decimal("1"),
        "3": Decimal("3"), "5": Decimal("5"), "5P": Decimal("1"), "10P": Decimal("3"),
    },
    "TP": {
        "0.1": Decimal("0.1"), "0.2": Decimal("0.2"), "0.5": Decimal("0.5"), "1": Decimal("1"),
        "3": Decimal("3"), "3P": Decimal("3"), "6P": Decimal("6"),
    },
}
FONTE_ERRO_RELACAO = {"TC": "IEC 61869-2", "TP": "IEC 61869-3"}

# Joelho da curva de excitação (IEEE C57.13): ponto em que 10 % a mais de tensão exige
# 50 % a mais de corrente de excitação.
JOELHO_AUMENTO_TENSAO = Decimal("1.10")
JOELHO_AUMENTO_CORRENTE = Decimal("1.50")


def normalizar_classe(classe: str) -> str:
    return (classe or "").strip().replace(",", ".").upper()


def erro_admissivel_relacao(classe: str, tipo: str):
    """
    Erro de relação admissível (%) para a classe de exatidão da placa. None quando a
    classe não está na tabela da norma do equipamento — o critério então não é definido.
    """
    tabela = ERRO_RELACAO_ADMISSIVEL.get(tipo, {})
    return tabela.get(normalizar_classe(classe))


def erro_relacao(medida, nominal):
    """Erro da relação (%) = (medida − nominal) ÷ nominal × 100 — IEC 61869-2 e -3 (erro de relação)."""
    return erro_relacao_pct(medida, nominal)


def erro_percentual(medido, esperado):
    """
    Erro (%) do valor medido frente ao esperado: (medido − esperado) ÷ esperado × 100.
    Usado no pickup e no tempo de atuação de relé de proteção (IEC 60255-151, método de
    comparação com o valor de ajuste/curva).
    """
    if medido is None or esperado is None or Decimal(esperado) == 0:
        return None
    return (Decimal(medido) - Decimal(esperado)) / Decimal(esperado) * _CEM


def dentro_da_tolerancia(erro, tolerancia):
    """|erro| ≤ tolerância informada. None sem erro ou sem tolerância."""
    if erro is None or tolerancia is None:
        return None
    return abs(Decimal(erro)) <= Decimal(tolerancia)


def simultaneidade(valores):
    """Diferença entre o maior e o menor tempo entre polos (ms). Precisa de pelo menos dois polos medidos."""
    medidos = [Decimal(v) for v in valores if v is not None]
    if len(medidos) < 2:
        return None
    return max(medidos) - min(medidos)


def _interpolar(pontos, tensao):
    """Corrente em `tensao` por interpolação linear entre os pontos (lista de (V, I) ordenada por V)."""
    for (v1, i1), (v2, i2) in zip(pontos, pontos[1:]):
        if v1 <= tensao <= v2:
            if v2 == v1:
                return i1
            return i1 + (i2 - i1) * (tensao - v1) / (v2 - v1)
    return None


def joelho_excitacao(pontos):
    """
    Tensão de joelho (V) pelo critério do IEEE C57.13: a primeira tensão em que
    I(1,10·V) ≥ 1,50 · I(V), com I interpolada entre os pontos lançados. Devolve o ponto
    lançado (não a interpolação), ou None quando a curva não chega lá.
    Pontos sem tensão ou corrente, e correntes zero, são ignorados.
    """
    validos = sorted(
        (Decimal(v), Decimal(i)) for v, i in pontos if v is not None and i is not None and Decimal(i) > 0
    )
    if len(validos) < 2:
        return None
    for v, i in validos:
        i_alto = _interpolar(validos, v * JOELHO_AUMENTO_TENSAO)
        if i_alto is not None and i_alto >= i * JOELHO_AUMENTO_CORRENTE:
            return v.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return None
