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
from django.utils import timezone

from apps.cadastros.models import (
    Cliente,
    Componente,
    Condicao,
    Equipamento,
    Instrumento,
    Rota,
    TecnologiaAnalise,
    TipoAnomalia,
    TipoComponente,
    TipoRecomendacao,
)
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


class ParametroMedicao(models.TextChoices):
    """
    Parâmetro coletado no ponto — compõe a nomenclatura do relatório (ex.: "1HA"
    = mancal 1, direção Horizontal, parâmetro Aceleração).
    """

    ACELERACAO = "A", "Aceleração"
    VELOCIDADE = "V", "Velocidade"
    ENVELOPE = "E", "Envelope"
    DEMODULACAO = "D", "Demodulação"


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
    numero_mancal = models.PositiveSmallIntegerField(
        "Nº do mancal", null=True, blank=True, help_text="1, 2, 3… conforme a numeração do croqui."
    )
    direcao = models.CharField("Direção", max_length=1, choices=Direcao.choices)
    parametro = models.CharField(
        "Parâmetro", max_length=1, choices=ParametroMedicao.choices, blank=True
    )
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

    @property
    def codigo_ponto(self) -> str:
        """
        Nomenclatura do relatório: nº do mancal + direção + parâmetro (ex.: "1HA").
        Omite as partes ainda não informadas.
        """
        return f"{self.numero_mancal or ''}{self.direcao or ''}{self.parametro or ''}"

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


# =============================================================================
# Fluxo de inspeção campo → escritório (spec dos áudios do Fabrício)
#
# Máquina de estados em duas etapas:
#   1) Análise de campo  — o inspetor "carrega uma rota" (Carregamento), percorre
#      os equipamentos (ItemInspecao), define a Condição de cada um e, quando há
#      falha, registra uma ou mais análises (Achado). É a "tabela transitória".
#   2) Transferência     — trava exigindo condição em todos os itens; ao confirmar,
#      o Carregamento passa a TRANSFERIDA e os Achados aparecem na Análise final.
#   3) Análise final      — refino no escritório: correção, nº de OSP, upload das
#      imagens (AchadoImagem) e liberação (visivel_cliente=True) para o portal.
#
# Implementado por status/flags (sem cópia física de tabelas): mesmo comportamento,
# sem duplicação de dados.
# =============================================================================


class StatusCarregamento(models.TextChoices):
    EM_CAMPO = "EM_CAMPO", "Em campo"
    TRANSFERIDA = "TRANSFERIDA", "Transferida"
    DESCARTADA = "DESCARTADA", "Descartada"


class Relatorio(BaseModel):
    """
    Agrupa as rotas (carregamentos) de uma inspeção sob um único número/laudo.

    Fonte ÚNICA do número e das datas de auditoria: `data_termino` é o último dia
    da inspeção (pode ser futura — regra de auditoria do Fabrício), compõe o número
    e a OSP; `data_inicio` é o primeiro dia real de coleta das rotas. OSP e capa
    leem sempre daqui, garantindo que todas as rotas do laudo tenham a mesma data.
    """

    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="relatorios")
    tecnologia = models.ForeignKey(
        TecnologiaAnalise, on_delete=models.PROTECT, related_name="relatorios", verbose_name="Tecnologia"
    )
    numero = models.CharField("Número do relatório", max_length=40)
    data_inicio = models.DateField("Data de início", null=True, blank=True)
    data_termino = models.DateField("Data de término (auditoria)")

    class Meta(BaseModel.Meta):
        verbose_name = "Relatório"
        verbose_name_plural = "Relatórios"
        constraints = [
            models.UniqueConstraint(fields=["cliente", "numero"], name="uniq_relatorio_cliente_numero"),
        ]

    def __str__(self):
        return self.numero

    @staticmethod
    def proximo_numero(tecnologia, data_termino) -> str:
        """
        Número no padrão do Fabrício: RT-{SIGLA}-{AAAA.MM.DD}.{SEQ}
        Ex.: RT-AVSMD-2026.04.23.02323

        RT = "Relatório Técnico"; SIGLA = sigla da tecnologia; a data é o último dia
        da inspeção (auditoria); SEQ é o sequencial GLOBAL da tabela de relatórios
        (o cliente bate o olho e sabe tecnologia, ano, mês e dia).
        """
        sigla = (getattr(tecnologia, "sigla", "") or "").strip().upper() or "XX"
        maior = 0
        for num in Relatorio.objects.values_list("numero", flat=True):
            try:
                maior = max(maior, int(str(num).rsplit(".", 1)[1]))
            except (IndexError, ValueError):
                continue
        return f"RT-{sigla}-{data_termino:%Y.%m.%d}.{maior + 1:05d}"


