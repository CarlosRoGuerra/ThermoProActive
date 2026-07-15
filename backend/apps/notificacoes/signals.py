"""Eventos automáticos de notificação (Anexo I 2.10.2)."""
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.coletas.models import MedicaoTecnica, MedicaoTermografia, MedicaoVibracao
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
    )


def _notif_equipamento_critico(instance, tipo_label):
    """2.10.2.2 — Equipamento crítico."""
    if instance.criticidade != "CRITICO":
        return
    inspecao = instance.inspecao
    destinatarios = list(pcm_do_cliente(inspecao.cliente))
    if inspecao.tecnico:
        destinatarios.append(inspecao.tecnico)
    notificar(
        EventoNotificacao.EQUIPAMENTO_CRITICO,
        destinatarios,
        titulo=f"Equipamento crítico: {instance.equipamento.tag}",
        mensagem=(
            f"Medição de {tipo_label} classificada como CRÍTICA em "
            f"{instance.ponto_medicao}. {instance.diagnostico_sugerido}"
        ),
        url=f"/inspecoes/{inspecao.id}",
        nivel=Nivel.CRITICO,
    )


@receiver(post_save, sender=MedicaoVibracao)
def notif_vibracao_critica(sender, instance, created, **kwargs):
    if created:
        _notif_equipamento_critico(instance, "vibração")


@receiver(post_save, sender=MedicaoTermografia)
def notif_termografia_critica(sender, instance, created, **kwargs):
    if created:
        _notif_equipamento_critico(instance, "termografia")


@receiver(post_save, sender=MedicaoTecnica)
def notif_tecnica_critica(sender, instance, created, **kwargs):
    if created:
        _notif_equipamento_critico(instance, instance.get_tipo_display().lower())
