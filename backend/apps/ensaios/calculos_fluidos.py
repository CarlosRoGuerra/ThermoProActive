"""
Cálculos da análise de fluidos lubrificantes e hidráulicos — funções puras, sem banco.

- Código de limpeza ISO 4406 a partir das contagens de partículas por mL.
- Classificação de um valor por uma referência cadastrada (Rotina/Alerta/Crítica).
- Tendência entre campanhas.

Nenhum limite técnico mora aqui: os números de alerta e crítico vêm de
`ReferenciaParametro` (com origem e vigência). Valor ausente devolve None.
"""
import re
from decimal import Decimal, InvalidOperation

# ISO 4406 (tabela de números de escala): o código R é o menor cujo limite
# superior de partículas por mL contém a contagem. Acima de 2.500.000/mL o código
# é ">28". Os limites não dobram exatamente (1,3; 2,5; 13; 25…), como na norma.
ISO4406_LIMITE_SUPERIOR = [
    (0, Decimal("0.01")), (1, Decimal("0.02")), (2, Decimal("0.04")), (3, Decimal("0.08")),
    (4, Decimal("0.16")), (5, Decimal("0.32")), (6, Decimal("0.64")), (7, Decimal("1.3")),
    (8, Decimal("2.5")), (9, Decimal("5")), (10, Decimal("10")), (11, Decimal("20")),
    (12, Decimal("40")), (13, Decimal("80")), (14, Decimal("160")), (15, Decimal("320")),
    (16, Decimal("640")), (17, Decimal("1300")), (18, Decimal("2500")), (19, Decimal("5000")),
    (20, Decimal("10000")), (21, Decimal("20000")), (22, Decimal("40000")), (23, Decimal("80000")),
    (24, Decimal("160000")), (25, Decimal("320000")), (26, Decimal("640000")), (27, Decimal("1300000")),
    (28, Decimal("2500000")),
]
ACIMA_DA_ESCALA = 29  # representa ">28"

# Tamanhos que formam o código (µm(c), contagem por mL): >4, >6 e >14.
TAMANHOS_CODIGO = ("P4", "P6", "P14")

ROTINA, ALERTA, CRITICA = "ROTINA", "ALERTA", "CRITICA"
ORDEM_STATUS = {None: -1, ROTINA: 0, ALERTA: 1, CRITICA: 2}


def _d(v):
    if v is None or v == "":
        return None
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError):
        return None


_GRAU_ISO_VG = re.compile(r"^\s*(?:ISO\s*)?(?:VG\s*)?(\d+(?:[.,]\d+)?)\s*$", re.IGNORECASE)


def grau_iso_vg(texto):
    """
    Viscosidade nominal a 40 °C (cSt) pelo grau ISO VG do fluido: "ISO VG 68",
    "VG 68", "ISO 68" ou "68" → 68. Outro formato (ex.: SAE 40) → None: o sistema
    não converte grau de outra escala.
    """
    m = _GRAU_ISO_VG.match(texto or "")
    return Decimal(m.group(1).replace(",", ".")) if m else None


def escala_iso4406(particulas_por_ml):
    """Número de escala ISO 4406 de uma contagem por mL (None sem contagem)."""
    n = _d(particulas_por_ml)
    if n is None or n < 0:
        return None
    for codigo, limite in ISO4406_LIMITE_SUPERIOR:
        if n <= limite:
            return codigo
    return ACIMA_DA_ESCALA


def texto_escala(r) -> str:
    if r is None:
        return "—"
    return ">28" if r == ACIMA_DA_ESCALA else str(r)


def codigo_iso4406(p4, p6, p14):
    """
    Código X/Y/Z (>4, >6 e >14 µm(c) por mL). Devolve (texto, [X, Y, Z]); sem as
    três contagens, (None, escalas parciais) — código incompleto não é inventado.
    Ex. (relatório Midori 2016, contagens por 100 mL ÷ 100): 16.127,07 / 11.760,71 /
    3.713,57 por mL → 21/21/19.
    """
    escalas = [escala_iso4406(p4), escala_iso4406(p6), escala_iso4406(p14)]
    if any(e is None for e in escalas):
        return None, escalas
    return "/".join(texto_escala(e) for e in escalas), escalas


