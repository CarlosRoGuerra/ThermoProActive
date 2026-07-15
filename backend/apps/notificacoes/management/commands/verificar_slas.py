"""
Verifica OSPs com SLA vencendo/vencido e dispara notificações (Anexo I 2.10.2.4).

Executar periodicamente (ex.: cron diário):
    python manage.py verificar_slas --dias 2
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.notificacoes.models import EventoNotificacao, Nivel
from apps.notificacoes.services import gestores, notificar
from apps.osp.models import STATUS_ABERTOS, OrdemServico


class Command(BaseCommand):
    help = "Notifica responsáveis sobre OSPs com SLA vencendo ou vencido."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dias", type=int, default=2,
            help="Janela (dias) à frente para considerar 'vencendo'.",
        )

    def handle(self, *args, **options):
        limite = timezone.now().date() + timedelta(days=options["dias"])
        osps = OrdemServico.objects.filter(
            status__in=STATUS_ABERTOS, sla_data__isnull=False, sla_data__lte=limite
        ).select_related("equipamento", "cliente", "responsavel")

        total = 0
        for osp in osps:
            vencido = osp.sla_data < timezone.now().date()
            destinatarios = list(gestores())
            if osp.responsavel:
                destinatarios.append(osp.responsavel)
            notificar(
                EventoNotificacao.SLA_VENCENDO,
                destinatarios,
                titulo=f"SLA {'vencido' if vencido else 'vencendo'}: OSP {osp.numero}",
                mensagem=(
                    f"A OSP {osp.numero} ({osp.equipamento.tag}) tem SLA em {osp.sla_data}. "
                    f"Status atual: {osp.get_status_display()}."
                ),
                url="/osps",
                nivel=Nivel.CRITICO if vencido else Nivel.ALERTA,
            )
            total += 1

        self.stdout.write(self.style.SUCCESS(f"OSPs notificadas: {total}"))
