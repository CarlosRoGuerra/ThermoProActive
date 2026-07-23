"""
Ordem de Serviço Preditiva (OSP) — Anexo I, item 2.6.

Gerada automaticamente quando uma medição é classificada como CRÍTICA (item 2.6.1.1),
com prioridade e SLA definidos por regra. Também pode ser criada manualmente.
"""
from datetime import timedelta
from decimal import Decimal

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


class GrauRisco(models.TextChoices):
    """
    Grau de Risco do laudo (glossário §6.2 do relatório técnico do cliente).
    É o que determina o prazo de correção da anomalia e aparece em destaque
    na Seção D — Ordem de Serviço.
    """

    GR0 = "GR0", "GR-0 — Sem anomalia"
    GR1 = "GR1", "GR-1 — Risco eminente"
    GR2 = "GR2", "GR-2 — Risco elevado"
    GR3 = "GR3", "GR-3 — Risco moderado"
    GR4 = "GR4", "GR-4 — Risco baixo"


#: Prazo máximo de intervenção (dias) por Grau de Risco — glossário §6.2.1 a §6.2.4.
PRAZO_GR_DIAS = {
    GrauRisco.GR1: 3,
    GrauRisco.GR2: 10,
    GrauRisco.GR3: 20,
    GrauRisco.GR4: 30,
}

#: Rótulo curto de severidade usado no relatório ("Risco Baixo" sob o GR-4).
DESCRICAO_GR = {
    GrauRisco.GR0: "Sem anomalia",
    GrauRisco.GR1: "Risco Eminente",
    GrauRisco.GR2: "Risco Elevado",
    GrauRisco.GR3: "Risco Moderado",
    GrauRisco.GR4: "Risco Baixo",
}


class StatusOSP(models.TextChoices):
    """
    Ciclo de vida acordado na reunião de 22/07/2026:
    Aberta → Planejada → Executada → Finalizada (alimentado pelo cliente).
    Os demais status seguem disponíveis para o fluxo interno.
    """

    ABERTA = "ABERTA", "Aberta"
    PLANEJADA = "PLANEJADA", "Planejada"
    EXECUTADA = "EXECUTADA", "Executada"
    EM_ANALISE = "EM_ANALISE", "Em análise"
    EM_EXECUCAO = "EM_EXECUCAO", "Em execução"
    AGUARDANDO_APROVACAO = "AGUARDANDO_APROVACAO", "Aguardando aprovação"
    FINALIZADA = "FINALIZADA", "Finalizada"
    CANCELADA = "CANCELADA", "Cancelada"


class Acompanhamento(models.TextChoices):
    """
    Situação da anomalia na REAVALIAÇÃO seguinte — alimenta o gráfico
    "Controle das O.S.P.'s" (Seção B do relatório). É independente do status
    operacional: uma OSP finalizada pode voltar como reincidente.
    """

    ABERTA = "ABERTA", "Aberta"
    CORRIGIDA = "CORRIGIDA", "Corrigida"
    REINCIDENTE = "REINCIDENTE", "Reincidente"
    NAO_REAVALIADA = "NAO_REAVALIADA", "Não reavaliada"
    RETORNO_INFO = "RETORNO_INFO", "Retorno de informação"


