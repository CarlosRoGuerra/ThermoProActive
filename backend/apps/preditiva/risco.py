"""Índice de risco por equipamento — Anexo I 2.4.1.5 (complemento).

O índice NÃO é probabilidade de falha. É uma priorização reproduzível a partir de
três componentes:

    p = w_sev · (s − 1)/2  +  w_tend · (t − 1)/2        (proxy de probabilidade, 0–1)
    c = consequência[criticidade do ativo] / máximo      (consequência, 0–1]
    índice = 100 · p · c

- s: severidade da condição atual, a pior entre as últimas leituras CLASSIFICADAS
  de cada série do equipamento (NORMAL=1, ALERTA=2, CRITICO=3).
- t: tendência, a pior entre as séries (ATINGIDO/ESTIMADO=3, TENDENCIA=2,
  SEM_TENDENCIA/SERIE_CONSTANTE=1). Série insuficiente não entra.
- c: criticidade A/B/C do ativo (cadastro de equipamento), via matriz.

Sem um dos três componentes o índice não é calculado (None) e o equipamento sai do
ranking ordenado, com as pendências listadas. Não se assume “normal” no lugar de
dado ausente.

A matriz (pesos, consequência e faixas) é cadastro do Master, com situação e
fonte. Sem cadastro, vale `MATRIZ_RESERVA`, marcada como provisória.
"""
from decimal import Decimal

from django.db.models import Q
from django.utils import timezone

SEVERIDADE_SCORE = {"NORMAL": 1, "ALERTA": 2, "CRITICO": 3}
TENDENCIA_SCORE = {"ATINGIDO": 3, "ESTIMADO": 3, "TENDENCIA": 2, "SEM_TENDENCIA": 1, "SERIE_CONSTANTE": 1}
TOLERANCIA_PESOS = Decimal("0.001")

#: Reserva do sistema, usada quando não há matriz cadastrada. Mesmos valores da
#: migração que cria a matriz provisória. Não é validada pelo cliente.
MATRIZ_RESERVA = {
    "id": None, "nome": "Matriz provisória do sistema", "origem": "reserva_do_sistema",
    "peso_severidade": 0.6, "peso_tendencia": 0.4,
    "consequencia": {"A": 3, "B": 2, "C": 1},
    "faixas": [
        {"ate": 25, "rotulo": "BAIXO"}, {"ate": 50, "rotulo": "MODERADO"},
        {"ate": 75, "rotulo": "ALTO"}, {"ate": 100, "rotulo": "MUITO ALTO"},
    ],
    "validacao": "PROVISORIA", "fonte": "Padrão provisório — a confirmar pelo cliente.",
}


def validar_matriz(m):
    """Confere pesos, consequência e faixas de uma matriz (objeto ou dict-like). Levanta ValueError."""
    def campo(nome):
        return m[nome] if isinstance(m, dict) else getattr(m, nome)

    ws, wt = Decimal(str(campo("peso_severidade"))), Decimal(str(campo("peso_tendencia")))
    if ws < 0 or wt < 0 or ws > 1 or wt > 1:
        raise ValueError("Os pesos devem estar entre 0 e 1.")
    if abs(ws + wt - 1) > TOLERANCIA_PESOS:
        raise ValueError("Os pesos da severidade e da tendência devem somar 1.")
    consequencia = campo("consequencia")
    if not isinstance(consequencia, dict) or set(consequencia) != {"A", "B", "C"}:
        raise ValueError('A consequência deve ter exatamente as chaves "A", "B" e "C".')
    for valor in consequencia.values():
        if isinstance(valor, bool) or not isinstance(valor, int) or not 1 <= valor <= 10:
            raise ValueError("Cada consequência deve ser um inteiro de 1 a 10.")
    faixas = campo("faixas")
    if not isinstance(faixas, list) or not faixas:
        raise ValueError("Informe ao menos uma faixa do índice.")
    anterior = 0.0
    for faixa in faixas:
        if not isinstance(faixa, dict) or not str(faixa.get("rotulo", "")).strip():
            raise ValueError('Cada faixa precisa de "ate" e "rotulo".')
        ate = faixa.get("ate")
        if isinstance(ate, bool) or not isinstance(ate, (int, float)) or not anterior < ate <= 100:
            raise ValueError("Os limites das faixas devem ser crescentes e estar entre 0 e 100.")
        anterior = float(ate)
    if anterior != 100:
        raise ValueError("A última faixa deve terminar em 100.")


