"""Estatística da tendência, só com a biblioteca padrão (sem numpy/scipy).

Escopo deliberadamente pequeno: regressão linear e exponencial (log-linear) por
mínimos quadrados, teste t da inclinação e intervalo de confiança da RETA de
tendência. Isso descreve a série observada. Não é previsão de falha, vida útil
remanescente nem probabilidade: o uso desses números é decidido em
`apps.preditiva.tendencia` e documentado em docs/23.

Convenções:
- x em dias reais desde o primeiro registro; y no valor medido (float).
- Confiança fixa de 95%, bilateral. Para gl > 30 usa-se o t de gl = 30 (2,042),
  que é mais largo que o assintótico 1,96 — a aproximação é conservadora.
- Funções devolvem None quando a conta não tem sentido (poucos pontos, x sem
  variação, log de valor não positivo). Quem chama traduz isso em status explícito.
"""
import math
from statistics import median

#: t bilateral 95% por graus de liberdade (tabela de Student).
T95 = {
    1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306,
    9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131,
    16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086, 21: 2.080, 22: 2.074,
    23: 2.069, 24: 2.064, 25: 2.060, 26: 2.056, 27: 2.052, 28: 2.048, 29: 2.045,
    30: 2.042,
}


def t_critico(gl: int):
    """t bilateral 95% para `gl` graus de liberdade; None se gl < 1."""
    if gl < 1:
        return None
    return T95[min(gl, 30)]


def _ajuste_base(xs, ys):
    """OLS de y = a + b·x. Devolve None sem variação em x."""
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx <= 0:
        return None
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    b = sxy / sxx
    a = my - b * mx
    sse = sum((y - (a + b * x)) ** 2 for x, y in zip(xs, ys))
    gl = n - 2
    s = math.sqrt(sse / gl) if gl > 0 else None
    return {"a": a, "b": b, "n": n, "mx": mx, "sxx": sxx, "gl": gl, "s": s,
            "se_b": (s / math.sqrt(sxx)) if s is not None else None}


def _r2_ajustado(r2, n):
    """R² ajustado com 1 preditor (x). Indefinido com n ≤ 2 ou R² indefinido."""
    if r2 is None or n <= 2:
        return None
    return 1 - (1 - r2) * (n - 1) / (n - 2)


def ajuste_linear(xs, ys):
    """Reta y = a + b·x. Precisa de ≥ 3 pontos (1 grau de liberdade no resíduo)."""
    if len(xs) < 3:
        return None
    base = _ajuste_base(xs, ys)
    if base is None:
        return None
    my = sum(ys) / len(ys)
    sst = sum((y - my) ** 2 for y in ys)
    sse = sum((y - (base["a"] + base["b"] * x)) ** 2 for x, y in zip(xs, ys))
    base["r2"] = (1 - sse / sst) if sst > 0 else None
    base["r2_ajustado"] = _r2_ajustado(base["r2"], base["n"])
    base["modelo"] = "linear"
    return base


def ajuste_exponencial(xs, ys):
    """Log-linear: ln(y) = a + b·x, ou seja y = exp(a + b·x). Exige y > 0.

    O R² é medido na escala ORIGINAL (y observado contra ŷ = exp(·)), para que a
    comparação com a linear use a mesma variável dependente.
    """
    if len(xs) < 3 or any(y is None or y <= 0 for y in ys):
        return None
    base = _ajuste_base(xs, [math.log(y) for y in ys])
    if base is None:
        return None
    my = sum(ys) / len(ys)
    sst = sum((y - my) ** 2 for y in ys)
    sse = sum((y - math.exp(base["a"] + base["b"] * x)) ** 2 for x, y in zip(xs, ys))
    base["r2"] = (1 - sse / sst) if sst > 0 else None
    base["r2_ajustado"] = _r2_ajustado(base["r2"], base["n"])
    base["modelo"] = "exponencial"
    return base


