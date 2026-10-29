"""
Indicadores dos painéis (Anexo I 2.8) — FONTE ÚNICA das fórmulas.

A tela (`/api/dashboard/`, `/api/dashboard/executivo/`, `/api/portal/visao-geral/`)
e a exportação (`/api/relatorios/painel-*/`) chamam estas funções: o número do
PDF é, por construção, o número da tela.

Convenções (documentadas em docs/16-PORTAL-BI-RELATORIOS-ANEXO-I-2.7-2.9.md):
* `None` = SEM BASE DE CÁLCULO (nenhum dado no recorte). `0` = medido e deu zero.
  A tela mostra "—" para `None`; nunca converter um no outro.
* Volume (inspeções, medições, OSPs criadas, custos, MTTR, MTBF, SLA de
  atendimento) respeita o PERÍODO. Retrato do momento (OSPs abertas, SLA vencido,
  inspeções em aberto) ignora o período, mas respeita cliente e parque.
* OSP cancelada não é falha: fica fora de toda conta, exceto `osps_canceladas`
  e `osps_por_status`.
* Fórmula que o cliente ainda não definiu está marcada como PROXY e listada nas
  pendências do docs/16 — não é apresentada como definição contratual.
"""
from collections import defaultdict
from dataclasses import replace
from decimal import Decimal

from django.db.models import Count, Q, Sum

from apps.coletas.models import MedicaoTecnica, MedicaoTermografia, MedicaoVibracao

from . import filtros as F

MODELOS_MEDICAO = (MedicaoVibracao, MedicaoTermografia, MedicaoTecnica)

#: Campos da Avaliação de Resultados (Seção D) — base do ROI definido pelo cliente.
CAMPOS_AVALIACAO = (
    "pred_mao_obra_valor", "pred_terceirizado_valor", "pred_material_valor",
    "pred_producao_valor", "pred_outros_valor",
    "emerg_mao_obra_valor", "emerg_terceirizado_valor", "emerg_material_valor",
    "emerg_producao_valor", "emerg_outros_valor",
)


def _pct(parte, total, casas=1):
    return round(parte / total * 100, casas) if total else None


def _media(valores, casas=1):
    return round(sum(valores) / len(valores), casas) if valores else None


# --- Blocos reutilizáveis -----------------------------------------------------

def criticidade_das_medicoes(user, f):
    """Contagem por classificação; '' (sem classificação) vira PENDENTE."""
    contagem = {"NORMAL": 0, "ALERTA": 0, "CRITICO": 0, "PENDENTE": 0}
    for modelo in MODELOS_MEDICAO:
        for linha in F.medicoes(user, f, modelo).values("criticidade").annotate(n=Count("id")):
            chave = linha["criticidade"] or "PENDENTE"
            contagem[chave] = contagem.get(chave, 0) + linha["n"]
    return contagem


def equipamentos_com_critica(user, f, *, periodo=True):
    """
    Equipamentos ATIVOS com ao menos uma medição CRÍTICA no recorte, agregados
    por equipamento (id — nunca pela TAG, que se repete entre clientes).
    """
    ativos = F.equipamentos(user, f)
    por_eq: dict = {}
    for modelo in MODELOS_MEDICAO:
        linhas = (
            F.medicoes(user, f, modelo, periodo=periodo)
            .filter(criticidade="CRITICO", equipamento__in=ativos)
            .values("equipamento_id", "equipamento__tag", "equipamento__nome",
                    "equipamento__setor__area__cliente__nome")
            .annotate(ocorrencias=Count("id"))
        )
        for linha in linhas:
            atual = por_eq.setdefault(linha["equipamento_id"], {
                "equipamento_id": linha["equipamento_id"],
                "equipamento__tag": linha["equipamento__tag"],
                "equipamento__nome": linha["equipamento__nome"],
                "cliente": linha["equipamento__setor__area__cliente__nome"],
                "ocorrencias": 0,
            })
            atual["ocorrencias"] += linha["ocorrencias"]
    return sorted(por_eq.values(), key=lambda r: (-r["ocorrencias"], r["equipamento__tag"]))


def disponibilidade(user, f, *, periodo=True):
    """
    PROXY (2.8.1.1.6 — o cliente não definiu horas de parada):
        (equipamentos ativos − equipamentos ativos com medição CRÍTICA) / ativos × 100
    `percentual=None` quando não há equipamento ativo no recorte.
    """
    total = F.equipamentos(user, f).count()
    criticos = len(equipamentos_com_critica(user, f, periodo=periodo))
    return {
        "percentual": _pct(total - criticos, total),
        "equipamentos_ativos": total,
        "equipamentos_com_critica": criticos,
        "definicao": "proxy",
    }


