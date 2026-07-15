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
    NOVA_OSP = "NOVA_OSP", "Nova OSP"
    EQUIPAMENTO_CRITICO = "EQUIPAMENTO_CRITICO", "Equipamento crítico"
    LAUDO_CONCLUIDO = "LAUDO_CONCLUIDO", "Laudo concluído"
    SLA_VENCENDO = "SLA_VENCENDO", "SLA vencendo"
    APROVACAO_PENDENTE = "APROVACAO_PENDENTE", "Aprovação pendente"


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
    canais_enviados = models.JSONField("Canais despachados", default=list, blank=True)

    lida = models.BooleanField("Lida", default=False)
    lida_em = models.DateTimeField("Lida em", null=True, blank=True)

    class Meta:
        verbose_name = "Notificação"
        verbose_name_plural = "Notificações"
        ordering = ["-criado_em"]
        indexes = [models.Index(fields=["destinatario", "lida"])]

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
