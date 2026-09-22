from rest_framework import viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination

from apps.accounts.permissions import (
    InternoEditaClienteVisualiza,
    MasterEditaDemaisVisualizam,
)

from .models import (
    Area,
    ClassificacaoInspecao,
    Cliente,
    Componente,
    Condicao,
    DadosTecnicosMotor,
    DadosTecnicosTransformador,
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
    CondicaoSerializer,
    DadosTecnicosMotorSerializer,
    DadosTecnicosTransformadorSerializer,
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
    """
    Interno edita; cliente apenas lê (item 2.7). Retorna só registros ativos.

    ESCOPO MULTI-TENANT — `campo_cliente`
    -------------------------------------
    `InternoEditaClienteVisualiza` libera leitura a qualquer autenticado, o que
    é correto para as tabelas de referência (normas, tipos), mas NÃO para dados
    de cliente: sem filtro, um usuário do Portal listava `/equipamentos/` e
    `/clientes/` e recebia o parque e os contatos de TODOS os clientes.

    Cada ViewSet que expõe dado de cliente declara `campo_cliente` com o caminho
    do ORM até o Cliente; para perfis do tipo cliente, o queryset é filtrado
    pelo cliente vinculado ao usuário. Os catálogos globais deixam `None`.

    Mesma regra já aplicada em coletas/osp/laudos/servicos/relatorios
    (`escopo_cliente`), agora também aqui.
    """

    #: O Portal é de consulta: o parque é cadastrado pela CONTRATADA
    #: (decisão de 2026-09-21, que reverte a de 2026-09-18). A única escrita do
    #: cliente no sistema é o retorno da Ordem de Serviço — ver
    #: `InternoEditaClienteResponde`.
    permission_classes = [InternoEditaClienteVisualiza]

    #: Caminho do ORM até `cadastros.Cliente`. `None` = tabela global.
    campo_cliente = None

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if self.campo_cliente and getattr(user, "is_cliente", False):
            # Usuário cliente sem vínculo não enxerga nada — falha fechada.
            if not user.cliente_id:
                return qs.none()
            return qs.filter(**{self.campo_cliente: user.cliente_id})
        return qs

    def perform_destroy(self, instance):
        # Soft-delete: preserva histórico técnico (não apaga fisicamente).
        instance.ativo = False
        instance.save(update_fields=["ativo"])

    def perform_create(self, serializer):
        self._impedir_apontar_para_outro_cliente(serializer.validated_data)
        serializer.save()

    def perform_update(self, serializer):
        self._impedir_apontar_para_outro_cliente(serializer.validated_data, instancia=serializer.instance)
        serializer.save()

    def _impedir_apontar_para_outro_cliente(self, validated_data, instancia=None):
        """
        `get_queryset()` protege LER/EDITAR um registro que já existe. Não impede
        um Master de cliente CRIAR um novo apontando pra fora da própria empresa
        (ex.: um Equipamento cujo `setor` é de outro cliente) nem REATRIBUIR um
        já existente pra lá — nenhum dos dois passa pelo filtro de leitura.
        Só se aplica a usuário cliente; interno sempre pode apontar pra qualquer
        cliente (é o trabalho dele cadastrar o parque de qualquer um).
        """
        user = self.request.user
        if not (self.campo_cliente and getattr(user, "is_cliente", False)):
            return
        primeiro_campo, _, resto = self.campo_cliente.partition("__")
        if primeiro_campo not in validated_data:
            return  # não mudou nesta requisição — o valor atual já foi validado na leitura
        valor = validated_data[primeiro_campo]
        pk_valor = getattr(valor, "pk", valor)
        if resto:
            ok = valor.__class__.objects.filter(pk=pk_valor, **{resto: user.cliente_id}).exists()
        else:
            ok = pk_valor == user.cliente_id
        if not ok:
            raise ValidationError({primeiro_campo: "Isso não pertence à sua empresa."})


class EmpresaViewSet(BaseCadastroViewSet):
    queryset = Empresa.objects.ativos()
    serializer_class = EmpresaSerializer
    search_fields = ["nome", "cnpj"]


class ClienteViewSet(BaseCadastroViewSet):
    """
    Cadastro do tomador de serviço (topo da hierarquia Cliente → Área → Setor).

    Só leitura para o cliente, como todo o resto do parque: ele consulta a
    própria estrutura, mas quem cadastra é a CONTRATADA.
    """

    # O usuário do Portal vê apenas a própria empresa.
    campo_cliente = "id"
    queryset = Cliente.objects.ativos()
    serializer_class = ClienteSerializer
    pagination_class = CatalogoPagination
    filterset_fields = ["uf", "cidade"]
    search_fields = [
        "nome", "nome_fantasia", "cnpj", "unidade_negocio", "cidade", "uf", "contato_gestor",
    ]


class AreaViewSet(BaseCadastroViewSet):
    campo_cliente = "cliente"
    queryset = Area.objects.ativos().select_related("cliente")
    serializer_class = AreaSerializer
    pagination_class = CatalogoPagination
    filterset_fields = ["cliente"]
    search_fields = ["nome", "codigo"]


class SetorViewSet(BaseCadastroViewSet):
    campo_cliente = "area__cliente"
    queryset = Setor.objects.ativos().select_related("area", "area__cliente")
    serializer_class = SetorSerializer
    pagination_class = CatalogoPagination
    filterset_fields = ["area", "area__cliente"]
    search_fields = ["nome", "codigo"]


class EquipamentoViewSet(BaseCadastroViewSet):
    campo_cliente = "setor__area__cliente"
    queryset = (
        Equipamento.objects.ativos()
        .select_related(
            "setor", "setor__area", "setor__area__cliente",
            "tipo_equipamento", "dados_motor", "dados_transformador",
        )
        .prefetch_related("componentes")
    )
    serializer_class = EquipamentoSerializer
    pagination_class = CatalogoPagination
    filterset_fields = ["setor", "setor__area", "setor__area__cliente", "classe_iso"]
    # Busca por TAG e número de série — como o cliente pediu na reunião.
    search_fields = ["tag", "nome", "fabricante", "modelo", "numero_serie"]


class DadosTecnicosMotorViewSet(BaseCadastroViewSet):
    """Datasheet de Motor Elétrico — acesso estruturado via /equipamentos/{id}/ (nested,
    somente leitura) e aqui para criar/editar (mesmo padrão de balanceamento-planos)."""

    campo_cliente = "equipamento__setor__area__cliente"
    queryset = DadosTecnicosMotor.objects.ativos().select_related("equipamento")
    serializer_class = DadosTecnicosMotorSerializer
    filterset_fields = ["equipamento"]


class DadosTecnicosTransformadorViewSet(BaseCadastroViewSet):
    campo_cliente = "equipamento__setor__area__cliente"
    queryset = DadosTecnicosTransformador.objects.ativos().select_related("equipamento")
    serializer_class = DadosTecnicosTransformadorSerializer
    filterset_fields = ["equipamento"]


class ComponenteViewSet(BaseCadastroViewSet):
    campo_cliente = "equipamento__setor__area__cliente"
    queryset = Componente.objects.ativos().select_related("equipamento")
    serializer_class = ComponenteSerializer
    filterset_fields = ["equipamento"]
    search_fields = ["nome"]


class InstrumentoViewSet(BaseCadastroViewSet):
    # Cadastro de instrumentação (Cadastros → admin cura). Técnicos apenas leem
    # para selecionar o instrumento nas medições (FK de leitura).
    queryset = Instrumento.objects.ativos().prefetch_related("tecnologias")
    serializer_class = InstrumentoSerializer
    permission_classes = [MasterEditaDemaisVisualizam]
    pagination_class = CatalogoPagination
    # Filtro por tecnologia: usado para oferecer só os instrumentos daquela
    # atividade na hora da coleta (ex.: numa análise de vibração, só o coletor).
    filterset_fields = ["tecnologias"]
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


class CondicaoViewSet(CatalogoViewSet):
    queryset = Condicao.objects.ativos()
    serializer_class = CondicaoSerializer
    # Filtro usado no campo: separar condições que exigem análise das que não exigem.
    filterset_fields = ["gera_acao"]


class GrupoAcessoViewSet(CatalogoViewSet):
    queryset = GrupoAcesso.objects.ativos()
    serializer_class = GrupoAcessoSerializer


class RotaViewSet(BaseCadastroViewSet):
    campo_cliente = "cliente"
    queryset = Rota.objects.ativos().select_related("cliente").prefetch_related("equipamentos")
    serializer_class = RotaSerializer
    filterset_fields = ["cliente"]
    search_fields = ["nome", "descricao"]
