"""
Ensaios laboratoriais e de campo — o mesmo motor para três tecnologias:

  - óleo isolante de transformador (FQ, CR, PCB, 2-FAL);
  - ensaios elétricos de transformador (R×T, R×I, R×O);
  - fluidos lubrificantes e hidráulicos (FQ, EF, CP) — ver o fim do arquivo.

Cada tecnologia tem o seu registro de campo (ColetaOleo, RegistroEnsaioEletrico,
ColetaFluido); ensaios, parâmetros, resultados e valores são comuns.

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
    """Ponto de coleta da amostra (ex.: Dreno Inferior Lado AT; Linha de retorno, antes do filtro)."""

    modulo = models.CharField(
        "Tecnologia", max_length=20, choices=ModuloTecnico.choices, blank=True,
        help_text="Em qual coleta o ponto aparece (óleo isolante, fluidos…). Vazio = em todas.",
    )

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

    # Única dentro do módulo: "FQ" existe no óleo isolante e nos fluidos lubrificantes.
    sigla = models.CharField("Sigla", max_length=10)
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
        constraints = [models.UniqueConstraint(fields=["modulo", "sigla"], name="uniq_ensaio_modulo_sigla")]

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
    simbolo = models.CharField("Símbolo", max_length=10, blank=True, help_text="Ex.: Fe, Cu, Si.")
    grupo = models.CharField("Grupo", max_length=40, blank=True,
                             help_text="Agrupa as linhas da ficha (ex.: Metais de desgaste, Contaminantes, Aditivos).")
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
    laboratorio = models.CharField("Laboratório", max_length=120, blank=True)
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
    metodo = models.CharField("Método/norma do laboratório", max_length=60, blank=True,
                              help_text="Só quando difere da norma do catálogo (ex.: ASTM D4951 no lugar de D5185).")

    class Meta:
        verbose_name = "Valor de parâmetro"
        verbose_name_plural = "Valores de parâmetros"
        ordering = ["parametro__ordem", "serie", "posicao"]

    def __str__(self):
        return f"{self.parametro} = {self.valor if self.valor is not None else self.valor_texto or '—'}"


# =============================================================================
# Fluidos lubrificantes e hidráulicos (ModuloTecnico.FLUIDO_LUBRIFICANTE)
#
#   Equipamento ──(rota)── ItemInspecao ─1:1─ ColetaFluido      dados da coleta
#                                       ─1:N─ ResultadoEnsaio  FQ · EF · CP
#   ProdutoFluido                                               dados do fluido
#   ReferenciaParametro                    limites por escopo, origem e vigência
#
# Nada de limite universal no código: cada referência é cadastrada com o escopo
# (equipamento, produto, cliente ou aplicação), a origem (norma, fabricante,
# laboratório, acordo, óleo novo) e a vigência; sem referência, o valor sai
# "sem referência" — nunca classificado por um número inventado.
# =============================================================================
class AplicacaoFluido(models.TextChoices):
    LUBRIFICANTE = "LUBRIFICANTE", "Lubrificante"
    HIDRAULICO = "HIDRAULICO", "Hidráulico"


class ProdutoFluido(Catalogo):
    """O fluido em uso (produto comercial): dados do fluido, não da coleta."""

    fabricante = models.CharField("Fabricante", max_length=80, blank=True)
    aplicacao = models.CharField("Aplicação", max_length=15, choices=AplicacaoFluido.choices, blank=True)
    grau_viscosidade = models.CharField("Grau de viscosidade", max_length=20, blank=True, help_text="Ex.: ISO VG 46")
    viscosidade_40c_cst = models.DecimalField("Viscosidade a 40 °C do óleo novo (cSt)", max_digits=8,
                                              decimal_places=2, null=True, blank=True)
    viscosidade_100c_cst = models.DecimalField("Viscosidade a 100 °C do óleo novo (cSt)", max_digits=8,
                                               decimal_places=2, null=True, blank=True)
    indice_viscosidade = models.DecimalField("Índice de viscosidade", max_digits=6, decimal_places=1,
                                             null=True, blank=True)

    class Meta(Catalogo.Meta):
        verbose_name = "Produto lubrificante / hidráulico"
        verbose_name_plural = "Produtos lubrificantes / hidráulicos"


class CondicaoOperacionalColeta(models.TextChoices):
    EM_OPERACAO = "EM_OPERACAO", "Em operação"
    APOS_PARADA = "APOS_PARADA", "Logo após a parada"
    PARADO = "PARADO", "Parado"


class ColetaFluido(BaseModel):
    """Registro da coleta da amostra de fluido lubrificante/hidráulico (ficha 1 do relatório)."""

    item = models.OneToOneField(ItemInspecao, on_delete=models.CASCADE, related_name="coleta_fluido")
    # Fluido
    aplicacao = models.CharField("Aplicação do fluido", max_length=15, choices=AplicacaoFluido.choices)
    produto = models.ForeignKey(ProdutoFluido, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name="coletas")
    fluido_informado = models.CharField("Fluido (quando não cadastrado)", max_length=120, blank=True)
    grau_viscosidade = models.CharField("Grau de viscosidade", max_length=20, blank=True)
    # Coleta
    identificacao_amostra = models.CharField("Identificação da amostra", max_length=40, blank=True,
                                             help_text="Etiqueta/número da amostra no laboratório.")
    data_coleta = models.DateField("Data da coleta")
    amostrador = models.CharField("Amostrador", max_length=120, blank=True)
    ponto_coleta = models.ForeignKey(PontoColeta, on_delete=models.SET_NULL, null=True, blank=True)
    temperatura_fluido_c = models.DecimalField("Temperatura do fluido (°C)", max_digits=6, decimal_places=1,
                                               null=True, blank=True)
    temperatura_ambiente_c = models.DecimalField("Temperatura ambiente (°C)", max_digits=6, decimal_places=1,
                                                 null=True, blank=True)
    condicao_operacional = models.CharField("Condição operacional na coleta", max_length=15,
                                            choices=CondicaoOperacionalColeta.choices, blank=True)
    # Histórico do fluido no equipamento
    horas_equipamento = models.DecimalField("Horas do equipamento", max_digits=10, decimal_places=1,
                                            null=True, blank=True, validators=[MinValueValidator(Decimal("0"))])
    horas_fluido = models.DecimalField("Horas do fluido (desde a última troca)", max_digits=10, decimal_places=1,
                                       null=True, blank=True, validators=[MinValueValidator(Decimal("0"))])
    data_ultima_troca = models.DateField("Data da última troca do fluido", null=True, blank=True)
    complemento_recente = models.BooleanField("Complemento recente de fluido", null=True, blank=True)
    volume_complemento_l = models.DecimalField("Volume complementado (L)", max_digits=8, decimal_places=1,
                                               null=True, blank=True, validators=[MinValueValidator(Decimal("0"))])
    troca_filtro_recente = models.BooleanField("Troca recente de filtro", null=True, blank=True)
    intervencao_recente = models.TextField("Intervenção/manutenção recente", blank=True)
    observacoes = models.TextField("Observações", blank=True)
    ensaios = models.ManyToManyField(Ensaio, blank=True, related_name="+", verbose_name="Ensaios solicitados")

    class Meta(BaseModel.Meta):
        verbose_name = "Coleta de amostra de fluido"
        verbose_name_plural = "Coletas de amostra de fluido"

    def __str__(self):
        return f"Coleta {self.data_coleta} — {self.item.equipamento.tag}"

    @property
    def nome_fluido(self) -> str:
        return self.produto.nome if self.produto_id else self.fluido_informado


class SolicitacaoPadraoEnsaio(BaseModel):
    """
    Ensaios marcados por padrão na coleta, por aplicação do fluido. Regra acordada
    com o cliente: lubrificante → FQ + EF; hidráulico → FQ + EF + CP. Editável no
    admin; o técnico ainda pode marcar ou desmarcar na coleta.
    """

    aplicacao = models.CharField("Aplicação", max_length=15, choices=AplicacaoFluido.choices)
    ensaio = models.ForeignKey(Ensaio, on_delete=models.CASCADE, related_name="solicitacoes_padrao")

    class Meta(BaseModel.Meta):
        verbose_name = "Ensaio solicitado por padrão"
        verbose_name_plural = "Ensaios solicitados por padrão"
        constraints = [models.UniqueConstraint(fields=["aplicacao", "ensaio"], name="uniq_solicitacao_padrao")]

    def __str__(self):
        return f"{self.get_aplicacao_display()} → {self.ensaio.sigla}"


class TipoReferencia(models.TextChoices):
    MAXIMO = "MAXIMO", "Máximo (alerta/crítico acima do limite)"
    MINIMO = "MINIMO", "Mínimo (alerta/crítico abaixo do limite)"
    VARIACAO = "VARIACAO", "Variação em relação ao valor de base (%)"
    CODIGO_ISO = "CODIGO_ISO", "Meta de limpeza ISO 4406"
    QUALITATIVO = "QUALITATIVO", "Resultado esperado (texto)"


class OrigemReferencia(models.TextChoices):
    NORMA = "NORMA", "Norma"
    FABRICANTE_EQUIPAMENTO = "FABRICANTE_EQUIPAMENTO", "Fabricante do equipamento"
    FABRICANTE_FLUIDO = "FABRICANTE_FLUIDO", "Fabricante do fluido"
    LABORATORIO = "LABORATORIO", "Laboratório"
    CLIENTE = "CLIENTE", "Acordo com o cliente / contrato"
    OLEO_NOVO = "OLEO_NOVO", "Óleo novo (baseline medido)"


class ReferenciaParametro(BaseModel):
    """
    Referência de um parâmetro para classificar o resultado em Rotina, Alerta ou
    Crítica. Vale para o escopo informado — campo vazio = qualquer —, e a mais
    específica ganha: equipamento > produto > cliente > aplicação (empate: a de
    vigência mais recente). Versionar = criar outra com vigência nova; a antiga
    continua explicando os laudos que já saíram.
    """

    parametro = models.ForeignKey(ParametroEnsaio, on_delete=models.CASCADE, related_name="referencias")
    # Escopo
    cliente = models.ForeignKey("cadastros.Cliente", on_delete=models.CASCADE, null=True, blank=True,
                                related_name="referencias_fluido")
    equipamento = models.ForeignKey("cadastros.Equipamento", on_delete=models.CASCADE, null=True, blank=True,
                                    related_name="referencias_fluido")
    produto = models.ForeignKey(ProdutoFluido, on_delete=models.CASCADE, null=True, blank=True,
                                related_name="referencias")
    aplicacao = models.CharField("Aplicação", max_length=15, choices=AplicacaoFluido.choices, blank=True)
    # Critério
    tipo = models.CharField("Tipo", max_length=12, choices=TipoReferencia.choices)
    valor_base = models.DecimalField("Valor de base", max_digits=14, decimal_places=4, null=True, blank=True,
                                     help_text="Óleo novo/nominal, para referência do tipo Variação.")
    limite_alerta = models.DecimalField("Limite de alerta", max_digits=14, decimal_places=4, null=True, blank=True,
                                        help_text="Na Variação, em %; na meta ISO, graus de código acima da meta.")
    limite_critico = models.DecimalField("Limite crítico", max_digits=14, decimal_places=4, null=True, blank=True,
                                         help_text="Na Variação, em %; na meta ISO, graus de código acima da meta.")
    referencia_texto = models.CharField("Meta / resultado esperado", max_length=40, blank=True,
                                        help_text="Meta ISO 4406 (ex.: 17/15/12) ou resultado esperado (ex.: Límpido).")
    # Rastreabilidade
    origem = models.CharField("Origem", max_length=25, choices=OrigemReferencia.choices)
    fonte = models.CharField("Fonte", max_length=250, blank=True,
                             help_text="Norma, manual do fabricante, laudo, contrato ou acordo que sustenta o valor.")
    vigencia_inicio = models.DateField("Vigência — início", null=True, blank=True)
    vigencia_fim = models.DateField("Vigência — fim", null=True, blank=True)
    observacao = models.TextField("Observação", blank=True)

    class Meta(BaseModel.Meta):
        verbose_name = "Referência de parâmetro (fluidos)"
        verbose_name_plural = "Referências de parâmetros (fluidos)"
        ordering = ["parametro__ensaio", "parametro__ordem", "-vigencia_inicio"]

    def __str__(self):
        return f"{self.parametro} — {self.get_tipo_display()} ({self.get_origem_display()})"
