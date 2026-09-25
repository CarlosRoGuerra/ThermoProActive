from rest_framework.routers import DefaultRouter

from .views import (
    ColetaOleoViewSet,
    EnsaioViewSet,
    ItemChecklistVisualViewSet,
    PontoColetaViewSet,
    RegistroEnsaioEletricoViewSet,
    ResultadoEnsaioViewSet,
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

urlpatterns = router.urls
