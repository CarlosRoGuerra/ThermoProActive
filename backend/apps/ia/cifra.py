"""
Cifra das chaves de API de IA em repouso (Fernet).

A chave de cifra vem de `IA_ENCRYPTION_KEY`; vazia, deriva do `SECRET_KEY` — mesmo padrão
dos segredos TOTP do MFA (`accounts.security`), com um prefixo próprio para que um segredo
de um domínio nunca decifre o do outro. Trocar a chave de cifra (ou o `SECRET_KEY`, quando
ela deriva dele) torna ilegíveis as chaves gravadas: basta cadastrá-las de novo.
"""
import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


class ChaveIlegivel(Exception):
    """A chave gravada não pôde ser decifrada (a chave de cifra do servidor mudou)."""


def _fernet() -> Fernet:
    semente = getattr(settings, "IA_ENCRYPTION_KEY", "") or settings.SECRET_KEY
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(f"ia-chaves:{semente}".encode("utf-8")).digest()))


def cifrar(texto: str) -> str:
    return _fernet().encrypt(texto.encode("utf-8")).decode("ascii")


def decifrar(cifrado: str) -> str:
    try:
        return _fernet().decrypt(cifrado.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError) as erro:
        raise ChaveIlegivel("A chave gravada não pôde ser lida. Cadastre-a novamente.") from erro
