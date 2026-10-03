"""
Grau de Risco (GR) e indicadores gerenciais da análise de fluidos — funções puras.

A regra do GR é a do relatório-modelo do laboratório (2016-11-0882, glossário 6.2):

    GR-1  anomalia observada a olho nu (decisão do inspetor, marcada como a condição
          do equipamento na folha de campo) ......... intervir em até 3 dias
    GR-2  anomalias em mais de 2 ensaios ............ até 30 dias
    GR-3  anomalias em 2 ensaios .................... até 60 dias
    GR-4  anomalia em apenas 1 ensaio ............... até 90 dias (parada programada)
    GR-0  (OK) nenhum ensaio com anomalia ........... nova inspeção em até 3 meses

"Anomalia" = ensaio (FQ, EF ou CP) com algum parâmetro em Alerta ou Crítica pelas
referências CADASTRADAS — o sistema não cria limite. Ensaio sem referência não conta
nem a favor nem contra: se nenhum ensaio da amostra pôde ser avaliado, não há GR.
"""
from collections import Counter, defaultdict

ROTINA, ALERTA, CRITICA = "ROTINA", "ALERTA", "CRITICA"
AVALIADOS = (ROTINA, ALERTA, CRITICA)
ANOMALIAS = (ALERTA, CRITICA)

# Do mais grave ao menos grave (a pior condição do mês é a que fica).
GRAUS = ("GR-1", "GR-2", "GR-3", "GR-4", "GR-0")
ROTULO_GRAU = {"GR-0": "OK", "GR-1": "GR-1", "GR-2": "GR-2", "GR-3": "GR-3", "GR-4": "GR-4"}
PRAZO_DIAS = {"GR-1": 3, "GR-2": 30, "GR-3": 60, "GR-4": 90}
OSP_COLUNAS = ("Aberta", "Corrigida", "Reincidente", "Não reavaliada")
MESES = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")


def _grau(sigla, origem, com_anomalia, avaliados):
    prazo = PRAZO_DIAS.get(sigla)
    return {
        "sigla": sigla, "rotulo": ROTULO_GRAU[sigla], "prazo_dias": prazo,
        "prazo_texto": (f"Intervenção em até {prazo} dias" if prazo else "Nova inspeção em até 3 meses"),
        "ensaios_com_anomalia": com_anomalia, "ensaios_avaliados": avaliados, "origem": origem,
    }


def _condicao_gr1(condicao) -> bool:
    return (condicao or "").upper().replace(" ", "").replace("-", "") == "GR1"


def grau_de_risco(statuses, condicao=""):
    """
    GR de uma amostra a partir do estado de cada ensaio ({"FQ": "ALERTA", ...}).
    `condicao` = sigla da condição marcada em campo; "GR-1" prevalece (olho nu).
    Devolve None quando nada pôde ser avaliado.
    """
    avaliados = [s for s in statuses.values() if s in AVALIADOS]
    com_anomalia = sum(1 for s in avaliados if s in ANOMALIAS)
    if _condicao_gr1(condicao):
        return _grau("GR-1", "ANALISTA", com_anomalia, len(avaliados))
    if not avaliados:
        return None
    if com_anomalia == 0:
        sigla = "GR-0"
    elif com_anomalia == 1:
        sigla = "GR-4"
    elif com_anomalia == 2:
        sigla = "GR-3"
    else:
        sigla = "GR-2"
    return _grau(sigla, "REFERENCIAS", com_anomalia, len(avaliados))


def _mes(d):
    return (d.year, d.month)


def _rotulo_mes(chave):
    return f"{MESES[chave[1] - 1]}/{str(chave[0])[2:]}"


def _distribuicao(contagem: Counter):
    total = sum(contagem.values()) or 1
    return [{"rotulo": k, "total": v, "percentual": round(v * 100 / total, 1)}
            for k, v in sorted(contagem.items(), key=lambda x: (-x[1], x[0]))]


def _pior(graus):
    return min(graus, key=GRAUS.index) if graus else None


def montar_graficos(amostras, historico, max_meses=12):
    """
    Indicadores da Seção B.

    amostras  — por equipamento: {"equipamento_id", "tipo", "grau" (dict|None), "anomalias" (rótulos dos
                parâmetros fora da referência), "data" (da coleta atual)}
    historico — {equipamento_id: {data: "GR-x"}} das coletas ANTERIORES (já avaliadas pelas referências
                da época).
    """
    condicoes = Counter(a["grau"]["rotulo"] if a["grau"] else "Sem avaliação" for a in amostras)
    componentes = Counter(a["tipo"] or "Sem tipo" for a in amostras)
    anomalias = Counter(rotulo for a in amostras for rotulo in set(a["anomalias"]))

    # Série por mês: o pior GR do equipamento no mês.
    por_mes = defaultdict(dict)  # mês -> equipamento -> [GR]
    for a in amostras:
        for data, sigla in historico.get(a["equipamento_id"], {}).items():
            por_mes[_mes(data)].setdefault(a["equipamento_id"], []).append(sigla)
        if a["grau"] and a["data"]:
            por_mes[_mes(a["data"])].setdefault(a["equipamento_id"], []).append(a["grau"]["sigla"])
    meses = sorted(por_mes)[-max_meses:]
    pior_no_mes = {m: [_pior(g) for g in por_mes[m].values()] for m in meses}
    graus_tempo = {
        "meses": [_rotulo_mes(m) for m in meses],
        "series": [{"gr": g, "rotulo": ROTULO_GRAU[g], "valores": [pior_no_mes[m].count(g) for m in meses]}
                   for g in GRAUS],
    }
    equipamentos_anomalias = {
        "meses": graus_tempo["meses"],
        "monitorados": [len(pior_no_mes[m]) for m in meses],
        "anomalias": [sum(1 for g in pior_no_mes[m] if g != "GR-0") for m in meses],
    }

    # Controle das O.S.P.: o que aconteceu com a anomalia da coleta anterior de cada equipamento.
    osp = {g: Counter() for g in GRAUS if g != "GR-0"}
    for a in amostras:
        passadas = {d: g for d, g in historico.get(a["equipamento_id"], {}).items() if a["data"] and d < a["data"]}
        anterior = passadas[max(passadas)] if passadas else None
        atual = a["grau"]["sigla"] if a["grau"] else None
        anomalia_anterior = anterior is not None and anterior != "GR-0"
        if atual is None:
            if anomalia_anterior:
                osp[anterior]["Não reavaliada"] += 1
        elif atual != "GR-0":
            osp[atual]["Reincidente" if anomalia_anterior else "Aberta"] += 1
        elif anomalia_anterior:
            osp[anterior]["Corrigida"] += 1
    return {
        "condicoes": _distribuicao(condicoes),
        "componentes": _distribuicao(componentes),
        "anomalias": _distribuicao(anomalias),
        "graus_tempo": graus_tempo,
        "equipamentos_anomalias": equipamentos_anomalias,
        "osp": {"colunas": list(OSP_COLUNAS),
                "linhas": [{"gr": g, "valores": [osp[g][c] for c in OSP_COLUNAS]} for g in osp]},
    }
