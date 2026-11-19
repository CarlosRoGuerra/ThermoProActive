"""
Correção da temperatura em função da carga (C.T.M. — glossário 6.1.5 da termografia).

Fórmula enviada pelo Fabrício em 16/11/2026 (documento "Calculo correção de temperatura em
função da carga"): o aquecimento por efeito Joule é proporcional ao quadrado da corrente
(P ∝ I²) e a elevação de temperatura acima do ambiente é proporcional à potência (ΔT ∝ P).

    ΔT1 = TM − TA                  elevação medida sobre a temperatura ambiente
    I2  = 0,90 × In                90 % da corrente nominal
    ΔT2 = ΔT1 × (I2 / I1)²         elevação na carga de 90 %
    T2  = TA + ΔT2                 → T. Medida Corrigida

Exemplo do documento: In 100 A, I1 70 A, TM 100 °C, TA 30 °C → ΔT2 = 115,71 °C e T2 = 145,7 °C.

Como (I2/I1)² = (90 / carga%)², o fator depende só da carga: ela vem das correntes
(I1 ÷ In) quando a nominal e a de trabalho foram medidas, ou do % digitado pelo analista.

Pontos que o documento não define, confirmados pelo Fabrício em 18/11/2026 (docs/27 §1.7):
  * I1 com correntes em várias fases: a da fase da anomalia. Uma fase só medida = ela;
    "todas as fases" = a maior. Várias fases sem escolha → não corrige (pede a fase).
  * Corrige qualquer carga, exceto 100 %. Abaixo de 90 % a temperatura corrigida sobe; acima
    de 90 % (inclusive acima da nominal) a projeção para 90 % a faz descer; em 90 % o fator é 1.
  * Não há carga mínima. Só não sai valor com carga zero (a fórmula divide pela corrente) ou
    quando o resultado não cabe no campo.
  * T. Delta Corrigida = (TM − TR) × fator — o ΔT da OSP (6.1.3) na carga de 90 %, que é a
    diferença entre a medida e a referência corrigidas pela mesma fórmula. Não depende do TA.
"""
from dataclasses import dataclass, replace
from decimal import ROUND_HALF_UP, Decimal

#: Carga de destino da correção, em % da corrente nominal (I2 = 0,90 × In).
CARGA_ALVO = Decimal("90")
#: Carga em que a temperatura medida não é corrigida (Fabrício, 18/11/2026).
CARGA_SEM_CORRECAO = Decimal("100")
#: Maior valor que os campos de temperatura (6 dígitos, 1 casa) guardam.
LIMITE_TEMPERATURA = Decimal("99999.9")

FASES = ("R", "S", "T")
TODAS_AS_FASES = "MAIOR"

UM_DECIMAL = Decimal("0.1")


