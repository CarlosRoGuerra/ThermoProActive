from django.contrib import admin

from .models import (
    Area,
    ClassificacaoInspecao,
    Cliente,
    Componente,
    Empresa,
    Equipamento,
    FalhaRecorrente,
    GrupoAcesso,
    Instrumento,
    Norma,
    Rota,
    Setor,
    TecnologiaAnalise,
    TipoAnomalia,
    TipoComponente,
    TipoCriticidade,
    TipoEquipamento,
    TipoInspecao,
    TipoRecomendacao,
)


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ["nome", "cnpj", "cidade_uf", "ativo"]
    search_fields = ["nome", "cnpj"]


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ["nome", "cnpj", "unidade_negocio", "cidade_uf", "ativo"]
    search_fields = ["nome", "cnpj"]


@admin.register(Area)
class AreaAdmin(admin.ModelAdmin):
    list_display = ["nome", "cliente", "ativo"]
    list_filter = ["cliente"]


@admin.register(Setor)
class SetorAdmin(admin.ModelAdmin):
    list_display = ["nome", "area", "ativo"]
    list_filter = ["area__cliente"]


class ComponenteInline(admin.TabularInline):
    model = Componente
    extra = 1


@admin.register(Equipamento)
class EquipamentoAdmin(admin.ModelAdmin):
    list_display = ["tag", "nome", "setor", "classe_iso", "rotacao_nominal_rpm", "ativo"]
    list_filter = ["classe_iso", "setor__area__cliente"]
    search_fields = ["tag", "nome"]
    inlines = [ComponenteInline]


@admin.register(Instrumento)
class InstrumentoAdmin(admin.ModelAdmin):
    list_display = ["tipo", "marca", "modelo", "numero_serie", "data_ultima_calibracao"]


@admin.register(Rota)
class RotaAdmin(admin.ModelAdmin):
    list_display = ["nome", "cliente", "periodicidade_dias", "ativo"]
    list_filter = ["cliente"]
    filter_horizontal = ["equipamentos"]


@admin.register(Norma)
class NormaAdmin(admin.ModelAdmin):
    list_display = ["codigo", "nome", "orgao", "ativo"]
    search_fields = ["codigo", "nome"]


@admin.register(TipoCriticidade)
class TipoCriticidadeAdmin(admin.ModelAdmin):
    list_display = ["nome", "nivel", "cor", "ativo"]
    ordering = ["nivel"]


# Catálogos simples (nome + descrição) — registro genérico.
@admin.register(
    TecnologiaAnalise,
    TipoEquipamento,
    ClassificacaoInspecao,
    TipoInspecao,
    FalhaRecorrente,
    TipoComponente,
    TipoAnomalia,
    TipoRecomendacao,
    GrupoAcesso,
)
class CatalogoAdmin(admin.ModelAdmin):
    list_display = ["nome", "descricao", "ativo"]
    search_fields = ["nome"]
