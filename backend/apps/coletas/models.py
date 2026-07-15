"""
Coleta de Dados — Anexo I, item 2.3.

`Inspecao` é o evento (visita/rota). `MedicaoVibracao` é o dado técnico do item 2.3.2.1.
A classificação de criticidade (item 2.4) é calculada no `save()` via apps.coletas.rules.

Modelagem extensível: cada novo tipo de análise do item 2.3.2 (termografia, fluidos,
ensaios elétricos…) vira uma nova tabela vinculada a `Inspecao`, sem alterar esta.
"""
from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.cadastros.models import Cliente, Componente, Equipamento, Instrumento
from apps.core.models import BaseModel, TimeStampedModel

from . import rules, rules_tecnicas


class TipoAnalise(models.TextChoices):
    VIBRACAO = "VIBRACAO", "Análise de Vibração"
    TERMOGRAFIA = "TERMOGRAFIA", "Termografia Infravermelha"
    FLUIDOS = "FLUIDOS", "Análise de Fluidos"
    ENSAIO_ELETRICO = "ENSAIO_ELETRICO", "Ensaios Elétricos"
    ULTRASSOM = "ULTRASSOM", "Ultrassom"
    ESPESSURA = "ESPESSURA", "Medição de Espessura"
    QUALIDADE_ENERGIA = "QUALIDADE_ENERGIA", "Qualidade de Energia"
    SENSITIVA = "SENSITIVA", "Inspeção Sensitiva"
    CORRETIVA = "CORRETIVA", "Manutenção Corretiva"


#: Tipos cobertos pela MedicaoTecnica genérica (vibração e termografia têm modelo dedicado).
TIPOS_TECNICOS = {
    TipoAnalise.FLUIDOS, TipoAnalise.ENSAIO_ELETRICO, TipoAnalise.ULTRASSOM,
    TipoAnalise.ESPESSURA, TipoAnalise.QUALIDADE_ENERGIA, TipoAnalise.SENSITIVA,
    TipoAnalise.CORRETIVA,
}


class StatusInspecao(models.TextChoices):
    ABERTA = "ABERTA", "Aberta"
    EM_ANALISE = "EM_ANALISE", "Em análise"
    CONCLUIDA = "CONCLUIDA", "Concluída"


class Criticidade(models.TextChoices):
    NORMAL = "NORMAL", "Normal"
    ALERTA = "ALERTA", "Alerta"
    CRITICO = "CRITICO", "Crítico"


class Direcao(models.TextChoices):
    HORIZONTAL = "H", "Horizontal"
    VERTICAL = "V", "Vertical"
    AXIAL = "A", "Axial"


class SistemaTermografia(models.TextChoices):
    ELETRICO = "ELETRICO", "Sistemas Elétricos"
    MEC_DINAMICO = "MEC_DINAMICO", "Sistemas Mecânicos Dinâmicos"
    MEC_ESTATICO = "MEC_ESTATICO", "Sistemas Mecânicos Estáticos"
    PROCESSO = "PROCESSO", "Processos Industriais"


ORDEM_CRITICIDADE = {"NORMAL": 0, "ALERTA": 1, "CRITICO": 2}


class Inspecao(BaseModel):
    """Evento de inspeção/coleta (item 2.3.1.1)."""

    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="inspecoes")
    tipo_analise = models.CharField(max_length=20, choices=TipoAnalise.choices, default=TipoAnalise.VIBRACAO)
    tecnico = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="inspecoes",
        verbose_name="Técnico/Analista responsável",
    )
    data = models.DateField("Data da inspeção")
    status = models.CharField(max_length=12, choices=StatusInspecao.choices, default=StatusInspecao.ABERTA)
    observacoes = models.TextField("Observações", blank=True)
    # Geolocalização da coleta (item 2.3.1.7)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    class Meta(BaseModel.Meta):
        verbose_name = "Inspeção"
        verbose_name_plural = "Inspeções"

    def __str__(self):
        return f"Inspeção #{self.pk} — {self.cliente} — {self.data}"

    @property
    def total_medicoes(self) -> int:
        return (
            self.medicoes_vibracao.count()
            + self.medicoes_termografia.count()
            + self.medicoes_tecnicas.count()
        )

    @property
    def criticidade_maxima(self) -> str:
        """Maior criticidade entre todas as medições — usada em dashboards e OSP."""
        valores = [m.criticidade for m in self.medicoes_vibracao.all()]
        valores += [m.criticidade for m in self.medicoes_termografia.all()]
        valores += [m.criticidade for m in self.medicoes_tecnicas.all()]
        if not valores:
            return Criticidade.NORMAL
        return max(valores, key=lambda c: ORDEM_CRITICIDADE.get(c, 0))


