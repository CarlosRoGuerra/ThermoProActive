"""Cadastros e registros da análise preditiva — Anexo I 2.4.1.3, 2.4.1.5 e 2.4.2.4.

Tudo que decide um número ou uma sugestão é cadastro do Master, com origem,
fonte e vigência, no padrão de `apps.cadastros.criterios`. Quando não há cadastro
validado, o sistema não inventa valor: devolve o motivo.

- ConfiguracaoTendencia: parâmetros estatísticos (pontos, janela, R², horizonte).
  Não são limites de alarme.
- LimiteAlarmeSerie: limite de alarme para séries que não têm critério próprio
  (termografia, ensaios elétricos, espessura…). Vibração usa o critério normativo.
- MatrizRisco: pesos, mapa de consequência e faixas do índice de risco.
- RegraSugestao: sugestão cadastrada por tecnologia/componente/anomalia/criticidade.
- AceitacaoSugestao: decisão do analista sobre uma sugestão exibida (aderência).
"""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.cadastros.models import (
    Cliente,
    Equipamento,
    OrigemCriterio,
    TecnologiaAnalise,
    TipoAnomalia,
    TipoComponente,
    TipoEquipamento,
    TipoRecomendacao,
)
from apps.core.models import BaseModel, TimeStampedModel
from apps.coletas.models import Achado, Criticidade, SistemaTermografia, TipoAnalise


class Validacao(models.TextChoices):
    PROVISORIA = "PROVISORIA", "Padrão provisório — a confirmar pelo cliente"
    VALIDADA = "VALIDADA", "Validada pelo responsável técnico"


class SentidoLimite(models.TextChoices):
    SUPERIOR = "SUPERIOR", "Acima do limite é pior (ex.: vibração, ΔT)"
    INFERIOR = "INFERIOR", "Abaixo do limite é pior (ex.: resistência de isolamento)"


class ConfiguracaoTendencia(BaseModel):
    """Parâmetros estatísticos da projeção de tendência — não são limites de alarme."""

    nome = models.CharField("Nome", max_length=120)
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, null=True, blank=True,
                                related_name="configuracoes_tendencia",
                                help_text="Vazio = vale para todos os clientes.")
    pontos_minimos = models.PositiveSmallIntegerField(
        "Pontos mínimos", default=4, validators=[MinValueValidator(3), MaxValueValidator(100)],
        help_text="Abaixo disso a série é tratada como insuficiente.",
    )
    janela = models.PositiveSmallIntegerField(
        "Janela (últimas N leituras)", default=8, validators=[MinValueValidator(3), MaxValueValidator(200)],
    )
    r2_minimo = models.DecimalField(
        "R² ajustado mínimo", max_digits=4, decimal_places=2, default=Decimal("0.50"),
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("1"))],
    )
    horizonte_dias = models.PositiveIntegerField(
        "Horizonte da estimativa (dias)", default=365, validators=[MinValueValidator(1), MaxValueValidator(3650)],
        help_text="Cruzamentos além deste prazo não geram data.",
    )
    margem_modelo = models.DecimalField(
        "Margem para o modelo exponencial", max_digits=4, decimal_places=2, default=Decimal("0.05"),
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("1"))],
        help_text="O exponencial só é usado se o R² ajustado superar o linear por pelo menos esta margem.",
    )
    validacao = models.CharField("Situação", max_length=12, choices=Validacao.choices, default=Validacao.PROVISORIA)
    fonte = models.CharField("Fonte / aprovação", max_length=250, blank=True)
    vigencia_inicio = models.DateField("Vigência — início", null=True, blank=True)
    vigencia_fim = models.DateField("Vigência — fim", null=True, blank=True)

    class Meta(BaseModel.Meta):
        verbose_name = "Configuração de tendência"
        verbose_name_plural = "Configurações de tendência"

    def __str__(self):
        return self.nome

    def clean(self):
        super().clean()
        if self.janela < self.pontos_minimos:
            raise ValidationError({"janela": "A janela deve ser maior ou igual ao número mínimo de pontos."})
        if self.validacao == Validacao.VALIDADA and not self.fonte.strip():
            raise ValidationError({"fonte": "Uma configuração validada precisa de fonte ou aprovação."})


