from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("ia/chaves", views.ChaveApiIAViewSet, basename="ia-chave")

urlpatterns = [
    path("ia/ativacoes/", views.AtivacoesIAView.as_view(), name="ia-ativacoes"),
    path("ia/ativacoes/<str:recurso>/", views.AtivacaoIAView.as_view(), name="ia-ativacao"),
] + router.urls
