from django.contrib import admin

from .models import HistoricoOSP, OrdemServico


class HistoricoOSPInline(admin.TabularInline):
    """Trilha de auditoria: somente leitura, sem incluir nem apagar."""

    model = HistoricoOSP
    extra = 0
    can_delete = False
    fields = ["criado_em", "tipo", "ator_nome", "ator_perfil", "status_anterior", "status_novo",
              "alteracoes", "motivo"]
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(OrdemServico)
class OrdemServicoAdmin(admin.ModelAdmin):
    list_display = [
        "numero", "equipamento", "cliente", "prioridade", "status",
        "sla_data", "gerada_automaticamente",
    ]
    list_filter = ["status", "prioridade", "gerada_automaticamente", "cliente"]
    search_fields = ["numero", "titulo", "equipamento__tag"]
    # O status só muda pela API (máquina de estados + permissão + histórico).
    readonly_fields = [
        "numero", "status", "gerada_automaticamente", "criticidade_origem", "finalizada_em",
        "sla_origem", "aprovado_por", "aprovado_em",
    ]
    inlines = [HistoricoOSPInline]

    def has_delete_permission(self, request, obj=None):
        return False
