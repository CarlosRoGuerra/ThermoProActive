"""
Ordem de Serviço Preditiva (OSP) — Anexo I, item 2.6.

Gerada automaticamente quando uma medição é classificada como CRÍTICA (item 2.6.1.1),
com prioridade e SLA definidos por regra. Também pode ser criada manualmente.
"""
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.cadastros.models import Cliente, Equipamento
from apps.coletas.models import Inspecao
from apps.core.models import TimeStampedModel


class Prioridade(models.TextChoices):
    BAIXA = "BAIXA", "Baixa"
    MEDIA = "MEDIA", "Média"
    ALTA = "ALTA", "Alta"
    URGENTE = "URGENTE", "Urgente"


# Prazo de SLA (dias) por prioridade — parametrizável (Cláusula 12.4).
SLA_DIAS = {
    Prioridade.URGENTE: 1,
    Prioridade.ALTA: 3,
    Prioridade.MEDIA: 7,
    Prioridade.BAIXA: 15,
}


class StatusOSP(models.TextChoices):
    ABERTA = "ABERTA", "Aberta"
    EM_ANALISE = "EM_ANALISE", "Em análise"
    EM_EXECUCAO = "EM_EXECUCAO", "Em execução"
    AGUARDANDO_APROVACAO = "AGUARDANDO_APROVACAO", "Aguardando aprovação"
    FINALIZADA = "FINALIZADA", "Finalizada"
    CANCELADA = "CANCELADA", "Cancelada"


#: Status que indicam OSP ainda em aberto (não permite duplicar para o mesmo equipamento).
STATUS_ABERTOS = {
    StatusOSP.ABERTA,
    StatusOSP.EM_ANALISE,
    StatusOSP.EM_EXECUCAO,
    StatusOSP.AGUARDANDO_APROVACAO,
}


class OrdemServico(TimeStampedModel):
    numero = models.CharField("Número da OSP", max_length=20, unique=True, editable=False)
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="osps")
    equipamento = models.ForeignKey(Equipamento, on_delete=models.PROTECT, related_name="osps")
    inspecao = models.ForeignKey(
        Inspecao, on_delete=models.SET_NULL, null=True, blank=True, related_name="osps"
    )

    titulo = models.CharField("Título", max_length=200)
    descricao = models.TextField("Descrição", blank=True)
    prioridade = models.CharField(max_length=8, choices=Prioridade.choices, default=Prioridade.MEDIA)
    status = models.CharField(max_length=20, choices=StatusOSP.choices, default=StatusOSP.ABERTA)
    criticidade_origem = models.CharField("Criticidade de origem", max_length=8, blank=True)
    gerada_automaticamente = models.BooleanField("Gerada automaticamente", default=False)

    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="osps", verbose_name="Técnico responsável",
    )
    sla_data = models.DateField("Prazo (SLA)", null=True, blank=True)
    finalizada_em = models.DateTimeField("Finalizada em", null=True, blank=True)

    # Custos — base para o relatório financeiro (Anexo I 2.9.1.5).
    custo_estimado = models.DecimalField(
        "Custo estimado (R$)", max_digits=12, decimal_places=2, null=True, blank=True
    )
    custo_real = models.DecimalField(
        "Custo real (R$)", max_digits=12, decimal_places=2, null=True, blank=True
    )

    class Meta:
        verbose_name = "Ordem de Serviço Preditiva"
        verbose_name_plural = "Ordens de Serviço Preditivas"
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.numero} — {self.equipamento.tag}"

    @staticmethod
    def proximo_numero() -> str:
        ano = timezone.now().year
        prefixo = f"OSP-{ano}-"
        ultimo = (
            OrdemServico.objects.filter(numero__startswith=prefixo)
            .order_by("-numero")
            .values_list("numero", flat=True)
            .first()
        )
        seq = int(ultimo.split("-")[-1]) + 1 if ultimo else 1
        return f"{prefixo}{seq:04d}"

    @property
    def sla_vencido(self) -> bool:
        return bool(
            self.sla_data
            and self.status in STATUS_ABERTOS
            and self.sla_data < timezone.now().date()
        )

    def save(self, *args, **kwargs):
        if not self.numero:
            self.numero = self.proximo_numero()
        if self.sla_data is None and self.prioridade:
            self.sla_data = timezone.now().date() + timedelta(days=SLA_DIAS.get(self.prioridade, 7))
        if self.status == StatusOSP.FINALIZADA and self.finalizada_em is None:
            self.finalizada_em = timezone.now()
        super().save(*args, **kwargs)
