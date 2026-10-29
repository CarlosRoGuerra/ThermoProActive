from django.contrib import admin, messages

from .entregas import reprocessar
from .models import EntregaNotificacao, Notificacao, PreferenciaNotificacao


class EntregaInline(admin.TabularInline):
    model = EntregaNotificacao
    extra = 0
    can_delete = False
    fields = ["canal", "status", "tentativas", "ultima_tentativa_em", "proxima_tentativa_em",
              "enviado_em", "ultimo_erro", "provedor_id"]
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Notificacao)
class NotificacaoAdmin(admin.ModelAdmin):
    list_display = ["titulo", "evento", "destinatario", "nivel", "lida", "criado_em"]
    list_filter = ["evento", "nivel", "lida"]
    search_fields = ["titulo", "mensagem", "destinatario__email", "chave"]
    readonly_fields = ["chave", "canais_enviados", "lida_em", "criado_em", "atualizado_em"]
    inlines = [EntregaInline]


@admin.register(EntregaNotificacao)
class EntregaNotificacaoAdmin(admin.ModelAdmin):
    list_display = ["notificacao", "canal", "status", "tentativas", "ultima_tentativa_em", "enviado_em"]
    list_filter = ["status", "canal"]
    readonly_fields = [f.name for f in EntregaNotificacao._meta.fields]
    actions = ["reenfileirar"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description="Reenfileirar (só FALHOU / NÃO CONFIGURADO; enviadas não são reenviadas)")
    def reenfileirar(self, request, queryset):
        n = reprocessar(queryset)
        self.message_user(request, f"{n} entrega(s) de volta à fila.", messages.SUCCESS)


@admin.register(PreferenciaNotificacao)
class PreferenciaNotificacaoAdmin(admin.ModelAdmin):
    list_display = ["user", "interno", "email", "whatsapp", "push"]