class Carregamento(BaseModel):
    """
    "Carregar rota" da Análise de campo: cabeçalho da inspeção em andamento.

    Enquanto `status=EM_CAMPO` é a folha de campo (transitória). A Transferência
    valida que todo item tem condição e passa para `TRANSFERIDA`. O número/datas
    de auditoria vêm do `relatorio` (várias rotas podem compartilhar o mesmo).
    """

    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="carregamentos")
    tecnologia = models.ForeignKey(
        TecnologiaAnalise, on_delete=models.PROTECT, related_name="carregamentos",
        verbose_name="Tecnologia",
    )
    relatorio = models.ForeignKey(
        Relatorio, on_delete=models.PROTECT, related_name="carregamentos", null=True, blank=True
    )
    rota = models.ForeignKey(
        Rota, on_delete=models.PROTECT, related_name="carregamentos", null=True, blank=True
    )
    instrumento = models.ForeignKey(
        Instrumento, on_delete=models.SET_NULL, related_name="carregamentos", null=True, blank=True
    )
    analista = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="carregamentos",
        verbose_name="Analista responsável",
    )
    # Dia real em que a rota foi coletada (verdade interna, distinto da data de
    # auditoria que fica no relatório).
    data_coleta = models.DateField("Data de coleta", default=timezone.localdate)
    status = models.CharField(
        max_length=12, choices=StatusCarregamento.choices, default=StatusCarregamento.EM_CAMPO
    )
    transferido_em = models.DateTimeField("Transferido em", null=True, blank=True)

    class Meta(BaseModel.Meta):
        verbose_name = "Carregamento de rota"
        verbose_name_plural = "Carregamentos de rota"

    def __str__(self):
        return f"Carregamento #{self.pk} — {self.tecnologia} — {self.data_coleta}"

    @property
    def itens_pendentes(self):
        """Itens ainda sem condição — bloqueiam a transferência."""
        return self.itens.filter(condicao__isnull=True)

    @property
    def pode_transferir(self) -> bool:
        return self.status == StatusCarregamento.EM_CAMPO and not self.itens_pendentes.exists()


class ItemInspecao(BaseModel):
    """
    Uma linha da folha de campo: um equipamento da rota dentro de um Carregamento.

    Pode haver mais de uma linha para o mesmo equipamento ("Adicionar linha", para
    lançar vários problemas) — distinguidas por `ordem`. A `condicao` é obrigatória
    para transferir; se ela gerar ação, o item recebe um ou mais `Achado`.
    """

    carregamento = models.ForeignKey(Carregamento, on_delete=models.CASCADE, related_name="itens")
    equipamento = models.ForeignKey(
        Equipamento, on_delete=models.PROTECT, related_name="itens_inspecao"
    )
    condicao = models.ForeignKey(
        Condicao, on_delete=models.SET_NULL, related_name="itens", null=True, blank=True
    )
    # Nº da linha dentro do carregamento (código da lista, distinto da tag).
    ordem = models.PositiveIntegerField("Ordem", default=1)

    class Meta(BaseModel.Meta):
        verbose_name = "Item de inspeção"
        verbose_name_plural = "Itens de inspeção"
        ordering = ["ordem", "id"]

    def __str__(self):
        return f"{self.equipamento.tag} (#{self.ordem}) — {self.carregamento_id}"


