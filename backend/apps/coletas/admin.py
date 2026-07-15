from django.contrib import admin

from .models import Inspecao, MedicaoTecnica, MedicaoTermografia, MedicaoVibracao


class MedicaoVibracaoInline(admin.TabularInline):
    model = MedicaoVibracao
    extra = 0
    readonly_fields = ["zona_iso", "criticidade", "diagnostico_sugerido", "data_hora"]


class MedicaoTermografiaInline(admin.TabularInline):
    model = MedicaoTermografia
    extra = 0
    readonly_fields = ["delta_t", "criticidade", "diagnostico_sugerido", "data_hora"]


class MedicaoTecnicaInline(admin.TabularInline):
    model = MedicaoTecnica
    extra = 0
    readonly_fields = ["criticidade", "diagnostico_sugerido", "data_hora"]


@admin.register(Inspecao)
class InspecaoAdmin(admin.ModelAdmin):
    list_display = ["id", "cliente", "tipo_analise", "tecnico", "data", "status"]
    list_filter = ["tipo_analise", "status", "cliente"]
    date_hierarchy = "data"
    inlines = [MedicaoVibracaoInline, MedicaoTermografiaInline, MedicaoTecnicaInline]


@admin.register(MedicaoTecnica)
class MedicaoTecnicaAdmin(admin.ModelAdmin):
    list_display = ["equipamento", "tipo", "grandeza", "valor", "unidade", "criticidade"]
    list_filter = ["criticidade", "tipo"]
    search_fields = ["equipamento__tag", "grandeza", "ponto_medicao"]
    readonly_fields = ["criticidade", "diagnostico_sugerido", "data_hora"]


@admin.register(MedicaoTermografia)
class MedicaoTermografiaAdmin(admin.ModelAdmin):
    list_display = ["equipamento", "ponto_medicao", "sistema", "delta_t", "criticidade"]
    list_filter = ["criticidade", "sistema"]
    search_fields = ["equipamento__tag", "ponto_medicao"]
    readonly_fields = ["delta_t", "criticidade", "diagnostico_sugerido", "data_hora"]


@admin.register(MedicaoVibracao)
class MedicaoVibracaoAdmin(admin.ModelAdmin):
    list_display = ["equipamento", "ponto_medicao", "direcao", "velocidade_rms", "zona_iso", "criticidade"]
    list_filter = ["criticidade", "zona_iso", "direcao"]
    search_fields = ["equipamento__tag", "ponto_medicao"]
    readonly_fields = ["zona_iso", "criticidade", "diagnostico_sugerido", "data_hora"]
