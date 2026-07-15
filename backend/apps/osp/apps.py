from django.apps import AppConfig


class OspConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.osp"
    verbose_name = "Ordens de Serviço Preditivas"

    def ready(self):
        # Conecta os signals que geram OSP automaticamente a partir de medições críticas.
        from . import signals  # noqa: F401
