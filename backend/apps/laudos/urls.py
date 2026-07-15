from rest_framework.routers import DefaultRouter

from .views import LaudoViewSet

router = DefaultRouter()
router.register("laudos", LaudoViewSet, basename="laudo")

urlpatterns = router.urls
