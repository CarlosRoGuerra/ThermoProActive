from django.conf import settings
from django.core.management.base import BaseCommand

from apps.core.models import RegistroAuditoria


class Command(BaseCommand):
    help = "Apaga registros de auditoria mais antigos que a retenção (AUDITORIA_RETENCAO_DIAS)."

    def add_arguments(self, parser):
        parser.add_argument("--dias", type=int, default=None, help="Sobrescreve a retenção configurada.")

    def handle(self, *args, **opcoes):
        dias = opcoes["dias"] or settings.AUDITORIA_RETENCAO_DIAS
        if dias < 1:
            self.stderr.write("A retenção precisa ser de pelo menos 1 dia.")
            return
        apagados, _ = RegistroAuditoria.objects.purgar_antigos(dias)
        self.stdout.write(f"{apagados} registro(s) de auditoria anteriores a {dias} dia(s) removido(s).")
