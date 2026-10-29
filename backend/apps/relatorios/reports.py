"""
Motor de relatórios — Anexo I, item 2.9.1.

Cada relatório é uma função que recebe (user, filtros) e devolve um `Relatorio`
(título + colunas + linhas), pronto para virar JSON (prévia) ou export (CSV/XLSX/PDF).
Prévia e arquivo saem do MESMO `Relatorio`: mesmos filtros, mesmo escopo, mesmos números.

Escopo e filtros: `apps.relatorios.filtros` (escopo do usuário primeiro, falha
fechada; filtro malformado → 400). "—" na célula = sem dado; 0 = contado e deu zero.
"""
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Count, Q

from apps.accounts.models import PERFIS_INTERNOS
from apps.coletas.models import MedicaoTecnica, MedicaoTermografia, MedicaoVibracao
from apps.osp.models import STATUS_ABERTOS, OrdemServico

from . import filtros as F
from . import indicadores as I

CRIT_LABEL = {"NORMAL": "Normal", "ALERTA": "Alerta", "CRITICO": "Crítico", "": "Pendente"}
SEM_DADO = "—"


@dataclass
class Relatorio:
    titulo: str
    colunas: list
    linhas: list


# --- Helpers ------------------------------------------------------------------

def _money(v):
    if v is None:
        return SEM_DADO
    return f"R$ {Decimal(v):.2f}".replace(".", ",")


def _num(v, unidade=""):
    if v is None:
        return SEM_DADO
    return f"{v} {unidade}".strip()


def _pct(v):
    return SEM_DADO if v is None else f"{v:g}%"


def _data(d):
    return d.isoformat() if d else SEM_DADO


# --- Builders -----------------------------------------------------------------

def rel_tecnico(user, f):
    """2.9.1.1 — Relatório técnico: todas as medições com criticidade."""
    rel = "inspecao__cliente", "equipamento"
    linhas = []
    for m in F.medicoes(user, f, MedicaoVibracao).select_related(*rel):
        linhas.append([
            m.inspecao.data.isoformat(), m.inspecao.cliente.nome, m.equipamento.tag,
            "Vibração", m.ponto_medicao, _num(m.velocidade_rms, "mm/s"), CRIT_LABEL.get(m.criticidade, m.criticidade),
        ])
    for m in F.medicoes(user, f, MedicaoTermografia).select_related(*rel):
        linhas.append([
            m.inspecao.data.isoformat(), m.inspecao.cliente.nome, m.equipamento.tag,
            "Termografia", m.ponto_medicao, SEM_DADO if m.delta_t is None else f"ΔT {m.delta_t}°C",
            CRIT_LABEL.get(m.criticidade, m.criticidade),
        ])
    for m in F.medicoes(user, f, MedicaoTecnica).select_related(*rel):
        linhas.append([
            m.inspecao.data.isoformat(), m.inspecao.cliente.nome, m.equipamento.tag,
            m.get_tipo_display(), m.ponto_medicao, _num(m.valor, m.unidade),
            CRIT_LABEL.get(m.criticidade, m.criticidade),
        ])
    linhas.sort(key=lambda r: (r[0], r[2], r[4]), reverse=True)
    return Relatorio(
        "Relatório Técnico — Medições",
        ["Data", "Cliente", "Equipamento", "Tipo", "Ponto", "Valor", "Criticidade"],
        linhas,
    )


def rel_gerencial(user, f):
    """
    2.9.1.2 — Relatório gerencial: resumo por cliente.
    % Crítico = críticas / medições CLASSIFICADAS (pendentes fora do denominador).
    OSPs abertas é retrato do momento (ignora o período).
    """
    from apps.cadastros.models import Cliente

    clientes = F.aplicar(Cliente.objects.ativos(), user, f.sem_parque(), cliente="id").order_by("nome")
    insp = defaultdict(int)
    for linha in F.inspecoes(user, f).values("cliente_id").annotate(n=Count("id")):
        insp[linha["cliente_id"]] = linha["n"]
    total, classificadas, criticas = defaultdict(int), defaultdict(int), defaultdict(int)
    for modelo in I.MODELOS_MEDICAO:
        for linha in F.medicoes(user, f, modelo).values("inspecao__cliente_id").annotate(
            n=Count("id"),
            classif=Count("id", filter=~Q(criticidade="")),
            crit=Count("id", filter=Q(criticidade="CRITICO")),
        ):
            c = linha["inspecao__cliente_id"]
            total[c] += linha["n"]
            classificadas[c] += linha["classif"]
            criticas[c] += linha["crit"]
    abertas = defaultdict(int)
    for linha in F.osps(user, f, periodo=False).filter(status__in=STATUS_ABERTOS).values("cliente_id").annotate(n=Count("id")):
        abertas[linha["cliente_id"]] = linha["n"]
    linhas = []
    for c in clientes:
        pct = I._pct(criticas[c.pk], classificadas[c.pk], 0)
        linhas.append([c.nome, insp[c.pk], total[c.pk], criticas[c.pk],
                       total[c.pk] - classificadas[c.pk], _pct(pct), abertas[c.pk]])
    return Relatorio(
        "Relatório Gerencial — Resumo por Cliente",
        ["Cliente", "Inspeções", "Medições", "Críticas", "Pendentes", "% Crítico", "OSPs abertas (hoje)"],
        linhas,
    )


