"""
Serviço de despacho de notificações (Anexo I 2.10).

`notificar()` cria o alerta interno (Notificacao) para cada destinatário e dispara os
demais canais habilitados na preferência do usuário.
"""
from django.contrib.auth import get_user_model

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


def notificar(evento, destinatarios, titulo, mensagem, url="", nivel=Nivel.ALERTA):
    """Cria notificações internas e dispara canais habilitados. Evita duplicar destinatário."""
    vistos = set()
    criadas = []
    for user in destinatarios:
        if user is None or user.pk in vistos:
            continue
        vistos.add(user.pk)

        notif = Notificacao.objects.create(
            destinatario=user, evento=evento, titulo=titulo,
            mensagem=mensagem, url=url, nivel=nivel,
        )
        pref = _preferencia(user)
        enviados = [Canal.INTERNO]
        if pref.email and channels.enviar_email(user, titulo, mensagem):
            enviados.append(Canal.EMAIL)
        if pref.whatsapp and channels.enviar_whatsapp(user, titulo, mensagem):
            enviados.append(Canal.WHATSAPP)
        if pref.push and channels.enviar_push(user, titulo, mensagem):
            enviados.append(Canal.PUSH)

        notif.canais_enviados = enviados
        notif.save(update_fields=["canais_enviados", "atualizado_em"])
        criadas.append(notif)
    return criadas
