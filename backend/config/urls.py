"""Rotas raiz da API ThermoProActive."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework_simplejwt.views import TokenRefreshView

from apps.accounts.views import LoginView, MeView

urlpatterns = [
    path("admin/", admin.site.urls),
    # --- Autenticação (Anexo I 2.1.1.3 — JWT) ---
    path("api/auth/login/", LoginView.as_view(), name="login"),
    path("api/auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/auth/me/", MeView.as_view(), name="me"),
    # --- Módulos ---
    path("api/", include("apps.accounts.urls")),
    path("api/", include("apps.cadastros.urls")),
    path("api/", include("apps.coletas.urls")),
    path("api/", include("apps.osp.urls")),
    path("api/", include("apps.laudos.urls")),
    path("api/", include("apps.notificacoes.urls")),
    path("api/", include("apps.relatorios.urls")),
    # --- Documentação OpenAPI/Swagger ---
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
