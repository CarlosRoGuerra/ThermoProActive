"""
Motor de regras da Análise de Vibração — Anexo I 2.3.2.1 e 2.4 (Análise Preditiva).

Implementa a classificação de severidade por zona ISO 10816/20816 e o diagnóstico
assistido (item 2.4.2.3). Os limiares ficam nesta tabela única para serem facilmente
parametrizados pelo cliente (Cláusula 12.4 — sem regra "escondida" em código espalhado).

Ver detalhamento em docs/01-DISCOVERY-modulos-tecnicos.md (§2 e §3).
"""
from dataclasses import dataclass
from decimal import Decimal

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
    # ISO 20816-3:2022 (Tabelas A.1 e A.2) — reserva pela base RÍGIDA, a mais
    # rigorosa (máquina sem o tipo de base informado). Os critérios cadastrados
    # separam rígida e flexível e trazem o deslocamento (µm RMS).
    "G2":  {"A": Decimal("1.40"), "B": Decimal("2.80"), "C": Decimal("4.50")},
    "G1":  {"A": Decimal("2.30"), "B": Decimal("4.50"), "C": Decimal("7.10")},
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


ZONAS = "ABCD"


def _zona(valor: Decimal, faixa: dict) -> str:
    if valor <= faixa["A"]:
        return "A"
    if valor <= faixa["B"]:
        return "B"
    if valor <= faixa["C"]:
        return "C"
    return "D"


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
    deslocamento: Decimal | None = None,
    avisos: tuple = (),
    fator_evolucao: Decimal | None = None,
) -> ResultadoVibracao:
    """
    Classifica uma medição de vibração.

    Args:
        classe_iso: classe ISO do equipamento (I–IV).
        velocidade_rms: velocidade RMS global em mm/s.
        fator_crista: fator de crista (opcional) — alta = impactos/rolamento.
        historico_vrms: Vrms das medições anteriores do mesmo ponto (mais recentes).
        faixas: limites {A, B, C} do critério vigente (`apps.cadastros.criterios`);
            sem eles, `FAIXAS_ISO_VRMS`. Pode trazer "deslocamento": {A, B, C} (µm RMS).
        deslocamento: deslocamento RMS global (µm). Com limites de deslocamento no
            critério, a zona é a PIOR entre velocidade e deslocamento (ISO 20816-3).
        avisos: observações do cadastro para o diagnóstico (ex.: base não informada).
    """
    from .analise_preditiva import numero_finito

    velocidade_rms = numero_finito(velocidade_rms)
    if velocidade_rms is None or velocidade_rms < 0:
        return ResultadoVibracao("", "", "Leitura ausente ou inválida; avaliação inconclusiva.")
    if faixas is not None:
        limites = [numero_finito(faixas.get(zona)) for zona in "ABC"]
        if any(v is None or v < 0 for v in limites) or not (limites[0] <= limites[1] <= limites[2]):
            return ResultadoVibracao("", "", "Limites inválidos; avaliação inconclusiva.")
    zona = _zona_por_vrms(classe_iso, velocidade_rms, faixas)
    zona_desloc = None
    if deslocamento is not None and faixas and faixas.get("deslocamento"):
        zona_desloc = _zona(Decimal(deslocamento), faixas["deslocamento"])
        if ZONAS.index(zona_desloc) > ZONAS.index(zona):
            zona = zona_desloc
    criticidade = ZONA_PARA_CRITICIDADE[zona]
    diagnosticos = []

    # Regra de evolução (tendência — itens 2.4.1.2 / 2.4.1.3)
    historico_valido = [numero_finito(v) for v in historico_vrms or []]
    fator_evolucao = numero_finito(fator_evolucao)
    if historico_valido and all(v is not None and v >= 0 for v in historico_valido) and fator_evolucao is not None and fator_evolucao > 1:
        media_hist = sum(historico_valido) / len(historico_valido)
        if media_hist > 0 and velocidade_rms > media_hist * fator_evolucao:
            criticidade = _eleva(criticidade)
            diagnosticos.append(
                f"Tendência de agravamento: {velocidade_rms} mm/s > "
                f"{fator_evolucao}× a média histórica ({media_hist:.2f} mm/s). "
                "Elevação por procedimento configurado; não confirma causa de falha."
            )

    # Diagnóstico assistido (item 2.4.2.3)
    fator_crista = numero_finito(fator_crista)
    if fator_crista is not None and fator_crista > FATOR_CRISTA_ALERTA:
        diagnosticos.append(
            f"Fator de crista {fator_crista} > {FATOR_CRISTA_ALERTA}: "
            "possível defeito incipiente de rolamento."
        )
        if criticidade == "NORMAL":
            criticidade = "ALERTA"

    base = (
        f"Velocidade RMS na zona {zona} do critério aplicado. "
        "A classificação da leitura não identifica a causa de falha; "
        "diagnóstico e recomendação dependem de avaliação técnica."
    )
    diagnosticos.insert(0, base)
    if zona_desloc is not None:
        diagnosticos.insert(1, f"Deslocamento {deslocamento} µm na zona {zona_desloc}.")
    diagnosticos.extend(avisos)
    if not faixas and classe_iso not in FAIXAS_ISO_VRMS:
        diagnosticos.insert(1, "Classe da máquina não definida no cadastro: avaliado pelos limites da Classe II.")

    return ResultadoVibracao(
        zona_iso=zona,
        criticidade=criticidade,
        diagnostico=" ".join(diagnosticos),
    )


# =============================================================================
# Termografia infravermelha — Anexo I 2.3.2.2.
# O ΔT é aritmético. Sem confirmação de referência, aplicação e critério por
# sistema, não é suficiente para classificar uma condição ou recomendar reparo.
# =============================================================================

@dataclass
class ResultadoTermografia:
    delta_t: Decimal | None
    criticidade: str
    diagnostico: str


def classificar_termografia(
    temperatura_ponto: Decimal, temperatura_referencia: Decimal
) -> ResultadoTermografia:
    """Registra o ΔT, mantendo a decisão técnica pendente de critério aplicável."""
    from .analise_preditiva import numero_finito
    temperatura_ponto, temperatura_referencia = numero_finito(temperatura_ponto), numero_finito(temperatura_referencia)
    if temperatura_ponto is None or temperatura_referencia is None:
        return ResultadoTermografia(None, "", "Temperaturas ausentes ou inválidas; avaliação inconclusiva.")
    delta = temperatura_ponto - temperatura_referencia
    diagnostico = (
        f"ΔT = {delta:.1f}°C (ponto {temperatura_ponto}°C / referência "
        f"{temperatura_referencia}°C). Classificação pendente de critério específico validado."
    )
    return ResultadoTermografia(delta_t=delta, criticidade="", diagnostico=diagnostico)
