"""
Adaptadores de canais de notificação — Anexo I 2.10.1.

Princípio (Cláusula 12.4): nenhum fornecedor é obrigatório. O e-mail usa o backend
padrão do Django (console em dev, SMTP em produção via .env). WhatsApp e Push são
adaptadores plugáveis: por padrão apenas registram em log e ficam DESLIGADOS; podem
ser conectados a qualquer provedor sem alterar a regra de negócio.
"""
import logging

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger("notificacoes")


def enviar_email(user, titulo: str, mensagem: str) -> bool:
    """Envia e-mail via backend configurado. Retorna True se despachado."""
    if not user.email:
        return False
    try:
        send_mail(
            subject=f"[ThermoProActive] {titulo}",
            message=mensagem,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            recipient_list=[user.email],
            fail_silently=True,
        )
        return True
    except Exception:  # nunca quebra o fluxo de negócio por falha de canal
        logger.exception("Falha ao enviar e-mail para %s", user.email)
        return False


def enviar_whatsapp(user, titulo: str, mensagem: str) -> bool:
    """
    Adaptador de WhatsApp. Desligado por padrão (NOTIFICACOES_WHATSAPP_ENABLED=False).
    Conecte aqui o provedor de sua preferência (API oficial, gateway, etc.).
    """
    if not getattr(settings, "NOTIFICACOES_WHATSAPP_ENABLED", False):
        return False
    if not getattr(user, "celular", ""):
        return False
    # Ponto de integração: chamar o provedor escolhido pela CONTRATANTE.
    logger.info("WhatsApp -> %s: %s", user.celular, titulo)
    return True


def enviar_push(user, titulo: str, mensagem: str) -> bool:
    """Adaptador de Push. Desligado por padrão (NOTIFICACOES_PUSH_ENABLED=False)."""
    if not getattr(settings, "NOTIFICACOES_PUSH_ENABLED", False):
        return False
    logger.info("Push -> usuário %s: %s", user.pk, titulo)
    return True
