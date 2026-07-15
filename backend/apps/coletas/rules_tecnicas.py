"""
Motor de regras das demais análises técnicas — Anexo I 2.3.2.3 a 2.3.2.10.

Arquitetura genérica: cada tipo de análise tem um "modo" de classificação e limiares
parametrizáveis (Cláusula 12.4 — nada de regra escondida). Cobre:
  Fluidos, Ensaios Elétricos (transformadores/motores), Ultrassom, Espessura,
  Qualidade de Energia, Sensitiva e Manutenção Corretiva (alinhamento/balanceamento).

Vibração (2.3.2.1) e Termografia (2.3.2.2) têm motores dedicados em rules.py.
Ver detalhamento de faixas em docs/01-DISCOVERY-modulos-tecnicos.md.
"""
from dataclasses import dataclass
from decimal import Decimal


@dataclass
class ResultadoTecnico:
    criticidade: str
    diagnostico: str


def _d(v) -> Decimal:
    return Decimal(str(v))


# Limiares por tipo (parametrizáveis). "modo" define como a leitura vira criticidade.
LIMIARES = {
    # Maior é pior (acima do limite = pior). Ex.: THD%, dB acima da linha de base.
    "ULTRASSOM": {"modo": "maior_pior", "alerta": _d("6"), "critico": _d("12"), "unidade": "dB"},
    "QUALIDADE_ENERGIA": {"modo": "maior_pior", "alerta": _d("5"), "critico": _d("8"), "unidade": "%"},
    "CORRETIVA": {"modo": "maior_pior", "alerta": _d("0.05"), "critico": _d("0.10"), "unidade": "mm/100mm"},
    # Perda percentual em relação à referência (espessura nominal).
    "ESPESSURA": {"modo": "perda_percentual", "alerta": _d("10"), "critico": _d("20"), "unidade": "mm"},
    # Desvio percentual em relação à referência (fluido saudável).
    "FLUIDOS": {"modo": "desvio_referencia", "alerta": _d("20"), "critico": _d("50")},
}

# Ensaios elétricos: isolação (MΩ, maior é melhor) — limites mínimos.
ISOLACAO_MIN_CRITICO = _d("100")   # < 100 MΩ → crítico
ISOLACAO_MIN_ALERTA = _d("1000")   # < 1000 MΩ → alerta
# Índice de polarização (IEEE 43): >= 2 bom, 1–2 questionável, < 1 ruim.
PI_ALERTA = _d("2.0")
PI_CRITICO = _d("1.0")


def _por_limiar(valor: Decimal, alerta: Decimal, critico: Decimal) -> str:
    if valor >= critico:
        return "CRITICO"
    if valor >= alerta:
        return "ALERTA"
    return "NORMAL"


def _ensaio_eletrico(grandeza: str, valor: Decimal, ref, parametros: dict) -> ResultadoTecnico:
    g = (grandeza or "").lower()
    pi = parametros.get("indice_polarizacao") if parametros else None

    if pi is not None:
        pi = _d(pi)
        if pi < PI_CRITICO:
            return ResultadoTecnico("CRITICO", f"Índice de polarização {pi} < {PI_CRITICO}: isolação deteriorada (IEEE 43).")
        if pi < PI_ALERTA:
            return ResultadoTecnico("ALERTA", f"Índice de polarização {pi} entre {PI_CRITICO} e {PI_ALERTA}: monitorar isolação.")
        return ResultadoTecnico("NORMAL", f"Índice de polarização {pi} ≥ {PI_ALERTA}: isolação em boas condições.")

    if "isola" in g:  # Resistência de isolação (MΩ) — maior é melhor
        if valor < ISOLACAO_MIN_CRITICO:
            return ResultadoTecnico("CRITICO", f"Resistência de isolação {valor} MΩ abaixo do mínimo ({ISOLACAO_MIN_CRITICO} MΩ).")
        if valor < ISOLACAO_MIN_ALERTA:
            return ResultadoTecnico("ALERTA", f"Resistência de isolação {valor} MΩ em nível de atenção.")
        return ResultadoTecnico("NORMAL", f"Resistência de isolação {valor} MΩ adequada.")

    # TTR / resistência ôhmica: desvio percentual vs. referência.
    if ref:
        desvio = abs(valor - _d(ref)) / _d(ref) * 100
        crit = _por_limiar(desvio, _d("1"), _d("2"))
        return ResultadoTecnico(crit, f"Desvio de {desvio:.2f}% em relação à referência ({ref}).")
    return ResultadoTecnico("NORMAL", f"Leitura registrada: {valor}.")


def classificar_tecnica(tipo: str, grandeza: str, valor, valor_referencia=None, parametros=None) -> ResultadoTecnico:
    """Classifica uma medição técnica genérica conforme o tipo de análise."""
    valor = _d(valor)
    parametros = parametros or {}

    if tipo == "ENSAIO_ELETRICO":
        return _ensaio_eletrico(grandeza, valor, valor_referencia, parametros)

    if tipo == "SENSITIVA":
        # Inspeção sensorial: criticidade informada pelo técnico (default Normal).
        crit = (parametros.get("criticidade") or "NORMAL").upper()
        if crit not in ("NORMAL", "ALERTA", "CRITICO"):
            crit = "NORMAL"
        return ResultadoTecnico(crit, parametros.get("observacao") or "Inspeção sensitiva registrada.")

    cfg = LIMIARES.get(tipo)
    if not cfg:
        return ResultadoTecnico("NORMAL", f"Leitura registrada: {valor} {grandeza}.")

    modo = cfg["modo"]
    if modo == "maior_pior":
        crit = _por_limiar(valor, cfg["alerta"], cfg["critico"])
        un = cfg.get("unidade", "")
        return ResultadoTecnico(crit, f"{grandeza}: {valor} {un} (alerta ≥ {cfg['alerta']}, crítico ≥ {cfg['critico']} {un}).")

    if modo == "perda_percentual" and valor_referencia:
        ref = _d(valor_referencia)
        perda = (ref - valor) / ref * 100 if ref else _d("0")
        crit = _por_limiar(perda, cfg["alerta"], cfg["critico"])
        return ResultadoTecnico(crit, f"Perda de {perda:.1f}% em relação à referência ({ref}).")

    if modo == "desvio_referencia" and valor_referencia:
        ref = _d(valor_referencia)
        desvio = abs(valor - ref) / ref * 100 if ref else _d("0")
        crit = _por_limiar(desvio, cfg["alerta"], cfg["critico"])
        return ResultadoTecnico(crit, f"Desvio de {desvio:.1f}% em relação à referência ({ref}).")

    return ResultadoTecnico("NORMAL", f"Leitura registrada: {valor} {grandeza}.")