def escolher_modelo(xs, ys, margem: float = 0.05):
    """Linear por padrão; exponencial só se o R² ajustado dele superar o da linear
    em pelo menos `margem`. Critério explícito, não preferência por forma.

    Devolve (ajuste, comparacao). `ajuste` pode ser None.
    """
    linear = ajuste_linear(xs, ys)
    exponencial = ajuste_exponencial(xs, ys)
    r2_linear = linear["r2_ajustado"] if linear else None
    r2_exponencial = exponencial["r2_ajustado"] if exponencial else None
    usa_exponencial = exponencial is not None and r2_exponencial is not None and (
        r2_linear is None or r2_exponencial - r2_linear >= margem
    )
    escolhido = exponencial if usa_exponencial else linear
    comparacao = {
        "criterio": "exponencial só com R² ajustado acima do linear em pelo menos a margem",
        "margem": margem,
        "r2_ajustado_linear": _arred(r2_linear),
        "r2_ajustado_exponencial": _arred(r2_exponencial),
        "escolhido": escolhido["modelo"] if escolhido else None,
    }
    return escolhido, comparacao


def valor_em(ajuste, x: float) -> float:
    """Valor da tendência central em x, na escala original."""
    eta = ajuste["a"] + ajuste["b"] * x
    return math.exp(eta) if ajuste["modelo"] == "exponencial" else eta


def banda_confianca(ajuste, x: float, t: float):
    """(inferior, superior) do intervalo de confiança da RETA de tendência em x.

    Não é intervalo de predição de uma nova medição. Na exponencial o intervalo é
    calculado no log e devolvido na escala original.
    """
    eta = ajuste["a"] + ajuste["b"] * x
    erro = ajuste["s"] * math.sqrt(1 / ajuste["n"] + (x - ajuste["mx"]) ** 2 / ajuste["sxx"])
    inferior, superior = eta - t * erro, eta + t * erro
    if ajuste["modelo"] == "exponencial":
        return math.exp(inferior), math.exp(superior)
    return inferior, superior


def inclinacao_significativa(ajuste):
    """(estatística t, significativa) para H0: b = 0 ao nível de 95%.

    Erro-padrão nulo = ajuste exato (resíduo zero): significativa se b ≠ 0.
    """
    t = t_critico(ajuste["gl"])
    if ajuste["se_b"] is None or t is None:
        return None, False
    if ajuste["se_b"] == 0:
        return (math.inf if ajuste["b"] != 0 else 0.0), ajuste["b"] != 0
    estatistica = ajuste["b"] / ajuste["se_b"]
    return estatistica, abs(estatistica) > t


def inverter_para(ajuste, alvo: float):
    """x em que a tendência central atinge `alvo`. None se impossível (b = 0 ou alvo ≤ 0 no log)."""
    if ajuste["b"] == 0:
        return None
    if ajuste["modelo"] == "exponencial":
        if alvo <= 0:
            return None
        return (math.log(alvo) - ajuste["a"]) / ajuste["b"]
    return (alvo - ajuste["a"]) / ajuste["b"]


def primeiro_x_que_atinge(funcao, alvo: float, x0: float, x1: float, sobe: bool):
    """Menor x em [x0, x1] com funcao(x) ≥ alvo (sobe) ou ≤ alvo (não sobe).

    Bisseção: supõe função monótona no intervalo, o que vale para as bandas de uma
    reta de inclinação do mesmo sentido do alvo. None se x1 não atinge o alvo.
    """
    def atingiu(x):
        return funcao(x) >= alvo if sobe else funcao(x) <= alvo

    if atingiu(x0):
        return x0
    if not atingiu(x1):
        return None
    lo, hi = x0, x1
    for _ in range(200):
        meio = (lo + hi) / 2
        if atingiu(meio):
            hi = meio
        else:
            lo = meio
        if hi - lo < 1e-9:
            break
    return hi


def atipicos(ys):
    """Índices de pontos atípicos pelo z modificado (Iglewicz-Hoaglin, |z| > 3,5).

    Apenas sinaliza: o ponto continua na regressão e o cálculo informa a marcação.
    MAD zero (série quase constante) não marca nada.
    """
    if len(ys) < 3:
        return []
    med = median(ys)
    mad = median(abs(y - med) for y in ys)
    if mad == 0:
        return []
    return [i for i, y in enumerate(ys) if abs(0.6745 * (y - med) / mad) > 3.5]


def _arred(valor, casas=6):
    return None if valor is None else round(valor, casas)
