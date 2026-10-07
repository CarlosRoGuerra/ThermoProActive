"""
Motor de regras da Análise de Vibração — Anexo I 2.3.2.1 e 2.4 (Análise Preditiva).

Implementa a classificação de severidade por zona ISO 10816/20816 e o diagnóstico
assistido (item 2.4.2.3). Os limiares ficam nesta tabela única para serem facilmente
parametrizados pelo cliente (Cláusula 12.4 — sem regra "escondida" em código espalhado).

Ver detalhamento em docs/01-DISCOVERY-modulos-tecnicos.md (§2 e §3).
"""
from dataclasses import dataclass
from decimal import Decimal
from statistics import mean

# Limite SUPERIOR de velocidade RMS (mm/s) de cada zona, por classe.
# zona D = acima do limite da zona C.
#
# A fonte de verdade é o cadastro `CriterioSeveridadeVibracao` (perfil normativo,
# com norma, edição, origem e vigência — `apps.cadastros.criterios`). Esta tabela
# é só o valor de reserva quando o banco não tem critério (e a carga inicial do
# cadastro). Origem de cada número:
#   - Classes I, III e IV e os limites A/B e C/D da Classe II: ISO 10816-1:1995,
#     Anexo B (norma substituída pela ISO 20816-1:2016).
#   - Classe II, B/C = 4,49 mm/s: ACORDO COM O CLIENTE (confirmado em 2026-09-16);
#     a ISO 10816-1 publica 2,80 mm/s. Não é valor da norma.
FAIXAS_ISO_VRMS = {
    "I":   {"A": Decimal("0.71"), "B": Decimal("1.80"), "C": Decimal("4.50")},
    "II":  {"A": Decimal("1.12"), "B": Decimal("4.49"), "C": Decimal("7.10")},
    "III": {"A": Decimal("1.80"), "B": Decimal("4.50"), "C": Decimal("11.20")},
    "IV":  {"A": Decimal("2.80"), "B": Decimal("7.10"), "C": Decimal("18.00")},
    # ISO 20816-3:2022, zonas da fundação flexível aplicadas ao grupo inteiro —
    # critério do responsável técnico (07/10/2026): crítico acima de 7,1 (Grupo 2)
    # e de 11,0 mm/s (Grupo 1).
    "G2":  {"A": Decimal("2.30"), "B": Decimal("4.50"), "C": Decimal("7.10")},
    "G1":  {"A": Decimal("3.50"), "B": Decimal("7.10"), "C": Decimal("11.00")},
}

# Zona ISO → criticidade base
ZONA_PARA_CRITICIDADE = {
    "A": "NORMAL",
    "B": "NORMAL",
    "C": "ALERTA",
    "D": "CRITICO",
}

CRITICIDADE_ORDEM = ["NORMAL", "ALERTA", "CRITICO"]

# Limiar do fator de crista para suspeita de defeito de rolamento (item 2.3.2.1.1).
FATOR_CRISTA_ALERTA = Decimal("5.0")
# Fator de evolução: vibração atual acima deste múltiplo da média histórica eleva o nível.
FATOR_EVOLUCAO = Decimal("1.5")


@dataclass
class ResultadoVibracao:
    zona_iso: str
    criticidade: str
    diagnostico: str


def _zona_por_vrms(classe_iso: str, vrms: Decimal, faixas: dict | None = None) -> str:
    # Sem classe (ou classe desconhecida) o legado avalia pela Classe II — o
    # diagnóstico diz isso (ver `classificar_vibracao`), nunca em silêncio.
    faixa = faixas or FAIXAS_ISO_VRMS.get(classe_iso, FAIXAS_ISO_VRMS["II"])
    if vrms <= faixa["A"]:
        return "A"
    if vrms <= faixa["B"]:
        return "B"
    if vrms <= faixa["C"]:
        return "C"
    return "D"


def _eleva(criticidade: str, niveis: int = 1) -> str:
    idx = min(CRITICIDADE_ORDEM.index(criticidade) + niveis, len(CRITICIDADE_ORDEM) - 1)
    return CRITICIDADE_ORDEM[idx]


