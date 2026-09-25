from rest_framework import viewsets

from apps.accounts.permissions import InternoEditaClienteVisualiza
from apps.cadastros.models import ModuloTecnico
from apps.cadastros.views import CatalogoPagination, CatalogoViewSet
from apps.coletas.models import ItemInspecao, StatusCarregamento
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
    TransformadorInspecaoSerializer,
)

CAMPO_CLIENTE = "item__carregamento__cliente"
MODULOS_TRANSFORMADOR = (ModuloTecnico.OLEO_ISOLANTE, ModuloTecnico.ENSAIO_ELETRICO)


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
    # `avaliacao` lê a placa do transformador, o registro de campo e os parâmetros
    # do ensaio — tudo carregado aqui, sem consulta por resultado.
    queryset = (
        ResultadoEnsaio.objects.ativos()
        .select_related("item__carregamento__tecnologia", "ensaio", "instrumento",
                        "item__equipamento__dados_transformador", "item__coleta_oleo", "item__registro_eletrico")
        .prefetch_related("valores__parametro", "ensaio__parametros")
    )
    serializer_class = ResultadoEnsaioSerializer
    filterset_fields = _DadoDeEnsaioViewSet.filterset_fields + ["ensaio", "ensaio__modulo", "situacao"]


# ------------------------- Fila de lançamento (leitura) -------------------------
class TransformadorInspecaoViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Transformadores das rotas de óleo isolante e de ensaios elétricos: a fila do
    lançamento no campo e no escritório. Só leitura — coleta, registro e
    resultados são gravados nos próprios endpoints.
    """

    permission_classes = [InternoEditaClienteVisualiza]
    serializer_class = TransformadorInspecaoSerializer
    pagination_class = CatalogoPagination
    filterset_fields = ["carregamento", "carregamento__cliente", "carregamento__status", "carregamento__relatorio",
                        "equipamento"]
    search_fields = ["equipamento__tag", "equipamento__nome", "carregamento__relatorio__numero"]

    def get_queryset(self):
        qs = (
            ItemInspecao.objects.ativos()
            .filter(carregamento__tecnologia__modulo_tecnico__in=MODULOS_TRANSFORMADOR)
            .exclude(carregamento__status=StatusCarregamento.DESCARTADA)
            .select_related(
                "carregamento__cliente", "carregamento__tecnologia", "carregamento__relatorio",
                "carregamento__analista", "equipamento__setor__area", "equipamento__dados_transformador",
                "condicao", "coleta_oleo", "registro_eletrico",
            )
            .prefetch_related("resultados_ensaio", "coleta_oleo__ensaios", "registro_eletrico__ensaios")
            .order_by("-carregamento__data_coleta", "equipamento__setor__area__nome", "equipamento__setor__nome",
                      "equipamento__tag", "ordem")
        )
        return escopo_cliente(qs, self.request.user, campo_cliente="carregamento__cliente")
