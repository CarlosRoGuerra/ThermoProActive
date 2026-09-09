"""
Serviços de Campo — Anexo I 2.3.2.8 (Manutenção Corretiva).

Substitui as planilhas de balanceamento dinâmico e de economia energética do Fabrício.
Diferente da coleta de rota (app `coletas`), aqui o registro é de uma **intervenção**:
fecha o ciclo Achado → OSP → serviço executado → economia gerada.

Princípio de projeto (decisão do Fabrício, 08/09/2026): **nenhuma grandeza tem valor
padrão**. Tensão, correntes, fator de potência, regime de operação, tarifa e custo do
serviço são todos medidos/informados na hora, naquele equipamento, naquele dia. Nenhum
campo numérico de campo usa `default=`, e nada é herdado do cadastro do cliente — um
default silencioso produziria um número plausível que ninguém mediu.

Os campos calculados (`editable=False`) vêm de `apps.servicos.rules`, testado contra os
números das planilhas originais. Ver docs/04-DISCOVERY-balanceamento-e-economia.md.
"""
from django.conf import settings
from django.db import models

from apps.cadastros.models import Cliente, Equipamento, Instrumento
from apps.coletas.models import Criticidade, Direcao
from apps.core.models import BaseModel

from . import rules


class TipoServico(models.TextChoices):
    BALANCEAMENTO = "BALANCEAMENTO", "Balanceamento dinâmico em campo"
    ALINHAMENTO = "ALINHAMENTO", "Alinhamento a laser"


class ServicoCampo(BaseModel):
    """
    Cabeçalho da intervenção — o cabeçalho das planilhas `Bal-1P`/`Bal-2P`.

    `osp` e `achado` são opcionais porque o serviço pode nascer de duas formas: como
    execução de uma OSP aberta pela rota preditiva (o caminho normal) ou como serviço
    avulso contratado direto.
    """

    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="servicos")
    equipamento = models.ForeignKey(Equipamento, on_delete=models.PROTECT, related_name="servicos")
    tipo = models.CharField("Tipo de serviço", max_length=15, choices=TipoServico.choices)

    # Origem (opcional) — é o que fecha o ciclo preditivo.
    osp = models.ForeignKey(
        "osp.OrdemServico", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="servicos", verbose_name="OSP de origem",
    )
    achado = models.ForeignKey(
        "coletas.Achado", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="servicos", verbose_name="Análise de origem",
    )
    relatorio = models.ForeignKey(
        "coletas.Relatorio", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="servicos", verbose_name="Relatório em que sai",
    )

    analista = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="servicos",
        verbose_name="Analista responsável",
    )
    instrumento = models.ForeignKey(
        Instrumento, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="servicos", help_text="Rastreabilidade de calibração (item 3.1.10).",
    )
    data_execucao = models.DateField("Data de execução")

    # Cabeçalho da planilha: "Rotação: 29,74 Hz".
    rotacao_hz = models.DecimalField(
        "Rotação (Hz)", max_digits=7, decimal_places=2, null=True, blank=True
    )
    rotacao_rpm = models.PositiveIntegerField("Rotação (RPM)", null=True, blank=True, editable=False)

    custo_servico = models.DecimalField(
        "Custo do serviço (R$)", max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Informado a cada serviço — não vem de tabela de preço.",
    )
    observacoes = models.TextField("Observações", blank=True)

    class Meta(BaseModel.Meta):
        verbose_name = "Serviço de campo"
        verbose_name_plural = "Serviços de campo"

    def __str__(self):
        return f"{self.get_tipo_display()} — {self.equipamento.tag} — {self.data_execucao}"

    @property
    def numero_planos(self) -> int:
        """1P ou 2P: era a escolha entre duas abas da planilha; aqui é uma contagem."""
        return self.planos.count()

    @property
    def reducao_media_pct(self):
        """Redução média entre os pontos medidos — resumo do serviço."""
        valores = [p.reducao_pct for p in self.pontos.all() if p.reducao_pct is not None]
        return sum(valores) / len(valores) if valores else None

    @property
    def criticidade_final(self) -> str:
        """Pior criticidade entre os pontos após o balanceamento (veredito do serviço)."""
        ordem = {"NORMAL": 0, "ALERTA": 1, "CRITICO": 2}
        valores = [p.criticidade for p in self.pontos.all() if p.criticidade]
        if not valores:
            return Criticidade.NORMAL
        return max(valores, key=lambda c: ordem.get(c, 0))

    def save(self, *args, **kwargs):
        self.rotacao_rpm = rules.hz_para_rpm(self.rotacao_hz) if self.rotacao_hz else None
        super().save(*args, **kwargs)


