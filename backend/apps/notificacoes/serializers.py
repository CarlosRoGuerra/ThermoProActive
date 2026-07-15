from rest_framework import serializers

from .models import Notificacao, PreferenciaNotificacao


class NotificacaoSerializer(serializers.ModelSerializer):
    evento_display = serializers.CharField(source="get_evento_display", read_only=True)
    nivel_display = serializers.CharField(source="get_nivel_display", read_only=True)

    class Meta:
        model = Notificacao
        fields = [
            "id", "evento", "evento_display", "titulo", "mensagem", "url",
            "nivel", "nivel_display", "canais_enviados", "lida", "lida_em", "criado_em",
        ]


class PreferenciaNotificacaoSerializer(serializers.ModelSerializer):
    class Meta:
        model = PreferenciaNotificacao
        fields = ["interno", "email", "whatsapp", "push"]
