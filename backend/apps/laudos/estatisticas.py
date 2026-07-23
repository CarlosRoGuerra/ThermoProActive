"""
Seção B — KPI's Dashboard do relatório técnico.

Calcula, a partir dos dados reais do cliente, as sete estatísticas gerenciais:
condições, graus de risco, componentes, anomalias, equipamentos × anomalias,
amplitude vibracional e controle das OSPs.

Paleta: a severidade (GR) é uma escala ORDENADA, então usa luminosidade
crescente (claro = risco baixo, escuro = risco eminente). Isso mantém os níveis
distinguíveis inclusive quando o relatório é impresso em preto e branco —
diferente do vermelho/laranja/amarelo original, em que GR-3 e GR-4 eram
praticamente indistinguíveis (ΔE 5,3 em visão normal).
"""
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal

from django.db.models import Count, Max

from apps.coletas.models import Inspecao, MedicaoVibracao
from apps.osp.models import Acompanhamento, GrauRisco, OrdemServico

#: Escala de severidade (validada: ΔE 16,8 em visão normal, 14,8 em daltonismo).
CORES_GR = {
    "GR0": "#1baf7a",  # sem anomalia — verde, fora da escala de severidade
    "GR4": "#f5cf00",
    "GR3": "#e88600",
    "GR2": "#c9401f",
    "GR1": "#6e0f18",
}

#: Estados operacionais (não são severidade): tons neutros, para não competirem
#: com a escala de risco nem sugerirem gravidade.
CORES_CONDICAO = {
    "OK": "#1baf7a",
    "IC": "#8a8a85",
    "MP": "#a8a8a2",
    "NM": "#6b6b66",
    "PDM": "#c2c2bb",
    "PDP": "#d6d6cf",
}

#: Paleta categórica validada (todos os checks PASS) — componentes e anomalias.
CORES_CATEGORICAS = [
    "#2a78d6", "#eb6834", "#1baf7a", "#eda100",
    "#e87ba4", "#008300", "#4a3aa7", "#8a8a85",
]

#: Limites ISO 10816 (zona C) por classe — a linha de referência "aceitável".
LIMITE_VRMS_POR_CLASSE = {
    "I": Decimal("4.50"), "II": Decimal("7.10"),
    "III": Decimal("11.20"), "IV": Decimal("18.00"),
}
LIMITE_ACELERACAO = Decimal("2.0")  # g — referência usada nos relatórios

MESES_ABREV = ["jan", "fev", "mar", "abr", "mai", "jun",
               "jul", "ago", "set", "out", "nov", "dez"]


def _rotulo_mes(d: date) -> str:
    return f"{MESES_ABREV[d.month - 1]}/{str(d.year)[2:]}"


def _fatias(contagem: Counter, cores: list[str], maximo: int = 8) -> list[dict]:
    """
    Converte contagens em fatias ordenadas por magnitude. O que passar do
    limite vira "Outros" — nunca se inventa uma cor nova para o 9º item.
    """
    itens = contagem.most_common()
    principais, resto = itens[:maximo], itens[maximo:]
    total = sum(contagem.values()) or 1
    fatias = [
        {
            "rotulo": rot,
            "valor": val,
            "percentual": round(val * 100 / total, 1),
            "cor": cores[i % len(cores)],
        }
        for i, (rot, val) in enumerate(principais)
    ]
    if resto:
        soma = sum(v for _, v in resto)
        fatias.append({
            "rotulo": "Outros", "valor": soma,
            "percentual": round(soma * 100 / total, 1), "cor": "#b0b0aa",
        })
    return fatias


