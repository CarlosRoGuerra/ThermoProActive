"""
Diagnóstico dos canais de notificação — mostra o que está configurado SEM exibir valores.

    python manage.py verificar_canais
    python manage.py verificar_canais --enviar-email-teste destino@empresa.com

O teste de e-mail é uma entrega REAL pelo SMTP configurado (não é simulação):
use um endereço da própria equipe. Não há teste equivalente para WhatsApp/push
aqui — o de WhatsApp depende do gateway do provedor (ver docs/17).
"""
from django.conf import settings
from django.core.mail import EmailMessage, get_connection
from django.core.management.base import BaseCommand, CommandError

from apps.notificacoes import channels
from apps.notificacoes.models import EntregaNotificacao


def _definida(nome):
    return "definida" if getattr(settings, nome, "") else "VAZIA"


class Command(BaseCommand):
    help = "Mostra o estado de configuração de cada canal (sem revelar credenciais)."

    def add_arguments(self, parser):
        parser.add_argument("--enviar-email-teste", metavar="DESTINO")

    def handle(self, *args, **opts):
        for canal, diagnostico in channels.DIAGNOSTICO.items():
            ok, faltando = diagnostico()
            linha = f"{canal:9} {'OPERACIONAL' if ok else 'NÃO CONFIGURADO'}"
            if faltando:
                linha += f" — falta: {', '.join(faltando)}"
            self.stdout.write(linha)
        self.stdout.write("INTERNO   OPERACIONAL — alerta gravado no sistema, sem provedor externo")
        backend = getattr(settings, "EMAIL_BACKEND", "").rsplit(".", 2)[-2]
        self.stdout.write(
            f"\nE-mail: backend={backend}, EMAIL_HOST {_definida('EMAIL_HOST')}, "
            f"EMAIL_HOST_USER {_definida('EMAIL_HOST_USER')}, EMAIL_HOST_PASSWORD {_definida('EMAIL_HOST_PASSWORD')}, "
            f"TLS={getattr(settings, 'EMAIL_USE_TLS', False)}, timeout={getattr(settings, 'EMAIL_TIMEOUT', None)}s"
        )
        self.stdout.write(
            f"WhatsApp: WHATSAPP_WEBHOOK_URL {_definida('WHATSAPP_WEBHOOK_URL')}, "
            f"WHATSAPP_WEBHOOK_TOKEN {_definida('WHATSAPP_WEBHOOK_TOKEN')}"
        )
        pendentes = EntregaNotificacao.objects.filter(status="PENDENTE").count()
        falhas = EntregaNotificacao.objects.filter(status="FALHOU").count()
        self.stdout.write(f"\nFila: {pendentes} pendente(s), {falhas} com falha definitiva.")

        destino = opts.get("enviar_email_teste")
        if destino:
            ok, faltando = channels.email_configurado()
            if not ok:
                raise CommandError("E-mail não configurado: " + ", ".join(faltando))
            try:
                EmailMessage(
                    subject="[Pred Ativos] Teste de configuração de e-mail",
                    body="Mensagem de teste do comando verificar_canais. Pode ignorar.",
                    from_email=settings.DEFAULT_FROM_EMAIL, to=[destino],
                    connection=get_connection(fail_silently=False, timeout=settings.EMAIL_TIMEOUT),
                ).send(fail_silently=False)
            except Exception as erro:
                raise CommandError(f"Falhou: {type(erro).__name__}: {channels.sanitizar(erro)}")
            self.stdout.write(self.style.SUCCESS("Servidor SMTP aceitou a mensagem de teste."))
