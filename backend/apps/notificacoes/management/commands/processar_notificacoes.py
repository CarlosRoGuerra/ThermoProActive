"""
Processa a fila de entregas (e-mail/WhatsApp/push) — retentativas com backoff.

    python manage.py processar_notificacoes                 # uma rodada
    python manage.py processar_notificacoes --reprocessar   # FALHOU/NAO_CONFIGURADO voltam à fila antes
    python manage.py processar_notificacoes --reprocessar --canal EMAIL

Seguro rodar em paralelo e repetidamente: cada entrega é reivindicada com lock
e nada que já foi ACEITO pelo provedor é reenviado.
"""
from django.core.management.base import BaseCommand

from apps.notificacoes.entregas import processar_pendentes, reprocessar


class Command(BaseCommand):
    help = "Envia as entregas pendentes e reenvia as que falharam temporariamente."

    def add_arguments(self, parser):
        parser.add_argument("--limite", type=int, default=200)
        parser.add_argument("--reprocessar", action="store_true",
                            help="Reenfileira entregas FALHOU/NAO_CONFIGURADO (nunca as já enviadas).")
        parser.add_argument("--canal", choices=["EMAIL", "WHATSAPP", "PUSH"])

    def handle(self, *args, **opts):
        if opts["reprocessar"]:
            n = reprocessar(canal=opts.get("canal"))
            self.stdout.write(f"Reenfileiradas: {n}")
        resumo = processar_pendentes(limite=opts["limite"])
        self.stdout.write(self.style.SUCCESS(
            "Entregas processadas: " + (", ".join(f"{k}={v}" for k, v in sorted(resumo.items())) or "nenhuma")
        ))
