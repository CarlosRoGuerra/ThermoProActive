"""
Ensaios de transformador — análise do óleo isolante (FQ, CR, PCB, 2-FAL) e
ensaios elétricos (R×T, R×I, R×O).

Reaproveita o fluxo das inspeções: o Relatorio numera o laudo, o Carregamento é a
rota de transformadores e cada ItemInspecao é um transformador (é ele que entra na
Relação de Equipamentos do relatório). Aqui fica só o que é específico:

    ItemInspecao ─1:1─ ColetaOleo ──1:N─ InspecaoVisualColeta
                 ─1:1─ RegistroEnsaioEletrico
                 ─1:N─ ResultadoEnsaio (um por ensaio: laudo, datas, conclusão)
                           └─1:N─ ValorParametro (valor por parâmetro, série e posição)

Ensaios e parâmetros são catálogos (unidade, norma, referência, tipo de limite,
casas decimais) — nenhum limite escondido em código. Valor ausente é nulo, nunca
zero: "não coletado", "abaixo do LD" e "indisponível" têm estado próprio.
"""
from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.cadastros.models import Catalogo, Instrumento, ModuloTecnico
from apps.coletas.models import ItemInspecao
from apps.core.models import BaseModel, TimeStampedModel

PERCENTUAL = [MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))]


# ------------------------------- Catálogos ----------------------------------
class TipoFluido(Catalogo):
    """Fluido isolante do transformador (ex.: Óleo Mineral B [Parafínico])."""

    class Meta(Catalogo.Meta):
        verbose_name = "Tipo de fluido isolante"
        verbose_name_plural = "Tipos de fluido isolante"


class PontoColeta(Catalogo):
    """Ponto de coleta da amostra (ex.: Dreno Inferior Lado AT)."""

    class Meta(Catalogo.Meta):
        verbose_name = "Ponto de coleta"
        verbose_name_plural = "Pontos de coleta"


class GrupoChecklist(models.TextChoices):
    GERAL = "GERAL", "Geral"
    TANQUE_EXPANSAO = "TANQUE_EXPANSAO", "Exclusivo para equipamentos com tanque de expansão"


class ItemChecklistVisual(Catalogo):
    """Item da inspeção visual do transformador na coleta da amostra."""

    grupo = models.CharField("Grupo", max_length=20, choices=GrupoChecklist.choices, default=GrupoChecklist.GERAL)
    ordem = models.PositiveSmallIntegerField("Ordem", default=0)

    class Meta(Catalogo.Meta):
        verbose_name = "Item de inspeção visual"
        verbose_name_plural = "Itens de inspeção visual"
        ordering = ["grupo", "ordem", "nome"]


class Ensaio(Catalogo):
    """Ensaio que gera uma ficha no relatório (FQ, CR, PCB, 2-FAL, R×T, R×I, R×O)."""

    sigla = models.CharField("Sigla", max_length=10, unique=True)
    modulo = models.CharField("Módulo do relatório", max_length=20, choices=ModuloTecnico.choices)
    titulo_ficha = models.CharField("Título da ficha", max_length=120)
    ordem = models.PositiveSmallIntegerField("Ordem", default=0)
    # Os rótulos mudam entre as fichas de referência (óleo × elétricos).
    rotulo_conclusao = models.CharField("Rótulo da conclusão", max_length=40, default="Conclusão")
    rotulo_informacoes = models.CharField("Rótulo das informações", max_length=40, default="Informações Adicionais")
    rotulo_proxima = models.CharField("Rótulo da próxima data", max_length=40, default="Data da Próxima Coleta")
    nota_tecnica = models.TextField(
        "Nota técnica", blank=True,
        help_text="Notas fixas impressas na ficha (norma, limites de quantificação…). Uma por linha.",
    )

    class Meta(Catalogo.Meta):
        verbose_name = "Ensaio"
        verbose_name_plural = "Ensaios"
        ordering = ["modulo", "ordem"]

    def __str__(self):
        return f"{self.sigla} — {self.nome}"


class TipoLimite(models.TextChoices):
    MAXIMO = "MAXIMO", "Máximo"
    MINIMO = "MINIMO", "Mínimo"
    FAIXA = "FAIXA", "Faixa"
    QUALITATIVO = "QUALITATIVO", "Qualitativo"
    INFORMATIVO = "INFORMATIVO", "Informativo (sem limite)"


