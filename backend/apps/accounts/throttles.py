"""
Limites de tentativa dos endpoints de autenticação.

`AnonRateThrottle` do DRF NÃO conta requisições de quem já está autenticado
(`get_cache_key` devolve None). Isso abria dois buracos: (1) quem tem QUALQUER
sessão válida — uma conta de baixo privilégio, por exemplo — martelava o login
de outras contas sem limite; (2) os endpoints de MFA e troca de senha, que só
existem para usuário logado, nunca eram limitados. Por isso aqui a chave é
sempre o IP (endpoints públicos) ou o usuário (endpoints autenticados),
independente do estado de autenticação.
"""
from rest_framework.throttling import SimpleRateThrottle


class _PorIP(SimpleRateThrottle):
    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


class LoginThrottle(_PorIP):
    scope = "auth_login"


class RecoveryThrottle(_PorIP):
    scope = "auth_recovery"


class OtpThrottle(_PorIP):
    scope = "auth_otp"


class RegistrationThrottle(_PorIP):
    scope = "auth_registration"


class SensivelUsuarioThrottle(SimpleRateThrottle):
    """Ações sensíveis de quem está logado (MFA, troca de senha): por usuário."""

    scope = "auth_sensivel"

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            ident = f"u{request.user.pk}"
        else:
            ident = self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}
