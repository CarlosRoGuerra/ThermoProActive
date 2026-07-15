"""Geração automática de laudo a partir de uma inspeção (Anexo I 2.5.1.1)."""
from apps.coletas.models import Inspecao

from .models import Laudo

ORDEM_CRITICIDADE = {"NORMAL": 0, "ALERTA": 1, "CRITICO": 2}
LABEL_CRITICIDADE = {"NORMAL": "Normal", "ALERTA": "Alerta", "CRITICO": "Crítico"}


def _linha_vibracao(m):
    ponto = f"{m.equipamento.tag} — {m.ponto_medicao} ({m.get_direcao_display()})"
    valor = f"{m.velocidade_rms} mm/s | Zona {m.zona_iso}"
    return ponto, valor, m.criticidade, m.diagnostico_sugerido


def _linha_termografia(m):
    ponto = f"{m.equipamento.tag} — {m.ponto_medicao} ({m.get_sistema_display()})"
    valor = f"ΔT {m.delta_t}°C"
    return ponto, valor, m.criticidade, m.diagnostico_sugerido


def _linha_tecnica(m):
    ponto = f"{m.equipamento.tag} — {m.ponto_medicao} ({m.grandeza})"
    valor = f"{m.valor} {m.unidade}".strip()
    return ponto, valor, m.criticidade, m.diagnostico_sugerido


def gerar_laudo_de_inspecao(inspecao: Inspecao, responsavel) -> Laudo:
    """Cria um laudo em rascunho consolidando o diagnóstico das medições da inspeção."""
    medicoes = [
        _linha_vibracao(m)
        for m in inspecao.medicoes_vibracao.select_related("equipamento", "componente")
    ] + [
        _linha_termografia(m)
        for m in inspecao.medicoes_termografia.select_related("equipamento", "componente")
    ] + [
        _linha_tecnica(m)
        for m in inspecao.medicoes_tecnicas.select_related("equipamento", "componente")
    ]

    criticidade_geral = "NORMAL"
    if medicoes:
        criticidade_geral = max(
            (crit for _, _, crit, _ in medicoes), key=lambda c: ORDEM_CRITICIDADE.get(c, 0)
        )

    linhas_diag, recomendacoes = [], []
    for ponto, valor, crit, diag in medicoes:
        linhas_diag.append(
            f"• {ponto}: {valor} | {LABEL_CRITICIDADE.get(crit, crit)}. {diag}"
        )
        if crit == "CRITICO":
            recomendacoes.append(f"• {ponto}: intervenção corretiva imediata recomendada (gerar OSP).")
        elif crit == "ALERTA":
            recomendacoes.append(f"• {ponto}: programar acompanhamento e monitorar tendência.")

    if not recomendacoes:
        recomendacoes.append("• Manter plano de monitoramento preditivo regular.")

    conclusao = (
        f"Foram analisadas {len(medicoes)} medições ({inspecao.get_tipo_analise_display()}). "
        f"Condição geral classificada como {LABEL_CRITICIDADE.get(criticidade_geral)}."
    )

    return Laudo.objects.create(
        inspecao=inspecao,
        titulo=f"Laudo de {inspecao.get_tipo_analise_display()} — {inspecao.cliente.nome}",
        criticidade_geral=criticidade_geral,
        diagnostico="\n".join(linhas_diag) or "Sem medições registradas.",
        recomendacoes="\n".join(recomendacoes),
        conclusao=conclusao,
        responsavel=responsavel,
    )
