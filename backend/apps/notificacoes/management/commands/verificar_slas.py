"""
Verifica OSPs com SLA vencendo/vencido e dispara notificações (Anexo I 2.10.2.4).

Executar periodicamente (ex.: cron diário):
    python manage.py verificar_slas --dias 2

Idempotente: cada aviso sai uma única vez por prazo (ver `osp.services.verificar_slas`).
"""
from django.conf import settings
from django.core.management.base import BaseCommand

from apps.osp.services import verificar_slas


class Command(BaseCommand):
    help = "Notifica responsáveis sobre OSPs com SLA vencendo ou vencido (uma vez por prazo)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dias", type=int, default=getattr(settings, "SLA_JANELA_VENCENDO_DIAS", 2),
            help="Janela (dias) à frente para considerar 'vencendo'.",
        )

    def handle(self, *args, **options):
        resumo = verificar_slas(dias=options["dias"])
        self.stdout.write(self.style.SUCCESS(
            f"OSPs notificadas: {resumo['vencendo'] + resumo['vencido']} "
            f"(vencendo: {resumo['vencendo']}, vencido: {resumo['vencido']})"
        ))
