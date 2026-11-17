"""
Configuração Django — ThermoProActive.

Stack: Django 5 + DRF + JWT + PostgreSQL (SQLite como fallback de dev).
Nenhuma configuração amarra a solução a um fornecedor específico (Cláusula 12.4):
o SGBD é escolhido por DATABASE_URL e todas as libs são open-source.
"""
import os
import warnings
from datetime import timedelta
from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured

from .seguranca import problemas_de_configuracao

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
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

# DEBUG: se não vier explícito, só vale True no desenvolvimento local "puro"
# (sem DATABASE_URL, ou seja, SQLite). Container/servidor configurado com banco e
# SEM `DEBUG` no ambiente é tratado como produção (DEBUG=False) — esquecer a
# variável não pode entregar stack trace e settings na tela. Os composes de
# desenvolvimento definem DEBUG=True explicitamente.
DEBUG = env.bool("DEBUG", default="DATABASE_URL" not in os.environ)

# Chave de desenvolvimento: usada SÓ com DEBUG=True. Em produção a chave tem de vir
# do ambiente e passa pela validação abaixo (achado A-07).
_SECRET_KEY_DEV = "dev-insecure-change-me-em-producao"
SECRET_KEY = env("SECRET_KEY", default=_SECRET_KEY_DEV if DEBUG else "")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["*"] if DEBUG else [])

_problemas = problemas_de_configuracao(debug=DEBUG, secret_key=SECRET_KEY, allowed_hosts=ALLOWED_HOSTS)
if _problemas:
    raise ImproperlyConfigured(
        "Configuração insegura para DEBUG=False — o servidor não sobe: "
        + "; ".join(_problemas)
    )

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
    "apps.preditiva",
    "apps.ia",
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
    "apps.core.auditoria.ContextoAuditoriaMiddleware",
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
    # A API navegável (HTML com formulários) só em desenvolvimento; em produção, JSON.
    "DEFAULT_RENDERER_CLASSES": (
        ("rest_framework.renderers.JSONRenderer", "rest_framework.renderers.BrowsableAPIRenderer")
        if DEBUG
        else ("rest_framework.renderers.JSONRenderer",)
    ),
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.PaginacaoPadrao",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_RATES": {
        "auth_login": "10/minute",
        "auth_recovery": "5/hour",
        "auth_otp": "10/minute",
        "auth_registration": "3/hour",
        "auth_sensivel": "10/minute",
    },
    # Quantos proxies reversos (nginx) existem NA FRENTE do Django. O DRF só
    # confia em X-Forwarded-For com isto definido; sem, o cabeçalho inteiro vira
    # a "identidade" do cliente e basta variá-lo para escapar do throttle.
    # 0 = usa só REMOTE_ADDR (dev, sem proxy). Produção atrás do nginx = 1.
    "NUM_PROXIES": env.int("NUM_PROXIES", default=0 if DEBUG else 1),
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
}

# Chave que cifra os segredos TOTP do MFA. Vazia = deriva do SECRET_KEY (compatível com o
# que já está gravado). Defina para desacoplar o MFA da rotação do SECRET_KEY (achado A-07).
MFA_ENCRYPTION_KEY = env("MFA_ENCRYPTION_KEY", default="")

# Chave que cifra as chaves de API de IA (apps.ia). Vazia = deriva do SECRET_KEY. Trocar esta
# chave (ou o SECRET_KEY, quando ela deriva dele) exige cadastrar as chaves de IA de novo.
IA_ENCRYPTION_KEY = env("IA_ENCRYPTION_KEY", default="")

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
# Sem timeout, um SMTP fora do ar prende o worker indefinidamente.
EMAIL_TIMEOUT = env.int("EMAIL_TIMEOUT", default=10)

