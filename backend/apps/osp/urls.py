from rest_framework.routers import DefaultRouter

from .views import (
    ApontamentoExecucaoViewSet,
    AssinaturaOSPViewSet,
    EvidenciaOSPViewSet,
    ItemModeloChecklistViewSet,
    ModeloChecklistViewSet,
    OrdemServicoViewSet,
    PecaOSPViewSet,
)

router = DefaultRouter()
router.register("osps", OrdemServicoViewSet, basename="osp")
# Itens 2.6.2.2 a 2.6.2.8 — ver docs/21.
router.register("osp-checklists", ModeloChecklistViewSet, basename="osp-checklist")
router.register("osp-checklist-itens", ItemModeloChecklistViewSet, basename="osp-checklist-item")
router.register("osp-pecas", PecaOSPViewSet, basename="osp-peca")
router.register("osp-evidencias", EvidenciaOSPViewSet, basename="osp-evidencia")
router.register("osp-apontamentos", ApontamentoExecucaoViewSet, basename="osp-apontamento")
router.register("osp-assinaturas", AssinaturaOSPViewSet, basename="osp-assinatura")

urlpatterns = router.urls
