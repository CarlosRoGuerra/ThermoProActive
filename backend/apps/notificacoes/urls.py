from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import EventoPreditivoViewSet, NotificacaoViewSet, PushAssinaturaView, PushChaveView

router = DefaultRouter()
router.register("notificacoes", NotificacaoViewSet, basename="notificacao")
router.register("eventos-preditivos", EventoPreditivoViewSet, basename="eventopreditivo")

urlpatterns = router.urls + [
    # Item 2.10.1.3: Web Push (VAPID). Assinatura por dispositivo do usuário logado.
    path("notificacoes/push/chave/", PushChaveView.as_view(), name="push-chave"),
    path("notificacoes/push/assinatura/", PushAssinaturaView.as_view(), name="push-assinatura"),
]