class Achado(BaseModel):
    """
    Análise de uma anomalia registrada em um item (o "problema"). Nasce no campo e
    é refinada no escritório. Vira uma OSP na Análise final.

    Campos comuns a todas as tecnologias + blocos específicos (vibração/termografia).
    `visivel_cliente` só vai a True quando confirmado no escritório com as imagens.
    """

    item = models.ForeignKey(ItemInspecao, on_delete=models.CASCADE, related_name="achados")

    # --- Comum a todas as tecnologias ---
    tipo_componente = models.ForeignKey(
        TipoComponente, on_delete=models.SET_NULL, related_name="achados", null=True, blank=True
    )
    componente_texto = models.CharField(
        "Componente (texto)", max_length=120, blank=True, help_text="Ex.: DJ5"
    )
    detalhe = models.CharField(
        "Detalhe do componente", max_length=200, blank=True,
        help_text="Uso interno (ex.: nº da imagem no termovisor) — não sai para o cliente.",
    )
    tipo_anomalia = models.ForeignKey(
        TipoAnomalia, on_delete=models.SET_NULL, related_name="achados", null=True, blank=True
    )
    anomalia_texto = models.TextField("Anomalia (texto)", blank=True)
    recomendacao = models.ForeignKey(
        TipoRecomendacao, on_delete=models.SET_NULL, related_name="achados", null=True, blank=True
    )
    recomendacao_texto = models.TextField("Recomendação (texto)", blank=True)
    observacoes = models.TextField("Observações", blank=True)

    # --- Vibração ---
    aceleracao_global = models.DecimalField(
        "Global de aceleração (g)", max_digits=8, decimal_places=3, null=True, blank=True
    )
    velocidade_global = models.DecimalField(
        "Global de velocidade (mm/s)", max_digits=8, decimal_places=3, null=True, blank=True
    )

    # --- Termografia: temperaturas ---
    temperatura_medida = models.DecimalField(
        "Temperatura medida (°C)", max_digits=6, decimal_places=1, null=True, blank=True
    )
    temperatura_referencia = models.DecimalField(
        "Temperatura de referência (°C)", max_digits=6, decimal_places=1, null=True, blank=True
    )
    delta_t = models.DecimalField(
        "ΔT (°C)", max_digits=6, decimal_places=1, null=True, blank=True, editable=False
    )
    carga_percentual = models.DecimalField(
        "Carga (%)", max_digits=5, decimal_places=1, null=True, blank=True
    )
    # Temperaturas corrigidas em função da carga (fórmula a definir com o cliente).
    temperatura_medida_corrigida = models.DecimalField(
        max_digits=6, decimal_places=1, null=True, blank=True, editable=False
    )
    temperatura_referencia_corrigida = models.DecimalField(
        max_digits=6, decimal_places=1, null=True, blank=True, editable=False
    )
    delta_t_corrigido = models.DecimalField(
        max_digits=6, decimal_places=1, null=True, blank=True, editable=False
    )

    # --- Termografia: grandezas elétricas (nominal + fases A/B/C ou R/S/T) ---
    corrente_nominal = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True)
    corrente_a = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True)
    corrente_b = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True)
    corrente_c = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True)
    tensao_nominal = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True)
    tensao_a = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True)
    tensao_b = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True)
    tensao_c = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True)

    # Condição / grau de risco DESTA análise (puxa da "Condição do Equipamento").
    # Cada análise do mesmo equipamento pode ter uma condição diferente; nasce
    # herdando a condição do item e é reclassificável no escritório. É ela que
    # aparece por análise na lista de equipamentos inspecionados do relatório.
    condicao = models.ForeignKey(
        Condicao, on_delete=models.SET_NULL, related_name="achados", null=True, blank=True,
        verbose_name="Condição / grau de risco",
    )

    # --- Escritório (Análise final) ---
    numero_osp = models.CharField("Número da OSP", max_length=40, blank=True)
    confirmada = models.BooleanField("Confirmada no escritório", default=False)
    visivel_cliente = models.BooleanField("Visível para o cliente", default=False)

    class Meta(BaseModel.Meta):
        verbose_name = "Achado / análise"
        verbose_name_plural = "Achados / análises"

    def __str__(self):
        return f"Achado #{self.pk} — {self.item.equipamento.tag}"

    def save(self, *args, **kwargs):
        # ΔT é sempre derivado da medida e da referência.
        if self.temperatura_medida is not None and self.temperatura_referencia is not None:
            self.delta_t = self.temperatura_medida - self.temperatura_referencia
        else:
            self.delta_t = None
        # Herda a condição do item na criação (reclassificável depois, no escritório).
        if self.condicao_id is None and self.item_id and self.item.condicao_id:
            self.condicao_id = self.item.condicao_id
        super().save(*args, **kwargs)


class TipoImagem(models.TextChoices):
    REAL = "REAL", "Foto real"
    TERMICA = "TERMICA", "Imagem térmica"
    TENDENCIA = "TENDENCIA", "Linha de tendência"
    ESPECTRO = "ESPECTRO", "Espectro"


class AchadoImagem(TimeStampedModel):
    """Evidência anexada no escritório. Padrão 800×600 (validado no upload/serializer)."""

    achado = models.ForeignKey(Achado, on_delete=models.CASCADE, related_name="imagens")
    tipo = models.CharField("Tipo de imagem", max_length=12, choices=TipoImagem.choices)
    arquivo = models.ImageField("Arquivo", upload_to="achados/")
    legenda = models.CharField("Legenda", max_length=200, blank=True)

    class Meta:
        verbose_name = "Imagem do achado"
        verbose_name_plural = "Imagens dos achados"
        ordering = ["tipo", "id"]

    def __str__(self):
        return f"{self.get_tipo_display()} — Achado #{self.achado_id}"
