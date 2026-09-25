"""
Configuração Django — ThermoProActive.

Stack: Django 5 + DRF + JWT + PostgreSQL (SQLite como fallback de dev).
Nenhuma configuração amarra a solução a um fornecedor específico (Cláusula 12.4):
o SGBD é escolhido por DATABASE_URL e todas as libs são open-source.
"""
from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, True),
    SECRET_KEY=(str, "dev-insecure-change-me-em-producao"),
    ALLOWED_HOSTS=(list, ["*"]),
    CORS_ALLOWED_ORIGINS=(list, ["http://localhost:3000", "http://127.0.0.1:3000"]),
    # Origens confiáveis para CSRF (necessário para o /admin sob HTTPS atrás de proxy,
    # e para qualquer POST/PATCH/DELETE autenticado por cookie — o login grava
    # tpa_access/tpa_refresh em cookie). Em produção, defina via env explicitamente
    # (ex.: https://seudominio.com.br); o padrão abaixo cobre só o dev local, para
    # não travar o front em :3000 com "Origin checking failed" a cada ambiente novo.
    CSRF_TRUSTED_ORIGINS=(list, ["http://localhost:3000", "http://127.0.0.1:3000"]),
)

# Lê backend/.env se existir (não obrigatório para dev com SQLite).
env_file = BASE_DIR / ".env"
if env_file.exists():
    environ.Env.read_env(str(env_file))

SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")

# --- Aplicações ---------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]
THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
    "drf_spectacular",
]
LOCAL_APPS = [
    "apps.core",
    "apps.accounts",
    "apps.cadastros",
    "apps.coletas",
    "apps.ensaios",
    "apps.servicos",
    "apps.osp",
    "apps.laudos",
    "apps.notificacoes",
    "apps.relatorios",
]
INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# --- Banco de dados -----------------------------------------------------------
# Em produção: DATABASE_URL=postgres://user:pass@host:5432/db
# Em dev (sem .env): SQLite, para rodar sem instalar PostgreSQL.
DATABASES = {
    "default": env.db_url(
        "DATABASE_URL",
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
    )
}

# --- Autenticação -------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- DRF + JWT ----------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "apps.accounts.authentication.CookieJWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_RATES": {
        "auth_login": "10/minute",
        "auth_recovery": "5/hour",
        "auth_otp": "10/minute",
        "auth_registration": "3/hour",
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
}

AUTH_COOKIE_ACCESS = "tpa_access"
AUTH_COOKIE_REFRESH = "tpa_refresh"
# Cookies com a flag `Secure` só são guardados pelo navegador sob HTTPS. Num
# deploy em HTTP puro (VPS acessada por IP, onde o Let's Encrypt não emite
# certificado) isso faz o login responder 200 e a sessão morrer no request
# seguinte — parece "sessão expirada", mas o cookie nunca chegou a ser gravado.
# Esta chave permite baixar a exigência conscientemente nesse cenário; o padrão
# continua seguro, então nada afrouxa sozinho.
COOKIES_SECURE = env.bool("COOKIES_SECURE", default=not DEBUG)
AUTH_COOKIE_SECURE = COOKIES_SECURE
FRONTEND_URL = env("FRONTEND_URL", default="http://localhost:3000")
CORS_ALLOW_CREDENTIALS = True

SPECTACULAR_SETTINGS = {
    "TITLE": "Pred Ativos API",
    "DESCRIPTION": "API de gestão de manutenção preditiva (Anexo I do contrato).",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# --- CORS ---------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = env("CORS_ALLOWED_ORIGINS")

# --- Notificações (Anexo I 2.10) ----------------------------------------------
# E-mail: backend de console em dev (imprime no stdout/log); SMTP em produção via .env.
# WhatsApp/Push: adaptadores opcionais, desligados por padrão (sem lock-in — Cláusula 12.4).
EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
DEFAULT_FROM_EMAIL = env(
    "DEFAULT_FROM_EMAIL", default="Pred Ativos <nao-responda@thermoproactive.local>"
)
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)

NOTIFICACOES_WHATSAPP_ENABLED = env.bool("NOTIFICACOES_WHATSAPP_ENABLED", default=False)
NOTIFICACOES_PUSH_ENABLED = env.bool("NOTIFICACOES_PUSH_ENABLED", default=False)

# --- Internacionalização ------------------------------------------------------
LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

# --- Arquivos estáticos e mídia ----------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# Uploads: o padrão do Django (2,5MB) recusa logomarcas/fotos em alta resolução.
# Elevado para permitir subir imagens nítidas (capa/cabeçalho do relatório).
# Obs.: se houver Nginx na frente, ajustar também `client_max_body_size`.
DATA_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024  # 20 MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024  # 20 MB

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Segurança em produção ----------------------------------------------------
# Aplicado apenas quando DEBUG=False (produção). Em dev nada muda.
# A terminação TLS é feita pelo Nginx; o header abaixo informa ao Django que a
# requisição original chegou via HTTPS (evita loops de redirect e cookies inseguros).
CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS")
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

if not DEBUG:
    # Cookies só trafegam sob HTTPS (ver COOKIES_SECURE acima).
    SESSION_COOKIE_SECURE = COOKIES_SECURE
    CSRF_COOKIE_SECURE = COOKIES_SECURE
    if COOKIES_SECURE:
        # HSTS: navegador passa a exigir HTTPS neste domínio (1 ano). Ative após
        # confirmar que o certificado está funcionando para não se trancar fora.
        # Sem TLS o cabeçalho seria ignorado de qualquer forma — e mandá-lo num
        # deploy HTTP só atrapalha uma futura migração para HTTPS.
        SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365
        SECURE_HSTS_INCLUDE_SUBDOMAINS = True
        SECURE_HSTS_PRELOAD = True
    # Cabeçalhos de proteção adicionais.
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
    SECURE_REFERRER_POLICY = "same-origin"
