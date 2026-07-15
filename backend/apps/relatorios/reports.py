"""
Motor de relatórios — Anexo I, item 2.9.1.

Cada relatório é uma função que recebe (user, filtros) e devolve um `Relatorio`
(título + colunas + linhas), pronto para virar JSON (preview) ou export (CSV/XLSX/PDF).
O escopo por cliente é respeitado (perfis cliente só veem os próprios dados — item 2.7).
"""
from dataclasses import dataclass
from decimal import Decimal

from apps.accounts.models import PERFIS_INTERNOS
from apps.cadastros.models import Cliente, Equipamento
from apps.coletas.models import Inspecao, MedicaoTecnica, MedicaoTermografia, MedicaoVibracao
from apps.laudos.models import Laudo
from apps.osp.models import STATUS_ABERTOS, OrdemServico

CRIT_LABEL = {"NORMAL": "Normal", "ALERTA": "Alerta", "CRITICO": "Crítico"}


@dataclass
class Relatorio:
    titulo: str
    colunas: list
    linhas: list


# --- Helpers ------------------------------------------------------------------

def _escopo(qs, user, campo_cliente):
    """Perfis cliente: restringe ao próprio cliente."""
    if user.is_cliente and user.cliente_id:
        return qs.filter(**{campo_cliente: user.cliente_id})
    return qs


def _filtrar(qs, filtros, campo_cliente, campo_data):
    cliente = filtros.get("cliente")
    if cliente:
        qs = qs.filter(**{campo_cliente: cliente})
    if filtros.get("data_inicio"):
        qs = qs.filter(**{f"{campo_data}__gte": filtros["data_inicio"]})
    if filtros.get("data_fim"):
        qs = qs.filter(**{f"{campo_data}__lte": filtros["data_fim"]})
    return qs


def _money(v):
    return f"R$ {Decimal(v):.2f}".replace(".", ",") if v is not None else "—"


# --- Builders -----------------------------------------------------------------

def rel_tecnico(user, filtros):
    """2.9.1.1 — Relatório técnico: todas as medições com criticidade."""
    vib = _filtrar(
        _escopo(MedicaoVibracao.objects.select_related("inspecao__cliente", "equipamento"), user, "inspecao__cliente"),
        filtros, "inspecao__cliente", "inspecao__data",
    )
    termo = _filtrar(
        _escopo(MedicaoTermografia.objects.select_related("inspecao__cliente", "equipamento"), user, "inspecao__cliente"),
        filtros, "inspecao__cliente", "inspecao__data",
    )
    linhas = []
    for m in vib:
        linhas.append([
            m.inspecao.data.isoformat(), m.inspecao.cliente.nome, m.equipamento.tag,
            "Vibração", m.ponto_medicao, f"{m.velocidade_rms} mm/s", CRIT_LABEL.get(m.criticidade, m.criticidade),
        ])
    for m in termo:
        linhas.append([
            m.inspecao.data.isoformat(), m.inspecao.cliente.nome, m.equipamento.tag,
            "Termografia", m.ponto_medicao, f"ΔT {m.delta_t}°C", CRIT_LABEL.get(m.criticidade, m.criticidade),
        ])
    tec = _filtrar(
        _escopo(MedicaoTecnica.objects.select_related("inspecao__cliente", "equipamento"), user, "inspecao__cliente"),
        filtros, "inspecao__cliente", "inspecao__data",
    )
    for m in tec:
        linhas.append([
            m.inspecao.data.isoformat(), m.inspecao.cliente.nome, m.equipamento.tag,
            m.get_tipo_display(), m.ponto_medicao, f"{m.valor} {m.unidade}".strip(),
            CRIT_LABEL.get(m.criticidade, m.criticidade),
        ])
    linhas.sort(key=lambda r: r[0], reverse=True)
    return Relatorio(
        "Relatório Técnico — Medições",
        ["Data", "Cliente", "Equipamento", "Tipo", "Ponto", "Valor", "Criticidade"],
        linhas,
    )


