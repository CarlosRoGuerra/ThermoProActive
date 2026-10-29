"""
Notificações — Anexo I, item 2.10.

Canais (2.10.1): alerta interno, e-mail, WhatsApp, push.
Eventos (2.10.2): nova OSP, equipamento crítico, laudo concluído, SLA vencendo,
aprovação pendente.

O alerta interno é sempre persistido como uma `Notificacao` (não depende de terceiros).
Os demais canais são despachados por adaptadores opcionais (ver `channels.py`), sem
fornecedor obrigatório — compatível com a Cláusula 12.4.
"""
from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel


class EventoNotificacao(models.TextChoices):
    ALERTA_PREDITIVO = "ALERTA_PREDITIVO", "Alerta preditivo"
    NOVA_OSP = "NOVA_OSP", "Nova OSP"
    EQUIPAMENTO_CRITICO = "EQUIPAMENTO_CRITICO", "Equipamento crítico"
    LAUDO_CONCLUIDO = "LAUDO_CONCLUIDO", "Laudo concluído"
    SLA_VENCENDO = "SLA_VENCENDO", "SLA vencendo"
    APROVACAO_PENDENTE = "APROVACAO_PENDENTE", "Aprovação pendente"
    OSP_STATUS = "OSP_STATUS", "Status da OSP alterado"


class Canal(models.TextChoices):
    INTERNO = "INTERNO", "Alerta interno"
    EMAIL = "EMAIL", "E-mail"
    WHATSAPP = "WHATSAPP", "WhatsApp"
    PUSH = "PUSH", "Push notification"


class Nivel(models.TextChoices):
    INFO = "INFO", "Informativo"
    ALERTA = "ALERTA", "Alerta"
    CRITICO = "CRITICO", "Crítico"


class Notificacao(TimeStampedModel):
    destinatario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notificacoes"
    )
    evento = models.CharField(max_length=24, choices=EventoNotificacao.choices)
    titulo = models.CharField("Título", max_length=160)
    mensagem = models.TextField("Mensagem")
    url = models.CharField("Link (rota do frontend)", max_length=200, blank=True)
    nivel = models.CharField(max_length=8, choices=Nivel.choices, default=Nivel.ALERTA)
    evento_preditivo = models.ForeignKey(
        "EventoPreditivo", on_delete=models.PROTECT, null=True, blank=True, related_name="notificacoes",
    )
    # Canais em que o provedor ACEITOU a mensagem (INTERNO sempre). O detalhe por
    # canal — tentativas, erro, datas — está em `entregas` (EntregaNotificacao).
    canais_enviados = models.JSONField("Canais despachados", default=list, blank=True)
    # Idempotência: a mesma ocorrência (ex.: "nova_osp:42") gera no máximo UMA
    # notificação por destinatário, mesmo com reprocessamento ou tarefa repetida.
    chave = models.CharField("Chave de idempotência", max_length=120, blank=True, default="")

    lida = models.BooleanField("Lida", default=False)
    lida_em = models.DateTimeField("Lida em", null=True, blank=True)

    class Meta:
        verbose_name = "Notificação"
        verbose_name_plural = "Notificações"
        ordering = ["-criado_em"]
        indexes = [models.Index(fields=["destinatario", "lida"])]
        constraints = [
            models.UniqueConstraint(fields=["evento_preditivo", "destinatario"],
                                    name="uniq_notificacao_evento_preditivo_destinatario"),
            models.UniqueConstraint(fields=["destinatario", "chave"], condition=~models.Q(chave=""),
                                    name="uniq_notificacao_chave_destinatario"),
        ]

    def __str__(self):
        return f"[{self.get_evento_display()}] {self.titulo} → {self.destinatario_id}"

    def marcar_lida(self):
        if not self.lida:
            self.lida = True
            self.lida_em = timezone.now()
            self.save(update_fields=["lida", "lida_em", "atualizado_em"])