class ParametroEnsaio(BaseModel):
    """Grandeza de um ensaio, com a unidade, a norma e a referência da ficha."""

    ensaio = models.ForeignKey(Ensaio, on_delete=models.CASCADE, related_name="parametros")
    codigo = models.CharField("Código", max_length=30, help_text="Identificador estável (ex.: H2, VISCOSIDADE).")
    nome = models.CharField("Nome", max_length=80)
    unidade = models.CharField("Unidade", max_length=20, blank=True)
    norma = models.CharField("Norma", max_length=80, blank=True)
    tipo_limite = models.CharField("Tipo de limite", max_length=12, choices=TipoLimite.choices,
                                   default=TipoLimite.INFORMATIVO)
    limite = models.DecimalField("Limite (máx., mín. ou início da faixa)", max_digits=14, decimal_places=4,
                                 null=True, blank=True)
    limite_superior = models.DecimalField("Fim da faixa", max_digits=14, decimal_places=4, null=True, blank=True)
    referencia_texto = models.CharField("Referência qualitativa", max_length=40, blank=True)
    casas_decimais = models.PositiveSmallIntegerField("Casas decimais", default=2)
    calculado = models.BooleanField(
        "Calculado", default=False,
        help_text="Calculado pelo sistema a partir de outros valores do ensaio; não é digitado.",
    )
    no_grafico = models.BooleanField("Entra no gráfico", default=True)
    ordem = models.PositiveSmallIntegerField("Ordem", default=0)

    class Meta(BaseModel.Meta):
        verbose_name = "Parâmetro de ensaio"
        verbose_name_plural = "Parâmetros de ensaio"
        ordering = ["ensaio", "ordem"]
        constraints = [models.UniqueConstraint(fields=["ensaio", "codigo"], name="uniq_parametro_ensaio_codigo")]

    def __str__(self):
        return f"{self.ensaio.sigla} · {self.nome}"


# --------------------------------- Coleta -----------------------------------
class ColetaOleo(BaseModel):
    """Registro de dados de coleta da amostra de óleo (ficha 1 do relatório de óleo)."""

    item = models.OneToOneField(ItemInspecao, on_delete=models.CASCADE, related_name="coleta_oleo")
    data_coleta = models.DateField("Data da coleta")
    amostrador = models.CharField("Amostrador", max_length=120, blank=True)
    temperatura_amostra_c = models.DecimalField("Temperatura da amostra (°C)", max_digits=6, decimal_places=1,
                                                null=True, blank=True)
    temperatura_ambiente_c = models.DecimalField("Temperatura ambiente (°C)", max_digits=6, decimal_places=1,
                                                 null=True, blank=True)
    umidade_relativa_pct = models.DecimalField("Umidade relativa do ar (%)", max_digits=5, decimal_places=1,
                                               null=True, blank=True, validators=PERCENTUAL)
    ponto_coleta = models.ForeignKey(PontoColeta, on_delete=models.SET_NULL, null=True, blank=True)
    tipo_fluido = models.ForeignKey(TipoFluido, on_delete=models.SET_NULL, null=True, blank=True)
    ensaios = models.ManyToManyField(Ensaio, blank=True, related_name="+", verbose_name="Ensaios solicitados")

    class Meta(BaseModel.Meta):
        verbose_name = "Coleta de amostra de óleo"
        verbose_name_plural = "Coletas de amostra de óleo"

    def __str__(self):
        return f"Coleta {self.data_coleta} — {self.item.equipamento.tag}"


class EstadoChecklist(models.TextChoices):
    OK = "OK", "Condição Normal"
    NC = "NC", "Não Conformidade"
    NA = "NA", "Não Aplicável"


class InspecaoVisualColeta(TimeStampedModel):
    coleta = models.ForeignKey(ColetaOleo, on_delete=models.CASCADE, related_name="inspecao_visual")
    item_checklist = models.ForeignKey(ItemChecklistVisual, on_delete=models.PROTECT, related_name="+")
    estado = models.CharField("Estado", max_length=2, choices=EstadoChecklist.choices)
    observacao = models.TextField("Observação", blank=True)
    foto = models.ImageField("Foto", upload_to="ensaios/inspecao_visual/", null=True, blank=True)

    class Meta:
        verbose_name = "Item da inspeção visual"
        verbose_name_plural = "Inspeção visual"
        ordering = ["item_checklist__grupo", "item_checklist__ordem"]
        constraints = [
            models.UniqueConstraint(fields=["coleta", "item_checklist"], name="uniq_inspecao_visual_item"),
        ]


class RegistroEnsaioEletrico(BaseModel):
    """Registro de dados dos ensaios elétricos (ficha 1 do relatório de ensaios elétricos)."""

    item = models.OneToOneField(ItemInspecao, on_delete=models.CASCADE, related_name="registro_eletrico")
    data_ensaio = models.DateField("Data do ensaio")
    analista = models.CharField("Analista", max_length=120, blank=True)
    tap = models.CharField("TAP", max_length=10, blank=True)
    tensao_tap_v = models.DecimalField("Tensão do TAP (V)", max_digits=9, decimal_places=2, null=True, blank=True)
    temperatura_oleo_c = models.DecimalField("Temperatura do óleo (°C)", max_digits=6, decimal_places=1,
                                             null=True, blank=True)
    temperatura_ambiente_c = models.DecimalField("Temperatura ambiente (°C)", max_digits=6, decimal_places=1,
                                                 null=True, blank=True)
    umidade_relativa_pct = models.DecimalField("Umidade relativa (%)", max_digits=5, decimal_places=1,
                                               null=True, blank=True, validators=PERCENTUAL)
    ensaios = models.ManyToManyField(Ensaio, blank=True, related_name="+", verbose_name="Ensaios solicitados")

    class Meta(BaseModel.Meta):
        verbose_name = "Registro de ensaios elétricos"
        verbose_name_plural = "Registros de ensaios elétricos"

    def __str__(self):
        return f"Ensaios elétricos {self.data_ensaio} — {self.item.equipamento.tag}"


