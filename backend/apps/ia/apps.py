from django.apps import AppConfig


class IaConfig(AppConfig):
    """Inteligência artificial — chaves de API dos provedores e ativação por recurso."""

    name = "apps.ia"
    label = "ia"
    verbose_name = "Inteligência artificial"
    default_auto_field = "django.db.models.BigAutoField"
