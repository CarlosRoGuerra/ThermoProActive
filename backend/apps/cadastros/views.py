from rest_framework import viewsets

from apps.accounts.permissions import InternoEditaClienteVisualiza

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
    queryset = Cliente.objects.ativos()
    serializer_class = ClienteSerializer
    search_fields = ["nome", "cnpj", "unidade_negocio"]


class AreaViewSet(BaseCadastroViewSet):
    queryset = Area.objects.ativos().select_related("cliente")
    serializer_class = AreaSerializer
    filterset_fields = ["cliente"]
    search_fields = ["nome"]


class SetorViewSet(BaseCadastroViewSet):
    queryset = Setor.objects.ativos().select_related("area", "area__cliente")
    serializer_class = SetorSerializer
    filterset_fields = ["area", "area__cliente"]
    search_fields = ["nome"]


class EquipamentoViewSet(BaseCadastroViewSet):
    queryset = (
        Equipamento.objects.ativos()
        .select_related("setor", "setor__area", "setor__area__cliente")
        .prefetch_related("componentes")
    )
    serializer_class = EquipamentoSerializer
    filterset_fields = ["setor", "setor__area", "setor__area__cliente", "classe_iso"]
    search_fields = ["tag", "nome", "fabricante", "modelo"]


class ComponenteViewSet(BaseCadastroViewSet):
    queryset = Componente.objects.ativos().select_related("equipamento")
    serializer_class = ComponenteSerializer
    filterset_fields = ["equipamento"]
    search_fields = ["nome"]


class InstrumentoViewSet(BaseCadastroViewSet):
    queryset = Instrumento.objects.ativos()
    serializer_class = InstrumentoSerializer
    search_fields = ["tipo", "marca", "modelo", "numero_serie"]


# --- Catálogos / tabelas de referência (Anexo I 2.2.1.5–2.2.1.14, 2.2.1.18) ---


class CatalogoViewSet(BaseCadastroViewSet):
    """Base para catálogos simples: busca por nome e soft-delete herdado."""

    search_fields = ["nome", "descricao"]


class NormaViewSet(CatalogoViewSet):
    queryset = Norma.objects.ativos()
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
    queryset = TipoComponente.objects.ativos()
    serializer_class = TipoComponenteSerializer


class TipoAnomaliaViewSet(CatalogoViewSet):
    queryset = TipoAnomalia.objects.ativos()
    serializer_class = TipoAnomaliaSerializer


class TipoRecomendacaoViewSet(CatalogoViewSet):
    queryset = TipoRecomendacao.objects.ativos()
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