def rel_gerencial(user, filtros):
    """2.9.1.2 — Relatório gerencial: resumo por cliente."""
    clientes = _escopo(Cliente.objects.ativos(), user, "id")
    if filtros.get("cliente"):
        clientes = clientes.filter(id=filtros["cliente"])
    linhas = []
    for c in clientes:
        insp = _filtrar(Inspecao.objects.filter(cliente=c), filtros, "cliente", "data")
        vib = MedicaoVibracao.objects.filter(inspecao__in=insp)
        termo = MedicaoTermografia.objects.filter(inspecao__in=insp)
        tec = MedicaoTecnica.objects.filter(inspecao__in=insp)
        total_med = vib.count() + termo.count() + tec.count()
        criticas = (
            vib.filter(criticidade="CRITICO").count()
            + termo.filter(criticidade="CRITICO").count()
            + tec.filter(criticidade="CRITICO").count()
        )
        osps_abertas = OrdemServico.objects.filter(cliente=c, status__in=STATUS_ABERTOS).count()
        pct = f"{round(criticas / total_med * 100)}%" if total_med else "0%"
        linhas.append([c.nome, insp.count(), total_med, criticas, pct, osps_abertas])
    return Relatorio(
        "Relatório Gerencial — Resumo por Cliente",
        ["Cliente", "Inspeções", "Medições", "Críticas", "% Crítico", "OSPs abertas"],
        linhas,
    )


def rel_por_equipamento(user, filtros):
    """2.9.1.3 — Relatório por equipamento."""
    eqs = _escopo(
        Equipamento.objects.ativos().select_related("setor__area__cliente"),
        user, "setor__area__cliente",
    )
    if filtros.get("cliente"):
        eqs = eqs.filter(setor__area__cliente=filtros["cliente"])
    linhas = []
    for e in eqs:
        nmed = e.medicoes_vibracao.count() + e.medicoes_termografia.count() + e.medicoes_tecnicas.count()
        ncrit = (
            e.medicoes_vibracao.filter(criticidade="CRITICO").count()
            + e.medicoes_termografia.filter(criticidade="CRITICO").count()
            + e.medicoes_tecnicas.filter(criticidade="CRITICO").count()
        )
        nosp = e.osps.count()
        linhas.append([e.tag, e.nome, e.setor.area.cliente.nome, nmed, ncrit, nosp])
    return Relatorio(
        "Relatório por Equipamento",
        ["TAG", "Equipamento", "Cliente", "Medições", "Críticas", "OSPs"],
        linhas,
    )


def rel_falhas(user, filtros):
    """2.9.1.4 — Relatório de falhas (anomalias detectadas)."""
    vib = _filtrar(
        _escopo(MedicaoVibracao.objects.select_related("equipamento", "inspecao__cliente"), user, "inspecao__cliente"),
        filtros, "inspecao__cliente", "inspecao__data",
    ).filter(criticidade__in=["ALERTA", "CRITICO"])
    termo = _filtrar(
        _escopo(MedicaoTermografia.objects.select_related("equipamento", "inspecao__cliente"), user, "inspecao__cliente"),
        filtros, "inspecao__cliente", "inspecao__data",
    ).filter(criticidade__in=["ALERTA", "CRITICO"])
    linhas = []
    for m in vib:
        linhas.append([m.inspecao.data.isoformat(), m.equipamento.tag, "Vibração",
                       CRIT_LABEL.get(m.criticidade), m.diagnostico_sugerido])
    for m in termo:
        linhas.append([m.inspecao.data.isoformat(), m.equipamento.tag, "Termografia",
                       CRIT_LABEL.get(m.criticidade), m.diagnostico_sugerido])
    tec = _filtrar(
        _escopo(MedicaoTecnica.objects.select_related("equipamento", "inspecao__cliente"), user, "inspecao__cliente"),
        filtros, "inspecao__cliente", "inspecao__data",
    ).filter(criticidade__in=["ALERTA", "CRITICO"])
    for m in tec:
        linhas.append([m.inspecao.data.isoformat(), m.equipamento.tag, m.get_tipo_display(),
                       CRIT_LABEL.get(m.criticidade), m.diagnostico_sugerido])
    linhas.sort(key=lambda r: r[0], reverse=True)
    return Relatorio(
        "Relatório de Falhas — Anomalias Detectadas",
        ["Data", "Equipamento", "Tipo", "Criticidade", "Diagnóstico"],
        linhas,
    )


