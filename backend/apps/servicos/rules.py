"""
Motor de cálculo dos Serviços de Campo — Anexo I 2.3.2.8 (Manutenção Corretiva).

Substitui as duas planilhas do Fabrício:
  · `Planilha Balanceamentos.xlsx`  → balanceamento dinâmico (1 ou 2 planos)
  · `Economia Geradas com Alinhamentos e Balanceamentos.xlsx` → economia energética

Funções puras, sem Django e sem I/O: os `save()` dos modelos chamam daqui, e a mesma
conta pode ser testada isoladamente contra os números da planilha (ver tests.py).
Todas as constantes ficam no topo deste arquivo (Cláusula 12.4 — sem regra escondida).

Ver decodificação célula a célula em docs/04-DISCOVERY-balanceamento-e-economia.md.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from apps.coletas import rules as rules_vibracao

# √3 do sistema trifásico. A planilha usa a constante literal 1,732 (`B5`); aqui é
# calculado — a diferença aparece a partir da 4ª casa (≈ R$ 0,22/ano no exemplo).
RAIZ_TRES = Decimal(3).sqrt()

# NENHUM valor de campo tem default aqui (decisão do Fabrício, 08/09/2026): tensão,
# correntes, fator de potência, regime de operação, custo do kWh e custo do serviço são
# TODOS coletados na hora, medidos naquele equipamento naquele dia. Um default silencioso
# (FP 0,93, 365 dias/ano, custo 0) produziria um número plausível que ninguém mediu — o
# tipo de erro que não aparece na revisão e chega ao relatório assinado. Por isso
# `calcular_economia` exige todos os argumentos e falha alto se faltar algum.
#
# O que sobra abaixo são REGRAS de classificação e constantes matemáticas — não são
# dados de campo e continuam parametrizadas aqui (Cláusula 12.4).

#: Redução mínima (%) para o balanceamento ser considerado eficaz. Abaixo disso o
#: serviço reduziu pouco e a causa provavelmente não é desbalanceamento puro.
REDUCAO_MINIMA_ACEITAVEL = Decimal("50")

#: Marcação do mostrador polar: 12 setores de 30°, como no gráfico de rosca da planilha.
SETORES_MOSTRADOR = 12
GRAUS_POR_SETOR = 30


def _d(v) -> Decimal:
    """Converte para Decimal aceitando str/int/float/Decimal (None vira erro claro)."""
    if isinstance(v, Decimal):
        return v
    try:
        return Decimal(str(v))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"Valor numérico inválido: {v!r}") from exc


# =============================================================================
# Balanceamento
# =============================================================================


@dataclass
class ResultadoBalanceamento:
    """Resultado de UM ponto de medição (mancal + direção) após as três corridas."""

    residual_pct: Decimal      # vibração que sobrou, em % da inicial (planilha: J6)
    reducao_pct: Decimal       # ganho obtido, em %                    (planilha: J7)
    zona_iso: str              # zona ISO 10816/20816 do resultado final
    criticidade: str           # NORMAL / ALERTA / CRITICO
    eficaz: bool               # redução ≥ REDUCAO_MINIMA_ACEITAVEL
    diagnostico: str


def calcular_reducao(reference_mms, trim_mms) -> tuple[Decimal, Decimal]:
    """
    Curva de redução da planilha (bloco `CURVA REDUÇÃO (x100%)`):

        residual = trim / reference        (J6 = G6 * I6 / C6, com I6 = 1)
        redução  = 1 - residual            (J7 = I6 - J6)

    Devolve (residual_pct, reducao_pct) em pontos percentuais.
    """
    reference = _d(reference_mms)
    trim = _d(trim_mms)
    if reference <= 0:
        raise ValueError("A vibração de referência (reference run) deve ser maior que zero.")
    residual = trim / reference * 100
    return residual, 100 - residual


def avaliar_ponto(classe_iso: str, reference_mms, trim_mms) -> ResultadoBalanceamento:
    """
    Avalia um ponto: quanto reduziu **e** se o resultado final está dentro da norma.

    A planilha só responde a primeira metade ("reduziu 86,2%"). A segunda vem do motor
    de vibração que já existe (`apps.coletas.rules`): 1,70 mm/s numa máquina classe II
    é zona B — ou seja, o serviço não só reduziu, como entregou a máquina aprovada.
    """
    residual_pct, reducao_pct = calcular_reducao(reference_mms, trim_mms)
    vibracao = rules_vibracao.classificar_vibracao(
        classe_iso=classe_iso, velocidade_rms=_d(trim_mms)
    )
    eficaz = reducao_pct >= REDUCAO_MINIMA_ACEITAVEL

    partes = [
        f"Vibração reduzida de {_d(reference_mms):.2f} para {_d(trim_mms):.2f} mm/s "
        f"({reducao_pct:.1f}% de redução; {residual_pct:.1f}% residual)."
    ]
    partes.append(
        f"Resultado final em zona {vibracao.zona_iso} (ISO 10816/20816, classe {classe_iso})."
    )
    if not eficaz:
        partes.append(
            f"Redução abaixo do mínimo esperado ({REDUCAO_MINIMA_ACEITAVEL}%) — "
            "avaliar se há causa concorrente ao desbalanceamento."
        )

    return ResultadoBalanceamento(
        residual_pct=residual_pct,
        reducao_pct=reducao_pct,
        zona_iso=vibracao.zona_iso,
        criticidade=vibracao.criticidade,
        eficaz=eficaz,
        diagnostico=" ".join(partes),
    )


def vetor_polar(fase_graus, amplitude=None, amplitude_maxima=None) -> tuple[Decimal, Decimal]:
    """
    Ponta do vetor no mostrador polar, em coordenadas de círculo unitário.

    Mesma convenção da planilha (abas `Graf-O`): 0° à direita, sentido anti-horário.

        ângulo = fase / 360 * 2π      x = cos(ângulo)     y = sen(ângulo)

    A planilha para por aí — o raio é sempre 1, então o mostrador mostra só a direção
    da fase. Informando `amplitude` e `amplitude_maxima`, o raio passa a ser
    proporcional à vibração e as três corridas (reference → trial → trim) mostram a
    convergência num gráfico só.
    """
    import math

    angulo = float(_d(fase_graus)) / 360.0 * 2 * math.pi
    raio = 1.0
    if amplitude is not None and amplitude_maxima:
        maxima = float(_d(amplitude_maxima))
        if maxima > 0:
            raio = min(float(_d(amplitude)) / maxima, 1.0)
    return _d(math.cos(angulo) * raio), _d(math.sin(angulo) * raio)


def hz_para_rpm(hz) -> int:
    """Rotação do cabeçalho da planilha: 29,74 Hz → 1.784 RPM."""
    return int((_d(hz) * 60).to_integral_value())


# =============================================================================
# Economia energética (vale para balanceamento E alinhamento)
# =============================================================================


@dataclass
class ResultadoEconomia:
    reducao_kw: Decimal          # redução de demanda            (planilha: B9)
    economia_kwh_ano: Decimal    # energia poupada no ano        (não existia na planilha)
    economia_rs_ano: Decimal     # economia financeira no ano    (planilha: B11)
    payback_dias: Decimal | None
    payback_meses: Decimal | None
    retorno_ano: Decimal | None  # quantas vezes o serviço se paga no ano (planilha: C11)
    premissas: list[str]


def calcular_economia(
    *,
    tensao_v,
    corrente_antes_a,
    corrente_apos_a,
    fator_potencia,
    horas_dia,
    dias_ano,
    custo_kwh,
    custo_servico,
) -> ResultadoEconomia:
    """
    Planilha de economia, com as unidades corrigidas e o payback separado do retorno.

    Todos os argumentos são obrigatórios e nomeados: são grandezas medidas em campo, e
    nenhuma tem valor padrão (ver nota no topo do módulo). Faltando qualquer uma, o
    cálculo levanta erro em vez de assumir.

        reducao_kw       = V × ΔI × FP × √3 / 1000        (B9 — é kW, não "KW/h")
        economia_kwh_ano = reducao_kw × horas_dia × dias_ano
        economia_rs_ano  = economia_kwh_ano × custo_kwh   (B11 — custo é R$/kWh)
        retorno_ano      = economia_rs_ano / custo_servico  (C11 — o "4,67")
        payback          = custo_servico / economia_rs_ano  (o que C11 NÃO é)

    ΔI negativo (corrente subiu após o serviço) é devolvido como economia negativa —
    é informação, não erro: significa que o serviço não reduziu o consumo.
    """
    tensao = _d(tensao_v)
    delta_i = _d(corrente_antes_a) - _d(corrente_apos_a)
    fp = _d(fator_potencia)

    reducao_kw = (tensao * delta_i * fp * RAIZ_TRES) / 1000
    economia_kwh_ano = reducao_kw * _d(horas_dia) * _d(dias_ano)
    economia_rs_ano = economia_kwh_ano * _d(custo_kwh)

    custo = _d(custo_servico)
    payback_dias = payback_meses = retorno_ano = None
    # Sem economia não há payback — caso real (a corrente subiu), não erro de entrada.
    if economia_rs_ano > 0 and custo > 0:
        retorno_ano = economia_rs_ano / custo
        payback_anos = custo / economia_rs_ano
        payback_dias = payback_anos * _d(dias_ano)
        payback_meses = payback_anos * 12

    premissas = [
        "Carga trifásica equilibrada.",
        "Tensão e fator de potência inalterados entre a medição anterior e a posterior.",
        "Correntes medidas no mesmo ponto e na mesma condição de operação.",
        f"Regime de {_d(horas_dia):g} h/dia × {dias_ano} dias/ano.",
    ]

    return ResultadoEconomia(
        reducao_kw=reducao_kw,
        economia_kwh_ano=economia_kwh_ano,
        economia_rs_ano=economia_rs_ano,
        payback_dias=payback_dias,
        payback_meses=payback_meses,
        retorno_ano=retorno_ano,
        premissas=premissas,
    )
