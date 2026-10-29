"""
Agendador das tarefas periódicas de notificação (serviço `agendador` do compose).

    python manage.py agendador            # roda para sempre
    python manage.py agendador --uma-vez  # um ciclo (cron externo / teste)

A cada `AGENDADOR_INTERVALO_SEGUNDOS`: processa a fila de entregas.
A cada `AGENDADOR_SLA_A_CADA_MINUTOS`: roda a verificação de SLA.

As duas tarefas são idempotentes (lock por entrega; marca por prazo no SLA),
então reiniciar o serviço, rodar duas instâncias ou rodar o comando à mão não
gera aviso duplicado. Falha de um ciclo é registrada e o próximo ciclo segue.
"""
import logging
import time

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import close_old_connections

logger = logging.getLogger("notificacoes")


def um_ciclo(executar_sla: bool) -> dict:
    from apps.notificacoes.entregas import processar_pendentes
    from apps.osp.services import verificar_slas

    saida = {}
    try:
        saida["entregas"] = processar_pendentes()
    except Exception:
        logger.exception("Agendador: falha ao processar entregas")
    if executar_sla:
        try:
            saida["sla"] = verificar_slas(dias=getattr(settings, "SLA_JANELA_VENCENDO_DIAS", 2))
        except Exception:
            logger.exception("Agendador: falha na verificação de SLA")
    return saida


class Command(BaseCommand):
    help = "Executa periodicamente a fila de notificações e o alerta de SLA."

    def add_arguments(self, parser):
        parser.add_argument("--uma-vez", action="store_true")

    def handle(self, *args, **opts):
        if opts["uma_vez"]:
            self.stdout.write(str(um_ciclo(executar_sla=True)))
            return
        intervalo = max(5, int(settings.AGENDADOR_INTERVALO_SEGUNDOS))
        a_cada_sla = max(1, int(settings.AGENDADOR_SLA_A_CADA_MINUTOS)) * 60
        ultimo_sla = 0.0
        self.stdout.write(f"Agendador iniciado: entregas a cada {intervalo}s, SLA a cada {a_cada_sla // 60} min.")
        while True:
            close_old_connections()
            agora = time.monotonic()
            executar_sla = agora - ultimo_sla >= a_cada_sla
            resultado = um_ciclo(executar_sla)
            if executar_sla:
                ultimo_sla = agora
            if resultado.get("entregas") or resultado.get("sla", {}).get("vencido") or resultado.get("sla", {}).get("vencendo"):
                logger.info("Agendador: %s", resultado)
            time.sleep(intervalo)
