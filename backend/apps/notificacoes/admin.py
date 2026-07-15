from django.contrib import admin

from .models import Notificacao, PreferenciaNotificacao


@admin.register(Notificacao)
class NotificacaoAdmin(admin.ModelAdmin):
    list_display = ["titulo", "evento", "destinatario", "nivel", "lida", "criado_em"]
    list_filter = ["evento", "nivel", "lida"]
    search_fields = ["titulo", "mensagem", "destinatario__email"]
    readonly_fields = ["canais_enviados", "lida_em", "criado_em", "atualizado_em"]


@admin.register(PreferenciaNotificacao)
class PreferenciaNotificacaoAdmin(admin.ModelAdmin):
    list_display = ["user", "interno", "email", "whatsapp", "push"]