def rel_por_equipamento(user, f):
    """2.9.1.3 — Relatório por equipamento (medições e OSPs no período)."""
    eqs = F.equipamentos(user, f).select_related("setor__area__cliente").order_by("tag")
    nmed, ncrit, nosp = defaultdict(int), defaultdict(int), defaultdict(int)
    for modelo in I.MODELOS_MEDICAO:
        for linha in F.medicoes(user, f, modelo).values("equipamento_id").annotate(
            n=Count("id"), crit=Count("id", filter=Q(criticidade="CRITICO"))
        ):
            nmed[linha["equipamento_id"]] += linha["n"]
            ncrit[linha["equipamento_id"]] += linha["crit"]
    for linha in F.osps(user, f).validas().values("equipamento_id").annotate(n=Count("id")):
        nosp[linha["equipamento_id"]] = linha["n"]
    linhas = [
        [e.tag, e.nome, e.setor.area.cliente.nome, nmed[e.pk], ncrit[e.pk], nosp[e.pk]]
        for e in eqs
    ]
    return Relatorio(
        "Relatório por Equipamento",
        ["TAG", "Equipamento", "Cliente", "Medições", "Críticas", "OSPs (não canceladas)"],
        linhas,
    )


def rel_falhas(user, f):
    """2.9.1.4 — Relatório de falhas (medições em alerta ou crítico)."""
    linhas = []
    for modelo, rotulo in ((MedicaoVibracao, "Vibração"), (MedicaoTermografia, "Termografia"), (MedicaoTecnica, None)):
        qs = F.medicoes(user, f, modelo).filter(criticidade__in=["ALERTA", "CRITICO"]).select_related(
            "equipamento", "inspecao__cliente"
        )
        for m in qs:
            linhas.append([m.inspecao.data.isoformat(), m.inspecao.cliente.nome, m.equipamento.tag,
                           rotulo or m.get_tipo_display(), CRIT_LABEL.get(m.criticidade), m.diagnostico_sugerido or SEM_DADO])
    linhas.sort(key=lambda r: (r[0], r[2]), reverse=True)
    return Relatorio(
        "Relatório de Falhas — Anomalias Detectadas",
        ["Data", "Cliente", "Equipamento", "Tipo", "Criticidade", "Diagnóstico"],
        linhas,
    )


def rel_financeiro(user, f):
    """
    2.9.1.5 — Relatório financeiro: custos das OSPs (não canceladas) abertas no período.
    Totais somam só o que foi informado; OSP sem valor aparece "—" e não conta como zero.
    Retorno = total emergencial − total preditiva (fórmula do cliente, Seção D).
    """
    osps = F.osps(user, f).validas().select_related("equipamento", "cliente").order_by("criado_em", "numero")
    linhas = []
    for o in osps:
        com_avaliacao = any(getattr(o, c) is not None for c in I.CAMPOS_AVALIACAO)
        linhas.append([o.numero, o.cliente.nome, o.equipamento.tag, o.get_status_display(),
                       _money(o.custo_estimado), _money(o.custo_real),
                       _money(o.retorno_investimento if com_avaliacao else None)])
    c = I.custos(osps)
    linhas.append([
        "TOTAL", f"{osps.count()} OSPs", "", f"{c['osps_sem_custo_real']} sem custo real",
        _money(c["estimado"]), _money(c["real"]), _money(c["retorno_investimento"]),
    ])
    return Relatorio(
        "Relatório Financeiro — Custos de Manutenção",
        ["OSP", "Cliente", "Equipamento", "Status", "Custo estimado", "Custo real", "Retorno (emergencial − preditiva)"],
        linhas,
    )