def rel_financeiro(user, filtros):
    """2.9.1.5 — Relatório financeiro: custos das OSPs."""
    osps = _filtrar(
        _escopo(OrdemServico.objects.select_related("equipamento"), user, "cliente"),
        filtros, "cliente", "criado_em__date",
    )
    linhas = []
    total_est = total_real = Decimal("0")
    for o in osps:
        total_est += o.custo_estimado or 0
        total_real += o.custo_real or 0
        linhas.append([o.numero, o.equipamento.tag, o.get_status_display(),
                       _money(o.custo_estimado), _money(o.custo_real)])
    linhas.append(["TOTAL", "", "", _money(total_est), _money(total_real)])
    return Relatorio(
        "Relatório Financeiro — Custos de Manutenção",
        ["OSP", "Equipamento", "Status", "Custo estimado", "Custo real"],
        linhas,
    )


def rel_produtividade(user, filtros):
    """2.9.1.6 — Relatório de produtividade por técnico (interno)."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    tecnicos = User.objects.filter(perfil__in=PERFIS_INTERNOS, is_active=True)
    linhas = []
    for t in tecnicos:
        insp = _filtrar(Inspecao.objects.filter(tecnico=t), filtros, "cliente", "data")
        nmed = (
            MedicaoVibracao.objects.filter(inspecao__in=insp).count()
            + MedicaoTermografia.objects.filter(inspecao__in=insp).count()
        )
        nlaudos = Laudo.objects.filter(responsavel=t).count()
        nosp_fim = OrdemServico.objects.filter(responsavel=t, status="FINALIZADA").count()
        linhas.append([t.nome, t.get_perfil_display(), insp.count(), nmed, nlaudos, nosp_fim])
    return Relatorio(
        "Relatório de Produtividade — Equipe Técnica",
        ["Técnico", "Perfil", "Inspeções", "Medições", "Laudos", "OSPs finalizadas"],
        linhas,
    )


def rel_historico(user, filtros):
    """2.9.1.7 — Histórico de manutenção (timeline de OSPs)."""
    osps = _filtrar(
        _escopo(OrdemServico.objects.select_related("equipamento"), user, "cliente"),
        filtros, "cliente", "criado_em__date",
    ).order_by("-criado_em")
    linhas = []
    for o in osps:
        linhas.append([
            o.numero, o.equipamento.tag, o.get_prioridade_display(), o.get_status_display(),
            o.criado_em.date().isoformat(),
            o.sla_data.isoformat() if o.sla_data else "—",
            o.finalizada_em.date().isoformat() if o.finalizada_em else "—",
        ])
    return Relatorio(
        "Histórico de Manutenção",
        ["OSP", "Equipamento", "Prioridade", "Status", "Aberta em", "SLA", "Finalizada em"],
        linhas,
    )


# --- Registro -----------------------------------------------------------------

REPORTS = {
    "tecnico": {"nome": "Relatório Técnico", "descricao": "Todas as medições e suas criticidades.", "categoria": "Técnico", "interno_only": False, "builder": rel_tecnico},
    "gerencial": {"nome": "Relatório Gerencial", "descricao": "Resumo consolidado por cliente.", "categoria": "Gerencial", "interno_only": False, "builder": rel_gerencial},
    "equipamento": {"nome": "Relatório por Equipamento", "descricao": "Medições e OSPs por equipamento.", "categoria": "Equipamento", "interno_only": False, "builder": rel_por_equipamento},
    "falhas": {"nome": "Relatório de Falhas", "descricao": "Anomalias (alerta/crítico) detectadas.", "categoria": "Falhas", "interno_only": False, "builder": rel_falhas},
    "financeiro": {"nome": "Relatório Financeiro", "descricao": "Custos estimados e reais das OSPs.", "categoria": "Financeiro", "interno_only": True, "builder": rel_financeiro},
    "produtividade": {"nome": "Relatório de Produtividade", "descricao": "Produção da equipe técnica.", "categoria": "Produtividade", "interno_only": True, "builder": rel_produtividade},
    "historico": {"nome": "Histórico de Manutenção", "descricao": "Linha do tempo das ordens de serviço.", "categoria": "Histórico", "interno_only": False, "builder": rel_historico},
}
