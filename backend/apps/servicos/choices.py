from django.db import models


class TipoServico(models.TextChoices):
    BALANCEAMENTO = "BALANCEAMENTO", "Balanceamento dinâmico em campo"
    ALINHAMENTO = "ALINHAMENTO", "Alinhamento a laser"