# WhatsApp: gateway HTTP do provedor escolhido pela CONTRATANTE (POST JSON, 2xx = aceito).
NOTIFICACOES_WHATSAPP_ENABLED = env.bool("NOTIFICACOES_WHATSAPP_ENABLED", default=False)
WHATSAPP_WEBHOOK_URL = env("WHATSAPP_WEBHOOK_URL", default="")
WHATSAPP_WEBHOOK_TOKEN = env("WHATSAPP_WEBHOOK_TOKEN", default="")
WHATSAPP_TIMEOUT = env.int("WHATSAPP_TIMEOUT", default=10)
# Push: não implementado (sem registro de dispositivos). A variável não liga nada.
NOTIFICACOES_PUSH_ENABLED = env.bool("NOTIFICACOES_PUSH_ENABLED", default=False)

# Entrega: tentativa logo após o commit + retentativas pelo `agendador`.
NOTIFICACOES_ENVIO_IMEDIATO = env.bool("NOTIFICACOES_ENVIO_IMEDIATO", default=True)
NOTIFICACOES_MAX_TENTATIVAS = env.int("NOTIFICACOES_MAX_TENTATIVAS", default=5)
# Agendador (comando `agendador`): ciclo das entregas e do alerta de SLA.
AGENDADOR_INTERVALO_SEGUNDOS = env.int("AGENDADOR_INTERVALO_SEGUNDOS", default=60)
AGENDADOR_SLA_A_CADA_MINUTOS = env.int("AGENDADOR_SLA_A_CADA_MINUTOS", default=60)
SLA_JANELA_VENCENDO_DIAS = env.int("SLA_JANELA_VENCENDO_DIAS", default=2)

# --- OSP (Anexo I 2.6) -----------------------------------------------------------
# Quem aprova a execução/finaliza a OSP ainda não foi confirmado pelo cliente
# (docs/03). Padrão: só a gestão da CONTRATADA. true = PCM e gestores do cliente
# também aprovam (apenas a OSP da própria empresa).
OSP_APROVACAO_PELO_CLIENTE = env.bool("OSP_APROVACAO_PELO_CLIENTE", default=False)

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
# A mídia NÃO é pública: `MEDIA_URL` fica sob /api/ (escopo do cookie de sessão) e é
# servida por `apps.core.midia.MidiaView`, que confere dono/cliente de cada arquivo
# (achado A-03). Em produção o binário sai do nginx via X-Accel-Redirect para a
# location `internal` abaixo; em DEBUG o próprio Django entrega o arquivo.
MEDIA_URL = "/api/media/"
MEDIA_ROOT = BASE_DIR / "media"
MEDIA_ACCEL_PREFIX = env("MEDIA_ACCEL_PREFIX", default="" if DEBUG else "/protected-media/")

# Uploads: o padrão do Django (2,5MB) recusa logomarcas/fotos em alta resolução.
# Elevado para permitir subir imagens nítidas (capa/cabeçalho do relatório).
# Obs.: se houver Nginx na frente, ajustar também `client_max_body_size`.
DATA_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024  # 20 MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024  # 20 MB

# Emissão documental: Chromium imprime o frontend existente na rede local.
LAUDOS_FRONTEND_URL = env("LAUDOS_FRONTEND_URL", default="http://127.0.0.1:3000")
LAUDOS_NODE_BIN = env("LAUDOS_NODE_BIN", default="node")
LAUDOS_RENDER_TIMEOUT_SEGUNDOS = env.int("LAUDOS_RENDER_TIMEOUT_SEGUNDOS", default=90)
LAUDOS_MAX_IMAGEM_BYTES = env.int("LAUDOS_MAX_IMAGEM_BYTES", default=10 * 1024 * 1024)
# Anexo de documento (PDF/XLSX/DOCX/CSV, Anexo I 2.3.1.3): teto por arquivo.
ANEXOS_MAX_BYTES = env.int("ANEXOS_MAX_BYTES", default=20 * 1024 * 1024)
LAUDOS_MAX_IMAGENS_BYTES = env.int("LAUDOS_MAX_IMAGENS_BYTES", default=40 * 1024 * 1024)
LAUDOS_MAX_PDF_BYTES = env.int("LAUDOS_MAX_PDF_BYTES", default=50 * 1024 * 1024)
LAUDOS_MAX_PAGINAS = env.int("LAUDOS_MAX_PAGINAS", default=1000)

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
        # Sem includeSubDomains/preload enquanto o domínio da contratante não for
        # definido: outros subdomínios dela sem HTTPS ficariam inacessíveis por 1 ano.
        SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365
    # Cabeçalhos de proteção adicionais.
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
    SECURE_REFERRER_POLICY = "same-origin"

