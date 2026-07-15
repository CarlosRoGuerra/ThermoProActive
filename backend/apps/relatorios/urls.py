from django.urls import path

from .views import RelatorioGerarView, RelatorioListView

urlpatterns = [
    path("relatorios/", RelatorioListView.as_view(), name="relatorios"),
    path("relatorios/<str:key>/", RelatorioGerarView.as_view(), name="relatorio-gerar"),
]
