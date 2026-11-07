"""Módulo de relatório da espessura (Anexo I 2.3.2.7) — família inspeção por rota.

A OSP mostra a última medição de espessura do MESMO equipamento e cliente, feita até a
data de término do relatório: nominal, medida, perda, taxa de corrosão entre campanhas
comparáveis e condição (só com limite cadastrado e validado).
"""
from .generico import CONSIDERACOES_GENERICAS, GLOSSARIO_GENERICO
from .inspecao import ModuloInspecaoRota

GLOSSARIO_ESPESSURA = GLOSSARIO_GENERICO + (
    ("6.8", "EN", "Espessura nominal: espessura de projeto da peça, informada na ficha da medição (mm)."),
    ("6.9", "PER", "Perda de espessura (%): (nominal − medida) ÷ nominal × 100."),
    ("6.10", "TCC", "Taxa de corrosão (mm/ano): redução de espessura entre duas campanhas comparáveis, dividida pelo tempo entre elas."),
    ("6.11", "LIM", "Limite de alerta e crítico: valor cadastrado e validado pelo responsável técnico; sem limite, a condição é pendente."),
)

CONSIDERACOES_ESPESSURA = (
    CONSIDERACOES_GENERICAS[0],
    "A condição da espessura só é classificada com limite cadastrado e validado para a peça. Sem ele, a "
    "medição é apresentada com a perda e a taxa, e a condição permanece pendente.",
    "A taxa de corrosão é uma razão entre duas leituras comparáveis (mesmo ponto, instrumento e ficha). Não é "
    "vida útil remanescente nem probabilidade de falha.",
    *CONSIDERACOES_GENERICAS[1:],
)

MODULO_ESPESSURA = ModuloInspecaoRota(
    chave="ESPESSURA",
    carta_glossario=GLOSSARIO_ESPESSURA,
    carta_consideracoes=CONSIDERACOES_ESPESSURA,
)


def ultima_espessura(cliente_id, equipamento_id, ate):
    """Leitura de espessura mais recente do equipamento até `ate` (data), ou None.

    Usa a análise de medição da preditiva: perda, taxa entre leituras comparáveis e a condição
    só com limite validado. Não grava nada.
    """
    from apps.coletas.espessura import classificar, dias_entre, perda_percentual, taxa_corrosao
    from apps.coletas.models import MedicaoTecnica, TipoAnalise
    from apps.preditiva.tendencia import limites_medicao, serie_comparavel

    qs = MedicaoTecnica.objects.filter(
        tipo=TipoAnalise.ESPESSURA, equipamento_id=equipamento_id, inspecao__cliente_id=cliente_id,
    ).select_related("inspecao", "equipamento__setor__area", "componente", "instrumento")
    if ate is not None:
        qs = qs.filter(inspecao__data__lte=ate)
    medicao = qs.order_by("-data_hora", "-pk").first()
    if medicao is None:
        return None
    nominal = (medicao.parametros or {}).get("espessura_nominal_mm")
    instantes, valores, _, _ = serie_comparavel(medicao, 2)
    taxa = None
    if len(valores) >= 2:
        taxa = taxa_corrosao(valores[-2], medicao.valor, dias_entre(instantes[-2], instantes[-1]))
    limite = limites_medicao(medicao)
    limites = {v["nivel"]: v["valor"] for v in limite["limites"]} if limite["validado"] else {}
    perda = perda_percentual(nominal, medicao.valor)
    return {
        "data": medicao.inspecao.data.isoformat(),
        "material": (medicao.parametros or {}).get("material", ""),
        "nominal_mm": str(nominal) if nominal is not None else None,
        "medida_mm": str(medicao.valor),
        "perda_percentual": str(perda) if perda is not None else None,
        "taxa_mm_ano": str(taxa) if taxa is not None else None,
        "condicao": classificar(medicao.valor, limites),
        "criterio_validado": limite["validado"],
    }
