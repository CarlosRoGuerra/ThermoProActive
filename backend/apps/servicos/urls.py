from rest_framework.routers import DefaultRouter

from .views import (
    BalanceamentoPlanoViewSet,
    BalanceamentoPontoViewSet,
    EconomiaEnergeticaViewSet,
    ServicoCampoViewSet,
)

router = DefaultRouter()
router.register("servicos", ServicoCampoViewSet, basename="servicocampo")
router.register("balanceamento-planos", BalanceamentoPlanoViewSet, basename="balanceamentoplano")
router.register("balanceamento-pontos", BalanceamentoPontoViewSet, basename="balanceamentoponto")
router.register("economias", EconomiaEnergeticaViewSet, basename="economiaenergetica")

urlpatterns = router.urls
