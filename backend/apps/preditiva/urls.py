from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("preditiva/configuracoes-tendencia", views.ConfiguracaoTendenciaViewSet,
                basename="preditiva-configuracao-tendencia")
router.register("preditiva/limites-alarme", views.LimiteAlarmeSerieViewSet, basename="preditiva-limite-alarme")
router.register("preditiva/matrizes-risco", views.MatrizRiscoViewSet, basename="preditiva-matriz-risco")
router.register("preditiva/regras-sugestao", views.RegraSugestaoViewSet, basename="preditiva-regra-sugestao")
router.register("preditiva/aceitacoes-sugestao", views.AceitacaoSugestaoViewSet,
                basename="preditiva-aceitacao-sugestao")

urlpatterns = [
    path("preditiva/tendencias/<str:modalidade>/<int:pk>/", views.TendenciaView.as_view(), name="preditiva-tendencia"),
    path("preditiva/tendencias/fluidos/<int:resultado_id>/<str:codigo>/", views.TendenciaFluidoView.as_view(),
         name="preditiva-tendencia-fluido"),
    path("preditiva/espessura/<int:pk>/", views.EspessuraView.as_view(), name="preditiva-espessura"),
    path("preditiva/motor-rxi/<int:pk>/", views.MotorRxiView.as_view(), name="preditiva-motor-rxi"),
    path("preditiva/ultrassom/<int:pk>/", views.UltrassomView.as_view(), name="preditiva-ultrassom"),
    path("preditiva/alinhamento/<int:pk>/", views.AlinhamentoView.as_view(), name="preditiva-alinhamento"),
    path("preditiva/qualidade-energia/<int:pk>/", views.QualidadeEnergiaView.as_view(),
         name="preditiva-qualidade-energia"),
    path("preditiva/risco/ranking/", views.RankingRiscoView.as_view(), name="preditiva-ranking-risco"),
    path("preditiva/sugestoes/", views.SugestoesView.as_view(), name="preditiva-sugestoes"),
    path("preditiva/aderencia-sugestoes/", views.AderenciaSugestoesView.as_view(), name="preditiva-aderencia"),
] + router.urls
