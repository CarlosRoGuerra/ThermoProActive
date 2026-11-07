"""Ultrassom elétrico e mecânico — Anexo I 2.3.2.6 (ficha, leitura e critério).

Ficha (`MedicaoTecnica`, tipo ULTRASSOM, subtipo ELETRICO ou MECANICO, unidade em dB):
- `ganho_db` (obrigatório): ganho do instrumento na leitura;
- `distancia_cm` (obrigatório, ≥ 0): distância do sensor à fonte;
- `frequencia_khz` (opcional): faixa/frequência de sintonia, quando o instrumento a registra;
- `tipo_evidencia` (opcional): ex.: ruído, descarga, vazamento, atrito.

Níveis em dB de instrumentos ou ajustes diferentes não são comparáveis. Por isso o
ganho e a distância entram no contexto da série (`contexto_medicao`), e a grandeza
separa o elétrico do mecânico (cada um tem o seu critério).

Classificação: só com `preditiva.LimiteAlarmeSerie` VALIDADO, sentido SUPERIOR (nível
acima do limite é pior), grandeza igual à da medição. Sem critério, PENDENTE. Não há
limite universal em dB.
"""
from decimal import Decimal, InvalidOperation

SUBTIPOS = ("ELETRICO", "MECANICO")
GRANDEZA_POR_SUBTIPO = {
    "ELETRICO": "Nível de ultrassom elétrico",
    "MECANICO": "Nível de ultrassom mecânico",
}


def _decimal(valor):
    if valor is None or isinstance(valor, bool):
        return None
    try:
        numero = Decimal(str(valor).replace(",", "."))
    except (InvalidOperation, ValueError):
        return None
    return numero if numero.is_finite() else None


def validar_ficha(parametros: dict) -> dict:
    """Erros da ficha de ultrassom (vazio = válida)."""
    erros = {}
    if _decimal(parametros.get("ganho_db")) is None:
        erros["ganho_db"] = "Informe o ganho do instrumento em dB: a leitura só é comparável com o mesmo ganho."
    distancia = _decimal(parametros.get("distancia_cm"))
    if distancia is None or distancia < 0:
        erros["distancia_cm"] = "Informe a distância do sensor à fonte em cm (zero ou maior)."
    frequencia = parametros.get("frequencia_khz")
    if frequencia not in (None, "") and (_decimal(frequencia) is None or _decimal(frequencia) <= 0):
        erros["frequencia_khz"] = "A frequência, quando informada, deve ser maior que zero (kHz)."
    return erros


def classificar_superior(valor, limites: dict):
    """Condição de um nível de ultrassom. `limites` = {"ALERTA": x, "CRITICO": y} (sentido SUPERIOR).

    Sem critério validado (ou valor ausente) → PENDENTE.
    """
    valor = _decimal(valor)
    alerta, critico = _decimal(limites.get("ALERTA")), _decimal(limites.get("CRITICO"))
    if valor is None or (alerta is None and critico is None):
        return "PENDENTE"
    if critico is not None and valor >= critico:
        return "CRITICO"
    if alerta is not None and valor >= alerta:
        return "ALERTA"
    return "NORMAL"


def ultima_leitura(cliente_id, equipamento_id, ate):
    """Última leitura de ultrassom do equipamento até `ate` (data), ou None. Não grava nada."""
    from .models import MedicaoTecnica, TipoAnalise

    qs = MedicaoTecnica.objects.filter(
        tipo=TipoAnalise.ULTRASSOM, equipamento_id=equipamento_id, inspecao__cliente_id=cliente_id,
    ).select_related("inspecao")
    if ate is not None:
        qs = qs.filter(inspecao__data__lte=ate)
    return qs.order_by("-data_hora", "-pk").first()
