from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Convite, Nivel, Perfil, SolicitacaoAcesso
from .security import enviar_email_convite, novo_token, registrar_evento
from .permissions import IsMaster, SouDoCliente
from .serializers import (
    ConvitePendenteSerializer,
    SolicitacaoAcessoListSerializer,
    UserSerializer,
    UserWriteSerializer,
)

User = get_user_model()


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

    @action(detail=True, methods=["get", "put"], url_path="setores")
    def setores(self, request, pk=None):
        """Item 2.1.1.6: setores permitidos de um usuário de cliente (Master interno)."""
        return _gerir_setores_do_usuario(request, self.get_object())

    @action(detail=True, methods=["get", "put"], url_path="dados-pessoais")
    def dados_pessoais(self, request, pk=None):
        """Item 3.1.2 (LGPD): dados pessoais de um usuário, só para o Master interno."""
        return _dados_pessoais_do_usuario(request, self.get_object())

    def create(self, request, *args, **kwargs):
        return Response(
            {"detail": "Novos acessos devem ser criados por convite em /api/auth/convites/."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def perform_update(self, serializer):
        from .auth_views import _revogar_todas

        senha_nova = bool(serializer.validated_data.get("password"))
        desativado = serializer.validated_data.get("is_active") is False
        usuario = serializer.save()
        registrar_evento(
            self.request, "USUARIO_ALTERADO", usuario=self.request.user,
            detalhes={"alvo_id": usuario.pk, "campos": sorted(k for k in serializer.validated_data if k != "password")},
        )
        # Troca de senha ou desativação feita por um Master precisa derrubar as sessões
        # já abertas daquela conta (mesma regra de reset/troca de senha pelo próprio dono).
        if senha_nova or desativado:
            _revogar_todas(usuario)
            registrar_evento(
                self.request, "SESSOES_REVOGADAS_ADMIN", usuario=self.request.user,
                detalhes={"alvo_id": usuario.pk},
            )

    def perform_destroy(self, instance):
        if instance.pk == self.request.user.pk:
            raise PermissionDenied("Você não pode excluir a própria conta.")
        registrar_evento(
            self.request, "USUARIO_EXCLUIDO", usuario=self.request.user, detalhes={"alvo_id": instance.pk},
        )
        super().perform_destroy(instance)


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
        # O formulário é público e o CNPJ é dado público: qualquer pessoa pode pedir
        # acesso "em nome" de uma empresa que JÁ É cliente. Se a empresa já tem
        # usuários, a aprovação NÃO concede Master automaticamente — o convite
        # (com o nível certo) é criado à mão por um Master da plataforma, que
        # confirma com a empresa quem é o solicitante.
        cliente_ja_tem_usuarios = User.objects.filter(cliente=cliente).exists()
        if (
            not User.objects.filter(email=email).exists()
            and not convite_pendente
            and not cliente_ja_tem_usuarios
        ):
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

        extra = {
            "cliente_id": cliente.id,
            "cliente_criado": cliente_criado,
            "convite_enviado": convite_enviado,
        }
        if cliente_ja_tem_usuarios:
            extra["aviso"] = (
                "Esta empresa já possui usuários: nenhum convite automático foi enviado. "
                "Confirme a identidade do solicitante com a empresa e convide-o manualmente."
            )
        return extra

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

    @action(detail=True, methods=["get", "put"], url_path="setores")
    def setores(self, request, pk=None):
        """Item 2.1.1.6: o Master do cliente restringe colegas da PRÓPRIA empresa a setores."""
        return _gerir_setores_do_usuario(request, self.get_object())

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


def _gerir_setores_do_usuario(request, alvo):
    """
    Item 2.1.1.6 — GET lê e PUT substitui os setores permitidos de um usuário de CLIENTE.
    PUT {"setores": [ids]}; lista vazia remove a restrição (volta ao cliente inteiro).
    Quem pode: Master interno, ou Master do MESMO cliente (nunca sobre si mesmo).
    Os setores precisam ser do cliente do alvo (multi-tenant).
    """
    from apps.cadastros.models import Setor
    from .models import RestricaoSetorUsuario

    ator = request.user
    if not alvo.is_cliente:
        return Response({"detail": "Restrição de setor vale só para usuários de cliente."}, status=400)
    if not ator.is_master or (ator.is_cliente and (ator.cliente_id != alvo.cliente_id or ator.pk == alvo.pk)):
        raise PermissionDenied("Apenas o Master interno ou o Master do mesmo cliente (sobre outro usuário) configura setores.")

    if request.method == "GET":
        ids = list(alvo.restricoes_setor.values_list("setor_id", flat=True))
        return Response({"restrito": bool(ids), "setores": ids})

    setores = request.data.get("setores")
    if not isinstance(setores, list) or not all(isinstance(i, int) for i in setores):
        return Response({"detail": "Informe 'setores' como lista de ids inteiros."}, status=400)
    ids = sorted(set(setores))
    if ids:
        validos = Setor.objects.filter(pk__in=ids, area__cliente_id=alvo.cliente_id, ativo=True).count()
        if validos != len(ids):
            return Response({"detail": "Há setor que não existe ou não pertence ao cliente deste usuário."}, status=400)
    anteriores = set(alvo.restricoes_setor.values_list("setor_id", flat=True))
    alvo.restricoes_setor.exclude(setor_id__in=ids).delete()
    for setor_id in set(ids) - anteriores:
        RestricaoSetorUsuario.objects.create(usuario=alvo, setor_id=setor_id, criado_por=ator)
    registrar_evento(
        request, "RESTRICAO_SETOR_ALTERADA", usuario=alvo,
        detalhes={"por": str(ator.pk), "antes": sorted(anteriores), "depois": ids},
    )
    return Response({"restrito": bool(ids), "setores": ids})


def _dados_pessoais_do_usuario(request, alvo):
    """
    Item 3.1.2 (LGPD, Cl. 13). GET/PUT só para o próprio usuário ou para Master interno.
    Nunca entram em listas, exports ou respostas de outros usuários. Valores não vão a log.
    """
    from .models import DadosPessoaisUsuario
    from .serializers import DadosPessoaisSerializer

    ator = request.user
    if ator.pk != alvo.pk and not (ator.is_interno and ator.is_master):
        raise PermissionDenied("Dados pessoais são visíveis só ao próprio usuário e ao Master interno.")
    dados, _ = DadosPessoaisUsuario.objects.get_or_create(usuario=alvo)
    if request.method == "GET":
        return Response(DadosPessoaisSerializer(dados).data)
    serializer = DadosPessoaisSerializer(dados, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    registrar_evento(request, "DADOS_PESSOAIS_ALTERADOS", usuario=alvo,
                     detalhes={"por": str(ator.pk), "campos": sorted(request.data.keys())})
    return Response(DadosPessoaisSerializer(dados).data)


class DadosPessoaisSelfView(APIView):
    """Item 3.1.2: o próprio usuário lê e edita os seus dados pessoais."""

    def get(self, request):
        return _dados_pessoais_do_usuario(request, request.user)

    def put(self, request):
        return _dados_pessoais_do_usuario(request, request.user)


class CertificadoA1View(APIView):
    """
    Item 2.5.1.3 — o responsável técnico (interno) cadastra o próprio certificado A1.
    POST multipart: arquivo (.pfx/.p12) + senha (validada e DESCARTADA, nunca guardada).
    GET: dados do certificado. DELETE: remove o certificado.
    """

    parser_classes = [MultiPartParser, FormParser]

    def _pode(self, request):
        if not request.user.is_interno:
            raise PermissionDenied("Certificado A1 é do responsável técnico (equipe interna).")

    def get(self, request):
        self._pode(request)
        from .models import CertificadoA1
        cert = CertificadoA1.objects.filter(usuario=request.user).first()
        if not cert:
            return Response({"certificado": None})
        return Response(_dados_certificado(cert))

    def post(self, request):
        self._pode(request)
        from .certificados import CertificadoInvalido, cifrar_arquivo, ler_pfx
        from .models import CertificadoA1
        arquivo = request.FILES.get("arquivo")
        senha = request.data.get("senha", "")
        if not arquivo or not senha:
            return Response({"detail": "Envie o arquivo do certificado e a senha."}, status=400)
        try:
            conteudo = arquivo.read()
            dados = ler_pfx(conteudo, senha)
        except CertificadoInvalido as erro:
            registrar_evento(request, "CERTIFICADO_A1_REJEITADO", usuario=request.user, sucesso=False)
            return Response({"detail": str(erro)}, status=400)
        if dados["valido_ate"] <= timezone.now():
            return Response({"detail": "Certificado vencido: não pode assinar laudos."}, status=400)
        cert, _ = CertificadoA1.objects.update_or_create(
            usuario=request.user,
            defaults={
                "arquivo_cifrado": cifrar_arquivo(conteudo),
                "titular": dados["titular"], "emissor": dados["emissor"],
                "numero_serie": dados["numero_serie"], "valido_ate": dados["valido_ate"],
                "sha256_certificado": dados["sha256_certificado"],
            },
        )
        registrar_evento(request, "CERTIFICADO_A1_CADASTRADO", usuario=request.user,
                         detalhes={"serie": cert.numero_serie, "valido_ate": cert.valido_ate.isoformat()})
        return Response(_dados_certificado(cert), status=201)

    def delete(self, request):
        self._pode(request)
        from .models import CertificadoA1
        apagados, _ = CertificadoA1.objects.filter(usuario=request.user).delete()
        if apagados:
            registrar_evento(request, "CERTIFICADO_A1_REMOVIDO", usuario=request.user)
        return Response(status=204)


def _dados_certificado(cert):
    return {
        "titular": cert.titular, "emissor": cert.emissor, "numero_serie": cert.numero_serie,
        "valido_ate": cert.valido_ate, "sha256_certificado": cert.sha256_certificado,
        "vencido": cert.valido_ate <= timezone.now(),
    }
