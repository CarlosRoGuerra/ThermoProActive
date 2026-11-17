"""
Porta de entrada dos recursos de IA: toda função que for usar um provedor pergunta AQUI
se o recurso está habilitado e com qual credencial. Nenhum outro módulo lê as tabelas
nem decifra a chave por conta própria.

    credencial = credencial_do_recurso(RecursoIA.LAUDO_VIBRACAO)
    if credencial is None:
        ...  # recurso desligado: a tela segue sem IA
"""
from dataclasses import dataclass, field

from .cifra import ChaveIlegivel
from .models import AtivacaoIA


@dataclass(frozen=True)
class CredencialIA:
    provedor: str
    modelo: str
    url_base: str
    # Fora do repr: a chave não pode parar num log por causa de um print ou de um traceback.
    chave: str = field(repr=False)


def credencial_do_recurso(recurso) -> CredencialIA | None:
    """Credencial do recurso, ou None quando ele está desligado ou sem chave utilizável."""
    ativacao = (
        AtivacaoIA.objects.select_related("credencial")
        .filter(recurso=recurso, habilitado=True, credencial__isnull=False)
        .first()
    )
    if ativacao is None:
        return None
    try:
        chave = ativacao.credencial.revelar()
    except ChaveIlegivel:
        return None
    return CredencialIA(
        provedor=ativacao.credencial.provedor, modelo=ativacao.modelo_efetivo,
        url_base=ativacao.credencial.url_base, chave=chave,
    )


def recurso_habilitado(recurso) -> bool:
    return credencial_do_recurso(recurso) is not None
