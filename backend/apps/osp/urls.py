from rest_framework.routers import DefaultRouter

from .views import OrdemServicoViewSet

router = DefaultRouter()
router.register("osps", OrdemServicoViewSet, basename="osp")

urlpatterns = router.urls
