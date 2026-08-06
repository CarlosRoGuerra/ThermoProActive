from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    AchadoImagemViewSet,
    AchadoViewSet,
    CarregamentoViewSet,
    DashboardExecutivoView,
    DashboardView,
    InspecaoViewSet,
    ItemInspecaoViewSet,
    MedicaoTecnicaViewSet,
    MedicaoTermografiaViewSet,
    MedicaoVibracaoViewSet,
    PortalVisaoGeralView,
    RelatorioViewSet,
)

router = DefaultRouter()
router.register("inspecoes", InspecaoViewSet, basename="inspecao")
router.register("medicoes-vibracao", MedicaoVibracaoViewSet, basename="medicaovibracao")
router.register("medicoes-termografia", MedicaoTermografiaViewSet, basename="medicaotermografia")
router.register("medicoes-tecnicas", MedicaoTecnicaViewSet, basename="medicaotecnica")
# Fluxo de inspeção campo → escritório
# (evita colidir com /relatorios da geração de relatórios, no app relatorios)
router.register("relatorios-inspecao", RelatorioViewSet, basename="relatorio")
router.register("carregamentos", CarregamentoViewSet, basename="carregamento")
router.register("itens-inspecao", ItemInspecaoViewSet, basename="iteminspecao")
router.register("achados", AchadoViewSet, basename="achado")
router.register("achados-imagens", AchadoImagemViewSet, basename="achadoimagem")

urlpatterns = [
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("dashboard/executivo/", DashboardExecutivoView.as_view(), name="dashboard-executivo"),
    path("portal/visao-geral/", PortalVisaoGeralView.as_view(), name="portal-visao-geral"),
    *router.urls,
]
