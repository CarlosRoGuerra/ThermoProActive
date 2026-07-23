"""Geração automática de OSP a partir de medições críticas (Anexo I 2.6.1.1)."""
from .models import STATUS_ABERTOS, GrauRisco, OrdemServico, Prioridade

# Criticidade da medição → prioridade da OSP.
CRITICIDADE_PARA_PRIORIDADE = {
    "CRITICO": Prioridade.ALTA,
    "ALERTA": Prioridade.MEDIA,
}

# Criticidade da medição → Grau de Risco do laudo (glossário §6.2).
# O analista pode reclassificar manualmente: quem dá o GR final é o técnico.
CRITICIDADE_PARA_GR = {
    "CRITICO": GrauRisco.GR2,
    "ALERTA": GrauRisco.GR3,
    "NORMAL": GrauRisco.GR4,
}


def gerar_osp_de_medicao(medicao, tipo_label: str) -> OrdemServico | None:
    """
    Cria uma OSP para uma medição crítica, caso ainda não exista OSP em aberto
    para o mesmo equipamento na mesma inspeção. Retorna a OSP criada ou None.
    """
    if medicao.criticidade != "CRITICO":
        return None

    inspecao = medicao.inspecao
    equipamento = medicao.equipamento

    ja_existe = OrdemServico.objects.filter(
        equipamento=equipamento,
        inspecao=inspecao,
        status__in=STATUS_ABERTOS,
    ).exists()
    if ja_existe:
        return None

    return OrdemServico.objects.create(
        cliente=inspecao.cliente,
        equipamento=equipamento,
        inspecao=inspecao,
        titulo=f"OSP automática — {equipamento.tag} ({tipo_label})",
        descricao=(
            f"Gerada automaticamente a partir de medição crítica em "
            f"{medicao.ponto_medicao}. {medicao.diagnostico_sugerido}"
        ),
        prioridade=CRITICIDADE_PARA_PRIORIDADE.get(medicao.criticidade, Prioridade.MEDIA),
        grau_risco=CRITICIDADE_PARA_GR.get(medicao.criticidade, GrauRisco.GR3),
        criticidade_origem=medicao.criticidade,
        anomalia=medicao.diagnostico_sugerido,
        componente=getattr(medicao.componente, "nome", "") or "",
        responsavel=inspecao.tecnico,
        gerada_automaticamente=True,
    )
