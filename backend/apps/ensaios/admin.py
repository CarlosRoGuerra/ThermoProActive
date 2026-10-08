from django.contrib import admin

from .models import (
    ColetaFluido,
    ColetaOleo,
    Ensaio,
    InspecaoVisualColeta,
    ItemChecklistVisual,
    MetaLimpezaRecomendada,
    ParametroEnsaio,
    PontoColeta,
    ProdutoFluido,
    ReferenciaParametro,
    RegistroEnsaioEletrico,
    ResultadoEnsaio,
    SolicitacaoPadraoEnsaio,
    TipoFluido,
    ValorParametro,
)


class ParametroInline(admin.TabularInline):
    model = ParametroEnsaio
    extra = 0
    fields = ["ordem", "codigo", "nome", "simbolo", "grupo", "unidade", "norma", "tipo_limite", "limite",
              "limite_superior", "referencia_texto", "casas_decimais", "calculado", "no_grafico", "ativo"]


@admin.register(Ensaio)
class EnsaioAdmin(admin.ModelAdmin):
    list_display = ["sigla", "nome", "modulo", "ordem", "ativo"]
    list_filter = ["modulo"]
    inlines = [ParametroInline]


@admin.register(TipoFluido)
class CatalogoEnsaioAdmin(admin.ModelAdmin):
    list_display = ["nome", "ativo"]


@admin.register(PontoColeta)
class PontoColetaAdmin(admin.ModelAdmin):
    list_display = ["nome", "modulo", "ativo"]
    list_filter = ["modulo"]


@admin.register(MetaLimpezaRecomendada)
class MetaLimpezaRecomendadaAdmin(admin.ModelAdmin):
    list_display = ["nome", "codigo", "fonte", "ativo"]
    search_fields = ["nome", "codigo"]


@admin.register(ProdutoFluido)
class ProdutoFluidoAdmin(admin.ModelAdmin):
    list_display = ["nome", "fabricante", "aplicacao", "grau_viscosidade", "viscosidade_40c_cst", "ativo"]
    list_filter = ["aplicacao"]
    search_fields = ["nome", "fabricante"]


@admin.register(SolicitacaoPadraoEnsaio)
class SolicitacaoPadraoEnsaioAdmin(admin.ModelAdmin):
    list_display = ["aplicacao", "ensaio", "ativo"]
    list_filter = ["aplicacao"]


@admin.register(ReferenciaParametro)
class ReferenciaParametroAdmin(admin.ModelAdmin):
    list_display = ["parametro", "tipo", "limite_alerta", "limite_critico", "referencia_texto", "origem",
                    "cliente", "equipamento", "produto", "aplicacao", "vigencia_inicio", "vigencia_fim", "ativo"]
    list_filter = ["origem", "tipo", "aplicacao", "parametro__ensaio__modulo"]


@admin.register(ColetaFluido)
class ColetaFluidoAdmin(admin.ModelAdmin):
    list_display = ["item", "data_coleta", "aplicacao", "produto", "amostrador"]
    list_filter = ["aplicacao"]


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
