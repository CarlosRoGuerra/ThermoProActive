"""Autenticação JWT por cookie HttpOnly (e Bearer só com sessão viva e rastreável)."""
from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.middleware.csrf import CsrfViewMiddleware
from django.utils import timezone
from rest_framework import exceptions
from rest_framework_simplejwt.authentication import JWTAuthentication

from .models import EstadoConta, SessaoAutenticacao


class _CsrfCheck(CsrfViewMiddleware):
    def _reject(self, request, reason):
        return reason


def enforce_csrf(request):
    check = _CsrfCheck(lambda req: None)
    check.process_request(request)
    reason = check.process_view(request, None, (), {})
    if reason:
        raise exceptions.PermissionDenied(f"Falha na verificação CSRF: {reason}")


# S-25: rotas que uma sessão com MFA pendente pode usar (configurar o 2º fator, sair,
# renovar a sessão, ler o próprio usuário). Qualquer outra rota vê a requisição como anônima.
ROTAS_COM_MFA_PENDENTE = frozenset({
    "/api/auth/mfa/setup/",
    "/api/auth/mfa/confirm/",
    "/api/auth/logout/",
    "/api/auth/session/refresh/",
    "/api/auth/csrf/",
    "/api/auth/me/",
})


class CookieJWTAuthentication(JWTAuthentication):
    """
    Todo token — de cookie ou de cabeçalho Authorization — precisa carregar o
    `sid` de uma `SessaoAutenticacao` viva do mesmo usuário e a conta precisa
    estar ATIVA. Assim logout, "encerrar outras sessões", troca/reset de senha
    e suspensão da conta valem para qualquer forma de apresentar o token.
    (Antes o ramo Bearer saía direto no `super()`, sem sid e sem checar sessão:
    um token emitido pelo login legado sobrevivia a tudo isso — achado A-06.)
    """

    @staticmethod
    def _sessao_viva(validated, user):
        """Devolve a `SessaoAutenticacao` viva (ou None)."""
        sid = validated.get("sid")
        if not sid or user.estado != EstadoConta.ACTIVE:
            return None
        try:
            return SessaoAutenticacao.objects.filter(
                pk=sid,
                usuario=user,
                revogada_em__isnull=True,
                expira_em__gt=timezone.now(),
            ).first()
        except (ValueError, DjangoValidationError):  # sid malformado (não é UUID)
            return None

    def authenticate(self, request):
        header = self.get_header(request)
        if header is not None:
            resultado = super().authenticate(request)
            if resultado is None:
                return None
            user, validated = resultado
            sessao = self._sessao_viva(validated, user)
            if not sessao:
                raise exceptions.AuthenticationFailed("Sessão inválida ou encerrada.")
            if sessao.mfa_pendente and request.path not in ROTAS_COM_MFA_PENDENTE:
                return None
            return user, validated

        raw_token = request.COOKIES.get(settings.AUTH_COOKIE_ACCESS)
        if not raw_token:
            return None
        # Cookie presente mas inválido/expirado (sessão antiga, servidor reiniciado
        # com outra SECRET_KEY, token vencido) não é uma tentativa de autenticação
        # a recusar — pro navegador é só um cookie velho que ele manda em toda
        # requisição, mesmo nas públicas. Levantar exceção aqui derrubava com 401
        # até endpoints AllowAny como /auth/csrf/ e o próprio /auth/*/login/,
        # e o front, sem saber o motivo real, mostrava "sem conexão com o servidor".
        # Trata como se não tivesse cookie nenhum: segue anônimo.
        try:
            validated = self.get_validated_token(raw_token)
            user = self.get_user(validated)
        except exceptions.AuthenticationFailed:
            return None
        enforce_csrf(request)
        sessao = self._sessao_viva(validated, user)
        if not sessao:
            return None
        if sessao.mfa_pendente and request.path not in ROTAS_COM_MFA_PENDENTE:
            # S-25: sessão restrita (MFA obrigatório ainda não configurado) = anônima fora
            # das rotas de configuração do 2º fator.
            return None
        return user, validated
