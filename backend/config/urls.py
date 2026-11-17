"""Rotas raiz da API ThermoProActive."""
from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.accounts.permissions import DocumentacaoApi
from apps.accounts.views import MeView
from apps.core.midia import MidiaView


urlpatterns = [
    # --- Autenticação (Anexo I 2.1.1.3 — JWT) ---
    # O login/refresh do SimpleJWT (api/auth/login/ e api/auth/refresh/) foi
    # REMOVIDO de propósito (achado A-06): emitia token sem MFA, sem bloqueio de
    # conta, sem throttle e sem registrar sessão. O login é /api/auth/{portal,admin}/login/
    # e a renovação é /api/auth/session/refresh/ (accounts/urls.py).
    path("api/auth/me/", MeView.as_view(), name="me"),
    # --- Mídia (uploads) autenticada, com escopo por cliente (achado A-03) ---
    path("api/media/<path:nome>", MidiaView.as_view(), name="midia"),
    # --- Módulos ---
    path("api/", include("apps.accounts.urls")),
    path("api/", include("apps.cadastros.urls")),
    path("api/", include("apps.coletas.urls")),
    path("api/", include("apps.ensaios.urls")),
    path("api/", include("apps.servicos.urls")),
    path("api/", include("apps.osp.urls")),
    path("api/", include("apps.laudos.urls")),
    path("api/", include("apps.notificacoes.urls")),
    path("api/", include("apps.relatorios.urls")),
    path("api/", include("apps.preditiva.urls")),
    path("api/", include("apps.ia.urls")),
    path("api/", include("apps.core.urls")),
    # --- Documentação OpenAPI/Swagger ---
    # Em DEBUG (dev) aberta; com DEBUG=False exige login de usuário interno.
    path("api/schema/", SpectacularAPIView.as_view(permission_classes=[DocumentacaoApi]), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema", permission_classes=[DocumentacaoApi]),
        name="docs",
    ),
]

if settings.DJANGO_ADMIN_ENABLED:
    # O painel operacional usa /admin/* no Next.js. O admin técnico do Django
    # fica isolado para não interceptar as rotas de autenticação do produto.
    urlpatterns.insert(0, path("django-admin/", admin.site.urls))

# Sem `static(MEDIA_URL…)` nem em DEBUG: a mídia SEMPRE passa por `MidiaView`.