def matriz_dict(m):
    """Matriz cadastrada como dicionário de cálculo."""
    return {
        "id": m.pk, "nome": m.nome, "origem": "cadastro",
        "peso_severidade": float(m.peso_severidade), "peso_tendencia": float(m.peso_tendencia),
        "consequencia": {k: int(v) for k, v in m.consequencia.items()},
        "faixas": m.faixas, "validacao": m.validacao, "fonte": m.fonte,
    }


def matriz_vigente(cliente_id=None, data=None):
    """Matriz do cliente antes da global; dentro da vigência; mais recente primeiro. None sem cadastro."""
    from .models import MatrizRisco

    data = data or timezone.localdate()
    qs = MatrizRisco.objects.filter(ativo=True).filter(
        Q(vigencia_inicio__isnull=True) | Q(vigencia_inicio__lte=data),
        Q(vigencia_fim__isnull=True) | Q(vigencia_fim__gte=data),
    )
    qs = qs.filter(Q(cliente__isnull=True) | Q(cliente_id=cliente_id)) if cliente_id else qs.filter(cliente__isnull=True)
    candidatas = sorted(qs, key=lambda m: (
        0 if m.cliente_id else 1, -(m.vigencia_inicio.toordinal() if m.vigencia_inicio else 0), -m.pk,
    ))
    return matriz_dict(candidatas[0]) if candidatas else dict(MATRIZ_RESERVA)


def pontuacao_tendencia(status_projecoes: str | None):
    return TENDENCIA_SCORE.get(status_projecoes)


def calcular_indice(severidade: str | None, tendencia: str | None, criticidade: str | None, matriz) -> dict:
    """Índice e decomposição. `severidade`/`tendencia`/`criticidade` são rótulos; None = ausente."""
    pendencias = []
    s = SEVERIDADE_SCORE.get(severidade or "")
    if s is None:
        pendencias.append("sem_condicao_classificada")
    t = TENDENCIA_SCORE.get(tendencia or "")
    if t is None:
        pendencias.append("sem_tendencia_avaliada")
    consequencia = matriz["consequencia"]
    c_valor = consequencia.get(criticidade or "")
    if c_valor is None:
        pendencias.append("criticidade_do_ativo_nao_informada")

    ws, wt = matriz["peso_severidade"], matriz["peso_tendencia"]
    componentes = {
        "severidade": {"valor": severidade or None, "score": s, "peso": ws,
                       "normalizado": (s - 1) / 2 if s else None,
                       "contribuicao": ws * (s - 1) / 2 if s else None},
        "tendencia": {"valor": tendencia or None, "score": t, "peso": wt,
                      "normalizado": (t - 1) / 2 if t else None,
                      "contribuicao": wt * (t - 1) / 2 if t else None},
        "consequencia": {"criticidade": criticidade or None, "valor": c_valor,
                         "maximo": max(consequencia.values()),
                         "normalizado": (c_valor / max(consequencia.values())) if c_valor else None},
    }
    completo = not pendencias
    indice = None
    faixa = None
    if completo:
        p = componentes["severidade"]["contribuicao"] + componentes["tendencia"]["contribuicao"]
        c = componentes["consequencia"]["normalizado"]
        indice = round(100 * p * c, 1)
        faixa = next((f["rotulo"] for f in matriz["faixas"] if indice <= f["ate"]), None)
    return {
        "indice": indice, "faixa": faixa, "completo": completo, "pendencias": pendencias,
        "componentes": componentes,
        "formula": "indice = 100 × [peso_severidade × (s−1)/2 + peso_tendencia × (t−1)/2] × consequencia/maximo",
        "matriz": {"id": matriz.get("id"), "nome": matriz["nome"], "origem": matriz["origem"],
                   "validacao": matriz["validacao"], "fonte": matriz.get("fonte", "")},
        "aviso": "Índice de priorização, não probabilidade de falha.",
    }


