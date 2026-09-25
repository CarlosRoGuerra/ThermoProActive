from rest_framework import viewsets

from apps.accounts.permissions import InternoEditaClienteVisualiza
from apps.cadastros.views import CatalogoViewSet
from apps.coletas.views import escopo_cliente

from .models import (
    ColetaOleo,
    Ensaio,
    ItemChecklistVisual,
    PontoColeta,
    RegistroEnsaioEletrico,
    ResultadoEnsaio,
    TipoFluido,
)
from .serializers import (
    ColetaOleoSerializer,
    EnsaioSerializer,
    ItemChecklistVisualSerializer,
    PontoColetaSerializer,
    RegistroEnsaioEletricoSerializer,
    ResultadoEnsaioSerializer,
    TipoFluidoSerializer,
)

CAMPO_CLIENTE = "item__carregamento__cliente"


# ------------------------------- Catálogos ----------------------------------
class EnsaioViewSet(CatalogoViewSet):
    queryset = Ensaio.objects.ativos().prefetch_related("parametros")
    serializer_class = EnsaioSerializer
    filterset_fields = ["modulo"]
    search_fields = ["nome", "sigla"]


class TipoFluidoViewSet(CatalogoViewSet):
    queryset = TipoFluido.objects.ativos()
    serializer_class = TipoFluidoSerializer


class PontoColetaViewSet(CatalogoViewSet):
    queryset = PontoColeta.objects.ativos()
    serializer_class = PontoColetaSerializer


class ItemChecklistVisualViewSet(CatalogoViewSet):
    queryset = ItemChecklistVisual.objects.ativos()
    serializer_class = ItemChecklistVisualSerializer
    filterset_fields = ["grupo"]


# ------------------------ Dados de campo e resultados ------------------------
class _DadoDeEnsaioViewSet(viewsets.ModelViewSet):
    """Lançado pela CONTRATADA; o cliente consulta o que é da própria empresa."""

    permission_classes = [InternoEditaClienteVisualiza]
    filterset_fields = ["item", "item__carregamento", "item__carregamento__relatorio", "item__equipamento"]

    def get_queryset(self):
        return escopo_cliente(super().get_queryset(), self.request.user, campo_cliente=CAMPO_CLIENTE)


class ColetaOleoViewSet(_DadoDeEnsaioViewSet):
    queryset = (
        ColetaOleo.objects.ativos()
        .select_related("item__carregamento__tecnologia", "ponto_coleta", "tipo_fluido")
        .prefetch_related("ensaios", "inspecao_visual__item_checklist")
    )
    serializer_class = ColetaOleoSerializer


class RegistroEnsaioEletricoViewSet(_DadoDeEnsaioViewSet):
    queryset = (
        RegistroEnsaioEletrico.objects.ativos()
        .select_related("item__carregamento__tecnologia")
        .prefetch_related("ensaios")
    )
    serializer_class = RegistroEnsaioEletricoSerializer


class ResultadoEnsaioViewSet(_DadoDeEnsaioViewSet):
    queryset = (
        ResultadoEnsaio.objects.ativos()
        .select_related("item__carregamento__tecnologia", "ensaio", "instrumento")
        .prefetch_related("valores__parametro")
    )
    serializer_class = ResultadoEnsaioSerializer
    filterset_fields = _DadoDeEnsaioViewSet.filterset_fields + ["ensaio", "ensaio__modulo", "situacao"]