class PreferenciaNotificacao(TimeStampedModel):
    """Canais habilitados por usuário (item 2.10.1)."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="pref_notificacao"
    )
    interno = models.BooleanField("Alertas internos", default=True)
    email = models.BooleanField("E-mail", default=True)
    whatsapp = models.BooleanField("WhatsApp", default=False)
    push = models.BooleanField("Push", default=False)

    class Meta:
        verbose_name = "Preferência de notificação"
        verbose_name_plural = "Preferências de notificação"

    def __str__(self):
        return f"Preferências de {self.user_id}"


class EstadoEventoPreditivo(TimeStampedModel):
    """Cursor de transições, bloqueado na gravação; consultas nunca o modificam."""

    medicao_tipo = models.CharField(max_length=64)
    medicao_id = models.PositiveBigIntegerField()
    ultima_criticidade = models.CharField(max_length=8, blank=True)
    sequencia = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["medicao_tipo", "medicao_id"],
                                                name="uniq_estado_evento_preditivo_medicao")]


class EventoPreditivo(TimeStampedModel):
    """Transição lógica com a evidência da época; não representa probabilidade de falha."""

    medicao_tipo = models.CharField(max_length=64)
    medicao_id = models.PositiveBigIntegerField()
    sequencia = models.PositiveIntegerField()
    inspecao = models.ForeignKey("coletas.Inspecao", on_delete=models.PROTECT, related_name="eventos_preditivos")
    equipamento = models.ForeignKey("cadastros.Equipamento", on_delete=models.PROTECT,
                                    related_name="eventos_preditivos")
    osp = models.ForeignKey("osp.OrdemServico", on_delete=models.PROTECT, null=True, blank=True,
                            related_name="eventos_preditivos")
    criticidade_anterior = models.CharField(max_length=8, blank=True)
    criticidade = models.CharField(max_length=8, blank=True)
    regra_versao = models.CharField(max_length=80)
    evidencias = models.JSONField(default=dict)
    orientacao = models.TextField(blank=True)

    class Meta:
        ordering = ["-criado_em", "-id"]
        constraints = [models.UniqueConstraint(fields=["medicao_tipo", "medicao_id", "sequencia"],
                                                name="uniq_evento_preditivo_transicao")]


class StatusEntrega(models.TextChoices):
    """
    Estado da entrega de UMA notificação em UM canal externo.

    ENVIADO quer dizer "o provedor aceitou" (SMTP respondeu OK, gateway devolveu
    2xx). Confirmação de recebimento/leitura não é rastreada. Nada vira ENVIADO
    sem uma resposta positiva do provedor.
    """

    PENDENTE = "PENDENTE", "Pendente"
    ENVIADO = "ENVIADO", "Aceito pelo provedor"
    SIMULADO = "SIMULADO", "Simulado (backend de desenvolvimento)"
    FALHOU = "FALHOU", "Falhou"
    NAO_CONFIGURADO = "NAO_CONFIGURADO", "Canal não configurado"
    IGNORADO = "IGNORADO", "Sem destino válido"


#: Estados finais que podem ser reenfileirados com segurança (nunca o ENVIADO).
STATUS_REPROCESSAVEIS = {StatusEntrega.FALHOU, StatusEntrega.NAO_CONFIGURADO}


class EntregaNotificacao(TimeStampedModel):
    """
    Rastreabilidade por canal (Anexo I 2.10.1): tentativas, próximo horário,
    último erro (sem segredos), id devolvido pelo provedor e data do aceite.
    """

    notificacao = models.ForeignKey(Notificacao, on_delete=models.CASCADE, related_name="entregas")
    canal = models.CharField(max_length=10, choices=Canal.choices)
    status = models.CharField(max_length=16, choices=StatusEntrega.choices, default=StatusEntrega.PENDENTE)
    tentativas = models.PositiveSmallIntegerField(default=0)
    proxima_tentativa_em = models.DateTimeField(null=True, blank=True, db_index=True)
    ultima_tentativa_em = models.DateTimeField(null=True, blank=True)
    enviado_em = models.DateTimeField(null=True, blank=True)
    ultimo_erro = models.CharField(max_length=500, blank=True)
    provedor_id = models.CharField("Id no provedor", max_length=120, blank=True)

    class Meta:
        verbose_name = "Entrega de notificação"
        verbose_name_plural = "Entregas de notificações"
        ordering = ["-criado_em", "-id"]
        constraints = [models.UniqueConstraint(fields=["notificacao", "canal"],
                                                name="uniq_entrega_notificacao_canal")]
        indexes = [models.Index(fields=["status", "proxima_tentativa_em"])]

    def __str__(self):
        return f"{self.notificacao_id}/{self.canal}: {self.status}"