def _arred(valor: Decimal) -> Decimal:
    """Uma casa, meio para cima sobre o valor cheio (145,714 → 145,7; 5,25 → 5,3)."""
    return valor.quantize(UM_DECIMAL, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class CorrecaoCarga:
    #: Carga usada: calculada das correntes ou a digitada.
    carga_percentual: Decimal | None
    #: True quando a carga veio de I1 ÷ In (o campo deixa de ser digitado).
    carga_calculada: bool
    #: I1 usada no cálculo e a fase dela ("" quando não houve corrente).
    corrente_trabalho: Decimal | None
    fase: str
    #: (I2 / I1)²; None quando não há correção.
    fator: Decimal | None
    temperatura_medida_corrigida: Decimal | None
    temperatura_referencia_corrigida: Decimal | None
    delta_t_corrigido: Decimal | None
    #: Por que alguma das temperaturas corrigidas não saiu ("" quando todas saíram).
    pendencia: str = ""


def corrente_de_trabalho(correntes: dict, fase: str) -> tuple:
    """(I1, fase usada, pendência) a partir das correntes medidas por fase."""
    medidas = {f: v for f, v in correntes.items() if v is not None}
    if fase in FASES:
        if fase in medidas:
            return medidas[fase], fase, ""
        return None, fase, f"A corrente da fase {fase} não foi medida."
    if fase == TODAS_AS_FASES:
        if not medidas:
            return None, "", ""
        maior = max(medidas, key=lambda f: medidas[f])
        return medidas[maior], maior, ""
    if len(medidas) == 1:
        (unica, valor), = medidas.items()
        return valor, unica, ""
    if len(medidas) > 1:
        return None, "", "Há corrente medida em mais de uma fase: informe a fase da anomalia."
    return None, "", ""


def calcular(*, temperatura_medida, temperatura_referencia, temperatura_ambiente,
             carga_digitada, corrente_nominal, correntes: dict, fase: str = "") -> CorrecaoCarga:
    pendencias = []
    i1, fase_usada, pendencia_fase = None, "", ""
    carga, calculada, ratio = carga_digitada, False, None

    if corrente_nominal is not None and corrente_nominal > 0 and any(v is not None for v in correntes.values()):
        i1, fase_usada, pendencia_fase = corrente_de_trabalho(correntes, fase)
        if i1 is not None:
            ratio = i1 / corrente_nominal  # I1 / In, sem arredondar
            carga, calculada = _arred(ratio * 100), True
        else:
            # Correntes medidas, mas sem saber qual vale: não cai no % digitado, para a OSP
            # não mostrar correntes e uma carga que não batem.
            pendencias.append(pendencia_fase)
    elif carga is not None:
        ratio = carga / 100

    vazio = CorrecaoCarga(carga, calculada, i1, fase_usada, None, None, None, None, "")
    if temperatura_medida is None:
        return vazio
    if ratio is None:
        if not pendencias:
            pendencias.append("Informe a corrente nominal e a de trabalho, ou o % de carga.")
        return replace(vazio, pendencia=" ".join(pendencias))
    if ratio <= 0:
        return replace(vazio, pendencia="Com carga zero não há como corrigir a temperatura.")
    # Comparada com uma casa, como a carga sai na OSP.
    if _arred(ratio * 100) == CARGA_SEM_CORRECAO:
        return replace(vazio, pendencia="Com a carga em 100 % da nominal a temperatura não é corrigida.")

    fator = (CARGA_ALVO / 100 / ratio) ** 2
    ta, tm, tr = temperatura_ambiente, temperatura_medida, temperatura_referencia

    def corrigida(valor):
        if valor is None:
            return None
        resultado = _arred(valor)
        if abs(resultado) > LIMITE_TEMPERATURA:
            pendencias.append("A carga é baixa demais para extrapolar: o valor corrigido passa do limite do campo.")
            return None
        return resultado

    tm_corr = corrigida(ta + (tm - ta) * fator) if ta is not None else None
    tr_corr = corrigida(ta + (tr - ta) * fator) if ta is not None and tr is not None else None
    dt_corr = corrigida((tm - tr) * fator) if tr is not None else None
    if ta is None:
        pendencias.append("Informe a temperatura ambiente para corrigir a temperatura medida.")
    return CorrecaoCarga(
        carga_percentual=carga, carga_calculada=calculada, corrente_trabalho=i1, fase=fase_usada,
        fator=fator, temperatura_medida_corrigida=tm_corr, temperatura_referencia_corrigida=tr_corr,
        delta_t_corrigido=dt_corr, pendencia=" ".join(dict.fromkeys(pendencias)),
    )


def calcular_do_achado(achado) -> CorrecaoCarga:
    return calcular(
        temperatura_medida=achado.temperatura_medida,
        temperatura_referencia=achado.temperatura_referencia,
        temperatura_ambiente=achado.temperatura_ambiente,
        carga_digitada=achado.carga_percentual,
        corrente_nominal=achado.corrente_nominal,
        correntes={"R": achado.corrente_a, "S": achado.corrente_b, "T": achado.corrente_c},
        fase=achado.fase_anomalia,
    )
