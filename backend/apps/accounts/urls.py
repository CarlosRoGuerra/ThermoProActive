from rest_framework.routers import DefaultRouter

from .views import UserViewSet

router = DefaultRouter()
router.register("usuarios", UserViewSet, basename="usuario")

urlpatterns = router.urls