# --- Admin técnico do Django --------------------------------------------------
# /django-admin/ tem login próprio (sem MFA e sem o bloqueio por tentativas do
# produto). S-26: o padrão é LIGADO só em desenvolvimento (DEBUG=True) e DESLIGADO
# em produção. Para usar o admin em produção, defina DJANGO_ADMIN_ENABLED=True
# explicitamente e restrinja por IP/VPN no nginx.
DJANGO_ADMIN_ENABLED = env.bool("DJANGO_ADMIN_ENABLED", default=DEBUG)

# Item 3.1.22: retenção da trilha de auditoria (dias). Apagar só por `manage.py purgar_auditoria`.
AUDITORIA_RETENCAO_DIAS = env.int("AUDITORIA_RETENCAO_DIAS", default=1825)

# Item 2.5.1.3: arquivo PEM com as raízes de confiança (ex.: AC ICP-Brasil) para avaliar a cadeia
# do certificado A1 na verificação. Vazio = a cadeia não é avaliada como confiável.
ASSINATURA_RAIZES_PEM = env.str("ASSINATURA_RAIZES_PEM", default="")

# E-mail "console" em produção grava no log do container os links de
# redefinição de senha e de convite (quem lê o log assume a conta).
if not DEBUG and EMAIL_BACKEND.endswith("console.EmailBackend"):
    warnings.warn(
        "EMAIL_BACKEND=console com DEBUG=False: links de redefinição de senha e convites "
        "serão impressos no log. Configure SMTP (EMAIL_BACKEND/EMAIL_HOST...).",
        RuntimeWarning,
        stacklevel=1,
    )

# --- Logs ---------------------------------------------------------------------
# Tudo em stdout (o Docker coleta/rotaciona). Mensagens de aplicação NUNCA devem
# conter senha, token, código TOTP ou dados pessoais — registre IDs, não valores.
# `django.request` fica em ERROR e o `django.security.*` em WARNING (host inválido,
# CSRF, entrada suspeita); stack trace nunca vai para o cliente (DEBUG=False).
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simples": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"},
    },
    "handlers": {
        "stdout": {"class": "logging.StreamHandler", "stream": "ext://sys.stdout", "formatter": "simples"},
    },
    "root": {"handlers": ["stdout"], "level": env("LOG_LEVEL", default="INFO")},
    "loggers": {
        "django.request": {"handlers": ["stdout"], "level": "ERROR", "propagate": False},
        "django.security": {"handlers": ["stdout"], "level": "WARNING", "propagate": False},
        # SQL e autoreload ruidosos em DEBUG: só se alguém pedir.
        "django.db.backends": {"handlers": ["stdout"], "level": "WARNING", "propagate": False},
    },
}

# Item 2.10.1.3 — Web Push (VAPID). Chaves geradas por `manage.py gerar_vapid_keys`.
# Sem as duas chaves o canal PUSH responde NAO_CONFIGURADO (nunca "enviado").
VAPID_PUBLIC_KEY = env.str("VAPID_PUBLIC_KEY", default="")
VAPID_PRIVATE_KEY = env.str("VAPID_PRIVATE_KEY", default="").replace("\n", "\n")
VAPID_CONTATO = env.str("VAPID_CONTATO", default="mailto:suporte@example.com")
# V-01: serviços de push aceitos como destino (separados por vírgula). Vazio = padrão de
# apps/notificacoes/seguranca_push.py (FCM, Mozilla, Apple, Windows). Só host público; IP literal é recusado.
PUSH_HOSTS_PERMITIDOS = env.str("PUSH_HOSTS_PERMITIDOS", default="")
