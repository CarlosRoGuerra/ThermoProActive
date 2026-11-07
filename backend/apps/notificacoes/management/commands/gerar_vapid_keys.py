import base64

from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from django.core.management.base import BaseCommand
from py_vapid import Vapid01


class Command(BaseCommand):
    help = "Gera o par de chaves VAPID do Web Push (imprime para copiar no ambiente; não grava)."

    def handle(self, *args, **opcoes):
        vapid = Vapid01()
        vapid.generate_keys()
        publica = vapid.public_key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
        chave_publica = base64.urlsafe_b64encode(publica).rstrip(b"=").decode("ascii")
        # Uma linha só, com \n escapado (settings.VAPID_PRIVATE_KEY desfaz o escape).
        pem = vapid.private_pem().decode("ascii").strip().replace("\r", "")
        chave_privada = pem.replace("\n", "\\n")
        self.stdout.write("Guarde as duas no ambiente (nunca no repositório):")
        self.stdout.write(f"VAPID_PUBLIC_KEY={chave_publica}")
        self.stdout.write(f"VAPID_PRIVATE_KEY={chave_privada}")
