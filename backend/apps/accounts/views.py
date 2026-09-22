from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import Convite, Nivel, Perfil, SolicitacaoAcesso
from .security import enviar_email_convite, novo_token, registrar_evento
from .permissions import IsMaster, SouDoCliente
from .serializers import (
    ConvitePendenteSerializer,
    LoginSerializer,
    SolicitacaoAcessoListSerializer,
    UserSerializer,
    UserWriteSerializer,
)

User = get_user_model()


class LoginView(TokenObtainPairView):
    """POST e-mail+senha → access/refresh + dados do usuário (item 2.1.1.3)."""

    serializer_class = LoginSerializer


class MeView(APIView):
    """Dados do usuário autenticado (para o front montar menu por perfil)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class UserViewSet(viewsets.ModelViewSet):
    """
    CRUD de usuários — somente nível Master (item 2.1.1.4 / 2.1.2.1).
    O cliente definiu que apenas o Master concede acessos, para não perder
    o controle sobre quem entra e o que cada um pode fazer.
    """

    queryset = User.objects.all().order_by("nome")
    permission_classes = [IsMaster]
    filterset_fields = ["perfil", "nivel", "is_active", "empresa", "cliente"]
    search_fields = ["nome", "email", "cpf"]

    def get_serializer_class(self):
        if self.action in ("list", "retrieve"):
            return UserSerializer
        return UserWriteSerializer

    def create(self, request, *args, **kwargs):
        return Response(
            {"detail": "Novos acessos devem ser criados por convite em /api/auth/convites/."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )


class SolicitacaoAcessoViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Fila de pedidos comerciais recebidos em /portal/cadastro — só leitura + as
    duas transições de status (aprovar/recusar). Mesma regra do UserViewSet
    (só Master concede acesso — "o cliente definiu que apenas o Master concede
    acessos, para não perder o controle sobre quem entra").

    Aprovar completa o onboarding: garante o Cliente (por CNPJ — reaproveita se já
    existir, nunca duplica) e convida o solicitante para o Portal, do mesmo jeito
    que um convite manual em Clientes/Usuários faria. Não é uma porta de entrada
    paralela: usa os MESMOS modelos (`Cliente`, `Convite`) e o mesmo e-mail que já
    existiam — só dispara automaticamente em vez de exigir repetir os dados à mão.
    """

    queryset = SolicitacaoAcesso.objects.all().order_by("-criado_em")
    serializer_class = SolicitacaoAcessoListSerializer
    permission_classes = [IsMaster]
    filterset_fields = ["status"]
    search_fields = ["nome", "email", "razao_social", "cnpj"]

    def _transicionar(self, request, alvo):
        solicitacao = self.get_object()
        if solicitacao.status != SolicitacaoAcesso.Status.PENDING:
            return solicitacao, Response(
                {"detail": f"Esta solicitação já foi {solicitacao.get_status_display().lower()}."},
                status=status.HTTP_409_CONFLICT,
            )
        solicitacao.status = alvo
        solicitacao.save(update_fields=["status", "atualizado_em"])
        registrar_evento(
            request,
            "SOLICITACAO_ACESSO_APROVADA" if alvo == SolicitacaoAcesso.Status.APPROVED else "SOLICITACAO_ACESSO_RECUSADA",
            usuario=request.user,
            detalhes={"solicitacao_id": solicitacao.pk, "email": solicitacao.email},
        )
        return solicitacao, None

    def _integrar_cliente(self, request, solicitacao):
        """Cria o Cliente (se ainda não existir esse CNPJ) e convida o solicitante."""
        from apps.cadastros.models import Cliente

        cliente, cliente_criado = Cliente.objects.get_or_create(
            cnpj=solicitacao.cnpj,
            defaults={
                "nome": solicitacao.razao_social,
                "nome_fantasia": solicitacao.nome_fantasia,
                "email": solicitacao.email_empresa or solicitacao.email,
                "telefone": solicitacao.telefone_empresa or solicitacao.telefone,
                "contato_gestor": solicitacao.nome,
            },
        )

        email = solicitacao.email.lower()
        convite_pendente = Convite.objects.filter(
            email=email, aceito_em__isnull=True, revogado_em__isnull=True, expira_em__gt=timezone.now()
        ).exists()
        convite_enviado = False
        if not User.objects.filter(email=email).exists() and not convite_pendente:
            token, token_hash = novo_token()
            # Primeiro usuário do cliente novo entra como Master do lado dele —
            # sem isso ninguém na empresa consegue convidar os próprios colegas
            # depois (só Master convida, regra do PodeConvidar).
            convite = Convite.objects.create(
                email=email, nome=solicitacao.nome, tipo=Convite.Tipo.PORTAL,
                perfil=Perfil.CLIENTE_CORP, nivel=Nivel.MASTER, cliente=cliente,
                token_hash=token_hash, expira_em=timezone.now() + timedelta(hours=72),
                criado_por=request.user,
            )
            enviar_email_convite(convite, token)
            convite_enviado = True

        return {
            "cliente_id": cliente.id,
            "cliente_criado": cliente_criado,
            "convite_enviado": convite_enviado,
        }

    @action(detail=True, methods=["post"])
    def aprovar(self, request, pk=None):
        solicitacao, erro = self._transicionar(request, SolicitacaoAcesso.Status.APPROVED)
        if erro:
            return erro
        extra = self._integrar_cliente(request, solicitacao)
        dados = SolicitacaoAcessoListSerializer(solicitacao).data
        dados.update(extra)
        return Response(dados)

    @action(detail=True, methods=["post"])
    def recusar(self, request, pk=None):
        solicitacao, erro = self._transicionar(request, SolicitacaoAcesso.Status.REJECTED)
        if erro:
            return erro
        return Response(SolicitacaoAcessoListSerializer(solicitacao).data)


class PaginacaoEquipe(PageNumberPagination):
    """
    A equipe de um cliente é uma lista curta e é usada para PREENCHER SELECT
    ("quem executou a corretiva"), não só para exibir. Com a paginação padrão
    (20, sem `page_size_query_param`), um `?page_size=200` era silenciosamente
    ignorado e o 21º colaborador sumia da lista sem nenhum aviso.
    """

    page_size = 100
    page_size_query_param = "page_size"
    max_page_size = 500


class MinhaEquipeViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Portal do Cliente: "quem já tem acesso" da PRÓPRIA empresa — o que faltava
    depois que uma solicitação de acesso é aprovada e o primeiro usuário (Master
    do lado do cliente) entra. Convidar continua sendo o endpoint que já existia
    (`POST /auth/convites/`, com `tipo=portal` e `cliente` = o do usuário logado)
    — esta tela só mostra a lista para não duplicar o formulário de convite.
    """

    serializer_class = UserSerializer
    permission_classes = [SouDoCliente]
    pagination_class = PaginacaoEquipe

    def get_queryset(self):
        # Escopo por cliente: nunca lista colega de outra empresa (multi-tenant).
        return User.objects.filter(cliente_id=self.request.user.cliente_id).order_by("nome")

    @action(detail=False, methods=["get"])
    def convites(self, request):
        """Convites enviados pra esta empresa que ainda não viraram conta."""
        pendentes = Convite.objects.filter(
            cliente_id=request.user.cliente_id,
            tipo=Convite.Tipo.PORTAL,
            aceito_em__isnull=True,
            revogado_em__isnull=True,
        ).order_by("-criado_em")
        return Response(ConvitePendenteSerializer(pendentes, many=True).data)
