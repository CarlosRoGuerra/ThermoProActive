"""
Laudos Técnicos — Anexo I, item 2.5.

`Laudo` é gerado a partir de uma `Inspecao` (item 2.5.1.1 — geração automática) e numerado
sequencialmente por ano (item 3.1.19). O conteúdo agrega diagnóstico, criticidade e
recomendações das medições (item 2.5.2). PDF é gerado pelo front via impressão do template
HTML — sem dependência nativa/proprietária (Cláusula 12.4).
"""
from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.coletas.models import Inspecao
from apps.core.models import TimeStampedModel


class StatusLaudo(models.TextChoices):
    RASCUNHO = "RASCUNHO", "Rascunho"
    EMITIDO = "EMITIDO", "Emitido"
    CANCELADO = "CANCELADO", "Cancelado"


class Laudo(TimeStampedModel):
    numero = models.CharField("Número do laudo", max_length=20, unique=True, editable=False)
    inspecao = models.ForeignKey(Inspecao, on_delete=models.PROTECT, related_name="laudos")
    versao = models.PositiveSmallIntegerField("Versão", default=1)

    titulo = models.CharField("Título", max_length=200)
    criticidade_geral = models.CharField("Criticidade geral", max_length=8, blank=True)
    diagnostico = models.TextField("Diagnóstico técnico", blank=True)        # item 2.5.2.2
    recomendacoes = models.TextField("Recomendações", blank=True)            # item 2.5.2.4
    conclusao = models.TextField("Conclusão", blank=True)

    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="laudos",
        verbose_name="Responsável técnico",
    )
    status = models.CharField(max_length=10, choices=StatusLaudo.choices, default=StatusLaudo.RASCUNHO)
    data_emissao = models.DateTimeField("Data de emissão", null=True, blank=True)

    class Meta:
        verbose_name = "Laudo"
        verbose_name_plural = "Laudos"
        ordering = ["-criado_em"]

    def __str__(self):
        return f"Laudo {self.numero} (v{self.versao})"

    @staticmethod
    def proximo_numero() -> str:
        ano = timezone.now().year
        prefixo = f"LT-{ano}-"
        ultimo = (
            Laudo.objects.filter(numero__startswith=prefixo)
            .order_by("-numero")
            .values_list("numero", flat=True)
            .first()
        )
        seq = int(ultimo.split("-")[-1]) + 1 if ultimo else 1
        return f"{prefixo}{seq:04d}"

    def save(self, *args, **kwargs):
        if not self.numero:
            self.numero = self.proximo_numero()
        super().save(*args, **kwargs)

    def emitir(self):
        self.status = StatusLaudo.EMITIDO
        self.data_emissao = timezone.now()
        self.save(update_fields=["status", "data_emissao", "atualizado_em"])
