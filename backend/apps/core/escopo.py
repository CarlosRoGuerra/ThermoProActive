"""
Escopo de acesso por cliente e por liberação (S-24, Portal — item 2.7).

Perfis de cliente só enxergam o que é da própria empresa (`escopo_cliente`, em
`apps.coletas.views`) e, além disso, só o que já foi LIBERADO pela contratada:
achado confirmado para o cliente, carregamento transferido, relatório finalizado.
Dados internos em elaboração ficam fora da API do cliente.

Internos (ADMIN/GESTOR/TÉCNICO) não passam por nenhum filtro desta camada.
"""


def liberado_ao_cliente(qs, user, **filtros_liberacao):
    """
    Para perfil de cliente, restringe `qs` aos registros liberados (`filtros_liberacao`
    são lookups do Django). Falha fechada: cliente sem `cliente_id` não vê nada.
    Para internos devolve `qs` inalterado.
    """
    if not user.is_cliente:
        return qs
    if not user.cliente_id:
        return qs.none()
    return qs.filter(**filtros_liberacao)


def setores_restritos(user):
    """
    Item 2.1.1.6. None = sem restrição de setor (vale o cliente inteiro). Lista de ids =
    restrito a esses setores. Só cliente pode ter restrição; interno sempre None.
    """
    if not user.is_cliente or not user.cliente_id:
        return None
    ids = list(user.restricoes_setor.values_list("setor_id", flat=True))
    return ids or None


def restringe_setor(qs, user, campo_setor):
    """
    Aplica a restrição de setor a `qs`. `campo_setor` é o caminho do ORM até o Setor
    (ex.: "setor", "equipamento__setor", "item__equipamento__setor"). Falha fechada:
    cliente sem vínculo não vê nada. Internos e clientes sem restrição: `qs` inalterado.
    """
    if not user.is_cliente:
        return qs
    if not user.cliente_id:
        return qs.none()
    ids = setores_restritos(user)
    if ids is None:
        return qs
    return qs.filter(**{f"{campo_setor}__in": ids})


def restringe_setor_por_filho(qs, user, modelo_filho, campo_fk_pai, campo_setor_filho="equipamento__setor"):
    """
    Para pai sem setor próprio (ex.: Carregamento, que tem itens): mantém o pai se ALGUM
    filho cai num setor permitido. Usa subconsulta, então não duplica linhas.
    """
    if not user.is_cliente:
        return qs
    if not user.cliente_id:
        return qs.none()
    ids = setores_restritos(user)
    if ids is None:
        return qs
    filhos = modelo_filho.objects.filter(**{f"{campo_setor_filho}__in": ids}).values(campo_fk_pai)
    return qs.filter(pk__in=filhos)


def restringe_setor_por_filhos(qs, user, filhos, campo_setor_filho="equipamento__setor"):
    """
    Como `restringe_setor_por_filho`, mas com filhos de vários tipos: o pai aparece se
    QUALQUER filho (de qualquer tipo) cair num setor permitido. `filhos` = [(modelo, campo_fk_pai)].
    Ex.: Inspeção tem medições de vibração, termografia e técnica, cada uma com equipamento.
    """
    from django.db.models import Q
    if not user.is_cliente:
        return qs
    if not user.cliente_id:
        return qs.none()
    ids = setores_restritos(user)
    if ids is None:
        return qs
    condicao = Q(pk__in=[])
    for modelo, campo_fk in filhos:
        condicao |= Q(pk__in=modelo.objects.filter(**{f"{campo_setor_filho}__in": ids}).values(campo_fk))
    return qs.filter(condicao)
