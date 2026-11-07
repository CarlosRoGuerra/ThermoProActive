from django.apps import AppConfig


class PreditivaConfig(AppConfig):
    """Análise preditiva — complementos do Anexo I 2.4.1.3, 2.4.1.5 e 2.4.2.4."""

    name = "apps.preditiva"
    label = "preditiva"
    verbose_name = "Análise preditiva (complementos)"
    default_auto_field = "django.db.models.BigAutoField"
