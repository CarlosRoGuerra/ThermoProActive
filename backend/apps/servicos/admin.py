"""Admin dos Serviços de Campo — conferência rápida sem passar pelo front."""
from django.contrib import admin

from .models import BalanceamentoPlano, BalanceamentoPonto, EconomiaEnergetica, ServicoCampo


class BalanceamentoPlanoInline(admin.TabularInline):
    model = BalanceamentoPlano
    extra = 0


class BalanceamentoPontoInline(admin.TabularInline):
    model = BalanceamentoPonto
    extra = 0
    readonly_fields = ["residual_pct", "reducao_pct", "zona_iso", "criticidade", "eficaz"]


class EconomiaEnergeticaInline(admin.StackedInline):
    model = EconomiaEnergetica
    extra = 0
    readonly_fields = [
        "reducao_kw", "economia_kwh_ano", "economia_rs_ano",
        "payback_meses", "payback_dias", "retorno_ano",
    ]


@admin.register(ServicoCampo)
class ServicoCampoAdmin(admin.ModelAdmin):
    list_display = ["__str__", "cliente", "tipo", "data_execucao", "rotacao_rpm", "analista"]
    list_filter = ["tipo", "cliente", "data_execucao"]
    search_fields = ["equipamento__tag", "equipamento__nome"]
    readonly_fields = ["rotacao_rpm"]
    inlines = [BalanceamentoPlanoInline, BalanceamentoPontoInline, EconomiaEnergeticaInline]
