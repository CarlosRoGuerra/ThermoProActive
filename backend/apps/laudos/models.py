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
    numero = models.CharField("Número do laudo", max_length=30, unique=True, editable=False)
    inspecao = models.ForeignKey(Inspecao, on_delete=models.PROTECT, related_name="laudos")
    versao = models.PositiveSmallIntegerField("Versão", default=1)

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

    def __str__(self):
        return f"Laudo {self.numero} (v{self.versao})"

    @staticmethod
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
        ultimo = (
            Laudo.objects.filter(numero__startswith="RT.")
            .order_by("-criado_em")
            .values_list("numero", flat=True)
            .first()
        )
        try:
            seq = int(ultimo.rsplit(".", 1)[-1]) + 1
        except (AttributeError, ValueError):
            seq = 1
        return f"RT.{sigla}.{dia:%Y.%m.%d}.{seq:05d}"

    def save(self, *args, **kwargs):
        # A data da medição em campo é a da inspeção, salvo informação em contrário.
        if self.data_medicao_campo is None and self.inspecao_id:
            self.data_medicao_campo = self.inspecao.data
        if not self.numero:
            tipo = self.inspecao.tipo_analise if self.inspecao_id else ""
            self.numero = self.proximo_numero(tipo, self.data_medicao_campo)
        super().save(*args, **kwargs)

    def emitir(self):
        self.status = StatusLaudo.EMITIDO
        self.data_emissao = timezone.now()
        self.save(update_fields=["status", "data_emissao", "atualizado_em"])