class LimiteAlarmeSerie(BaseModel):
    """Limite de alarme cadastrado para uma série numérica sem critério normativo próprio."""

    modalidade = models.CharField("Modalidade", max_length=20,
                                  choices=[c for c in TipoAnalise.choices if c[0] != TipoAnalise.VIBRACAO])
    grandeza = models.CharField("Grandeza", max_length=80,
                                help_text="Igual à grandeza registrada na medição. Termografia: delta_t.")
    unidade = models.CharField("Unidade", max_length=20, blank=True)
    # Só termografia: sistema específico (ELETRICO, MEC_DINAMICO, MEC_ESTATICO, PROCESSO). Vazio = todos.
    sistema = models.CharField("Sistema termográfico", max_length=15, blank=True, default="",
                               choices=[("", "Todos os sistemas")] + list(SistemaTermografia.choices))
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, null=True, blank=True,
                                related_name="limites_alarme_serie")
    tipo_equipamento = models.ForeignKey(TipoEquipamento, on_delete=models.CASCADE, null=True, blank=True,
                                         related_name="limites_alarme_serie")
    equipamento = models.ForeignKey(Equipamento, on_delete=models.CASCADE, null=True, blank=True,
                                    related_name="limites_alarme_serie")
    sentido = models.CharField("Sentido", max_length=10, choices=SentidoLimite.choices,
                               default=SentidoLimite.SUPERIOR)
    valor_alerta = models.DecimalField("Limite de alerta", max_digits=14, decimal_places=4, null=True, blank=True)
    valor_critico = models.DecimalField("Limite crítico", max_digits=14, decimal_places=4, null=True, blank=True)
    origem = models.CharField("Origem", max_length=20, choices=OrigemCriterio.choices,
                              default=OrigemCriterio.RESPONSAVEL_TECNICO)
    fonte = models.CharField("Fonte", max_length=250, blank=True,
                             help_text="Norma, manual, contrato ou acordo que sustenta o valor.")
    validacao = models.CharField("Situação", max_length=12, choices=Validacao.choices, default=Validacao.PROVISORIA)
    vigencia_inicio = models.DateField("Vigência — início", null=True, blank=True)
    vigencia_fim = models.DateField("Vigência — fim", null=True, blank=True)

    class Meta(BaseModel.Meta):
        verbose_name = "Limite de alarme de série"
        verbose_name_plural = "Limites de alarme de série"

    def __str__(self):
        return f"{self.get_modalidade_display()} · {self.grandeza}"

    def clean(self):
        super().clean()
        if self.valor_alerta is None and self.valor_critico is None:
            raise ValidationError("Informe ao menos o limite de alerta ou o crítico.")
        if self.valor_alerta is not None and self.valor_critico is not None:
            ordem_ok = (self.valor_alerta <= self.valor_critico) if self.sentido == SentidoLimite.SUPERIOR \
                else (self.valor_alerta >= self.valor_critico)
            if not ordem_ok:
                raise ValidationError("Limite de alerta e crítico fora de ordem para o sentido escolhido.")
        if self.validacao == Validacao.VALIDADA and not self.fonte.strip():
            raise ValidationError({"fonte": "Um limite validado precisa de fonte ou aprovação."})


class MatrizRisco(BaseModel):
    """
    Matriz do índice de risco por equipamento. O índice é uma PRIORIZAÇÃO:
    índice = 100 × p × c, com p = proxy de probabilidade (severidade e tendência
    ponderadas, normalizadas entre 0 e 1) e c = consequência (criticidade do ativo,
    normalizada). Não é probabilidade de falha. Os pesos e as faixas são
    parâmetros cadastrados, confirmados pelo cliente.
    """

    nome = models.CharField("Nome", max_length=120)
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, null=True, blank=True,
                                related_name="matrizes_risco", help_text="Vazio = vale para todos os clientes.")
    peso_severidade = models.DecimalField("Peso da severidade atual", max_digits=4, decimal_places=2,
                                          default=Decimal("0.60"))
    peso_tendencia = models.DecimalField("Peso da tendência", max_digits=4, decimal_places=2,
                                         default=Decimal("0.40"))
    consequencia = models.JSONField(
        "Consequência por criticidade do ativo (A, B, C)", default=dict,
        help_text='Ex.: {"A": 3, "B": 2, "C": 1} — inteiros de 1 a 10.',
    )
    faixas = models.JSONField(
        "Faixas do índice (0–100)", default=list,
        help_text='Lista crescente de {"ate": número, "rotulo": texto}; a última faixa termina em 100.',
    )
    validacao = models.CharField("Situação", max_length=12, choices=Validacao.choices, default=Validacao.PROVISORIA)
    fonte = models.CharField("Fonte / aprovação", max_length=250, blank=True)
    vigencia_inicio = models.DateField("Vigência — início", null=True, blank=True)
    vigencia_fim = models.DateField("Vigência — fim", null=True, blank=True)

    class Meta(BaseModel.Meta):
        verbose_name = "Matriz de risco"
        verbose_name_plural = "Matrizes de risco"

    def __str__(self):
        return self.nome

    def clean(self):
        from .risco import validar_matriz

        super().clean()
        try:
            validar_matriz(self)
        except ValueError as erro:
            raise ValidationError(str(erro))
        if self.validacao == Validacao.VALIDADA and not self.fonte.strip():
            raise ValidationError({"fonte": "Uma matriz validada precisa de fonte ou aprovação."})