class BalanceamentoPlano(BaseModel):
    """
    Plano de correção — onde a massa é fixada.

    Separado de `BalanceamentoPonto` de propósito: a planilha de 2 planos trata
    "mancal 3 = plano 1", mas plano de correção e ponto de medição são coisas distintas
    (um plano pode ser avaliado por mais de um mancal). Ver §3 do discovery.
    """

    servico = models.ForeignKey(ServicoCampo, on_delete=models.CASCADE, related_name="planos")
    numero = models.PositiveSmallIntegerField("Plano nº", help_text="1 ou 2")
    descricao = models.CharField(
        "Descrição", max_length=120, blank=True, help_text="Ex.: lado acoplamento"
    )

    # "Teste Inicial: Plano 1 — 0° / 30,0 g"
    massa_teste_g = models.DecimalField(
        "Massa de teste (g)", max_digits=9, decimal_places=2, null=True, blank=True
    )
    angulo_teste = models.DecimalField(
        "Ângulo da massa de teste (°)", max_digits=5, decimal_places=1, null=True, blank=True
    )
    # Massa que ficou na máquina ao final ("100 g" da linha Massas / trim run).
    massa_final_g = models.DecimalField(
        "Massa final (g)", max_digits=9, decimal_places=2, null=True, blank=True
    )
    angulo_final = models.DecimalField(
        "Ângulo da massa final (°)", max_digits=5, decimal_places=1, null=True, blank=True
    )

    class Meta(BaseModel.Meta):
        verbose_name = "Plano de balanceamento"
        verbose_name_plural = "Planos de balanceamento"
        ordering = ["numero"]
        constraints = [
            models.UniqueConstraint(
                fields=["servico", "numero"], name="uniq_plano_por_servico"
            ),
        ]

    def __str__(self):
        return f"Plano {self.numero} — {self.servico_id}"


class BalanceamentoPonto(BaseModel):
    """
    Uma linha do corpo da planilha: um ponto de medição × as três corridas.

    `residual_pct`, `reducao_pct`, `zona_iso` e `criticidade` são calculados no `save()`
    — a planilha calculava os dois primeiros e não tinha os dois últimos.
    """

    servico = models.ForeignKey(ServicoCampo, on_delete=models.CASCADE, related_name="pontos")
    plano = models.ForeignKey(
        BalanceamentoPlano, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="pontos", verbose_name="Plano corrigido por este ponto",
    )
    numero_mancal = models.PositiveSmallIntegerField("Mancal")
    direcao = models.CharField("Direção", max_length=1, choices=Direcao.choices)

    # REFERENCE RUN (ANTES) — obrigatório: é a base de toda a curva de redução.
    reference_mms = models.DecimalField("Reference run (mm/s)", max_digits=8, decimal_places=2)
    reference_fase = models.DecimalField("Reference run — fase (°)", max_digits=5, decimal_places=1)

    # TRIAL RUN — opcional: em máquina com histórico o analista pode pular a corrida de teste.
    trial_mms = models.DecimalField(
        "Trial run (mm/s)", max_digits=8, decimal_places=2, null=True, blank=True
    )
    trial_fase = models.DecimalField(
        "Trial run — fase (°)", max_digits=5, decimal_places=1, null=True, blank=True
    )

    # TRIM RUN — o resultado final. Nulo enquanto o serviço está em andamento: o
    # técnico mede o reference, aplica a massa de teste, mede o trial, calcula, aplica a
    # massa final e só então mede o trim. Isso leva uma hora — exigir o trim para salvar
    # obrigaria a anotar no papel e digitar depois, que é o que o sistema elimina.
    trim_mms = models.DecimalField(
        "Trim run (mm/s)", max_digits=8, decimal_places=2, null=True, blank=True
    )
    trim_fase = models.DecimalField(
        "Trim run — fase (°)", max_digits=5, decimal_places=1, null=True, blank=True
    )

    # Calculados (bloco CURVA REDUÇÃO + veredito ISO que a planilha não tinha).
    residual_pct = models.DecimalField(
        "Vibração residual (%)", max_digits=8, decimal_places=3, null=True, editable=False
    )
    reducao_pct = models.DecimalField(
        "Redução obtida (%)", max_digits=8, decimal_places=3, null=True, editable=False
    )
    zona_iso = models.CharField("Zona ISO do resultado", max_length=1, blank=True, editable=False)
    criticidade = models.CharField(
        "Criticidade final", max_length=8, choices=Criticidade.choices, blank=True, editable=False
    )
    eficaz = models.BooleanField("Balanceamento eficaz", default=False, editable=False)
    diagnostico = models.TextField("Diagnóstico", blank=True, editable=False)

    class Meta(BaseModel.Meta):
        verbose_name = "Ponto de balanceamento"
        verbose_name_plural = "Pontos de balanceamento"
        ordering = ["numero_mancal", "direcao"]

    def __str__(self):
        return f"Mancal {self.numero_mancal}{self.direcao}: {self.reference_mms} → {self.trim_mms} mm/s"

    @property
    def codigo_ponto(self) -> str:
        """Mesma nomenclatura da vibração: mancal + direção (ex.: "2H")."""
        return f"{self.numero_mancal}{self.direcao}"

    @property
    def completo(self) -> bool:
        """Só há resultado depois do trim run — antes disso o ponto está em andamento."""
        return self.trim_mms is not None and self.trim_fase is not None

    def save(self, *args, **kwargs):
        if self.completo:
            resultado = rules.avaliar_ponto(
                classe_iso=self.servico.equipamento.classe_iso,
                reference_mms=self.reference_mms,
                trim_mms=self.trim_mms,
            )
            self.residual_pct = resultado.residual_pct
            self.reducao_pct = resultado.reducao_pct
            self.zona_iso = resultado.zona_iso
            self.criticidade = resultado.criticidade
            self.eficaz = resultado.eficaz
            self.diagnostico = resultado.diagnostico
        else:
            # Ponto em andamento: nada de resultado parcial, que seria lido como final.
            self.residual_pct = self.reducao_pct = None
            self.zona_iso = self.criticidade = self.diagnostico = ""
            self.eficaz = False
        super().save(*args, **kwargs)


