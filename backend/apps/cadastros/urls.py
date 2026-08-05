from rest_framework.routers import DefaultRouter

from .views import (
    AreaViewSet,
    ClassificacaoInspecaoViewSet,
    ClienteViewSet,
    ComponenteViewSet,
    CondicaoViewSet,
    EmpresaViewSet,
    EquipamentoViewSet,
    FalhaRecorrenteViewSet,
    GrupoAcessoViewSet,
    InstrumentoViewSet,
    NormaViewSet,
    RotaViewSet,
    SetorViewSet,
    TecnologiaAnaliseViewSet,
    TipoAnomaliaViewSet,
    TipoComponenteViewSet,
    TipoCriticidadeViewSet,
    TipoEquipamentoViewSet,
    TipoInspecaoViewSet,
    TipoRecomendacaoViewSet,
)

router = DefaultRouter()
# Cadastros principais
router.register("empresas", EmpresaViewSet)
router.register("clientes", ClienteViewSet)
router.register("areas", AreaViewSet)
router.register("setores", SetorViewSet)
router.register("equipamentos", EquipamentoViewSet)
router.register("componentes", ComponenteViewSet)
router.register("instrumentos", InstrumentoViewSet)
router.register("rotas", RotaViewSet)
# Catálogos / tabelas de referência
router.register("normas", NormaViewSet)
router.register("tecnologias-analise", TecnologiaAnaliseViewSet)
router.register("tipos-equipamento", TipoEquipamentoViewSet)
router.register("classificacoes-inspecao", ClassificacaoInspecaoViewSet)
router.register("tipos-inspecao", TipoInspecaoViewSet)
router.register("falhas-recorrentes", FalhaRecorrenteViewSet)
router.register("tipos-componente", TipoComponenteViewSet)
router.register("tipos-anomalia", TipoAnomaliaViewSet)
router.register("tipos-recomendacao", TipoRecomendacaoViewSet)
router.register("tipos-criticidade", TipoCriticidadeViewSet)
router.register("condicoes", CondicaoViewSet)
router.register("grupos-acesso", GrupoAcessoViewSet)

urlpatterns = router.urls
