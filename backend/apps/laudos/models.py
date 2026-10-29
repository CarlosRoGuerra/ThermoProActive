"""
Laudos Técnicos — Anexo I, item 2.5.

`Laudo` é gerado a partir de uma `Inspecao` (item 2.5.1.1 — geração automática) e numerado
sequencialmente por ano (item 3.1.19). O conteúdo agrega diagnóstico, criticidade e
recomendações das medições (item 2.5.2). A emissão congela o conteúdo e gera o PDF
com Chromium nos layouts existentes, preservando os bytes em armazenamento privado.
"""
from django.conf import settings
from django.db import models, transaction
from django.db.models import Q
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.coletas.models import Inspecao
from apps.core.models import TimeStampedModel


class StatusLaudo(models.TextChoices):
    RASCUNHO = "RASCUNHO", "Rascunho"
    EMITIDO = "EMITIDO", "Emitido"
    CANCELADO = "CANCELADO", "Cancelado"


#: Sigla da tecnologia usada na numeração do relatório (RT.**AV**.2026.02.13.02308).
SIGLA_POR_TIPO_ANALISE = {
    "VIBRACAO": "AV",           # Análise Vibracional
    "TERMOGRAFIA": "TI",        # Termografia Infravermelha
    "FLUIDOS": "AF",            # Análise de Fluidos
    "ENSAIO_ELETRICO": "EE",
    "ULTRASSOM": "US",
    "ESPESSURA": "ME",          # Medição de Espessura
    "QUALIDADE_ENERGIA": "QE",
    "SENSITIVA": "IS",          # Inspeção Sensitiva
    "CORRETIVA": "MC",
}


class Laudo(TimeStampedModel):
    numero = models.CharField("Número do laudo", max_length=60, unique=True, editable=False)
    inspecao = models.ForeignKey(Inspecao, on_delete=models.PROTECT, related_name="laudos", null=True, blank=True)
    relatorio_origem = models.ForeignKey("coletas.Relatorio", on_delete=models.PROTECT,
                                         related_name="laudos", null=True, blank=True)
    cliente_documento = models.ForeignKey("cadastros.Cliente", on_delete=models.PROTECT,
                                          null=True, blank=True, editable=False, related_name="laudos_documentais")
    versao = models.PositiveSmallIntegerField("Versão", default=1)
    documento_raiz = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True,
                                       related_name="versoes_documento", editable=False)
    anterior = models.OneToOneField("self", on_delete=models.PROTECT, null=True, blank=True,
                                    related_name="revisao_seguinte", editable=False)
    motivo_revisao = models.TextField(blank=True, editable=False)
    template = models.ForeignKey("TemplateLaudo", on_delete=models.PROTECT, null=True, blank=True)
    snapshot_emissao = models.JSONField(default=dict, blank=True, editable=False)
    snapshot_hash = models.CharField(max_length=64, blank=True, editable=False)
    assinatura = models.JSONField(default=dict, blank=True, editable=False)
    pdf_conteudo = models.BinaryField(null=True, editable=False)
    pdf_hash = models.CharField(max_length=64, blank=True, editable=False)
    cancelado_em = models.DateTimeField(null=True, blank=True, editable=False)
    cancelado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                       null=True, blank=True, related_name="laudos_cancelados", editable=False)
    motivo_cancelamento = models.TextField(blank=True, editable=False)

    # Datas do bloco "Data(s) da(s) Execução(ões)" do relatório técnico.
    data_medicao_campo = models.DateField("Medições em campo", null=True, blank=True)
    data_upload_osps = models.DateField("Upload das OSPs", null=True, blank=True)
    data_upload_relatorio = models.DateField("Upload do relatório completo", null=True, blank=True)

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
        constraints = [
            models.CheckConstraint(condition=(models.Q(inspecao__isnull=False, relatorio_origem__isnull=True)
                                    | models.Q(inspecao__isnull=True, relatorio_origem__isnull=False)), name="laudo_uma_origem"),
            models.UniqueConstraint(fields=["documento_raiz", "versao"], name="laudo_versao_documento_unica"),
        ]

    def __str__(self):
        return f"Laudo {self.numero} (v{self.versao})"

    @staticmethod
    def q_do_cliente(cliente_id):
        """Laudos do cliente — mesma regra de `cliente` (o documental prevalece)."""
        return Q(cliente_documento_id=cliente_id) | (Q(cliente_documento__isnull=True) & (
            Q(inspecao__cliente_id=cliente_id) | Q(relatorio_origem__cliente_id=cliente_id)))

    @property
    def cliente(self):
        if self.cliente_documento_id:
            return self.cliente_documento
        return self.inspecao.cliente if self.inspecao_id else self.relatorio_origem.cliente

    @property
    def pdf_disponivel(self):
        return bool(self.pdf_conteudo and self.pdf_hash)

    @staticmethod
    @transaction.atomic
    def proximo_numero(tipo_analise: str = "", data=None) -> str:
        """
        Numeração no padrão do relatório técnico do cliente:
            RT.AV.2026.02.13.02308
            └┬┘ └┬┘ └───┬────┘ └─┬─┘
             │   │      │        └── sequencial global (5 dígitos)
             │   │      └── data da medição em campo
             │   └── sigla da tecnologia (AV = Análise Vibracional)
             └── Relatório Técnico
        """
        sigla = SIGLA_POR_TIPO_ANALISE.get(tipo_analise, "RT")
        dia = data or timezone.now().date()
        # Sequencial global e contínuo (não reinicia por ano), como no relatório.
        cursor, _ = SequenciaLaudo.objects.get_or_create(pk=1)
        cursor = SequenciaLaudo.objects.select_for_update().get(pk=cursor.pk)
        if cursor.ultimo == 0:
            existentes = []
            for numero in Laudo.objects.filter(numero__startswith="RT.").values_list("numero", flat=True):
                try:
                    existentes.append(int(numero.rsplit(".", 1)[-1].split("-V")[0]))
                except ValueError:
                    continue
            cursor.ultimo = max(existentes, default=0)
        cursor.ultimo += 1
        cursor.save(update_fields=["ultimo"])
        seq = cursor.ultimo
        return f"RT.{sigla}.{dia:%Y.%m.%d}.{seq:05d}"

    @transaction.atomic
    def save(self, *args, **kwargs):
        if bool(self.inspecao_id) == bool(self.relatorio_origem_id):
            raise ValidationError("Informe exatamente uma origem: inspeção ou relatório de rotas.")
        if self.cliente_documento_id is None:
            self.cliente_documento = self.inspecao.cliente if self.inspecao_id else self.relatorio_origem.cliente
        if self.pk:
            anterior = type(self).objects.select_for_update().get(pk=self.pk)
            operacao = getattr(self, "_operacao_autorizada", "")
            if anterior.status != StatusLaudo.RASCUNHO:
                permitidos = {"status", "cancelado_em", "cancelado_por_id", "motivo_cancelamento", "atualizado_em"} if operacao == "cancelar" else set()
                alterados = {campo.attname for campo in self._meta.fields if getattr(self, campo.attname) != getattr(anterior, campo.attname)}
                if alterados - permitidos:
                    raise ValidationError("Documento emitido/cancelado é imutável. Crie uma revisão para alterar o conteúdo.")
            elif self.status != anterior.status and operacao not in {"emitir", "cancelar"}:
                raise ValidationError("Use as ações de emissão ou cancelamento para mudar o status.")
            if self.inspecao_id != anterior.inspecao_id or self.relatorio_origem_id != anterior.relatorio_origem_id:
                raise ValidationError("A origem do documento não pode ser alterada.")
            if anterior.cliente_documento_id and self.cliente_documento_id != anterior.cliente_documento_id:
                raise ValidationError("O cliente documental não pode ser alterado.")
        elif self.status != StatusLaudo.RASCUNHO:
            raise ValidationError("Novos documentos devem começar como rascunho.")
        # A data da medição em campo é a da inspeção, salvo informação em contrário.
        if self.data_medicao_campo is None and self.inspecao_id:
            self.data_medicao_campo = self.inspecao.data
        elif self.data_medicao_campo is None and self.relatorio_origem_id:
            self.data_medicao_campo = self.relatorio_origem.data_inicio or self.relatorio_origem.data_termino
        if not self.numero:
            tipo = self.inspecao.tipo_analise if self.inspecao_id else ""
            self.numero = self.proximo_numero(tipo, self.data_medicao_campo)
        super().save(*args, **kwargs)

    def emitir(self):
        raise ValidationError("A emissão exige o serviço autorizado com responsável autenticado e snapshot.")

    def delete(self, *args, **kwargs):
        raise ValidationError("Preserve o histórico documental; use o cancelamento com motivo.")