def avaliar_equipamento(equipamento, analises, matriz):
    """Monta o índice de um equipamento a partir das análises de tendência das suas séries.

    `analises`: lista de dicts de `tendencia.analisar_medicao`, uma por série (a leitura mais recente).
    """
    classificadas = [a["criticidade"] for a in analises if a["criticidade"] in SEVERIDADE_SCORE]
    severidade = max(classificadas, key=SEVERIDADE_SCORE.get) if classificadas else None
    tendencias = []
    for a in analises:
        status = a["serie"]["status"]
        if status == "TENDENCIA":
            estados = {p["estado"] for p in a["serie"]["projecoes"]}
            status = "ATINGIDO" if "ATINGIDO" in estados else "ESTIMADO" if "ESTIMADO" in estados else "TENDENCIA"
        tendencias.append(status if pontuacao_tendencia(status) is not None else None)
    validas = [x for x in tendencias if x]
    tendencia = max(validas, key=TENDENCIA_SCORE.get) if validas else None
    resultado = calcular_indice(severidade, tendencia, equipamento.criticidade or None, matriz)
    series = []
    for a, status in zip(analises, tendencias):
        series.append({
            "modalidade": a["modalidade"], "grandeza": a["grandeza"], "ponto_medicao": a["ponto_medicao"],
            "medicao_id": a["medicao_id"], "criticidade": a["criticidade"] or None,
            "status_tendencia": status, "status_serie": a["serie"]["status"], "motivo": a["serie"]["motivo"],
            "limite_validado": a["limite"]["validado"], "limite_motivo": a["limite"]["motivo"],
            "projecoes": [{k: p.get(k) for k in ("nivel", "limite", "estado", "data_estimada",
                                                    "intervalo_confianca", "dias_ate_limite")}
                          for p in a["serie"]["projecoes"]],
        })
    return {
        "equipamento": {"id": equipamento.pk, "tag": equipamento.tag, "nome": equipamento.nome,
                        "cliente_id": equipamento.setor.area.cliente_id},
        **resultado,
        "series": series,
        "series_sem_leitura_classificada": sum(1 for a in analises if not a["criticidade"]),
    }


def ordenar_ranking(itens):
    """Completos primeiro, pelo índice (maior primeiro); incompletos depois, por tag."""
    return sorted(itens, key=lambda i: (
        0 if i["completo"] else 1, -(i["indice"] or 0), i["equipamento"]["tag"],
    ))


def ultimas_por_serie(equipamento_ids):
    """{equipamento_id: {chave_da_serie: medição mais recente}} para os equipamentos informados."""
    from collections import defaultdict

    from apps.coletas.models import MedicaoTecnica, MedicaoTermografia, MedicaoVibracao

    from .tendencia import chave_grupo

    ultimas = defaultdict(dict)
    ids = list(equipamento_ids)
    if not ids:
        return ultimas
    for modelo in (MedicaoVibracao, MedicaoTermografia, MedicaoTecnica):
        qs = modelo.objects.filter(equipamento_id__in=ids).select_related(
            "equipamento__setor__area", "inspecao",
        ).order_by("-data_hora", "-pk")
        for m in qs.iterator():
            ultimas[m.equipamento_id].setdefault(chave_grupo(m), m)
    return ultimas


def severidade_atual(equipamento_id):
    """Pior criticidade CLASSIFICADA entre as últimas leituras de cada série; None se nenhuma."""
    ultimas = ultimas_por_serie([equipamento_id]).get(equipamento_id, {})
    classificadas = [m.criticidade for m in ultimas.values() if m.criticidade in SEVERIDADE_SCORE]
    return max(classificadas, key=SEVERIDADE_SCORE.get) if classificadas else None


def ranking_equipamentos(equipamentos, data=None):
    """Ranking de risco dos equipamentos informados (o escopo de cliente já foi aplicado por quem chama).

    Para cada série usa a leitura mais recente e a análise de tendência dela. A matriz
    vem do cliente do equipamento. Não grava nada.
    """
    from .tendencia import analisar_medicao

    eqs = list(equipamentos.select_related("setor__area"))
    ultimas = ultimas_por_serie([e.pk for e in eqs])
    matrizes = {}
    itens = []
    for eq in eqs:
        cliente_id = eq.setor.area.cliente_id
        if cliente_id not in matrizes:
            matrizes[cliente_id] = matriz_vigente(cliente_id, data)
        analises = [analisar_medicao(m) for m in ultimas.get(eq.pk, {}).values()]
        itens.append(avaliar_equipamento(eq, analises, matrizes[cliente_id]))
    return ordenar_ranking(itens)
