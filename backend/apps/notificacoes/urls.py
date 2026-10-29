from rest_framework.routers import DefaultRouter

from .views import EventoPreditivoViewSet, NotificacaoViewSet

router = DefaultRouter()
router.register("notificacoes", NotificacaoViewSet, basename="notificacao")
router.register("eventos-preditivos", EventoPreditivoViewSet, basename="eventopreditivo")

urlpatterns = router.urls
