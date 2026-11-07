"""Qualidade de energia — Anexo I 2.3.2.10 (ficha, grandezas e critério).

Três grandezas, cada uma em %, lidas separadamente (`MedicaoTecnica`, tipo QUALIDADE_ENERGIA):
- "THD de tensão" (distorção harmônica total de tensão);
- "THD de corrente" (distorção harmônica total de corrente);
- "Desequilíbrio de tensão".

Ficha (`parametros`):
- `janela_agregacao` (obrigatório): janela e critério de agregação do analisador (ex.: "10 min",
  "95 %"). Sem ela, os percentis e médias não são comparáveis;
- `fase` (opcional): fase de medição (R, S, T ou trifásico);
- `tensao_nominal_v` (opcional, > 0).

Classificação: só com `preditiva.LimiteAlarmeSerie` VALIDADO da grandeza, sentido superior
(valor acima do limite é pior). Sem critério, PENDENTE. Não há limiar universal de THD ou de
desequilíbrio aqui; o limite vem do cadastro do cliente, com a norma que ele adotar.
Esta ficha não constitui estudo completo de qualidade de energia (sem série temporal).
"""
from decimal import Decimal, InvalidOperation

GRANDEZAS = ("THD de tensão", "THD de corrente", "Desequilíbrio de tensão")
UNIDADE = "%"


def _decimal(valor):
    if valor is None or isinstance(valor, bool):
        return None
    try:
        numero = Decimal(str(valor).replace(",", "."))
    except (InvalidOperation, ValueError):
        return None
    return numero if numero.is_finite() else None


def validar_ficha(parametros: dict) -> dict:
    """Erros da ficha de qualidade de energia (vazio = válida)."""
    erros = {}
    if not str(parametros.get("janela_agregacao") or "").strip():
        erros["janela_agregacao"] = "Informe a janela e o critério de agregação do analisador (ex.: 10 min, 95 %)."
    tensao = parametros.get("tensao_nominal_v")
    if tensao not in (None, "") and (_decimal(tensao) is None or _decimal(tensao) <= 0):
        erros["tensao_nominal_v"] = "A tensão nominal, quando informada, deve ser maior que zero (V)."
    return erros


def classificar_superior(valor, limites: dict):
    """Condição de uma grandeza de qualidade (sentido superior). Sem critério validado → PENDENTE."""
    valor = _decimal(valor)
    alerta, critico = _decimal(limites.get("ALERTA")), _decimal(limites.get("CRITICO"))
    if valor is None or (alerta is None and critico is None):
        return "PENDENTE"
    if critico is not None and valor >= critico:
        return "CRITICO"
    if alerta is not None and valor >= alerta:
        return "ALERTA"
    return "NORMAL"


def ultimas_leituras(cliente_id, equipamento_id, ate):
    """{grandeza: medição mais recente até `ate`} das três grandezas. Não grava nada."""
    from .models import MedicaoTecnica, TipoAnalise

    qs = MedicaoTecnica.objects.filter(
        tipo=TipoAnalise.QUALIDADE_ENERGIA, equipamento_id=equipamento_id, inspecao__cliente_id=cliente_id,
        grandeza__in=GRANDEZAS,
    ).select_related("inspecao")
    if ate is not None:
        qs = qs.filter(inspecao__data__lte=ate)
    ultimas = {}
    for m in qs.order_by("-data_hora", "-pk"):
        ultimas.setdefault(m.grandeza, m)
    return ultimas