class MedicaoVibracao(TimeStampedModel):
    """
    Medição de vibração em um ponto/direção — Anexo I 2.3.2.1.1.

    `zona_iso`, `criticidade` e `diagnostico_sugerido` são calculados automaticamente
    (não editáveis manualmente) pelo motor de regras em `save()`.
    """

    inspecao = models.ForeignKey(Inspecao, on_delete=models.CASCADE, related_name="medicoes_vibracao")
    equipamento = models.ForeignKey(Equipamento, on_delete=models.PROTECT, related_name="medicoes_vibracao")
    componente = models.ForeignKey(
        Componente, on_delete=models.PROTECT, related_name="medicoes_vibracao", null=True, blank=True
    )
    instrumento = models.ForeignKey(
        Instrumento, on_delete=models.PROTECT, related_name="medicoes_vibracao", null=True, blank=True
    )

    ponto_medicao = models.CharField("Ponto de medição", max_length=80, help_text="Ex.: Mancal LA")
    direcao = models.CharField("Direção", max_length=1, choices=Direcao.choices)
    rotacao_rpm = models.PositiveIntegerField("Rotação na coleta (RPM)", null=True, blank=True)

    # Grandezas medidas
    velocidade_rms = models.DecimalField("Velocidade RMS (mm/s)", max_digits=7, decimal_places=2)
    aceleracao_rms = models.DecimalField("Aceleração RMS (g)", max_digits=7, decimal_places=2, null=True, blank=True)
    deslocamento_pp = models.DecimalField("Deslocamento pico-a-pico (µm)", max_digits=8, decimal_places=2, null=True, blank=True)
    fator_crista = models.DecimalField("Fator de crista", max_digits=5, decimal_places=2, null=True, blank=True)
    temperatura = models.DecimalField("Temperatura no ponto (°C)", max_digits=5, decimal_places=1, null=True, blank=True)

    # Resultado calculado (item 2.4)
    zona_iso = models.CharField("Zona ISO", max_length=1, blank=True, editable=False)
    criticidade = models.CharField(
        "Criticidade", max_length=8, choices=Criticidade.choices, blank=True, editable=False
    )
    diagnostico_sugerido = models.TextField("Diagnóstico sugerido", blank=True, editable=False)

    data_hora = models.DateTimeField("Data/hora da medição", auto_now_add=True)

    class Meta:
        verbose_name = "Medição de vibração"
        verbose_name_plural = "Medições de vibração"
        ordering = ["-data_hora"]

    def __str__(self):
        return f"{self.equipamento.tag} — {self.ponto_medicao} ({self.direcao}): {self.velocidade_rms} mm/s"

    def _historico_vrms(self, limite: int = 3) -> list:
        """Vrms das medições anteriores do mesmo equipamento/ponto/direção."""
        qs = (
            MedicaoVibracao.objects.filter(
                equipamento=self.equipamento,
                ponto_medicao=self.ponto_medicao,
                direcao=self.direcao,
            )
            .exclude(pk=self.pk)
            .order_by("-data_hora")[:limite]
        )
        return [m.velocidade_rms for m in qs]

    def save(self, *args, **kwargs):
        resultado = rules.classificar_vibracao(
            classe_iso=self.equipamento.classe_iso,
            velocidade_rms=self.velocidade_rms,
            fator_crista=self.fator_crista,
            historico_vrms=self._historico_vrms(),
        )
        self.zona_iso = resultado.zona_iso
        self.criticidade = resultado.criticidade
        self.diagnostico_sugerido = resultado.diagnostico
        super().save(*args, **kwargs)


