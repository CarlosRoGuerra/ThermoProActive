"""Modelos base reutilizados por todas as apps (arquitetura modular — Cláusula 4.2)."""
from django.db import models


class TimeStampedModel(models.Model):
    """Auditoria mínima de criação/atualização (apoio à LGPD — Cláusula 13.2)."""

    criado_em = models.DateTimeField("Criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-criado_em"]


class AtivoQuerySet(models.QuerySet):
    def ativos(self):
        return self.filter(ativo=True)


class BaseModel(TimeStampedModel):
    """Base com soft-delete lógico (não apaga histórico técnico/laudos)."""

    ativo = models.BooleanField("Ativo", default=True)

    objects = AtivoQuerySet.as_manager()

    class Meta:
        abstract = True
        ordering = ["-criado_em"]