def falhas_recorrentes(user, f):
    """
    PROXY (2.8.1.1.3): equipamento com 2+ OSPs válidas abertas no período,
    mais o total de OSPs marcadas como REINCIDENTE na reavaliação.
    """
    validas = F.osps(user, f).validas()
    repetidas = (
        validas.values("equipamento_id", "equipamento__tag", "equipamento__nome")
        .annotate(osps=Count("id")).filter(osps__gte=2).order_by("-osps", "equipamento__tag")
    )
    lista = list(repetidas)
    return {
        "equipamentos": lista[:10],
        "total_equipamentos": len(lista),
        "osps_reincidentes": validas.filter(acompanhamento="REINCIDENTE").count(),
        "definicao": "proxy",
    }


def sla_atendimento(user, f):
    """
    2.8.1.1.4 — das OSPs válidas criadas no período e FINALIZADAS com prazo,
    quantas fecharam até a data do SLA (`OrdemServico.sla_cumprido`).
    `abertas_vencidas` é retrato do momento.
    """
    finalizadas = list(
        F.osps(user, f).validas().filter(status="FINALIZADA", finalizada_em__isnull=False, sla_data__isnull=False)
        .only("status", "sla_data", "finalizada_em")
    )
    no_prazo = sum(1 for o in finalizadas if o.sla_cumprido)
    return {
        "finalizadas_com_prazo": len(finalizadas),
        "no_prazo": no_prazo,
        "percentual": _pct(no_prazo, len(finalizadas)),
        "abertas_vencidas": F.osps(user, f, periodo=False).com_sla_vencido().count(),
    }


# --- Painéis ------------------------------------------------------------------

def operacional(user, f) -> dict:
    """Dashboard operacional — 2.8.1.1.1 a 2.8.1.1.6."""
    from apps.osp.models import STATUS_ABERTOS

    inspecoes = F.inspecoes(user, f)
    inspecoes_agora = F.inspecoes(user, replace(f, data_inicio=None, data_fim=None))
    crit = criticidade_das_medicoes(user, f)
    osps_periodo = F.osps(user, f)
    osps_agora = F.osps(user, f, periodo=False)
    return {
        "filtros": f.como_dict(),
        "total_inspecoes": inspecoes.count(),
        "inspecoes_abertas": inspecoes_agora.filter(status="ABERTA").count(),
        "total_medicoes": sum(crit.values()),
        "medicoes_por_criticidade": crit,
        "medicoes_pendentes": crit["PENDENTE"],
        "equipamentos_criticos": equipamentos_com_critica(user, f)[:10],
        "falhas_recorrentes": falhas_recorrentes(user, f),
        "sla_atendimento": sla_atendimento(user, f),
        "disponibilidade": disponibilidade(user, f),
        "osps_abertas": osps_agora.filter(status__in=STATUS_ABERTOS).count(),
        "osps_sla_vencido": osps_agora.com_sla_vencido().count(),
        "osps_por_status": dict(osps_periodo.values_list("status").annotate(n=Count("id"))),
        # Cancelada não é anomalia: fica fora do total (e segue em por_status).
        "osps_total": osps_periodo.validas().count(),
    }


def _ultimos_meses(fim, n=6):
    ano, mes = fim.year, fim.month
    saida = []
    for _ in range(n):
        saida.append((ano, mes))
        mes -= 1
        if mes == 0:
            mes, ano = 12, ano - 1
    return list(reversed(saida))


def custos(osps) -> dict:
    """
    2.8.1.2.2 — somas SÓ do que foi informado (`None` se ninguém informou).
    `retorno_investimento` = Σ (total emergencial − total preditiva), fórmula do
    cliente para a Seção D, apenas nas OSPs com Avaliação de Resultados lançada.
    """
    agg = osps.aggregate(
        real=Sum("custo_real"), estimado=Sum("custo_estimado"),
        n_real=Count("id", filter=Q(custo_real__isnull=False)),
        n_estimado=Count("id", filter=Q(custo_estimado__isnull=False)),
    )
    com_avaliacao = osps.filter(
        Q(*[Q(**{f"{c}__isnull": False}) for c in CAMPOS_AVALIACAO], _connector=Q.OR)
    )
    retornos = [o.retorno_investimento for o in com_avaliacao]
    total = osps.count()
    return {
        "real": float(agg["real"]) if agg["real"] is not None else None,
        "estimado": float(agg["estimado"]) if agg["estimado"] is not None else None,
        "osps_com_custo_real": agg["n_real"],
        "osps_sem_custo_real": total - agg["n_real"],
        "osps_com_custo_estimado": agg["n_estimado"],
        "retorno_investimento": float(sum(retornos, Decimal("0"))) if retornos else None,
        "osps_com_avaliacao": len(retornos),
    }