def classificar_vibracao(
    classe_iso: str,
    velocidade_rms: Decimal,
    fator_crista: Decimal | None = None,
    historico_vrms: list[Decimal] | None = None,
    faixas: dict | None = None,
) -> ResultadoVibracao:
    """
    Classifica uma medição de vibração.

    Args:
        classe_iso: classe ISO do equipamento (I–IV).
        velocidade_rms: velocidade RMS global em mm/s.
        fator_crista: fator de crista (opcional) — alta = impactos/rolamento.
        historico_vrms: Vrms das medições anteriores do mesmo ponto (mais recentes).
        faixas: limites {A, B, C} do critério vigente (`apps.cadastros.criterios`);
            sem eles, `FAIXAS_ISO_VRMS`.
    """
    zona = _zona_por_vrms(classe_iso, velocidade_rms, faixas)
    criticidade = ZONA_PARA_CRITICIDADE[zona]
    diagnosticos = []

    # Regra de evolução (tendência — itens 2.4.1.2 / 2.4.1.3)
    if historico_vrms:
        media_hist = Decimal(mean(historico_vrms))
        if media_hist > 0 and velocidade_rms > media_hist * FATOR_EVOLUCAO:
            criticidade = _eleva(criticidade)
            diagnosticos.append(
                f"Tendência de agravamento: {velocidade_rms} mm/s > "
                f"{FATOR_EVOLUCAO}× a média histórica ({media_hist:.2f} mm/s)."
            )

    # Diagnóstico assistido (item 2.4.2.3)
    if fator_crista is not None and fator_crista > FATOR_CRISTA_ALERTA:
        diagnosticos.append(
            f"Fator de crista {fator_crista} > {FATOR_CRISTA_ALERTA}: "
            "possível defeito incipiente de rolamento."
        )
        if criticidade == "NORMAL":
            criticidade = "ALERTA"

    base = {
        "A": "Vibração na zona A (equipamento em ótima condição).",
        "B": "Vibração na zona B (operação contínua aceitável).",
        "C": "Vibração na zona C (tolerável — recomenda-se monitoramento próximo).",
        "D": "Vibração na zona D (inadmissível — risco de dano; intervenção recomendada).",
    }[zona]
    diagnosticos.insert(0, base)
    if not faixas and classe_iso not in FAIXAS_ISO_VRMS:
        diagnosticos.insert(1, "Classe da máquina não definida no cadastro: avaliado pelos limites da Classe II.")

    return ResultadoVibracao(
        zona_iso=zona,
        criticidade=criticidade,
        diagnostico=" ".join(diagnosticos),
    )


# =============================================================================
# Termografia infravermelha — Anexo I 2.3.2.2.
# Classificação por ΔT (ponto quente vs. ponto de referência), limiares
# NBR 15572 / NETA. Limiares parametrizáveis (Cláusula 12.4).
# Ver docs/01-DISCOVERY-modulos-tecnicos.md.
# =============================================================================

# ΔT (°C) sobre a referência:
TERMO_DELTA_ALERTA = Decimal("3")    # 4–15°C: provável deficiência → reparo programado
TERMO_DELTA_CRITICO = Decimal("15")  # > 15°C: discrepância grave → reparo imediato


@dataclass
class ResultadoTermografia:
    delta_t: Decimal
    criticidade: str
    diagnostico: str


def classificar_termografia(
    temperatura_ponto: Decimal, temperatura_referencia: Decimal
) -> ResultadoTermografia:
    """Classifica uma medição termográfica pelo ΔT em relação à referência."""
    delta = temperatura_ponto - temperatura_referencia

    if delta > TERMO_DELTA_CRITICO:
        criticidade = "CRITICO"
        recomendacao = "Discrepância grave: reparo corretivo imediato recomendado."
    elif delta > TERMO_DELTA_ALERTA:
        criticidade = "ALERTA"
        recomendacao = "Provável deficiência: programar reparo na próxima oportunidade."
    else:
        criticidade = "NORMAL"
        recomendacao = "Dentro do esperado: manter monitoramento periódico."

    diagnostico = (
        f"ΔT = {delta:.1f}°C (ponto {temperatura_ponto}°C / referência "
        f"{temperatura_referencia}°C). {recomendacao}"
    )
    return ResultadoTermografia(delta_t=delta, criticidade=criticidade, diagnostico=diagnostico)