def rel_produtividade(user, f):
    """
    2.9.1.6 — Produtividade por técnico (interno), toda no período:
    inspeções (data), medições dessas inspeções (3 tipos), laudos EMITIDOS
    (data de emissão) e OSPs FINALIZADAS (data de finalização) sob sua responsabilidade.
    """
    from django.contrib.auth import get_user_model

    tecnicos = get_user_model().objects.filter(perfil__in=PERFIS_INTERNOS, is_active=True).order_by("nome")
    insp = F.inspecoes(user, f)
    n_insp = dict(insp.values("tecnico_id").annotate(n=Count("id")).values_list("tecnico_id", "n"))
    n_med = defaultdict(int)
    for modelo in I.MODELOS_MEDICAO:
        for tid, n in modelo.objects.filter(inspecao__in=insp).values("inspecao__tecnico_id").annotate(
            n=Count("id")
        ).values_list("inspecao__tecnico_id", "n"):
            n_med[tid] += n
    n_laudos = dict(
        F.laudos(user, f).filter(status="EMITIDO").values("responsavel_id").annotate(n=Count("id"))
        .values_list("responsavel_id", "n")
    )
    fins = F.aplicar(
        OrdemServico.objects.filter(status="FINALIZADA"),
        user, f, cliente="cliente", data="finalizada_em__date",
    )
    n_osp = dict(fins.values("responsavel_id").annotate(n=Count("id")).values_list("responsavel_id", "n"))
    linhas = [
        [t.nome, t.get_perfil_display(), n_insp.get(t.pk, 0), n_med[t.pk], n_laudos.get(t.pk, 0), n_osp.get(t.pk, 0)]
        for t in tecnicos
    ]
    return Relatorio(
        "Relatório de Produtividade — Equipe Técnica",
        ["Técnico", "Perfil", "Inspeções", "Medições", "Laudos emitidos", "OSPs finalizadas"],
        linhas,
    )


def rel_historico(user, f):
    """2.9.1.7 — Histórico de manutenção (todas as OSPs abertas no período, inclusive canceladas)."""
    osps = F.osps(user, f).select_related("equipamento", "cliente").order_by("-criado_em")
    linhas = [
        [o.numero, o.cliente.nome, o.equipamento.tag, o.get_prioridade_display(), o.get_status_display(),
         o.criado_em.date().isoformat(), _data(o.sla_data),
         _data(o.finalizada_em.date() if o.finalizada_em else None)]
        for o in osps
    ]
    return Relatorio(
        "Histórico de Manutenção",
        ["OSP", "Cliente", "Equipamento", "Prioridade", "Status", "Aberta em", "SLA", "Finalizada em"],
        linhas,
    )


# --- Painéis exportáveis (2.8.1.3.3) -------------------------------------------

def rel_painel_operacional(user, f):
    """Os números do dashboard operacional, com fórmula ao lado (mesma função da tela)."""
    d = I.operacional(user, f)
    c, sla, disp, rec = d["medicoes_por_criticidade"], d["sla_atendimento"], d["disponibilidade"], d["falhas_recorrentes"]
    linhas = [
        ["Inspeções no período", d["total_inspecoes"], "", "inspeções ativas com data no período"],
        ["Inspeções em aberto (hoje)", d["inspecoes_abertas"], "", "status ABERTA, sem filtro de período"],
        ["Medições no período", d["total_medicoes"], "", "vibração + termografia + técnicas, pela data da inspeção"],
        ["Medições críticas", c["CRITICO"], "", "classificação CRITICO"],
        ["Medições em alerta", c["ALERTA"], "", "classificação ALERTA"],
        ["Medições pendentes", c["PENDENTE"], "", "sem classificação"],
        ["Equipamentos com medição crítica", disp["equipamentos_com_critica"], "", "equipamentos ativos, contados por id"],
        ["Índice de disponibilidade (proxy)", SEM_DADO if disp["percentual"] is None else disp["percentual"], "%",
         "(ativos − ativos com crítica) / ativos × 100"],
        ["Equipamentos com falha recorrente (proxy)", rec["total_equipamentos"], "", "2+ OSPs não canceladas no período"],
        ["OSPs reincidentes", rec["osps_reincidentes"], "", "acompanhamento = REINCIDENTE"],
        ["SLA de atendimento", SEM_DADO if sla["percentual"] is None else sla["percentual"], "%",
         "finalizadas até o prazo / finalizadas com prazo"],
        ["OSPs abertas (hoje)", d["osps_abertas"], "", "status em aberto, sem filtro de período"],
        ["OSPs com SLA vencido (hoje)", d["osps_sla_vencido"], "", "abertas com prazo anterior a hoje"],
        ["OSPs no período (não canceladas)", d["osps_total"], "", "criadas no período"],
    ]
    return Relatorio("Painel Operacional — Indicadores", ["Indicador", "Valor", "Unidade", "Fórmula"], linhas)


