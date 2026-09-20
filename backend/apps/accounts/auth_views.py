import uuid
from datetime import timedelta
from urllib.parse import quote

from django.conf import settings
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.middleware.csrf import get_token
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from .auth_serializers import (
    AceitarConviteSerializer,
    AlterarSenhaSerializer,
    ConfirmarMFASerializer,
    CriarConviteSerializer,
    EsqueciSenhaSerializer,
    LoginContextualSerializer,
    RedefinirSenhaSerializer,
    SolicitacaoAcessoSerializer,
)
from .authentication import enforce_csrf
from .models import (
    Convite,
    DispositivoMFA,
    EstadoConta,
    EventoSeguranca,
    FinalidadeToken,
    Nivel,
    Perfil,
    SessaoAutenticacao,
)
from .security import (
    consumir_codigo_recuperacao,
    criar_token_usuario,
    criptografar_segredo,
    descriptografar_segredo,
    enviar_email_convite,
    enviar_email_redefinicao,
    enviar_email_senha_alterada,
    enviar_email_verificacao,
    gerar_codigos_recuperacao,
    hash_ip,
    metadados_requisicao,
    novo_segredo_totp,
    novo_token,
    registrar_evento,
    validar_totp,
)
from .serializers import UserSerializer
from .throttles import LoginThrottle, OtpThrottle, RecoveryThrottle, RegistrationThrottle

User = get_user_model()


def _cookie_kwargs(max_age):
    return {
        "max_age": int(max_age),
        "httponly": True,
        "secure": settings.AUTH_COOKIE_SECURE,
        "samesite": "Lax",
    }


def _set_auth_cookies(response, access, refresh, *, lembrar=False):
    access_age = int(settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"].total_seconds())
    refresh_age = int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds())
    if not lembrar:
        # Cookie de sessão: o token ainda possui expiração absoluta no servidor.
        response.set_cookie(
            settings.AUTH_COOKIE_ACCESS, str(access), httponly=True,
            secure=settings.AUTH_COOKIE_SECURE, samesite="Lax", path="/api/",
        )
        response.set_cookie(
            settings.AUTH_COOKIE_REFRESH, str(refresh), httponly=True,
            secure=settings.AUTH_COOKIE_SECURE, samesite="Lax", path="/api/auth/",
        )
    else:
        response.set_cookie(
            settings.AUTH_COOKIE_ACCESS, str(access), path="/api/", **_cookie_kwargs(access_age)
        )
        response.set_cookie(
            settings.AUTH_COOKIE_REFRESH, str(refresh), path="/api/auth/", **_cookie_kwargs(refresh_age)
        )


def _clear_auth_cookies(response):
    response.delete_cookie(settings.AUTH_COOKIE_ACCESS, path="/api/", samesite="Lax")
    response.delete_cookie(settings.AUTH_COOKIE_REFRESH, path="/api/auth/", samesite="Lax")


def _emitir_sessao(request, usuario, lembrar=False):
    session_id = uuid.uuid4()
    refresh = RefreshToken.for_user(usuario)
    refresh["sid"] = str(session_id)
    access = refresh.access_token
    access["sid"] = str(session_id)
    agora = timezone.now()
    SessaoAutenticacao.objects.create(
        id=session_id,
        usuario=usuario,
        refresh_jti=str(refresh["jti"]),
        lembrar=lembrar,
        ultimo_uso_em=agora,
        expira_em=agora + settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"],
        **metadados_requisicao(request),
    )
    return access, refresh


def _revogar_sessao(sessao):
    if sessao.revogada_em:
        return
    sessao.revogada_em = timezone.now()
    sessao.save(update_fields=["revogada_em", "atualizado_em"])
    token = OutstandingToken.objects.filter(jti=sessao.refresh_jti).first()
    if token:
        BlacklistedToken.objects.get_or_create(token=token)


def _revogar_todas(usuario, exceto=None):
    qs = usuario.sessoes_auth.filter(revogada_em__isnull=True)
    if exceto:
        qs = qs.exclude(pk=exceto)
    for sessao in qs:
        _revogar_sessao(sessao)


class CsrfView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return Response({"csrfToken": get_token(request)})


