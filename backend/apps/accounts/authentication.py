"""Autenticação JWT por cookie HttpOnly, com fallback Bearer para integrações."""
from django.conf import settings
from django.middleware.csrf import CsrfViewMiddleware
from django.utils import timezone
from rest_framework import exceptions
from rest_framework_simplejwt.authentication import JWTAuthentication

from .models import SessaoAutenticacao


class _CsrfCheck(CsrfViewMiddleware):
    def _reject(self, request, reason):
        return reason


def enforce_csrf(request):
    check = _CsrfCheck(lambda req: None)
    check.process_request(request)
    reason = check.process_view(request, None, (), {})
    if reason:
        raise exceptions.PermissionDenied(f"Falha na verificação CSRF: {reason}")


class CookieJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        header = self.get_header(request)
        if header is not None:
            return super().authenticate(request)

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
        sid = validated.get("sid")
        if not sid or not SessaoAutenticacao.objects.filter(
            pk=sid,
            usuario=user,
            revogada_em__isnull=True,
            expira_em__gt=timezone.now(),
        ).exists():
            return None
        return user, validated
