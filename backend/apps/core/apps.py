from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    verbose_name = "Núcleo"

    def ready(self):
        # Item 3.1.22: liga a trilha de auditoria (sinais de criar/alterar/excluir).
        from apps.core.auditoria import conectar
        conectar()
