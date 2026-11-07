"""
Certificado A1 (PKCS#12) do responsável técnico — leitura, validação e cifra em repouso.
Não guarda a senha do .pfx em nenhum lugar.
"""
import hashlib

from cryptography import x509
from cryptography.hazmat.primitives.serialization import Encoding, pkcs12
from cryptography.x509.oid import NameOID

from .security import _fernet

TAMANHO_MAXIMO_PFX = 200 * 1024


class CertificadoInvalido(ValueError):
    pass


def _nome(name, oid):
    valores = name.get_attributes_for_oid(oid)
    return valores[0].value if valores else ""


def ler_pfx(conteudo: bytes, senha: str) -> dict:
    """Valida o .pfx com a senha e devolve os dados do certificado. Levanta CertificadoInvalido."""
    if not conteudo or len(conteudo) > TAMANHO_MAXIMO_PFX:
        raise CertificadoInvalido("Arquivo de certificado vazio ou grande demais.")
    try:
        chave, cert, _extras = pkcs12.load_key_and_certificates(conteudo, senha.encode("utf-8"))
    except (ValueError, TypeError):
        raise CertificadoInvalido("Não foi possível abrir o certificado: arquivo ou senha inválidos.")
    if cert is None or chave is None:
        raise CertificadoInvalido("O arquivo precisa conter o certificado e a chave privada.")
    valido_ate = cert.not_valid_after_utc
    return {
        "titular": _nome(cert.subject, NameOID.COMMON_NAME)[:255],
        "emissor": _nome(cert.issuer, NameOID.COMMON_NAME)[:255],
        "numero_serie": format(cert.serial_number, "X")[:80],
        "valido_ate": valido_ate,
        "sha256_certificado": hashlib.sha256(cert.public_bytes(Encoding.DER)).hexdigest(),
        "cert_pem": cert.public_bytes(Encoding.PEM),
    }



def cifrar_arquivo(conteudo: bytes) -> str:
    return _fernet().encrypt(conteudo).decode("ascii")


def decifrar_arquivo(cifrado: str) -> bytes:
    return _fernet().decrypt(cifrado.encode("ascii"))
