from django.contrib import admin

from .models import OrdemServico


@admin.register(OrdemServico)
class OrdemServicoAdmin(admin.ModelAdmin):
    list_display = [
        "numero", "equipamento", "cliente", "prioridade", "status",
        "sla_data", "gerada_automaticamente",
    ]
    list_filter = ["status", "prioridade", "gerada_automaticamente", "cliente"]
    list_editable = ["status"]
    search_fields = ["numero", "titulo", "equipamento__tag"]
    readonly_fields = ["numero", "gerada_automaticamente", "criticidade_origem", "finalizada_em"]
