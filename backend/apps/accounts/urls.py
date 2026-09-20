from django.urls import path
from rest_framework.routers import DefaultRouter

from .auth_views import (
    AdminEsqueciSenhaView,
    AdminLoginView,
    AlterarSenhaView,
    ConvitePublicoView,
    ConviteView,
    CsrfView,
    EventosSegurancaView,
    LogoutView,
    MFAConfirmView,
    MFADisableView,
    MFASetupView,
    PortalEsqueciSenhaView,
    PortalLoginView,
    RedefinirSenhaView,
    RefreshCookieView,
    SegurancaResumoView,
    SessoesView,
    SolicitacaoAcessoView,
    TokenStatusView,
    VerificarEmailView,
    ReenviarVerificacaoView,
)
from .views import MinhaEquipeViewSet, SolicitacaoAcessoViewSet, UserViewSet

router = DefaultRouter()
router.register("usuarios", UserViewSet, basename="usuario")
router.register("solicitacoes-acesso", SolicitacaoAcessoViewSet, basename="solicitacao-acesso")
router.register("minha-equipe", MinhaEquipeViewSet, basename="minha-equipe")

urlpatterns = [
    path("auth/csrf/", CsrfView.as_view(), name="auth-csrf"),
    path("auth/portal/login/", PortalLoginView.as_view(), name="portal-login"),
    path("auth/admin/login/", AdminLoginView.as_view(), name="admin-login"),
    path("auth/session/refresh/", RefreshCookieView.as_view(), name="cookie-refresh"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("auth/portal/esqueci-senha/", PortalEsqueciSenhaView.as_view(), name="portal-forgot"),
    path("auth/admin/esqueci-senha/", AdminEsqueciSenhaView.as_view(), name="admin-forgot"),
    path("auth/redefinir-senha/", RedefinirSenhaView.as_view(), name="reset-password"),
    path("auth/token/status/", TokenStatusView.as_view(), name="token-status"),
    path("auth/verificar-email/", VerificarEmailView.as_view(), name="verify-email"),
    path("auth/verificar-email/reenviar/", ReenviarVerificacaoView.as_view(), name="resend-verification"),
    path("auth/solicitacoes-acesso/", SolicitacaoAcessoView.as_view(), name="access-request"),
    path("auth/convites/", ConviteView.as_view(), name="invite-create"),
    path("auth/convites/<str:token>/", ConvitePublicoView.as_view(), name="invite-public"),
    path("auth/seguranca/", SegurancaResumoView.as_view(), name="security-summary"),
    path("auth/seguranca/alterar-senha/", AlterarSenhaView.as_view(), name="change-password"),
    path("auth/seguranca/sessoes/", SessoesView.as_view(), name="sessions"),
    path("auth/seguranca/eventos/", EventosSegurancaView.as_view(), name="security-events"),
    path("auth/mfa/setup/", MFASetupView.as_view(), name="mfa-setup"),
    path("auth/mfa/confirm/", MFAConfirmView.as_view(), name="mfa-confirm"),
    path("auth/mfa/disable/", MFADisableView.as_view(), name="mfa-disable"),
] + router.urls
