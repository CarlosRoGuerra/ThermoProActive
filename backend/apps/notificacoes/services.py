"""
Serviço de despacho de notificações (Anexo I 2.10).

`notificar()` cria o alerta interno (Notificacao) para cada destinatário e dispara os
demais canais habilitados na preferência do usuário.
"""
from django.contrib.auth import get_user_model
from django.db import transaction

from apps.accounts.models import Perfil

from . import channels
from .models import Canal, Nivel, Notificacao, PreferenciaNotificacao

User = get_user_model()


# --- Helpers de destinatários -------------------------------------------------

def gestores():
    return User.objects.filter(perfil__in=[Perfil.ADMIN, Perfil.GESTOR], is_active=True)


def pcm_do_cliente(cliente):
    return User.objects.filter(cliente=cliente, perfil=Perfil.CLIENTE_PCM, is_active=True)


def clientes_do_cliente(cliente):
    return User.objects.filter(
        cliente=cliente,
        perfil__in=[Perfil.CLIENTE_CORP, Perfil.CLIENTE_LOCAL, Perfil.CLIENTE_PCM],
        is_active=True,
    )


def aprovadores_do_cliente(cliente):
    return User.objects.filter(
        cliente=cliente,
        perfil__in=[Perfil.CLIENTE_CORP, Perfil.CLIENTE_LOCAL, Perfil.CLIENTE_PCM],
        is_active=True,
    )


# --- Despacho -----------------------------------------------------------------

def _preferencia(user) -> PreferenciaNotificacao:
    pref, _ = PreferenciaNotificacao.objects.get_or_create(user=user)
    return pref


def destinatario_permitido(user, cliente=None) -> bool:
    """
    Conta ativa (is_active E estado ACTIVE) e, se for do Portal, da MESMA
    empresa do evento. Interno recebe de qualquer cliente que atende.
    Defesa em profundidade: os helpers acima já filtram, mas responsável/técnico
    entram direto e a regra não pode depender de quem montou a lista.
    """
    if user is None or not user.is_active or getattr(user, "estado", "ACTIVE") != "ACTIVE":
        return False
    if getattr(user, "is_cliente", False):
        cliente_id = getattr(cliente, "pk", cliente)
        return bool(user.cliente_id) and cliente_id is not None and user.cliente_id == cliente_id
    return True


def notificar(evento, destinatarios, titulo, mensagem, url="", nivel=Nivel.ALERTA, *,
              evento_preditivo=None, chave="", cliente=None):
    """
    Registra o alerta interno de cada destinatário e enfileira os canais externos
    escolhidos na preferência dele (ver `entregas`).

    * `cliente`: empresa a que o evento pertence. Usuário do Portal de OUTRA
      empresa (ou de nenhuma) é descartado — nunca recebe o aviso.
      Sem `cliente`, nenhum usuário do Portal recebe.
    * `chave`: identifica a ocorrência ("nova_osp:42"). Com ela, repetir o evento
      (retry, reprocessamento, agendador rodando de novo) não duplica: no máximo
      uma notificação por destinatário e chave, garantido no banco.
    * Os canais externos só saem depois do commit; falha de canal nunca desfaz
      nem interrompe a operação que gerou o evento.
    """
    from .entregas import canais_da_preferencia, criar_entregas, processar_imediatamente

    if evento_preditivo is not None and not chave:
        chave = f"evento_preditivo:{evento_preditivo.pk}"
    vistos = set()
    criadas, entregas = [], []
    for user in destinatarios:
        if user is None or user.pk in vistos:
            continue
        vistos.add(user.pk)
        if not destinatario_permitido(user, cliente):
            continue

        dados = dict(evento=evento, titulo=titulo, mensagem=mensagem, url=url,
                     nivel=nivel, canais_enviados=[Canal.INTERNO], evento_preditivo=evento_preditivo)
        if chave:
            with transaction.atomic():
                notif, criada = Notificacao.objects.get_or_create(destinatario=user, chave=chave, defaults=dados)
            if not criada:
                continue
        else:
            notif = Notificacao.objects.create(destinatario=user, **dados)
        entregas += criar_entregas(notif, canais_da_preferencia(_preferencia(user)))
        criadas.append(notif)
    if entregas:
        # Nunca envia canal externo por uma transação que pode sofrer rollback.
        transaction.on_commit(lambda ids=tuple(entregas): processar_imediatamente(ids), robust=True)
    return criadas
