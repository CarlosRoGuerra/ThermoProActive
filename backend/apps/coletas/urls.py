from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    DashboardExecutivoView,
    DashboardView,
    InspecaoViewSet,
    MedicaoTecnicaViewSet,
    MedicaoTermografiaViewSet,
    MedicaoVibracaoViewSet,
    PortalVisaoGeralView,
)

router = DefaultRouter()
router.register("inspecoes", InspecaoViewSet, basename="inspecao")
router.register("medicoes-vibracao", MedicaoVibracaoViewSet, basename="medicaovibracao")
router.register("medicoes-termografia", MedicaoTermografiaViewSet, basename="medicaotermografia")
router.register("medicoes-tecnicas", MedicaoTecnicaViewSet, basename="medicaotecnica")

urlpatterns = [
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("dashboard/executivo/", DashboardExecutivoView.as_view(), name="dashboard-executivo"),
    path("portal/visao-geral/", PortalVisaoGeralView.as_view(), name="portal-visao-geral"),
    *router.urls,
]
