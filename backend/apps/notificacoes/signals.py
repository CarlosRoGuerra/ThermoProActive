"""Eventos automáticos de notificação (Anexo I 2.10.2)."""
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.osp.models import OrdemServico

from .models import EventoNotificacao, Nivel
from .services import notificar, pcm_do_cliente


@receiver(post_save, sender=OrdemServico)
def notif_nova_osp(sender, instance, created, **kwargs):
    """2.10.2.1 — Nova OS."""
    if not created:
        return
    destinatarios = list(pcm_do_cliente(instance.cliente))
    if instance.responsavel:
        destinatarios.append(instance.responsavel)
    notificar(
        EventoNotificacao.NOVA_OSP,
        destinatarios,
        titulo=f"Nova OSP {instance.numero}",
        mensagem=(
            f"OSP gerada para o equipamento {instance.equipamento.tag} "
            f"(prioridade {instance.get_prioridade_display()}, SLA {instance.sla_data})."
        ),
        url="/osps",
        nivel=Nivel.ALERTA,
        chave=f"nova_osp:{instance.pk}",
        cliente=instance.cliente,
    )
# Alertas de medições são emitidos uma vez pela transição registrada em
# preditivos.processar_medicao, acionada pelos signals de OSP na criação/edição.
