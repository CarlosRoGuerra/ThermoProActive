from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    ColetaFluidoViewSet,
    ColetaOleoViewSet,
    EnsaioViewSet,
    FluidoHistoricoView,
    FluidoInspecaoViewSet,
    ItemChecklistVisualViewSet,
    ParametroEnsaioViewSet,
    PontoColetaViewSet,
    ProdutoFluidoViewSet,
    ReferenciaParametroViewSet,
    RegistroEnsaioEletricoViewSet,
    ResultadoEnsaioViewSet,
    SolicitacaoPadraoEnsaioViewSet,
    TipoFluidoViewSet,
    TransformadorInspecaoViewSet,
)

router = DefaultRouter()
# Catálogos dos ensaios de transformador
router.register("ensaios", EnsaioViewSet, basename="ensaio")
router.register("tipos-fluido", TipoFluidoViewSet, basename="tipofluido")
router.register("pontos-coleta", PontoColetaViewSet, basename="pontocoleta")
router.register("itens-checklist-visual", ItemChecklistVisualViewSet, basename="itemchecklistvisual")
# Coleta do óleo, registro dos ensaios elétricos e resultados (laudos) por ensaio
router.register("coletas-oleo", ColetaOleoViewSet, basename="coletaoleo")
router.register("registros-ensaio-eletrico", RegistroEnsaioEletricoViewSet, basename="registroensaioeletrico")
router.register("resultados-ensaio", ResultadoEnsaioViewSet, basename="resultadoensaio")
# Fila do lançamento: transformadores das rotas de óleo e de ensaios elétricos
router.register("transformadores-inspecao", TransformadorInspecaoViewSet, basename="transformadorinspecao")
# Fluidos lubrificantes e hidráulicos: catálogos, referências, coleta e a fila do lançamento
router.register("parametros-ensaio", ParametroEnsaioViewSet, basename="parametroensaio")
router.register("produtos-fluido", ProdutoFluidoViewSet, basename="produtofluido")
router.register("solicitacoes-padrao-ensaio", SolicitacaoPadraoEnsaioViewSet, basename="solicitacaopadraoensaio")
router.register("referencias-parametro", ReferenciaParametroViewSet, basename="referenciaparametro")
router.register("coletas-fluido", ColetaFluidoViewSet, basename="coletafluido")
router.register("fluidos-inspecao", FluidoInspecaoViewSet, basename="fluidoinspecao")

urlpatterns = router.urls + [
    path("fluidos-historico/", FluidoHistoricoView.as_view(), name="fluidos-historico"),
]