class SequenciaLaudo(models.Model):
    ultimo = models.PositiveIntegerField(default=0)


class TemplateLaudo(TimeStampedModel):
    nome = models.CharField(max_length=120)
    cliente = models.ForeignKey("cadastros.Cliente", on_delete=models.PROTECT, null=True, blank=True)
    tipo_analise = models.CharField(max_length=20, blank=True)
    configuracao = models.JSONField(default=dict, blank=True)
    versao = models.PositiveIntegerField(default=1, editable=False)
    ativo = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        from .templates import validar_configuracao
        validar_configuracao(self.configuracao)
        if self.pk:
            anterior = type(self).objects.get(pk=self.pk)
            if any(getattr(self, campo) != getattr(anterior, campo) for campo in ("nome", "cliente_id", "tipo_analise", "configuracao")):
                self.versao = anterior.versao + 1
        super().save(*args, **kwargs)


class EventoLaudo(TimeStampedModel):
    laudo = models.ForeignKey(Laudo, on_delete=models.PROTECT, related_name="eventos")
    acao = models.CharField(max_length=20)
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    motivo = models.TextField(blank=True)
    dados = models.JSONField(default=dict)

    class Meta:
        ordering = ["criado_em", "id"]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Eventos documentais não podem ser alterados.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Eventos documentais não podem ser excluídos.")


class AnexoLaudo(TimeStampedModel):
    """Imagem privada; a emissão incorpora seus bytes ao snapshot."""
    laudo = models.ForeignKey(Laudo, on_delete=models.PROTECT, related_name="anexos")
    nome = models.CharField(max_length=255)
    legenda = models.CharField(max_length=200, blank=True)
    mime = models.CharField(max_length=40, editable=False)
    sha256 = models.CharField(max_length=64, editable=False)
    tamanho = models.PositiveIntegerField(editable=False)
    conteudo = models.BinaryField(editable=False)
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, editable=False)

    class Meta:
        ordering = ["criado_em", "id"]

    def save(self, *args, **kwargs):
        if self.laudo.status != StatusLaudo.RASCUNHO:
            raise ValidationError("Evidências de documento emitido/cancelado são imutáveis.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.laudo.status != StatusLaudo.RASCUNHO:
            raise ValidationError("Evidências de documento emitido/cancelado são imutáveis.")
        return super().delete(*args, **kwargs)

    @property
    def data_uri(self):
        import base64
        return f"data:{self.mime};base64,{base64.b64encode(bytes(self.conteudo)).decode('ascii')}"