#: Status que indicam OSP ainda em aberto (não permite duplicar para o mesmo equipamento).
STATUS_ABERTOS = {
    StatusOSP.ABERTA,
    StatusOSP.PLANEJADA,
    StatusOSP.EXECUTADA,
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

    # --- Conteúdo técnico da Seção D do relatório ---------------------------
    grau_risco = models.CharField(
        "Grau de risco", max_length=3, choices=GrauRisco.choices, blank=True,
        help_text="Define o prazo de correção (GR-1: 3d, GR-2: 10d, GR-3: 20d, GR-4: 30d).",
    )
    acompanhamento = models.CharField(
        "Acompanhamento", max_length=15, choices=Acompanhamento.choices,
        default=Acompanhamento.ABERTA,
        help_text="Situação da anomalia na reavaliação seguinte (gráfico Controle das OSPs).",
    )
    anomalia = models.TextField("Anomalia detectada", blank=True)
    recomendacao = models.TextField("Recomendação", blank=True)
    observacao = models.TextField("Observação", blank=True)
    componente = models.CharField("Componente", max_length=120, blank=True)
    amplitude_velocidade = models.DecimalField(
        "Amplitude velocidade global (mm/s)", max_digits=8, decimal_places=2, null=True, blank=True
    )
    amplitude_aceleracao = models.DecimalField(
        "Amplitude aceleração global (mm/s²)", max_digits=8, decimal_places=2, null=True, blank=True
    )

    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="osps", verbose_name="Técnico responsável",
    )
    sla_data = models.DateField("Prazo (SLA)", null=True, blank=True)
    finalizada_em = models.DateTimeField("Finalizada em", null=True, blank=True)

    # --- Etapas alimentadas pelo cliente (reunião 22/07: data + responsável) --
    planejado_em = models.DateTimeField("Planejamento em", null=True, blank=True)
    planejado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="osps_planejadas", verbose_name="Planejamento por",
    )
    executado_em = models.DateTimeField("Corretiva em", null=True, blank=True)
    executado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="osps_executadas", verbose_name="Corretiva por",
    )
    finalizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="osps_finalizadas", verbose_name="Finalização por",
    )
    descricao_corretiva = models.TextField(
        "Descrição da corretiva executada", blank=True,
        help_text="O que a equipe de manutenção efetivamente fez.",
    )

    # --- Avaliação de Resultados (tabela verde da Seção D) -------------------
    # Compara o custo da manutenção ORIENTADA PELA PREDITIVA com o que teria sido
    # gasto numa EMERGÊNCIA. A diferença é o retorno do investimento (ROI).
    pred_mao_obra_h = models.DecimalField("Preditiva — mão de obra (h)", max_digits=10, decimal_places=2, null=True, blank=True)
    pred_mao_obra_valor = models.DecimalField("Preditiva — mão de obra (R$)", max_digits=12, decimal_places=2, null=True, blank=True)
    pred_terceirizado_h = models.DecimalField("Preditiva — serviço terceirizado (h)", max_digits=10, decimal_places=2, null=True, blank=True)
    pred_terceirizado_valor = models.DecimalField("Preditiva — serviço terceirizado (R$)", max_digits=12, decimal_places=2, null=True, blank=True)
    pred_material_valor = models.DecimalField("Preditiva — material de reparo (R$)", max_digits=12, decimal_places=2, null=True, blank=True)
    pred_producao_h = models.DecimalField("Preditiva — produção (h/ton)", max_digits=10, decimal_places=2, null=True, blank=True)
    pred_producao_valor = models.DecimalField("Preditiva — produção (R$)", max_digits=12, decimal_places=2, null=True, blank=True)
    pred_outros_valor = models.DecimalField("Preditiva — outros (R$)", max_digits=12, decimal_places=2, null=True, blank=True)

    emerg_mao_obra_h = models.DecimalField("Emergencial — mão de obra (h)", max_digits=10, decimal_places=2, null=True, blank=True)
    emerg_mao_obra_valor = models.DecimalField("Emergencial — mão de obra (R$)", max_digits=12, decimal_places=2, null=True, blank=True)
    emerg_terceirizado_h = models.DecimalField("Emergencial — serviço terceirizado (h)", max_digits=10, decimal_places=2, null=True, blank=True)
    emerg_terceirizado_valor = models.DecimalField("Emergencial — serviço terceirizado (R$)", max_digits=12, decimal_places=2, null=True, blank=True)
    emerg_material_valor = models.DecimalField("Emergencial — material de reparo (R$)", max_digits=12, decimal_places=2, null=True, blank=True)
    emerg_producao_h = models.DecimalField("Emergencial — produção (h/ton)", max_digits=10, decimal_places=2, null=True, blank=True)
    emerg_producao_valor = models.DecimalField("Emergencial — produção (R$)", max_digits=12, decimal_places=2, null=True, blank=True)
    emerg_outros_valor = models.DecimalField("Emergencial — outros (R$)", max_digits=12, decimal_places=2, null=True, blank=True)

    # Custos consolidados — base do relatório financeiro (Anexo I 2.9.1.5).
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

    @property
    def grau_risco_descricao(self) -> str:
        """Rótulo que acompanha o GR no relatório (ex.: 'Risco Baixo')."""
        return DESCRICAO_GR.get(self.grau_risco, "")

    @property
    def prazo_dias(self) -> int | None:
        """Prazo máximo de intervenção segundo o Grau de Risco."""
        return PRAZO_GR_DIAS.get(self.grau_risco)

    def _somar(self, campos: list[str]) -> Decimal:
        return sum((getattr(self, c) or Decimal("0")) for c in campos)

    @property
    def total_preditiva(self) -> Decimal:
        """Custo total da manutenção orientada pela preditiva."""
        return self._somar([
            "pred_mao_obra_valor", "pred_terceirizado_valor", "pred_material_valor",
            "pred_producao_valor", "pred_outros_valor",
        ])

    @property
    def total_emergencial(self) -> Decimal:
        """Custo projetado caso a falha tivesse ocorrido em emergência."""
        return self._somar([
            "emerg_mao_obra_valor", "emerg_terceirizado_valor", "emerg_material_valor",
            "emerg_producao_valor", "emerg_outros_valor",
        ])

    @property
    def retorno_investimento(self) -> Decimal:
        """
        ROI = quanto se evitou gastar ao corrigir pela preditiva em vez da emergência
        ("o cálculo de uma menos a outra", conforme definido pelo cliente).
        """
        return self.total_emergencial - self.total_preditiva

    def save(self, *args, **kwargs):
        if not self.numero:
            self.numero = self.proximo_numero()
        # O prazo segue o Grau de Risco quando informado; senão, cai na prioridade.
        if self.sla_data is None:
            dias = PRAZO_GR_DIAS.get(self.grau_risco) or SLA_DIAS.get(self.prioridade, 7)
            self.sla_data = timezone.now().date() + timedelta(days=dias)
        # Carimba data/hora ao entrar em cada etapa do ciclo definido com o cliente.
        agora = timezone.now()
        if self.status == StatusOSP.PLANEJADA and self.planejado_em is None:
            self.planejado_em = agora
        if self.status == StatusOSP.EXECUTADA and self.executado_em is None:
            self.executado_em = agora
        if self.status == StatusOSP.FINALIZADA and self.finalizada_em is None:
            self.finalizada_em = agora
        # Consolida o custo real a partir da Avaliação de Resultados.
        if self.custo_real is None and self.total_preditiva:
            self.custo_real = self.total_preditiva
        super().save(*args, **kwargs)