class EconomiaEnergetica(BaseModel):
    """
    Planilha `Economia Geradas com Alinhamentos e Balanceamentos.xlsx`.

    Um-para-um com o serviço, e vale para balanceamento E alinhamento. Todos os campos
    de entrada são obrigatórios e medidos na hora: sem tarifa não há economia calculável,
    e assumir uma produziria um valor financeiro falso no relatório do cliente.
    """

    servico = models.OneToOneField(
        ServicoCampo, on_delete=models.CASCADE, related_name="economia"
    )

    # --- Entradas (as células amarelas da planilha) ---
    tensao_v = models.DecimalField("Tensão do motor (V)", max_digits=9, decimal_places=2)
    corrente_antes_a = models.DecimalField(
        "Corrente antes (A)", max_digits=9, decimal_places=2
    )
    corrente_apos_a = models.DecimalField("Corrente após (A)", max_digits=9, decimal_places=2)
    fator_potencia = models.DecimalField(
        "Fator de potência", max_digits=4, decimal_places=3, help_text="Medido no motor."
    )
    horas_dia = models.DecimalField(
        "Regime diário de operação (h)", max_digits=4, decimal_places=1
    )
    dias_ano = models.PositiveSmallIntegerField(
        "Dias de operação por ano", help_text="Na planilha era fixo em 365."
    )
    custo_kwh = models.DecimalField(
        "Custo da energia (R$/kWh)", max_digits=8, decimal_places=4,
        help_text="Tarifa vigente informada pelo cliente.",
    )

    # --- Calculados (as células verdes) ---
    reducao_kw = models.DecimalField(
        "Redução de demanda (kW)", max_digits=12, decimal_places=4, null=True, editable=False
    )
    economia_kwh_ano = models.DecimalField(
        "Economia (kWh/ano)", max_digits=14, decimal_places=2, null=True, editable=False
    )
    economia_rs_ano = models.DecimalField(
        "Economia (R$/ano)", max_digits=14, decimal_places=2, null=True, editable=False
    )
    payback_meses = models.DecimalField(
        "Payback (meses)", max_digits=8, decimal_places=2, null=True, blank=True, editable=False
    )
    payback_dias = models.DecimalField(
        "Payback (dias)", max_digits=8, decimal_places=1, null=True, blank=True, editable=False
    )
    retorno_ano = models.DecimalField(
        "Retorno (×/ano)", max_digits=10, decimal_places=3, null=True, blank=True, editable=False,
        help_text='O "4,67" da planilha: quantas vezes o serviço se paga no ano.',
    )

    class Meta(BaseModel.Meta):
        verbose_name = "Economia energética"
        verbose_name_plural = "Economias energéticas"

    def __str__(self):
        return f"Economia — {self.servico}"

    @property
    def premissas(self) -> list[str]:
        """Impressas junto do resultado: sem elas o número não se sustenta em auditoria."""
        return self._resultado().premissas

    def _resultado(self):
        return rules.calcular_economia(
            tensao_v=self.tensao_v,
            corrente_antes_a=self.corrente_antes_a,
            corrente_apos_a=self.corrente_apos_a,
            fator_potencia=self.fator_potencia,
            horas_dia=self.horas_dia,
            dias_ano=self.dias_ano,
            custo_kwh=self.custo_kwh,
            custo_servico=self.servico.custo_servico or 0,
        )

    def save(self, *args, **kwargs):
        r = self._resultado()
        self.reducao_kw = r.reducao_kw
        self.economia_kwh_ano = r.economia_kwh_ano
        self.economia_rs_ano = r.economia_rs_ano
        self.payback_meses = r.payback_meses
        self.payback_dias = r.payback_dias
        self.retorno_ano = r.retorno_ano
        super().save(*args, **kwargs)
