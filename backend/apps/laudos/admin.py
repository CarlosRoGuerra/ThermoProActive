from django.contrib import admin

from .models import Laudo


@admin.register(Laudo)
class LaudoAdmin(admin.ModelAdmin):
    list_display = ["numero", "titulo", "criticidade_geral", "status", "responsavel", "data_emissao"]
    list_filter = ["status", "criticidade_geral"]
    search_fields = ["numero", "titulo"]
    readonly_fields = ["numero", "data_emissao"]