class RegraSugestao(BaseModel):
    """Sugestão cadastrada: tecnologia + anomalia (+ componente) + criticidade mínima → recomendação."""

    nome = models.CharField("Nome", max_length=160)
    tecnologia = models.ForeignKey(TecnologiaAnalise, on_delete=models.PROTECT, related_name="regras_sugestao")
    tipo_componente = models.ForeignKey(TipoComponente, on_delete=models.PROTECT, null=True, blank=True,
                                        related_name="regras_sugestao",
                                        help_text="Vazio = qualquer componente.")
    tipo_anomalia = models.ForeignKey(TipoAnomalia, on_delete=models.PROTECT, related_name="regras_sugestao")
    criticidade_minima = models.CharField("Criticidade mínima do equipamento", max_length=8,
                                          choices=Criticidade.choices, default=Criticidade.ALERTA)
    recomendacao = models.ForeignKey(TipoRecomendacao, on_delete=models.PROTECT, related_name="regras_sugestao")
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, null=True, blank=True,
                                related_name="regras_sugestao", help_text="Vazio = vale para todos os clientes.")
    prioridade = models.PositiveSmallIntegerField("Prioridade (menor aparece antes)", default=100)
    validacao = models.CharField("Situação", max_length=12, choices=Validacao.choices, default=Validacao.PROVISORIA)
    fonte = models.CharField("Fonte / aprovação", max_length=250, blank=True)
    vigencia_inicio = models.DateField("Vigência — início", null=True, blank=True)
    vigencia_fim = models.DateField("Vigência — fim", null=True, blank=True)

    class Meta(BaseModel.Meta):
        verbose_name = "Regra de sugestão técnica"
        verbose_name_plural = "Regras de sugestão técnica"
        ordering = ["prioridade", "nome"]

    def __str__(self):
        return self.nome

    def clean(self):
        super().clean()
        if self.validacao == Validacao.VALIDADA and not self.fonte.strip():
            raise ValidationError({"fonte": "Uma regra validada precisa de fonte ou aprovação."})


class DecisaoSugestao(models.TextChoices):
    ACEITA = "ACEITA", "Aceita como sugerida"
    EDITADA = "EDITADA", "Aceita com alteração"
    REJEITADA = "REJEITADA", "Rejeitada"


class OrigemSugestao(models.TextChoices):
    REGRA = "REGRA", "Regra cadastrada"
    HISTORICO = "HISTORICO", "Histórico de escolhas dos técnicos"


class AceitacaoSugestao(TimeStampedModel):
    """Decisão do analista sobre uma sugestão exibida — mede a aderência, nunca aplica sozinha."""

    achado = models.ForeignKey(Achado, on_delete=models.CASCADE, related_name="aceitacoes_sugestao")
    recomendacao_sugerida = models.ForeignKey(TipoRecomendacao, on_delete=models.PROTECT,
                                              related_name="aceitacoes_sugestao")
    origem = models.CharField("Origem da sugestão", max_length=10, choices=OrigemSugestao.choices)
    regra = models.ForeignKey(RegraSugestao, on_delete=models.SET_NULL, null=True, blank=True,
                              related_name="aceitacoes")
    decisao = models.CharField("Decisão", max_length=10, choices=DecisaoSugestao.choices)
    recomendacao_final = models.ForeignKey(TipoRecomendacao, on_delete=models.PROTECT, null=True, blank=True,
                                           related_name="aceitacoes_finais")
    justificativa = models.TextField("Justificativa", blank=True)
    evidencia = models.JSONField("Evidência da sugestão no momento da decisão", default=dict, blank=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                related_name="aceitacoes_sugestao")

    class Meta:
        verbose_name = "Aceitação de sugestão"
        verbose_name_plural = "Aceitações de sugestão"
        ordering = ["-criado_em"]
        indexes = [models.Index(fields=["achado", "recomendacao_sugerida"])]

    def __str__(self):
        return f"{self.get_decisao_display()} — {self.recomendacao_sugerida}"
