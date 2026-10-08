from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import InternoEditaClienteVisualiza, IsInterno, MasterEditaDemaisVisualizam
from apps.cadastros.models import Equipamento, ModuloTecnico
from apps.cadastros.views import CatalogoPagination, CatalogoViewSet
from apps.coletas.models import ItemInspecao, StatusCarregamento
from apps.coletas.views import escopo_cliente

from .models import (
    ColetaFluido,
    ColetaOleo,
    Ensaio,
    ItemChecklistVisual,
    MetaLimpezaRecomendada,
    ParametroEnsaio,
    PontoColeta,
    ProdutoFluido,
    ReferenciaParametro,
    RegistroEnsaioEletrico,
    ResultadoEnsaio,
    SolicitacaoPadraoEnsaio,
    TipoFluido,
)
from .serializers import (
    ColetaFluidoSerializer,
    ColetaOleoSerializer,
    EnsaioSerializer,
    FluidoInspecaoSerializer,
    ItemChecklistVisualSerializer,
    MetaLimpezaRecomendadaSerializer,
    ParametroEnsaioSerializer,
    PontoColetaSerializer,
    ProdutoFluidoSerializer,
    ReferenciaParametroSerializer,
    RegistroEnsaioEletricoSerializer,
    ResultadoEnsaioSerializer,
    SolicitacaoPadraoEnsaioSerializer,
    TipoFluidoSerializer,
    TransformadorInspecaoSerializer,
)

CAMPO_CLIENTE = "item__carregamento__cliente"
MODULOS_TRANSFORMADOR = (ModuloTecnico.OLEO_ISOLANTE, ModuloTecnico.ENSAIO_ELETRICO)
FLUIDO = ModuloTecnico.FLUIDO_LUBRIFICANTE


# ------------------------------- Catálogos ----------------------------------
class EnsaioViewSet(CatalogoViewSet):
    queryset = Ensaio.objects.ativos().prefetch_related("parametros", "solicitacoes_padrao")
    serializer_class = EnsaioSerializer
    filterset_fields = ["modulo"]
    search_fields = ["nome", "sigla"]


class TipoFluidoViewSet(CatalogoViewSet):
    queryset = TipoFluido.objects.ativos()
    serializer_class = TipoFluidoSerializer


class PontoColetaViewSet(CatalogoViewSet):
    queryset = PontoColeta.objects.ativos()
    serializer_class = PontoColetaSerializer
    filterset_fields = ["modulo"]


class ParametroEnsaioViewSet(viewsets.ReadOnlyModelViewSet):
    """Parâmetros dos ensaios (catálogo editado no admin) — para escolher em referências."""

    permission_classes = [IsAuthenticated]
    queryset = ParametroEnsaio.objects.ativos().select_related("ensaio").order_by("ensaio__modulo", "ensaio__ordem",
                                                                                 "ordem")
    serializer_class = ParametroEnsaioSerializer
    pagination_class = CatalogoPagination
    filterset_fields = ["ensaio", "ensaio__modulo", "calculado"]


class MetaLimpezaRecomendadaViewSet(CatalogoViewSet):
    """Metas de limpeza ISO 4406 recomendadas por máquina/componente (consulta para cadastrar a meta)."""

    queryset = MetaLimpezaRecomendada.objects.ativos()
    serializer_class = MetaLimpezaRecomendadaSerializer
    search_fields = ["nome", "codigo"]


class ProdutoFluidoViewSet(CatalogoViewSet):
    queryset = ProdutoFluido.objects.ativos()
    serializer_class = ProdutoFluidoSerializer
    filterset_fields = ["aplicacao"]
    search_fields = ["nome", "fabricante", "grau_viscosidade"]


class SolicitacaoPadraoEnsaioViewSet(CatalogoViewSet):
    queryset = SolicitacaoPadraoEnsaio.objects.ativos().select_related("ensaio")
    serializer_class = SolicitacaoPadraoEnsaioSerializer
    filterset_fields = ["aplicacao", "ensaio"]
    search_fields = ["ensaio__sigla", "ensaio__nome"]


class ReferenciaParametroViewSet(viewsets.ModelViewSet):
    """
    Referências dos parâmetros de fluidos (alerta/crítico por escopo, origem e
    vigência). Só a equipe interna consulta — a referência de um cliente não
    aparece para outro —, e só o Master altera (critério técnico = dado de sistema).
    """

    permission_classes = [IsInterno, MasterEditaDemaisVisualizam]
    queryset = (ReferenciaParametro.objects.ativos()
                .select_related("parametro__ensaio", "cliente", "equipamento", "produto"))
    serializer_class = ReferenciaParametroSerializer
    pagination_class = CatalogoPagination
    filterset_fields = ["parametro", "parametro__ensaio", "cliente", "equipamento", "produto", "aplicacao", "tipo",
                        "origem"]
    search_fields = ["parametro__nome", "parametro__codigo", "fonte"]


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


class ColetaFluidoViewSet(_DadoDeEnsaioViewSet):
    queryset = (
        ColetaFluido.objects.ativos()
        .select_related("item__carregamento__tecnologia", "ponto_coleta", "produto")
        .prefetch_related("ensaios")
    )
    serializer_class = ColetaFluidoSerializer


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
                        "item__equipamento__dados_transformador", "item__equipamento__setor__area",
                        "item__coleta_oleo", "item__registro_eletrico", "item__coleta_fluido")
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


class FluidoInspecaoViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Equipamentos das rotas de fluidos lubrificantes e hidráulicos: a fila do
    lançamento no campo (coleta) e no escritório (laudos). Só leitura.
    """

    permission_classes = [InternoEditaClienteVisualiza]
    serializer_class = FluidoInspecaoSerializer
    pagination_class = CatalogoPagination
    filterset_fields = ["carregamento", "carregamento__cliente", "carregamento__status", "carregamento__relatorio",
                        "equipamento"]
    search_fields = ["equipamento__tag", "equipamento__nome", "carregamento__relatorio__numero"]

    def get_queryset(self):
        qs = (
            ItemInspecao.objects.ativos()
            .filter(carregamento__tecnologia__modulo_tecnico=FLUIDO)
            .exclude(carregamento__status=StatusCarregamento.DESCARTADA)
            .select_related(
                "carregamento__cliente", "carregamento__tecnologia", "carregamento__relatorio",
                "carregamento__analista", "equipamento__setor__area", "equipamento__tipo_equipamento",
                "condicao", "coleta_fluido__produto",
            )
            .prefetch_related("resultados_ensaio", "coleta_fluido__ensaios")
            .order_by("-carregamento__data_coleta", "equipamento__setor__area__nome", "equipamento__setor__nome",
                      "equipamento__tag", "ordem")
        )
        return escopo_cliente(qs, self.request.user, campo_cliente="carregamento__cliente")


class FluidoHistoricoView(APIView):
    """
    Histórico de análise de fluidos — tendência por equipamento → ensaio →
    parâmetro → data.

      GET /api/fluidos-historico/                  equipamentos com resultado
      GET /api/fluidos-historico/?equipamento=<id> séries do equipamento

    O cliente vê só os próprios equipamentos e só os resultados de relatórios já
    finalizados (laudo revisado); a equipe interna vê tudo, inclusive o que ainda
    está em análise.
    """

    permission_classes = [IsAuthenticated]
    LIMITE_COLETAS = 24

    def _resultados(self, request):
        qs = ResultadoEnsaio.objects.ativos().filter(ensaio__modulo=FLUIDO, situacao="REALIZADO")
        qs = escopo_cliente(qs, request.user, campo_cliente=CAMPO_CLIENTE)
        if request.user.is_cliente:
            qs = qs.filter(item__carregamento__relatorio__data_finalizacao__isnull=False)
        return qs

    def get(self, request):
        from .relatorio import _Campanha
        from .relatorio_fluidos import (
            CAMPOS_AVALIACAO,
            ResolvedorReferencias,
            _campanhas_historico,
            montar_ficha_fluido,
        )

        resultados = self._resultados(request)
        equipamento_id = request.query_params.get("equipamento")
        if not equipamento_id:
            linhas = {}
            for r in resultados.select_related("item__equipamento__setor__area", "item__coleta_fluido__produto",
                                               "item__carregamento"):
                eq = r.item.equipamento
                c = _Campanha(r)
                atual = linhas.get(eq.id)
                if atual is None or c.data > atual["ultima_coleta"]:
                    coleta = c.coleta_fluido
                    linhas[eq.id] = {
                        "equipamento": eq.id, "tag": eq.tag, "nome": eq.nome,
                        "area": eq.setor.area.nome if eq.setor_id else "", "setor": eq.setor.nome if eq.setor_id else "",
                        "ultima_coleta": c.data, "fluido": coleta.nome_fluido if coleta else "",
                        "aplicacao": coleta.aplicacao if coleta else "",
                        "coletas": (atual or {}).get("coletas", set()) | {r.item_id},
                    }
                else:
                    atual["coletas"].add(r.item_id)
            saida = [{**v, "coletas": len(v["coletas"])} for v in linhas.values()]
            return Response(sorted(saida, key=lambda x: (x["area"], x["setor"], x["tag"])))

        visiveis = escopo_cliente(Equipamento.objects.all(), request.user, campo_cliente="setor__area__cliente")
        eq = get_object_or_404(visiveis.select_related("setor__area", "tipo_equipamento"), pk=equipamento_id)
        por_ensaio = {}
        for r in (resultados.filter(item__equipamento=eq)
                  .select_related("ensaio", "instrumento", "item__carregamento", "item__coleta_oleo",
                                  "item__registro_eletrico", "item__coleta_fluido__produto")
                  .prefetch_related("valores__parametro", "ensaio__parametros")):
            por_ensaio.setdefault(r.ensaio_id, []).append(r)
        ensaios = []
        for lista in por_ensaio.values():
            ensaio = lista[0].ensaio
            params = [p for p in ensaio.parametros.all() if p.ativo]
            campanhas = _campanhas_historico([_Campanha(r) for r in lista], self.LIMITE_COLETAS)
            atual = campanhas[-1]
            ficha = montar_ficha_fluido(ensaio, params, atual.resultado, atual, campanhas, eq,
                                        ResolvedorReferencias(p.id for p in params), False)
            ensaios.append({
                "sigla": ensaio.sigla, "nome": ensaio.nome, "ordem": ensaio.ordem,
                **{k: ficha[k] for k in CAMPOS_AVALIACAO if k in ficha},
            })
        ensaios.sort(key=lambda e: e["ordem"])
        return Response({
            "equipamento": {"id": eq.id, "tag": eq.tag, "nome": eq.nome,
                            "area": eq.setor.area.nome if eq.setor_id else "",
                            "setor": eq.setor.nome if eq.setor_id else ""},
            "ensaios": ensaios,
        })
