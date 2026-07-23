from rest_framework import viewsets
from rest_framework.pagination import PageNumberPagination

from apps.accounts.permissions import InternoEditaClienteVisualiza, MasterEditaDemaisVisualizam

from .models import (
    Area,
    ClassificacaoInspecao,
    Cliente,
    Componente,
    Empresa,
    Equipamento,
    FalhaRecorrente,
    GrupoAcesso,
    Instrumento,
    Norma,
    Rota,
    Setor,
    TecnologiaAnalise,
    TipoAnomalia,
    TipoComponente,
    TipoCriticidade,
    TipoEquipamento,
    TipoInspecao,
    TipoRecomendacao,
)
from .serializers import (
    AreaSerializer,
    ClassificacaoInspecaoSerializer,
    ClienteSerializer,
    ComponenteSerializer,
    EmpresaSerializer,
    EquipamentoSerializer,
    FalhaRecorrenteSerializer,
    GrupoAcessoSerializer,
    InstrumentoSerializer,
    NormaSerializer,
    RotaSerializer,
    SetorSerializer,
    TecnologiaAnaliseSerializer,
    TipoAnomaliaSerializer,
    TipoComponenteSerializer,
    TipoCriticidadeSerializer,
    TipoEquipamentoSerializer,
    TipoInspecaoSerializer,
    TipoRecomendacaoSerializer,
)


class CatalogoPagination(PageNumberPagination):
    """Catálogos são tabelas pequenas de referência: entrega a lista completa
    (até 1000) para permitir ordenação/busca no cliente sem paginar."""

    page_size = 500
    page_size_query_param = "page_size"
    max_page_size = 1000


class BaseCadastroViewSet(viewsets.ModelViewSet):
    """Interno edita; cliente apenas lê (item 2.7). Retorna só registros ativos."""

    permission_classes = [InternoEditaClienteVisualiza]

    def perform_destroy(self, instance):
        # Soft-delete: preserva histórico técnico (não apaga fisicamente).
        instance.ativo = False
        instance.save(update_fields=["ativo"])


class EmpresaViewSet(BaseCadastroViewSet):
    queryset = Empresa.objects.ativos()
    serializer_class = EmpresaSerializer
    search_fields = ["nome", "cnpj"]


class ClienteViewSet(BaseCadastroViewSet):
    """Cadastro do tomador de serviço (topo da hierarquia Cliente → Área → Setor)."""

    queryset = Cliente.objects.ativos()
    serializer_class = ClienteSerializer
    pagination_class = CatalogoPagination
    filterset_fields = ["uf", "cidade"]
    search_fields = [
        "nome", "nome_fantasia", "cnpj", "unidade_negocio", "cidade", "uf", "contato_gestor",
    ]


class AreaViewSet(BaseCadastroViewSet):
    queryset = Area.objects.ativos().select_related("cliente")
    serializer_class = AreaSerializer
    pagination_class = CatalogoPagination
    filterset_fields = ["cliente"]
    search_fields = ["nome", "codigo"]


class SetorViewSet(BaseCadastroViewSet):
    queryset = Setor.objects.ativos().select_related("area", "area__cliente")
    serializer_class = SetorSerializer
    pagination_class = CatalogoPagination
    filterset_fields = ["area", "area__cliente"]
    search_fields = ["nome", "codigo"]


class EquipamentoViewSet(BaseCadastroViewSet):
    queryset = (
        Equipamento.objects.ativos()
        .select_related("setor", "setor__area", "setor__area__cliente")
        .prefetch_related("componentes")
    )
    serializer_class = EquipamentoSerializer
    pagination_class = CatalogoPagination
    filterset_fields = ["setor", "setor__area", "setor__area__cliente", "classe_iso"]
    # Busca por TAG e número de série — como o cliente pediu na reunião.
    search_fields = ["tag", "nome", "fabricante", "modelo", "numero_serie"]


class ComponenteViewSet(BaseCadastroViewSet):
    queryset = Componente.objects.ativos().select_related("equipamento")
    serializer_class = ComponenteSerializer
    filterset_fields = ["equipamento"]
    search_fields = ["nome"]


class InstrumentoViewSet(BaseCadastroViewSet):
    # Cadastro de instrumentação (Cadastros → admin cura). Técnicos apenas leem
    # para selecionar o instrumento nas medições (FK de leitura).
    queryset = Instrumento.objects.ativos()
    serializer_class = InstrumentoSerializer
    permission_classes = [MasterEditaDemaisVisualizam]
    pagination_class = CatalogoPagination
    search_fields = ["tipo", "marca", "modelo", "numero_serie", "entidade_calibracao"]


# --- Catálogos / tabelas de referência (Anexo I 2.2.1.5–2.2.1.14, 2.2.1.18) ---


class CatalogoViewSet(BaseCadastroViewSet):
    """Base para catálogos simples: busca por nome, lista completa (sem paginar)
    e escrita restrita ao Admin (curadoria centralizada das tabelas de referência)."""

    permission_classes = [MasterEditaDemaisVisualizam]
    pagination_class = CatalogoPagination
    search_fields = ["nome", "descricao"]


class NormaViewSet(CatalogoViewSet):
    queryset = Norma.objects.ativos().prefetch_related("tecnologias")
    serializer_class = NormaSerializer
    search_fields = ["nome", "codigo", "orgao"]


class TecnologiaAnaliseViewSet(CatalogoViewSet):
    queryset = TecnologiaAnalise.objects.ativos()
    serializer_class = TecnologiaAnaliseSerializer


class TipoEquipamentoViewSet(CatalogoViewSet):
    queryset = TipoEquipamento.objects.ativos()
    serializer_class = TipoEquipamentoSerializer


class ClassificacaoInspecaoViewSet(CatalogoViewSet):
    queryset = ClassificacaoInspecao.objects.ativos()
    serializer_class = ClassificacaoInspecaoSerializer


class TipoInspecaoViewSet(CatalogoViewSet):
    queryset = TipoInspecao.objects.ativos().select_related("classificacao")
    serializer_class = TipoInspecaoSerializer
    filterset_fields = ["classificacao"]


class FalhaRecorrenteViewSet(CatalogoViewSet):
    queryset = FalhaRecorrente.objects.ativos()
    serializer_class = FalhaRecorrenteSerializer


class TipoComponenteViewSet(CatalogoViewSet):
    queryset = TipoComponente.objects.ativos().prefetch_related("tecnologias")
    serializer_class = TipoComponenteSerializer


class TipoAnomaliaViewSet(CatalogoViewSet):
    queryset = TipoAnomalia.objects.ativos().prefetch_related("tecnologias")
    serializer_class = TipoAnomaliaSerializer


class TipoRecomendacaoViewSet(CatalogoViewSet):
    queryset = TipoRecomendacao.objects.ativos().prefetch_related("tecnologias")
    serializer_class = TipoRecomendacaoSerializer


class TipoCriticidadeViewSet(CatalogoViewSet):
    queryset = TipoCriticidade.objects.ativos()
    serializer_class = TipoCriticidadeSerializer


class GrupoAcessoViewSet(CatalogoViewSet):
    queryset = GrupoAcesso.objects.ativos()
    serializer_class = GrupoAcessoSerializer


class RotaViewSet(BaseCadastroViewSet):
    queryset = Rota.objects.ativos().select_related("cliente").prefetch_related("equipamentos")
    serializer_class = RotaSerializer
    filterset_fields = ["cliente"]
    search_fields = ["nome", "descricao"]