class LoginContextualView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [LoginThrottle, OtpThrottle]
    contexto = "portal"

    def post(self, request):
        email = str(request.data.get("email", "")).strip().lower()
        usuario = User.objects.filter(email=email).first()
        if usuario and usuario.bloqueado_ate and usuario.bloqueado_ate > timezone.now():
            registrar_evento(request, "CONTA_BLOQUEADA", usuario=usuario, sucesso=False)
            return Response(
                {"detail": "Acesso temporariamente indisponível. Tente novamente mais tarde."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        serializer = LoginContextualSerializer(data=request.data, context={"request": request})
        if not serializer.is_valid():
            if usuario:
                usuario.tentativas_login += 1
                if usuario.tentativas_login >= 8:
                    usuario.bloqueado_ate = timezone.now() + timedelta(minutes=15)
                usuario.save(update_fields=["tentativas_login", "bloqueado_ate", "atualizado_em"])
            registrar_evento(request, "LOGIN_FALHOU", usuario=usuario, sucesso=False, detalhes={"area": self.contexto})
            return Response({"detail": "E-mail ou senha incorretos."}, status=status.HTTP_401_UNAUTHORIZED)

        usuario = serializer.validated_data["usuario"]
        if usuario.bloqueado_ate and usuario.bloqueado_ate > timezone.now():
            registrar_evento(request, "CONTA_BLOQUEADA", usuario=usuario, sucesso=False)
            return Response({"detail": "Acesso temporariamente indisponível. Tente novamente mais tarde."}, status=429)

        area_correta = usuario.is_cliente if self.contexto == "portal" else usuario.is_interno
        if not area_correta:
            registrar_evento(request, "LOGIN_AREA_INCORRETA", usuario=usuario, sucesso=False, detalhes={"area": self.contexto})
            return Response({"detail": "E-mail ou senha incorretos."}, status=status.HTTP_401_UNAUTHORIZED)

        dispositivo = getattr(usuario, "mfa", None)
        if dispositivo and dispositivo.ativo:
            codigo = serializer.validated_data.get("codigo_mfa", "")
            passo = validar_totp(
                descriptografar_segredo(dispositivo.segredo_criptografado),
                codigo,
                ultimo_passo=dispositivo.ultimo_passo_usado,
            )
            recuperacao = passo is None and consumir_codigo_recuperacao(dispositivo, codigo)
            if passo is None and not recuperacao:
                return Response(
                    {"mfa_required": True, "detail": "Informe o código de autenticação."},
                    status=status.HTTP_428_PRECONDITION_REQUIRED,
                )
            if passo is not None:
                dispositivo.ultimo_passo_usado = passo
                dispositivo.save(update_fields=["ultimo_passo_usado", "atualizado_em"])

        usuario.tentativas_login = 0
        usuario.bloqueado_ate = None
        usuario.last_login = timezone.now()
        usuario.save(update_fields=["tentativas_login", "bloqueado_ate", "last_login", "atualizado_em"])
        lembrar = serializer.validated_data["lembrar"] and self.contexto == "portal"
        access, refresh = _emitir_sessao(request, usuario, lembrar)
        resposta = Response({"user": UserSerializer(usuario).data})
        _set_auth_cookies(resposta, access, refresh, lembrar=lembrar)
        get_token(request)
        registrar_evento(request, "LOGIN_REALIZADO", usuario=usuario, detalhes={"area": self.contexto})
        return resposta


class PortalLoginView(LoginContextualView):
    contexto = "portal"


class AdminLoginView(LoginContextualView):
    contexto = "admin"


class RefreshCookieView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        enforce_csrf(request)
        bruto = request.COOKIES.get(settings.AUTH_COOKIE_REFRESH)
        if not bruto:
            return Response({"detail": "Sessão expirada."}, status=401)
        try:
            anterior = RefreshToken(bruto)
            session_id = anterior.get("sid")
            sessao = SessaoAutenticacao.objects.select_related("usuario").get(pk=session_id)
            if not sessao.ativa:
                raise TokenError("Sessão revogada")
            anterior.blacklist()
            novo = RefreshToken.for_user(sessao.usuario)
            novo["sid"] = str(sessao.id)
            access = novo.access_token
            access["sid"] = str(sessao.id)
            sessao.refresh_jti = str(novo["jti"])
            sessao.ultimo_uso_em = timezone.now()
            sessao.expira_em = timezone.now() + settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"]
            sessao.save(update_fields=["refresh_jti", "ultimo_uso_em", "expira_em", "atualizado_em"])
        except (TokenError, SessaoAutenticacao.DoesNotExist, ValueError):
            resposta = Response({"detail": "Sessão expirada."}, status=401)
            _clear_auth_cookies(resposta)
            return resposta
        resposta = Response(status=204)
        _set_auth_cookies(resposta, access, novo, lembrar=sessao.lembrar)
        return resposta


class LogoutView(APIView):
    def post(self, request):
        sid = request.auth.get("sid") if request.auth else None
        sessao = SessaoAutenticacao.objects.filter(pk=sid, usuario=request.user).first()
        if sessao:
            _revogar_sessao(sessao)
        registrar_evento(request, "LOGOUT", usuario=request.user)
        resposta = Response(status=204)
        _clear_auth_cookies(resposta)
        return resposta


class EsqueciSenhaView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [RecoveryThrottle]
    contexto = "portal"
    mensagem = "Se existir uma conta associada a esse e-mail, enviaremos as instruções para recuperação."

    def post(self, request):
        serializer = EsqueciSenhaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        usuario = User.objects.filter(
            email=serializer.validated_data["email"].lower(), is_active=True, estado=EstadoConta.ACTIVE
        ).first()
        area_correta = usuario and (usuario.is_cliente if self.contexto == "portal" else usuario.is_interno)
        if area_correta:
            token, _ = criar_token_usuario(
                usuario, FinalidadeToken.RESET_PASSWORD, self.contexto, minutos=30
            )
            enviar_email_redefinicao(usuario, token, self.contexto)
            registrar_evento(request, "RECUPERACAO_SOLICITADA", usuario=usuario, detalhes={"area": self.contexto})
        else:
            registrar_evento(request, "RECUPERACAO_SOLICITADA", sucesso=True, detalhes={"area": self.contexto})
        return Response({"detail": self.mensagem})


class PortalEsqueciSenhaView(EsqueciSenhaView):
    contexto = "portal"


class AdminEsqueciSenhaView(EsqueciSenhaView):
    contexto = "admin"


class RedefinirSenhaView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [RecoveryThrottle]

    @transaction.atomic
    def post(self, request):
        serializer = RedefinirSenhaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        registro = serializer.validated_data["registro"]
        usuario = registro.usuario
        usuario.set_password(serializer.validated_data["nova_senha"])
        usuario.senha_alterada_em = timezone.now()
        usuario.exigir_troca_senha = False
        usuario.save(update_fields=["password", "senha_alterada_em", "exigir_troca_senha", "atualizado_em"])
        registro.usado_em = timezone.now()
        registro.save(update_fields=["usado_em", "atualizado_em"])
        _revogar_todas(usuario)
        registrar_evento(request, "SENHA_REDEFINIDA", usuario=usuario, detalhes={"area": registro.contexto})
        transaction.on_commit(lambda: enviar_email_senha_alterada(usuario))
        return Response({"detail": "Senha alterada com sucesso.", "contexto": registro.contexto})


class TokenStatusView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        from .security import localizar_token
        registro = localizar_token(str(request.data.get("token", "")), FinalidadeToken.RESET_PASSWORD)
        valido = bool(registro and not registro.usado_em and registro.expira_em > timezone.now())
        return Response({"valid": valido, "contexto": registro.contexto if valido else None})


class VerificarEmailView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [OtpThrottle]

    def post(self, request):
        from .security import localizar_token
        registro = localizar_token(str(request.data.get("token", "")), FinalidadeToken.VERIFY_EMAIL)
        if not registro or registro.usado_em or registro.expira_em <= timezone.now():
            return Response({"detail": "Este link não é mais válido."}, status=410)
        registro.usado_em = timezone.now()
        registro.usuario.email_verificado_em = timezone.now()
        if registro.usuario.estado == EstadoConta.PENDING_EMAIL_VERIFICATION:
            registro.usuario.estado = EstadoConta.ACTIVE
        registro.save(update_fields=["usado_em", "atualizado_em"])
        registro.usuario.save(update_fields=["email_verificado_em", "estado", "atualizado_em"])
        registrar_evento(request, "EMAIL_CONFIRMADO", usuario=registro.usuario)
        return Response({"detail": "E-mail confirmado com sucesso."})


class ReenviarVerificacaoView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [RecoveryThrottle]

    def post(self, request):
        usuario = User.objects.filter(
            email=str(request.data.get("email", "")).lower(),
            estado=EstadoConta.PENDING_EMAIL_VERIFICATION,
        ).first()
        if usuario:
            contexto = "portal" if usuario.is_cliente else "admin"
            token, _ = criar_token_usuario(usuario, FinalidadeToken.VERIFY_EMAIL, contexto, minutos=30)
            enviar_email_verificacao(usuario, token, contexto)
        return Response({"detail": "Se houver uma confirmação pendente, enviaremos um novo link."})


class SolicitacaoAcessoView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [RegistrationThrottle]

    def post(self, request):
        serializer = SolicitacaoAcessoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        meta = metadados_requisicao(request)
        pedido = serializer.save(ip_hash=meta["ip_hash"])
        registrar_evento(request, "SOLICITACAO_ACESSO_CRIADA", detalhes={"solicitacao_id": pedido.pk})
        return Response(
            {"detail": "Recebemos sua solicitação. Nossa equipe entrará em contato após a análise."},
            status=201,
        )


class PodeConvidar(permissions.BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_master)


class ConviteView(APIView):
    permission_classes = [PodeConvidar]

    def post(self, request):
        serializer = CriarConviteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dados = serializer.validated_data
        if request.user.is_cliente:
            if dados["tipo"] != Convite.Tipo.PORTAL or dados.get("cliente") != request.user.cliente:
                return Response({"detail": "Você só pode convidar pessoas da sua organização."}, status=403)
            if dados["nivel"] == Nivel.MASTER:
                return Response({"detail": "Solicite à ThermoProActive a concessão do nível Master."}, status=403)
        token, token_hash = novo_token()
        convite = serializer.save(
            token_hash=token_hash,
            expira_em=timezone.now() + timedelta(hours=72),
            criado_por=request.user,
        )
        enviar_email_convite(convite, token)
        registrar_evento(request, "CONVITE_CRIADO", usuario=request.user, detalhes={"tipo": convite.tipo})
        return Response({"detail": "Convite enviado.", "id": convite.pk}, status=201)


class ConvitePublicoView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [RecoveryThrottle]

    def get(self, request, token):
        from .security import hash_opaco
        convite = Convite.objects.filter(token_hash=hash_opaco(token)).first()
        valido = bool(convite and not convite.aceito_em and not convite.revogado_em and convite.expira_em > timezone.now())
        if not valido:
            return Response({"valid": False, "detail": "Este convite não é mais válido."}, status=410)
        return Response({"valid": True, "nome": convite.nome, "email": convite.email, "tipo": convite.tipo})

    @transaction.atomic
    def post(self, request, token):
        dados = dict(request.data)
        dados["token"] = token
        serializer = AceitarConviteSerializer(data=dados)
        serializer.is_valid(raise_exception=True)
        convite = serializer.validated_data["convite"]
        usuario = User.objects.create_user(
            email=convite.email,
            password=serializer.validated_data["senha"],
            nome=convite.nome,
            perfil=convite.perfil,
            nivel=convite.nivel,
            empresa=convite.empresa,
            cliente=convite.cliente,
            estado=EstadoConta.ACTIVE,
            email_verificado_em=timezone.now(),
            termos_aceitos_em=timezone.now(),
            senha_alterada_em=timezone.now(),
            mfa_obrigatorio=convite.tipo == Convite.Tipo.ADMIN and convite.perfil == Perfil.ADMIN,
        )
        convite.aceito_em = timezone.now()
        convite.save(update_fields=["aceito_em", "atualizado_em"])
        registrar_evento(request, "CONVITE_ACEITO", usuario=usuario, detalhes={"tipo": convite.tipo})
        return Response({"detail": "Acesso criado com sucesso.", "contexto": convite.tipo}, status=201)


class AlterarSenhaView(APIView):
    def post(self, request):
        serializer = AlterarSenhaSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["nova_senha"])
        request.user.senha_alterada_em = timezone.now()
        request.user.save(update_fields=["password", "senha_alterada_em", "atualizado_em"])
        sid = request.auth.get("sid") if request.auth else None
        _revogar_todas(request.user, exceto=sid)
        registrar_evento(request, "SENHA_ALTERADA", usuario=request.user)
        enviar_email_senha_alterada(request.user)
        return Response({"detail": "Senha atualizada. As outras sessões foram encerradas."})


class SessoesView(APIView):
    def get(self, request):
        atual = request.auth.get("sid") if request.auth else None
        dados = [
            {
                "id": str(item.id),
                "atual": str(item.id) == str(atual),
                "dispositivo": item.user_agent or "Dispositivo não identificado",
                "ultimo_uso_em": item.ultimo_uso_em,
                "criado_em": item.criado_em,
            }
            for item in request.user.sessoes_auth.filter(
                revogada_em__isnull=True, expira_em__gt=timezone.now()
            )
        ]
        return Response(dados)

    def delete(self, request):
        atual = request.auth.get("sid") if request.auth else None
        _revogar_todas(request.user, exceto=atual)
        registrar_evento(request, "OUTRAS_SESSOES_ENCERRADAS", usuario=request.user)
        return Response(status=204)


class EventosSegurancaView(APIView):
    def get(self, request):
        eventos = request.user.eventos_seguranca.all()[:20]
        return Response([
            {"evento": e.evento, "sucesso": e.sucesso, "criado_em": e.criado_em}
            for e in eventos
        ])


class MFASetupView(APIView):
    throttle_classes = [OtpThrottle]

    def post(self, request):
        segredo = novo_segredo_totp()
        dispositivo, _ = DispositivoMFA.objects.update_or_create(
            usuario=request.user,
            defaults={"segredo_criptografado": criptografar_segredo(segredo), "confirmado_em": None},
        )
        emissor = quote("Pred Ativos")
        conta = quote(request.user.email)
        uri = f"otpauth://totp/{emissor}:{conta}?secret={segredo}&issuer={emissor}&digits=6&period=30"
        return Response({"secret": segredo, "otpauth_uri": uri})


class MFAConfirmView(APIView):
    throttle_classes = [OtpThrottle]

    def post(self, request):
        serializer = ConfirmarMFASerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dispositivo = getattr(request.user, "mfa", None)
        if not dispositivo:
            return Response({"detail": "Inicie a configuração do MFA."}, status=400)
        passo = validar_totp(
            descriptografar_segredo(dispositivo.segredo_criptografado),
            serializer.validated_data["codigo"],
        )
        if passo is None:
            return Response({"detail": "Código inválido ou expirado."}, status=400)
        dispositivo.confirmado_em = timezone.now()
        dispositivo.ultimo_passo_usado = passo
        dispositivo.save(update_fields=["confirmado_em", "ultimo_passo_usado", "atualizado_em"])
        codigos = gerar_codigos_recuperacao(dispositivo)
        registrar_evento(request, "MFA_ATIVADO", usuario=request.user)
        return Response({"detail": "Autenticação em dois fatores ativada.", "recovery_codes": codigos})


class MFADisableView(APIView):
    throttle_classes = [OtpThrottle]

    def post(self, request):
        serializer = ConfirmarMFASerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not serializer.validated_data.get("senha") or not request.user.check_password(serializer.validated_data["senha"]):
            return Response({"detail": "Confirme sua senha atual."}, status=400)
        dispositivo = getattr(request.user, "mfa", None)
        if not dispositivo or not dispositivo.ativo:
            return Response({"detail": "MFA não está ativo."}, status=400)
        passo = validar_totp(
            descriptografar_segredo(dispositivo.segredo_criptografado),
            serializer.validated_data["codigo"],
        )
        if passo is None:
            return Response({"detail": "Código inválido ou expirado."}, status=400)
        dispositivo.delete()
        registrar_evento(request, "MFA_DESATIVADO", usuario=request.user)
        return Response({"detail": "Autenticação em dois fatores desativada."})


class SegurancaResumoView(APIView):
    def get(self, request):
        dispositivo = getattr(request.user, "mfa", None)
        return Response({
            "mfa_ativo": bool(dispositivo and dispositivo.ativo),
            "mfa_obrigatorio": request.user.mfa_obrigatorio,
            "email_verificado": bool(request.user.email_verificado_em),
            "senha_alterada_em": request.user.senha_alterada_em,
            "sessoes_ativas": request.user.sessoes_auth.filter(
                revogada_em__isnull=True, expira_em__gt=timezone.now()
            ).count(),
        })