def rel_painel_executivo(user, f):
    d = I.executivo(user, f)
    k, c = d["kpis"], d["custos"]
    v = lambda x: SEM_DADO if x is None else x  # noqa: E731
    linhas = [
        ["OSPs no período (não canceladas)", k["osps_total"], "", "criadas no período"],
        ["OSPs finalizadas", k["osps_finalizadas"], "", "status FINALIZADA"],
        ["OSPs canceladas", k["osps_canceladas"], "", "fora de todas as demais contas"],
        ["Taxa de conclusão", v(k["taxa_conclusao"]), "%", "finalizadas / não canceladas"],
        ["MTTR", v(k["mttr_horas"]), "h", "média (finalização − abertura) das finalizadas"],
        ["MTBF (proxy)", v(k["mtbf_dias"]), "dias", "média dos intervalos entre OSPs consecutivas do mesmo equipamento"],
        ["SLA cumprido", v(k["sla_cumprido_pct"]), "%", "finalizadas até o prazo / finalizadas com prazo"],
        ["OSPs com SLA vencido (hoje)", k["osps_sla_vencido"], "", "abertas com prazo anterior a hoje"],
        ["Custo real", _money(c["real"]), "R$", f"soma do informado ({c['osps_com_custo_real']} OSPs; {c['osps_sem_custo_real']} sem valor)"],
        ["Custo estimado", _money(c["estimado"]), "R$", f"soma do informado ({c['osps_com_custo_estimado']} OSPs)"],
        ["Retorno da preditiva", _money(c["retorno_investimento"]), "R$",
         f"Σ (emergencial − preditiva) em {c['osps_com_avaliacao']} OSPs com Avaliação de Resultados"],
    ]
    for p in d["performance"]:
        linhas.append([f"Unidade: {p['cliente']}", p["osps"], "OSPs",
                       f"{p['finalizadas']} finalizadas · {p['criticas']} medições críticas · custo real {_money(p['custo_real'])}"])
    for m in d["evolucao"]:
        linhas.append([f"Mês {m['mes']}", m["osps"], "OSPs", f"{m['criticas']} medições críticas"])
    return Relatorio("Painel Executivo — Indicadores", ["Indicador", "Valor", "Unidade", "Fórmula"], linhas)


# --- Registro -----------------------------------------------------------------
#: `aceita_parque`: o relatório consegue aplicar área/setor/equipamento. Quando
#: não consegue, o filtro é recusado com 400 — nunca ignorado em silêncio.

REPORTS = {
    "tecnico": {"nome": "Relatório Técnico", "descricao": "Todas as medições e suas criticidades.", "categoria": "Técnico", "interno_only": False, "aceita_parque": True, "builder": rel_tecnico},
    "gerencial": {"nome": "Relatório Gerencial", "descricao": "Resumo consolidado por cliente.", "categoria": "Gerencial", "interno_only": False, "aceita_parque": True, "builder": rel_gerencial},
    "equipamento": {"nome": "Relatório por Equipamento", "descricao": "Medições e OSPs por equipamento.", "categoria": "Equipamento", "interno_only": False, "aceita_parque": True, "builder": rel_por_equipamento},
    "falhas": {"nome": "Relatório de Falhas", "descricao": "Anomalias (alerta/crítico) detectadas.", "categoria": "Falhas", "interno_only": False, "aceita_parque": True, "builder": rel_falhas},
    "financeiro": {"nome": "Relatório Financeiro", "descricao": "Custos estimados e reais das OSPs.", "categoria": "Financeiro", "interno_only": True, "aceita_parque": True, "builder": rel_financeiro},
    "produtividade": {"nome": "Relatório de Produtividade", "descricao": "Produção da equipe técnica.", "categoria": "Produtividade", "interno_only": True, "aceita_parque": False, "builder": rel_produtividade},
    "historico": {"nome": "Histórico de Manutenção", "descricao": "Linha do tempo das ordens de serviço.", "categoria": "Histórico", "interno_only": False, "aceita_parque": True, "builder": rel_historico},
    "painel-operacional": {"nome": "Indicadores operacionais", "descricao": "Os números do painel operacional, com as fórmulas.", "categoria": "Painel", "interno_only": False, "aceita_parque": True, "builder": rel_painel_operacional},
    "painel-executivo": {"nome": "Indicadores executivos", "descricao": "KPIs, custos, MTBF/MTTR, unidades e evolução.", "categoria": "Painel", "interno_only": True, "aceita_parque": True, "builder": rel_painel_executivo},
}
