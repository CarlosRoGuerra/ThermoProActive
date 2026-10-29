from rest_framework.routers import DefaultRouter

from .views import LaudoViewSet, TemplateLaudoViewSet

router = DefaultRouter()
router.register("laudos", LaudoViewSet, basename="laudo")
router.register("templates-laudo", TemplateLaudoViewSet, basename="template-laudo")

urlpatterns = router.urls
