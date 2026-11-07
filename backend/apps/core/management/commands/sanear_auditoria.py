from django.core.management.base import BaseCommand

from apps.core.auditoria import sanear_registros
from apps.core.models import RegistroAuditoria


class Command(BaseCommand):
    help = (
        "Aplica as regras de mascaramento (V-03) aos registros de auditoria já gravados. "
        "Idempotente. É a única correção à trilha, feita em modo de saneamento."
    )

    def handle(self, *args, **opcoes):
        alterados = sanear_registros(RegistroAuditoria)
        self.stdout.write(f"{alterados} registro(s) de auditoria saneado(s).")
