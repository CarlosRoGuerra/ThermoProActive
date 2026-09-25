from django.contrib import admin

from .models import (
    ColetaOleo,
    Ensaio,
    InspecaoVisualColeta,
    ItemChecklistVisual,
    ParametroEnsaio,
    PontoColeta,
    RegistroEnsaioEletrico,
    ResultadoEnsaio,
    TipoFluido,
    ValorParametro,
)


class ParametroInline(admin.TabularInline):
    model = ParametroEnsaio
    extra = 0
    fields = ["ordem", "codigo", "nome", "unidade", "norma", "tipo_limite", "limite", "limite_superior",
              "referencia_texto", "casas_decimais", "calculado", "no_grafico", "ativo"]


@admin.register(Ensaio)
class EnsaioAdmin(admin.ModelAdmin):
    list_display = ["sigla", "nome", "modulo", "ordem", "ativo"]
    list_filter = ["modulo"]
    inlines = [ParametroInline]


@admin.register(TipoFluido, PontoColeta)
class CatalogoEnsaioAdmin(admin.ModelAdmin):
    list_display = ["nome", "ativo"]


@admin.register(ItemChecklistVisual)
class ItemChecklistVisualAdmin(admin.ModelAdmin):
    list_display = ["nome", "grupo", "ordem", "ativo"]
    list_filter = ["grupo"]


class InspecaoVisualInline(admin.TabularInline):
    model = InspecaoVisualColeta
    extra = 0


@admin.register(ColetaOleo)
class ColetaOleoAdmin(admin.ModelAdmin):
    list_display = ["item", "data_coleta", "amostrador"]
    inlines = [InspecaoVisualInline]


@admin.register(RegistroEnsaioEletrico)
class RegistroEnsaioEletricoAdmin(admin.ModelAdmin):
    list_display = ["item", "data_ensaio", "tap", "tensao_tap_v"]


class ValorInline(admin.TabularInline):
    model = ValorParametro
    extra = 0


@admin.register(ResultadoEnsaio)
class ResultadoEnsaioAdmin(admin.ModelAdmin):
    list_display = ["item", "ensaio", "situacao", "numero_laudo", "criticidade", "data_analise"]
    list_filter = ["ensaio", "situacao", "criticidade"]
    inlines = [ValorInline]
