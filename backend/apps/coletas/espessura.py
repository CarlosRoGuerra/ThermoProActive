"""Medição de espessura — Anexo I 2.3.2.7 (ficha e cálculos).

Aritmética sem critério normativo embutido:
- perda (%) = (espessura nominal − espessura medida) / espessura nominal × 100;
- taxa de corrosão (mm/ano) = (espessura anterior − espessura atual) / (dias / 365,25),
  com a leitura anterior da MESMA série comparável (mesmo ponto, instrumento e
  material/malha). Taxa positiva = perda de espessura; negativa = aumento, que
  indica erro de medição ou mudança de ponto e é sinalizada, não corrigida.

A classificação (NORMAL/ALERTA/CRITICO) só existe com limite cadastrado e validado
(`preditiva.LimiteAlarmeSerie`, sentido INFERIOR: espessura abaixo do limite é pior).
Sem ele, a condição permanece PENDENTE. Nenhum valor mínimo de projeto é assumido.
"""
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

DIAS_POR_ANO = Decimal("365.25")
CAMPOS_FICHA = ("material", "espessura_nominal_mm")


def _decimal(valor):
    if valor is None or isinstance(valor, bool):
        return None
    try:
        numero = Decimal(str(valor))
    except (InvalidOperation, ValueError):
        return None
    return numero if numero.is_finite() else None


def validar_ficha(parametros: dict) -> dict:
    """Erros da ficha de espessura por campo (vazio = válida). Não altera o dicionário."""
    erros = {}
    if not str(parametros.get("material") or "").strip():
        erros["material"] = "Informe o material da peça (ex.: aço carbono ASTM A36)."
    nominal = _decimal(parametros.get("espessura_nominal_mm"))
    if nominal is None or nominal <= 0:
        erros["espessura_nominal_mm"] = "Informe a espessura nominal em mm, maior que zero."
    return erros


def perda_percentual(nominal, medida):
    """Perda em % sobre a nominal. None se a nominal não for positiva ou faltar algum valor."""
    nominal, medida = _decimal(nominal), _decimal(medida)
    if nominal is None or medida is None or nominal <= 0:
        return None
    return ((nominal - medida) / nominal * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def taxa_corrosao(anterior, atual, dias):
    """Taxa em mm/ano entre duas leituras. None se faltar dado ou o intervalo não for positivo."""
    anterior, atual, dias = _decimal(anterior), _decimal(atual), _decimal(dias)
    if anterior is None or atual is None or dias is None or dias <= 0:
        return None
    anos = dias / DIAS_POR_ANO
    return ((anterior - atual) / anos).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def dias_entre(anterior_dt, atual_dt):
    """Dias reais (fração) entre dois instantes; None se algum faltar."""
    if anterior_dt is None or atual_dt is None:
        return None
    delta: timedelta = atual_dt - anterior_dt
    return Decimal(delta.days) + Decimal(delta.seconds) / Decimal(86400)


def classificar(medida, limites: dict):
    """Condição pela espessura. `limites` = {"ALERTA": x, "CRITICO": y} (sentido INFERIOR).

    Sem limite (ou medida ausente) → PENDENTE, sem classe.
    """
    medida = _decimal(medida)
    alerta, critico = _decimal(limites.get("ALERTA")), _decimal(limites.get("CRITICO"))
    if medida is None or (alerta is None and critico is None):
        return "PENDENTE"
    if critico is not None and medida <= critico:
        return "CRITICO"
    if alerta is not None and medida <= alerta:
        return "ALERTA"
    return "NORMAL"
