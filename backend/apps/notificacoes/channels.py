"""
Adaptadores de canais de notificação — Anexo I 2.10.1.

Princípio (Cláusula 12.4): nenhum fornecedor é obrigatório.

* E-mail: backend de e-mail do Django (SMTP em produção, configurado por .env).
* WhatsApp: gateway HTTP genérico (`WHATSAPP_WEBHOOK_URL`) — qualquer provedor
  (API oficial da Meta via middleware, Evolution, n8n, Twilio...) que receba um
  POST JSON e devolva 2xx ao ACEITAR a mensagem.
* Push: NÃO implementado. Exige registro de dispositivos/assinaturas no front,
  que não existe; o adaptador responde NAO_CONFIGURADO, nunca "enviado".

Regra comum: só há ENVIADO com resposta positiva do provedor. Backend de e-mail
de desenvolvimento (console/locmem/arquivo) gera SIMULADO. Nada aqui grava
segredo, e-mail ou telefone em log ou em `ultimo_erro`.
"""
import json
import logging
import re
import smtplib
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass

from django.conf import settings
from django.core.mail import EmailMessage, get_connection

from .models import StatusEntrega

logger = logging.getLogger("notificacoes")

#: Backends do Django que não entregam nada a ninguém.
BACKENDS_SIMULADOS = ("console", "locmem", "dummy", "filebased")


@dataclass(frozen=True)
class Resultado:
    status: str
    erro: str = ""
    provedor_id: str = ""
    #: Falha transitória (timeout, 5xx, conexão): vale tentar de novo.
    temporario: bool = False


def sanitizar(texto) -> str:
    """Tira segredos configurados e tokens do texto de erro antes de gravar/logar."""
    texto = str(texto or "")
    for nome in ("EMAIL_HOST_PASSWORD", "EMAIL_HOST_USER", "WHATSAPP_WEBHOOK_TOKEN", "WHATSAPP_WEBHOOK_URL"):
        valor = str(getattr(settings, nome, "") or "")
        if len(valor) >= 4:
            texto = texto.replace(valor, "***")
    texto = re.sub(r"(?i)(bearer|token|apikey|api_key|password|senha)([\"':= ]+)\S+", r"\1\2***", texto)
    texto = re.sub(r"[\w.+-]+@[\w-]+\.[\w.]+", "<e-mail>", texto)
    texto = re.sub(r"\+?\d[\d ()-]{8,}\d", "<telefone>", texto)
    return texto[:500]


# --- E-mail ---------------------------------------------------------------------

def email_configurado() -> tuple[bool, list[str]]:
    """(configurado?, variáveis faltando). Nunca devolve valores."""
    backend = getattr(settings, "EMAIL_BACKEND", "")
    if any(f".{nome}." in backend for nome in BACKENDS_SIMULADOS):
        return False, ["EMAIL_BACKEND (está em modo de desenvolvimento)"]
    if backend.endswith("smtp.EmailBackend"):
        faltando = [n for n in ("EMAIL_HOST", "DEFAULT_FROM_EMAIL") if not getattr(settings, n, "")]
        return not faltando, faltando
    return True, []


def enviar_email(user, titulo: str, mensagem: str, *, chave_envio: str = "") -> Resultado:
    if not user.email:
        return Resultado(StatusEntrega.IGNORADO, "Usuário sem e-mail.")
    backend = getattr(settings, "EMAIL_BACKEND", "")
    simulado = any(f".{nome}." in backend for nome in BACKENDS_SIMULADOS)
    try:
        conexao = get_connection(fail_silently=False, timeout=getattr(settings, "EMAIL_TIMEOUT", 10))
        enviados = EmailMessage(
            subject=f"[Pred Ativos] {titulo}", body=mensagem,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None), to=[user.email],
            headers={"X-Notificacao-Id": chave_envio} if chave_envio else None, connection=conexao,
        ).send(fail_silently=False)
    except (smtplib.SMTPRecipientsRefused, smtplib.SMTPSenderRefused, smtplib.SMTPAuthenticationError,
            smtplib.SMTPNotSupportedError) as erro:
        # Recusa do servidor ou credencial errada: repetir não resolve.
        return Resultado(StatusEntrega.FALHOU, f"{type(erro).__name__}: {sanitizar(erro)}")
    except (smtplib.SMTPException, OSError, socket.timeout) as erro:
        return Resultado(StatusEntrega.FALHOU, f"{type(erro).__name__}: {sanitizar(erro)}", temporario=True)
    if enviados != 1:
        return Resultado(StatusEntrega.FALHOU, "O backend de e-mail não confirmou o envio.", temporario=True)
    if simulado:
        return Resultado(StatusEntrega.SIMULADO, "Backend de e-mail de desenvolvimento: nada saiu do servidor.")
    return Resultado(StatusEntrega.ENVIADO)