def montar_secao_b(inspecao) -> dict:
    """Estatísticas gerenciais do cliente, com histórico mês a mês."""
    cliente = inspecao.cliente

    inspecoes = Inspecao.objects.filter(cliente=cliente).order_by("data")
    osps = (
        OrdemServico.objects.filter(cliente=cliente)
        .select_related("tipo_anomalia", "tipo_componente")
    )

    # --- 1. Status das condições (distribuição atual) ----------------------
    condicoes = Counter()
    for o in osps:
        if o.grau_risco:
            condicoes[o.grau_risco.replace("GR", "GR-")] += 1
    # Equipamentos medidos sem OSP estão em normalidade operacional.
    total_medidos = (
        MedicaoVibracao.objects.filter(inspecao__cliente=cliente)
        .values("equipamento").distinct().count()
    )
    sem_osp = max(total_medidos - sum(condicoes.values()), 0)
    if sem_osp:
        condicoes["OK"] = sem_osp

    cor_de = lambda r: CORES_GR.get(r.replace("-", ""), CORES_CONDICAO.get(r, "#b0b0aa"))
    total_cond = sum(condicoes.values()) or 1
    status_condicoes = [
        {
            "rotulo": rot, "valor": val,
            "percentual": round(val * 100 / total_cond, 1),
            "cor": cor_de(rot),
        }
        for rot, val in sorted(condicoes.items(), key=lambda kv: -kv[1])
    ]

    # --- 2. Graus de risco por mês (composição) ---------------------------
    por_mes_gr: dict[str, Counter] = defaultdict(Counter)
    for o in osps:
        if o.grau_risco:
            por_mes_gr[_rotulo_mes(o.criado_em.date())][o.grau_risco] += 1
    graus_mensal = [
        {
            "mes": mes,
            "total": sum(c.values()),
            "series": [
                {"gr": gr.replace("GR", "GR-"), "valor": c.get(gr, 0), "cor": CORES_GR[gr]}
                for gr in ("GR1", "GR2", "GR3", "GR4")
            ],
        }
        for mes, c in sorted(por_mes_gr.items())
    ]

    # --- 3 e 4. Componentes e anomalias (categorias do catálogo) ----------
    comp = Counter(
        o.tipo_componente.nome if o.tipo_componente else (o.componente or "Não informado")
        for o in osps
    )
    anom = Counter(
        o.tipo_anomalia.nome if o.tipo_anomalia else "Não classificada"
        for o in osps
    )

    # --- 5. Equipamentos inspecionados × anomalias por mês ----------------
    equip_por_mes: dict[str, set] = defaultdict(set)
    for m in MedicaoVibracao.objects.filter(inspecao__cliente=cliente).select_related("inspecao"):
        equip_por_mes[_rotulo_mes(m.inspecao.data)].add(m.equipamento_id)
    anom_por_mes = Counter(_rotulo_mes(o.criado_em.date()) for o in osps)
    meses = sorted(set(equip_por_mes) | set(anom_por_mes))
    equipamentos_x_anomalias = [
        {
            "mes": m,
            "equipamentos": len(equip_por_mes.get(m, ())),
            "anomalias": anom_por_mes.get(m, 0),
        }
        for m in meses
    ]

    # --- 6. Amplitude vibracional global por mês --------------------------
    # Unidades diferentes (mm/s e g) ficam em gráficos separados: um único eixo
    # por gráfico, nunca dois eixos sobrepostos.
    amplitude = []
    for insp in inspecoes:
        agg = MedicaoVibracao.objects.filter(inspecao=insp).aggregate(
            pico_v=Max("velocidade_rms"), pico_a=Max("aceleracao_rms")
        )
        if agg["pico_v"] is None:
            continue
        classes = set(
            MedicaoVibracao.objects.filter(inspecao=insp)
            .values_list("equipamento__classe_iso", flat=True)
        )
        limite = max(
            (LIMITE_VRMS_POR_CLASSE.get(c, Decimal("7.10")) for c in classes),
            default=Decimal("7.10"),
        )
        amplitude.append({
            "mes": _rotulo_mes(insp.data),
            "pico_velocidade": agg["pico_v"],
            "limite_velocidade": limite,
            "pico_aceleracao": agg["pico_a"],
            "limite_aceleracao": LIMITE_ACELERACAO,
        })

    # --- 7. Controle das OSPs (situação na reavaliação) -------------------
    rotulos_acomp = dict(Acompanhamento.choices)
    controle = (
        osps.values("acompanhamento").annotate(total=Count("id")).order_by("-total")
    )
    cores_acomp = {
        "CORRIGIDA": "#1baf7a", "ABERTA": "#eda100",
        "REINCIDENTE": "#c9401f", "NAO_REAVALIADA": "#8a8a85",
        "RETORNO_INFO": "#2a78d6",
    }
    total_ctrl = sum(c["total"] for c in controle) or 1
    controle_osps = [
        {
            "rotulo": rotulos_acomp.get(c["acompanhamento"], c["acompanhamento"]),
            "valor": c["total"],
            "percentual": round(c["total"] * 100 / total_ctrl, 1),
            "cor": cores_acomp.get(c["acompanhamento"], "#b0b0aa"),
        }
        for c in controle
    ]

    return {
        "resumo": {
            "equipamentos_monitorados": total_medidos,
            "anomalias_detectadas": sum(1 for o in osps if o.grau_risco),
            "osps_abertas": sum(1 for o in osps if o.acompanhamento == Acompanhamento.ABERTA),
            "inspecoes_realizadas": inspecoes.count(),
        },
        "status_condicoes": status_condicoes,
        "graus_mensal": graus_mensal,
        "componentes": _fatias(comp, CORES_CATEGORICAS),
        "anomalias": _fatias(anom, CORES_CATEGORICAS),
        "equipamentos_x_anomalias": equipamentos_x_anomalias,
        "amplitude": amplitude,
        "controle_osps": controle_osps,
        "legenda_gr": [
            {"gr": gr.replace("GR", "GR-"), "cor": cor} for gr, cor in CORES_GR.items()
        ],
    }
