"""Primitivos de segurança da autenticação.

Segredos e tokens completos nunca são escritos em logs ou persistidos em texto puro.
"""
import base64
import hashlib
import hmac
import secrets
import struct
import time
from datetime import timedelta

from cryptography.fernet import Fernet
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.mail import send_mail
from django.urls import reverse
from django.utils import timezone

from .models import CodigoRecuperacaoMFA, EventoSeguranca, TokenUsoUnico


def hash_opaco(valor: str) -> str:
    return hashlib.sha256(valor.encode("utf-8")).hexdigest()


def hash_ip(ip: str) -> str:
    if not ip:
        return ""
    chave = settings.SECRET_KEY.encode("utf-8")
    return hmac.new(chave, ip.encode("utf-8"), hashlib.sha256).hexdigest()


def metadados_requisicao(request) -> dict:
    encaminhado = request.META.get("HTTP_X_FORWARDED_FOR", "")
    ip = encaminhado.split(",")[0].strip() if encaminhado else request.META.get("REMOTE_ADDR", "")
    return {
        "ip_hash": hash_ip(ip),
        "user_agent": request.META.get("HTTP_USER_AGENT", "")[:300],
    }


def registrar_evento(request, evento: str, *, usuario=None, sucesso=True, detalhes=None):
    meta = metadados_requisicao(request)
    return EventoSeguranca.objects.create(
        usuario=usuario,
        evento=evento,
        sucesso=sucesso,
        detalhes=detalhes or {},
        **meta,
    )


def novo_token() -> tuple[str, str]:
    token = secrets.token_urlsafe(48)
    return token, hash_opaco(token)


def criar_token_usuario(usuario, finalidade, contexto, *, minutos=30, email=""):
    TokenUsoUnico.objects.filter(
        usuario=usuario, finalidade=finalidade, usado_em__isnull=True
    ).update(usado_em=timezone.now())
    token, token_hash = novo_token()
    registro = TokenUsoUnico.objects.create(
        usuario=usuario,
        finalidade=finalidade,
        contexto=contexto,
        token_hash=token_hash,
        email=email or usuario.email,
        expira_em=timezone.now() + timedelta(minutes=minutos),
    )
    return token, registro


def localizar_token(token: str, finalidade: str):
    if not token:
        return None
    return TokenUsoUnico.objects.select_related("usuario").filter(
        token_hash=hash_opaco(token), finalidade=finalidade
    ).first()


def url_frontend(caminho: str) -> str:
    return f"{settings.FRONTEND_URL.rstrip('/')}/{caminho.lstrip('/')}"


def enviar_email_redefinicao(usuario, token: str, contexto: str):
    rota = "admin/redefinir-senha" if contexto == "admin" else "portal/redefinir-senha"
    link = f"{url_frontend(rota)}?token={token}"
    send_mail(
        "Redefinição de senha — Pred Ativos",
        (
            f"Olá, {usuario.nome}.\n\n"
            "Recebemos uma solicitação para redefinir sua senha. "
            f"Use o link abaixo nas próximas 30 minutos:\n\n{link}\n\n"
            "Se você não solicitou esta alteração, ignore este e-mail. "
            "Sua senha atual continuará válida."
        ),
        settings.DEFAULT_FROM_EMAIL,
        [usuario.email],
        fail_silently=False,
    )


def enviar_email_senha_alterada(usuario):
    send_mail(
        "Sua senha foi alterada — Pred Ativos",
        (
            f"Olá, {usuario.nome}.\n\n"
            "A senha da sua conta Pred Ativos foi alterada. "
            "As demais sessões foram encerradas por segurança.\n\n"
            "Se você não realizou esta alteração, solicite uma nova redefinição "
            "de senha e avise o responsável pela sua conta imediatamente."
        ),
        settings.DEFAULT_FROM_EMAIL,
        [usuario.email],
        fail_silently=True,
    )


def enviar_email_verificacao(usuario, token: str, contexto: str = "portal"):
    link = f"{url_frontend(f'{contexto}/verificar-email')}?token={token}"
    send_mail(
        "Confirme seu e-mail — Pred Ativos",
        (
            f"Olá, {usuario.nome}.\n\nConfirme seu e-mail pelo link abaixo:\n\n{link}\n\n"
            "O link expira em 30 minutos e funciona uma única vez."
        ),
        settings.DEFAULT_FROM_EMAIL,
        [usuario.email],
        fail_silently=False,
    )


def enviar_email_convite(convite, token: str):
    link = url_frontend(f"{convite.tipo}/convite/{token}")
    send_mail(
        "Convite de acesso — Pred Ativos",
        (
            f"Olá, {convite.nome}.\n\n"
            "Você recebeu um convite para acessar o Pred Ativos. "
            f"Crie sua senha pelo link abaixo:\n\n{link}\n\n"
            "O convite é pessoal, de uso único e expira em 72 horas."
        ),
        settings.DEFAULT_FROM_EMAIL,
        [convite.email],
        fail_silently=False,
    )


def _fernet() -> Fernet:
    chave = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(chave))


def criptografar_segredo(segredo: str) -> str:
    return _fernet().encrypt(segredo.encode("ascii")).decode("ascii")


def descriptografar_segredo(segredo: str) -> str:
    return _fernet().decrypt(segredo.encode("ascii")).decode("ascii")


def novo_segredo_totp() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _codigo_totp(segredo: str, passo: int, digitos=6) -> str:
    padding = "=" * ((8 - len(segredo) % 8) % 8)
    chave = base64.b32decode(segredo + padding, casefold=True)
    digest = hmac.new(chave, struct.pack(">Q", passo), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    numero = (struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF) % (10**digitos)
    return str(numero).zfill(digitos)


def validar_totp(segredo: str, codigo: str, *, ultimo_passo=None) -> int | None:
    if not codigo or not codigo.isdigit() or len(codigo) != 6:
        return None
    atual = int(time.time() // 30)
    for passo in (atual - 1, atual, atual + 1):
        if ultimo_passo is not None and passo <= ultimo_passo:
            continue
        if hmac.compare_digest(_codigo_totp(segredo, passo), codigo):
            return passo
    return None


def gerar_codigos_recuperacao(dispositivo, quantidade=8) -> list[str]:
    dispositivo.codigos_recuperacao.all().delete()
    codigos = []
    for _ in range(quantidade):
        bruto = f"{secrets.token_hex(2)}-{secrets.token_hex(2)}".upper()
        CodigoRecuperacaoMFA.objects.create(
            dispositivo=dispositivo, codigo_hash=make_password(bruto)
        )
        codigos.append(bruto)
    return codigos


def consumir_codigo_recuperacao(dispositivo, codigo: str) -> bool:
    for item in dispositivo.codigos_recuperacao.filter(usado_em__isnull=True):
        if check_password(codigo.strip().upper(), item.codigo_hash):
            item.usado_em = timezone.now()
            item.save(update_fields=["usado_em", "atualizado_em"])
            return True
    return False