# --- WhatsApp -------------------------------------------------------------------

def whatsapp_configurado() -> tuple[bool, list[str]]:
    if not getattr(settings, "NOTIFICACOES_WHATSAPP_ENABLED", False):
        return False, ["NOTIFICACOES_WHATSAPP_ENABLED"]
    faltando = [n for n in ("WHATSAPP_WEBHOOK_URL", "WHATSAPP_WEBHOOK_TOKEN") if not getattr(settings, n, "")]
    return not faltando, faltando


def telefone_e164(celular: str) -> str | None:
    """
    Normaliza para E.164 sem '+'. PREMISSA: número sem DDI é brasileiro (55).
    Devolve None se não parecer um celular válido.
    """
    digitos = re.sub(r"\D", "", celular or "")
    if len(digitos) in (10, 11):
        digitos = "55" + digitos
    return digitos if 12 <= len(digitos) <= 15 else None


def enviar_whatsapp(user, titulo: str, mensagem: str, *, chave_envio: str = "") -> Resultado:
    configurado, faltando = whatsapp_configurado()
    if not configurado:
        return Resultado(StatusEntrega.NAO_CONFIGURADO, "Faltando: " + ", ".join(faltando))
    numero = telefone_e164(getattr(user, "celular", ""))
    if not numero:
        return Resultado(StatusEntrega.IGNORADO, "Usuário sem celular válido.")
    corpo = json.dumps({
        "to": numero, "title": titulo, "text": f"*{titulo}*\n{mensagem}", "idempotency_key": chave_envio,
    }).encode("utf-8")
    requisicao = urllib.request.Request(
        settings.WHATSAPP_WEBHOOK_URL, data=corpo, method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.WHATSAPP_WEBHOOK_TOKEN}",
            # O gateway deve descartar repetições com a mesma chave (entrega "pelo menos uma vez").
            "Idempotency-Key": chave_envio,
        },
    )
    try:
        with urllib.request.urlopen(requisicao, timeout=getattr(settings, "WHATSAPP_TIMEOUT", 10)) as resposta:
            bruto = resposta.read(4096)
            codigo = resposta.status
    except urllib.error.HTTPError as erro:
        temporario = erro.code in (408, 425, 429) or erro.code >= 500
        return Resultado(StatusEntrega.FALHOU, f"HTTP {erro.code} do gateway de WhatsApp.", temporario=temporario)
    except (urllib.error.URLError, OSError, socket.timeout) as erro:
        return Resultado(StatusEntrega.FALHOU, f"{type(erro).__name__}: {sanitizar(erro)}", temporario=True)
    if not 200 <= codigo < 300:
        return Resultado(StatusEntrega.FALHOU, f"HTTP {codigo} do gateway de WhatsApp.", temporario=codigo >= 500)
    try:
        dados = json.loads(bruto or b"{}")
    except ValueError:
        dados = {}
    # Gateway que responde 2xx mas diz que recusou não conta como enviado.
    if isinstance(dados, dict) and (dados.get("accepted") is False or dados.get("error")):
        return Resultado(StatusEntrega.FALHOU, sanitizar(dados.get("error") or "Gateway recusou a mensagem."))
    provedor_id = str((dados.get("id") or dados.get("message_id") or "") if isinstance(dados, dict) else "")[:120]
    return Resultado(StatusEntrega.ENVIADO, provedor_id=provedor_id)


# --- Push -----------------------------------------------------------------------

def push_configurado() -> tuple[bool, list[str]]:
    return False, ["implementação de Web Push/FCM (assinaturas de dispositivo, chaves VAPID)"]


def enviar_push(user, titulo: str, mensagem: str, *, chave_envio: str = "") -> Resultado:
    return Resultado(
        StatusEntrega.NAO_CONFIGURADO,
        "Push não implementado: o sistema não registra dispositivos/assinaturas de push.",
    )


#: Nome da função por canal, resolvido na hora do envio (assim um teste pode substituí-la).
ADAPTADORES = {"EMAIL": "enviar_email", "WHATSAPP": "enviar_whatsapp", "PUSH": "enviar_push"}
DIAGNOSTICO = {"EMAIL": email_configurado, "WHATSAPP": whatsapp_configurado, "PUSH": push_configurado}
