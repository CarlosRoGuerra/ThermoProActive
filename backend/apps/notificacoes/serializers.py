from rest_framework import serializers

from .models import EntregaNotificacao, EventoPreditivo, Notificacao, PreferenciaNotificacao


class EntregaResumoSerializer(serializers.ModelSerializer):
    """Estado por canal. O texto do erro fica só no admin (pode citar a infraestrutura)."""

    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = EntregaNotificacao
        fields = ["canal", "status", "status_display", "tentativas", "enviado_em"]


class NotificacaoSerializer(serializers.ModelSerializer):
    evento_display = serializers.CharField(source="get_evento_display", read_only=True)
    nivel_display = serializers.CharField(source="get_nivel_display", read_only=True)
    entregas = EntregaResumoSerializer(many=True, read_only=True)

    class Meta:
        model = Notificacao
        fields = [
            "id", "evento", "evento_display", "titulo", "mensagem", "url",
            "nivel", "nivel_display", "canais_enviados", "entregas", "lida", "lida_em", "criado_em", "evento_preditivo",
        ]


class PreferenciaNotificacaoSerializer(serializers.ModelSerializer):
    class Meta:
        model = PreferenciaNotificacao
        fields = ["interno", "email", "whatsapp", "push"]
        # O alerta interno é o registro do evento no sistema: não pode ser desligado.
        read_only_fields = ["interno"]


class EventoPreditivoSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventoPreditivo
        fields = "__all__"