def executivo(user, f, *, hoje=None) -> dict:
    """Dashboard executivo — 2.8.1.2.1 a 2.8.1.2.6."""
    from django.utils import timezone

    from apps.cadastros.models import Cliente

    todas = F.osps(user, f)
    canceladas = todas.filter(status="CANCELADA").count()
    osps = todas.validas()
    total = osps.count()
    finalizadas = osps.filter(status="FINALIZADA", finalizada_em__isnull=False)

    # MTTR (2.8.1.2.4): média de horas entre abertura e finalização das OSPs
    # válidas criadas no período e já finalizadas.
    mttr = _media([
        (o.finalizada_em - o.criado_em).total_seconds() / 3600
        for o in finalizadas.only("finalizada_em", "criado_em")
    ])

    # MTBF (2.8.1.2.3): média de dias entre aberturas CONSECUTIVAS de OSPs
    # válidas do mesmo equipamento, dentro do período. Equipamento com uma só
    # OSP não contribui (não há intervalo). PROXY: "falha" = OSP aberta.
    por_eq = defaultdict(list)
    for linha in osps.order_by("criado_em").values("equipamento_id", "criado_em"):
        por_eq[linha["equipamento_id"]].append(linha["criado_em"])
    mtbf = _media([
        (ts[i] - ts[i - 1]).total_seconds() / 86400
        for ts in por_eq.values() for i in range(1, len(ts))
    ])

    sla = sla_atendimento(user, f)

    # Evolução (2.8.1.2.6): 6 meses terminando no fim do período (ou hoje).
    # Cliente e parque valem; o período não (a janela é fixa).
    sem_periodo = replace(f, data_inicio=None, data_fim=None)
    fim = f.data_fim or (hoje or timezone.localdate())
    osps_janela = F.osps(user, sem_periodo).validas()
    evolucao = []
    for ano, mes in _ultimos_meses(fim):
        criticas = sum(
            F.medicoes(user, sem_periodo, m).filter(
                criticidade="CRITICO", inspecao__data__year=ano, inspecao__data__month=mes
            ).count()
            for m in MODELOS_MEDICAO
        )
        evolucao.append({
            "mes": f"{mes:02d}/{ano}",
            "criticas": criticas,
            "osps": osps_janela.filter(criado_em__date__year=ano, criado_em__date__month=mes).count(),
        })

    # Performance por unidade (2.8.1.2.5): unidade = cliente (tomador do serviço).
    clientes = F.aplicar(Cliente.objects.ativos(), user, f.sem_parque(), cliente="id")
    por_cliente = {
        linha["cliente_id"]: linha
        for linha in osps.values("cliente_id").annotate(
            osps=Count("id"),
            finalizadas=Count("id", filter=Q(status="FINALIZADA")),
            custo_real=Sum("custo_real"),
        )
    }
    criticas_cliente = defaultdict(int)
    for m in MODELOS_MEDICAO:
        for linha in F.medicoes(user, f, m).filter(criticidade="CRITICO").values(
            "inspecao__cliente_id"
        ).annotate(n=Count("id")):
            criticas_cliente[linha["inspecao__cliente_id"]] += linha["n"]
    performance = []
    for c in clientes.order_by("nome"):
        linha = por_cliente.get(c.pk, {})
        custo = linha.get("custo_real")
        performance.append({
            "cliente": c.nome,
            "osps": linha.get("osps", 0),
            "finalizadas": linha.get("finalizadas", 0),
            "criticas": criticas_cliente.get(c.pk, 0),
            "custo_real": float(custo) if custo is not None else None,
        })

    return {
        "filtros": f.como_dict(),
        "kpis": {
            "osps_total": total,
            "osps_finalizadas": finalizadas.count(),
            "osps_canceladas": canceladas,
            "osps_sla_vencido": sla["abertas_vencidas"],
            "sla_cumprido_pct": sla["percentual"],
            "taxa_conclusao": _pct(finalizadas.count(), total, 0),
            "mttr_horas": mttr,
            "mtbf_dias": mtbf,
        },
        "custos": custos(osps),
        "evolucao": evolucao,
        "performance": performance,
    }
