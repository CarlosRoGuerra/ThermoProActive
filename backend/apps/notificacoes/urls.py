from rest_framework.routers import DefaultRouter

from .views import NotificacaoViewSet

router = DefaultRouter()
router.register("notificacoes", NotificacaoViewSet, basename="notificacao")

urlpatterns = router.urls