class MedicaoTermografia(TimeStampedModel):
    """
    Medição de termografia infravermelha — Anexo I 2.3.2.2.

    `delta_t`, `criticidade` e `diagnostico_sugerido` são calculados automaticamente
    pelo motor de regras (ΔT — NBR 15572 / NETA) em `save()`.
    """

    inspecao = models.ForeignKey(Inspecao, on_delete=models.CASCADE, related_name="medicoes_termografia")
    equipamento = models.ForeignKey(Equipamento, on_delete=models.PROTECT, related_name="medicoes_termografia")
    componente = models.ForeignKey(
        Componente, on_delete=models.PROTECT, related_name="medicoes_termografia", null=True, blank=True
    )
    instrumento = models.ForeignKey(
        Instrumento, on_delete=models.PROTECT, related_name="medicoes_termografia", null=True, blank=True
    )

    ponto_medicao = models.CharField("Ponto de medição", max_length=80, help_text="Ex.: Conexão fase R")
    sistema = models.CharField(
        "Sistema", max_length=15, choices=SistemaTermografia.choices, default=SistemaTermografia.ELETRICO
    )

    temperatura_ponto = models.DecimalField("Temperatura do ponto (°C)", max_digits=6, decimal_places=1)
    temperatura_referencia = models.DecimalField(
        "Temperatura de referência (°C)", max_digits=6, decimal_places=1,
        help_text="Ponto similar saudável (ou fase equivalente).",
    )
    temperatura_ambiente = models.DecimalField(
        "Temperatura ambiente (°C)", max_digits=6, decimal_places=1, null=True, blank=True
    )
    emissividade = models.DecimalField("Emissividade", max_digits=4, decimal_places=2, default=Decimal("0.95"))
    carga_percentual = models.DecimalField(
        "Carga (%)", max_digits=5, decimal_places=1, null=True, blank=True,
        help_text="Carga no momento da medição (sistemas elétricos).",
    )

    # Resultado calculado (item 2.4)
    delta_t = models.DecimalField("ΔT (°C)", max_digits=6, decimal_places=1, editable=False)
    criticidade = models.CharField(
        "Criticidade", max_length=8, choices=Criticidade.choices, blank=True, editable=False
    )
    diagnostico_sugerido = models.TextField("Diagnóstico sugerido", blank=True, editable=False)

    data_hora = models.DateTimeField("Data/hora da medição", auto_now_add=True)

    class Meta:
        verbose_name = "Medição de termografia"
        verbose_name_plural = "Medições de termografia"
        ordering = ["-data_hora"]

    def __str__(self):
        return f"{self.equipamento.tag} — {self.ponto_medicao}: ΔT {self.delta_t}°C"

    def save(self, *args, **kwargs):
        resultado = rules.classificar_termografia(
            temperatura_ponto=self.temperatura_ponto,
            temperatura_referencia=self.temperatura_referencia,
        )
        self.delta_t = resultado.delta_t
        self.criticidade = resultado.criticidade
        self.diagnostico_sugerido = resultado.diagnostico
        super().save(*args, **kwargs)


class MedicaoTecnica(TimeStampedModel):
    """
    Medição técnica genérica — Anexo I 2.3.2.3 a 2.3.2.10 (fluidos, ensaios elétricos,
    ultrassom, espessura, qualidade de energia, sensitiva, corretiva).

    Estrutura flexível (grandeza + valor + unidade + parâmetros) classificada pelo
    registro de regras `apps.coletas.rules_tecnicas` conforme o `tipo`.
    """

    inspecao = models.ForeignKey(Inspecao, on_delete=models.CASCADE, related_name="medicoes_tecnicas")
    equipamento = models.ForeignKey(Equipamento, on_delete=models.PROTECT, related_name="medicoes_tecnicas")
    componente = models.ForeignKey(
        Componente, on_delete=models.PROTECT, related_name="medicoes_tecnicas", null=True, blank=True
    )
    instrumento = models.ForeignKey(
        Instrumento, on_delete=models.PROTECT, related_name="medicoes_tecnicas", null=True, blank=True
    )

    tipo = models.CharField("Tipo de análise", max_length=20, choices=TipoAnalise.choices)
    ponto_medicao = models.CharField("Ponto de medição", max_length=80)
    grandeza = models.CharField("Grandeza medida", max_length=80, help_text="Ex.: Resistência de isolação")
    valor = models.DecimalField("Valor", max_digits=14, decimal_places=4)
    unidade = models.CharField("Unidade", max_length=20, blank=True)
    valor_referencia = models.DecimalField(
        "Valor de referência", max_digits=14, decimal_places=4, null=True, blank=True
    )
    parametros = models.JSONField("Parâmetros adicionais", default=dict, blank=True)

    # Resultado calculado (item 2.4)
    criticidade = models.CharField(max_length=8, choices=Criticidade.choices, blank=True, editable=False)
    diagnostico_sugerido = models.TextField("Diagnóstico sugerido", blank=True, editable=False)

    data_hora = models.DateTimeField("Data/hora da medição", auto_now_add=True)

    class Meta:
        verbose_name = "Medição técnica"
        verbose_name_plural = "Medições técnicas"
        ordering = ["-data_hora"]

    def __str__(self):
        return f"{self.equipamento.tag} — {self.get_tipo_display()} {self.grandeza}: {self.valor} {self.unidade}"

    def save(self, *args, **kwargs):
        resultado = rules_tecnicas.classificar_tecnica(
            tipo=self.tipo, grandeza=self.grandeza, valor=self.valor,
            valor_referencia=self.valor_referencia, parametros=self.parametros,
        )
        self.criticidade = resultado.criticidade
        self.diagnostico_sugerido = resultado.diagnostico
        super().save(*args, **kwargs)