# -------------------------------- Resultados --------------------------------
class SituacaoResultado(models.TextChoices):
    REALIZADO = "REALIZADO", "Realizado"
    NAO_COLETADO = "NAO_COLETADO", "Amostra não coletada"
    NAO_REALIZADO = "NAO_REALIZADO", "Não realizado"
    SEM_RESULTADO = "SEM_RESULTADO", "Aguardando resultado"


class CriticidadeResultado(models.TextChoices):
    """Criticidade do laudo de cada ensaio — não é o Grau de Risco das inspeções."""

    ROTINA = "ROTINA", "Rotina"
    ALERTA = "ALERTA", "Alerta"
    CRITICA = "CRITICA", "Crítica"


class OrigemResultado(models.TextChoices):
    MANUAL = "MANUAL", "Digitado"
    PLANILHA = "PLANILHA", "Planilha"
    API = "API", "Integração (API)"
    ARQUIVO = "ARQUIVO", "Arquivo do laboratório"


class ResultadoEnsaio(BaseModel):
    """Resultado de um ensaio para um transformador — cada ensaio tem o próprio laudo."""

    item = models.ForeignKey(ItemInspecao, on_delete=models.CASCADE, related_name="resultados_ensaio")
    ensaio = models.ForeignKey(Ensaio, on_delete=models.PROTECT, related_name="resultados")
    situacao = models.CharField("Situação", max_length=15, choices=SituacaoResultado.choices,
                                default=SituacaoResultado.SEM_RESULTADO)
    numero_laudo = models.CharField("Número do laudo", max_length=40, blank=True)
    criticidade = models.CharField("Criticidade", max_length=10, choices=CriticidadeResultado.choices, blank=True)
    data_analise = models.DateField("Data da análise", null=True, blank=True)
    data_proxima = models.DateField("Data da próxima coleta/análise", null=True, blank=True)
    conclusao = models.TextField("Conclusão / observações", blank=True)
    recomendacao = models.TextField("Recomendação", blank=True)
    informacoes_adicionais = models.TextField("Informações adicionais", blank=True)
    instrumento = models.ForeignKey(Instrumento, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="resultados_ensaio")
    origem = models.CharField("Origem do dado", max_length=10, choices=OrigemResultado.choices,
                              default=OrigemResultado.MANUAL)

    class Meta(BaseModel.Meta):
        verbose_name = "Resultado de ensaio"
        verbose_name_plural = "Resultados de ensaio"
        constraints = [models.UniqueConstraint(fields=["item", "ensaio"], name="uniq_resultado_item_ensaio")]

    def __str__(self):
        return f"{self.ensaio.sigla} — {self.item.equipamento.tag} ({self.get_situacao_display()})"


class EstadoValor(models.TextChoices):
    MEDIDO = "MEDIDO", "Medido"
    ABAIXO_LD = "ABAIXO_LD", "Abaixo do limite de detecção"
    ABAIXO_LQ = "ABAIXO_LQ", "Abaixo do limite de quantificação"
    NAO_DETECTADO = "NAO_DETECTADO", "Não detectado"
    ACIMA_ESCALA = "ACIMA_ESCALA", "Acima do fundo de escala"
    INDISPONIVEL = "INDISPONIVEL", "Indisponível"


class ValorParametro(TimeStampedModel):
    """Um valor recebido do laboratório ou medido em campo. Nulo quando não há número."""

    resultado = models.ForeignKey(ResultadoEnsaio, on_delete=models.CASCADE, related_name="valores")
    parametro = models.ForeignKey(ParametroEnsaio, on_delete=models.PROTECT, related_name="valores")
    serie = models.CharField("Série", max_length=40, blank=True,
                             help_text="Fase (R×T), ligação (R×I) ou par de terminais.")
    posicao = models.DecimalField("Posição", max_digits=10, decimal_places=2, null=True, blank=True,
                                  help_text="Tempo em segundos na R×I.")
    valor = models.DecimalField("Valor", max_digits=18, decimal_places=6, null=True, blank=True)
    valor_texto = models.CharField("Valor como recebido / qualitativo", max_length=60, blank=True)
    estado = models.CharField("Estado", max_length=15, choices=EstadoValor.choices, default=EstadoValor.MEDIDO)
    limite_deteccao = models.DecimalField("Limite de detecção", max_digits=14, decimal_places=4,
                                          null=True, blank=True)

    class Meta:
        verbose_name = "Valor de parâmetro"
        verbose_name_plural = "Valores de parâmetros"
        ordering = ["parametro__ordem", "serie", "posicao"]

    def __str__(self):
        return f"{self.parametro} = {self.valor if self.valor is not None else self.valor_texto or '—'}"
