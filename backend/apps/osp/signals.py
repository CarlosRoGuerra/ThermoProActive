"""Signals que disparam a geração automática de OSP (Anexo I 2.6.1.1)."""
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.coletas.models import MedicaoTecnica, MedicaoTermografia, MedicaoVibracao

from .services import gerar_osp_de_medicao


@receiver(post_save, sender=MedicaoVibracao)
def osp_por_vibracao(sender, instance, created, **kwargs):
    if created:
        gerar_osp_de_medicao(instance, tipo_label="Vibração")


@receiver(post_save, sender=MedicaoTermografia)
def osp_por_termografia(sender, instance, created, **kwargs):
    if created:
        gerar_osp_de_medicao(instance, tipo_label="Termografia")


@receiver(post_save, sender=MedicaoTecnica)
def osp_por_tecnica(sender, instance, created, **kwargs):
    if created:
        gerar_osp_de_medicao(instance, tipo_label=instance.get_tipo_display())