def ler_codigo(texto):
    """'17/15/12' → [17, 15, 12]; '-/15/12' ou inválido → None."""
    partes = (texto or "").replace(" ", "").split("/")
    if len(partes) != 3:
        return None
    try:
        return [ACIMA_DA_ESCALA if p == ">28" else int(p) for p in partes]
    except ValueError:
        return None


def comparar_com_meta(escalas, meta):
    """
    Graus de código acima da meta (o pior dos três tamanhos). 0 ou negativo =
    dentro do alvo. None quando falta código ou meta.
    """
    if not escalas or meta is None or any(e is None for e in escalas):
        return None
    return max(o - m for o, m in zip(escalas, meta))


# ------------------------------ Referências ------------------------------
def classificar(*, tipo, valor=None, texto="", estado="MEDIDO", valor_base=None, limite_alerta=None,
                limite_critico=None, referencia_texto="", escalas=None):
    """
    Classifica um resultado pela referência cadastrada. Devolve
    {"status": ROTINA|ALERTA|CRITICA|None, "variacao_pct": Decimal|None, "excesso": int|None}.

    `None` quando a referência não tem o limite necessário ou não há valor — o
    sistema não decide sem critério.
    """
    saida = {"status": None, "variacao_pct": None, "excesso": None}
    alerta, critico, v = _d(limite_alerta), _d(limite_critico), _d(valor)

    if tipo == "CODIGO_ISO":
        excesso = comparar_com_meta(escalas, ler_codigo(referencia_texto))
        if excesso is None:
            return saida
        saida["excesso"] = excesso
        if excesso <= 0:
            saida["status"] = ROTINA
        elif critico is not None and excesso >= critico:
            saida["status"] = CRITICA
        elif alerta is None or excesso >= alerta:
            saida["status"] = ALERTA
        else:
            saida["status"] = ROTINA
        return saida

    if tipo == "QUALITATIVO":
        if not (texto or "").strip() or not (referencia_texto or "").strip():
            return saida
        iguais = texto.strip().casefold() == referencia_texto.strip().casefold()
        saida["status"] = ROTINA if iguais else ALERTA
        return saida

    if v is None:
        # Abaixo do limite de detecção/quantificação: atende a um máximo.
        if tipo == "MAXIMO" and estado in ("ABAIXO_LD", "ABAIXO_LQ", "NAO_DETECTADO") and (alerta or critico):
            saida["status"] = ROTINA
        return saida

    if tipo == "MAXIMO":
        if critico is None and alerta is None:
            return saida
        saida["status"] = CRITICA if critico is not None and v > critico else (
            ALERTA if alerta is not None and v > alerta else ROTINA)
    elif tipo == "MINIMO":
        if critico is None and alerta is None:
            return saida
        saida["status"] = CRITICA if critico is not None and v < critico else (
            ALERTA if alerta is not None and v < alerta else ROTINA)
    elif tipo == "VARIACAO":
        base = _d(valor_base)
        if not base:
            return saida
        variacao = (v - base) / base * Decimal("100")
        saida["variacao_pct"] = variacao.quantize(Decimal("0.1"))
        if critico is None and alerta is None:
            return saida
        absoluta = abs(variacao)
        saida["status"] = CRITICA if critico is not None and absoluta > critico else (
            ALERTA if alerta is not None and absoluta > alerta else ROTINA)
    return saida


def pior(statuses):
    """Status mais grave de uma lista (Crítica > Alerta > Rotina); None se nenhum."""
    melhor = None
    for s in statuses:
        if ORDEM_STATUS.get(s, -1) > ORDEM_STATUS.get(melhor, -1):
            melhor = s
    return melhor


# ------------------------------- Tendência -------------------------------
def tendencia(valores):
    """
    Variação do último valor em relação ao anterior e ao primeiro da série
    (só valores numéricos, em ordem cronológica). Um único valor não tem tendência.
    """
    numeros = [_d(v) for v in valores if _d(v) is not None]
    if len(numeros) < 2:
        return None
    atual, anterior, primeiro = numeros[-1], numeros[-2], numeros[0]

    def pct(a, b):
        return ((a - b) / b * Decimal("100")).quantize(Decimal("0.1")) if b else None

    delta = atual - anterior
    return {
        "delta_anterior": delta,
        "pct_anterior": pct(atual, anterior),
        "pct_primeiro": pct(atual, primeiro),
        "direcao": "SOBE" if delta > 0 else "DESCE" if delta < 0 else "ESTAVEL",
        "pontos": len(numeros),
    }
