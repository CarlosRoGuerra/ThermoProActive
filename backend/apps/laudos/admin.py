from django.contrib import admin

from .models import Laudo


@admin.register(Laudo)
class LaudoAdmin(admin.ModelAdmin):
    list_display = ["numero", "titulo", "criticidade_geral", "status", "responsavel", "data_emissao"]
    list_filter = ["status", "criticidade_geral"]
    search_fields = ["numero", "titulo"]
    readonly_fields = ["numero", "data_emissao"]

    def get_readonly_fields(self, request, obj=None):
        return [campo.name for campo in self.model._meta.fields] if obj and obj.status != "RASCUNHO" else [
            "numero", "versao", "status", "data_emissao", "documento_raiz", "anterior", "snapshot_emissao",
            "snapshot_hash", "assinatura", "pdf_conteudo", "pdf_hash", "cancelado_em", "cancelado_por",
            "motivo_cancelamento", "motivo_revisao",
        ]

    def has_delete_permission(self, request, obj=None):
        return False
