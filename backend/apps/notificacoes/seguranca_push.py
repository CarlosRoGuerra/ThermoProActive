"""
V-01 — Web Push sem SSRF.

O endpoint de uma assinatura de push vem do navegador do usuário. O servidor faz POST para
ele, então é preciso garantir que ele aponta só para os serviços de push conhecidos e nunca
para a rede interna. Três defesas, em camadas:

1. Registro e envio: https, sem credenciais na URL, porta padrão (443), host NÃO é IP literal,
   host dentro da allowlist de serviços de push (configurável por `PUSH_HOSTS_PERMITIDOS`).
2. Envio: resolve o DNS do host AGORA e recusa qualquer IP que não seja público (privado,
   loopback, link-local, reservado, multicast, não especificado).
3. Envio: sem seguir redirecionamento (a sessão do requests força `allow_redirects=False`).

Limite residual (documentado em docs/22): a janela entre a checagem do DNS e a conexão ainda
existe (DNS rebinding). Ela é pequena porque o host já precisa estar na allowlist dos
provedores, que não são controlados por quem assina.
"""
import ipaddress
import socket
from urllib.parse import urlsplit

import requests
from django.conf import settings

PORTA_PADRAO = 443
TAMANHO_MAXIMO_ENDPOINT = 500

#: Serviços de push conhecidos. Entrada que começa com "." casa o sufixo (subdomínios).
HOSTS_PERMITIDOS_PADRAO = (
    "fcm.googleapis.com",                       # Chrome, Edge (FCM)
    "updates.push.services.mozilla.com",        # Firefox
    ".push.services.mozilla.com",
    ".push.apple.com",                          # Safari (macOS e iOS)
    ".notify.windows.com",                      # Edge/Windows (WNS)
)


class EndpointNaoPermitido(ValueError):
    """Endpoint de push recusado. A mensagem é curta e não diz qual regra bateu (sem oráculo)."""


class DnsIndisponivel(OSError):
    """Não foi possível resolver o host agora (falha temporária)."""


def hosts_permitidos():
    configurado = getattr(settings, "PUSH_HOSTS_PERMITIDOS", None)
    if not configurado:
        return HOSTS_PERMITIDOS_PADRAO
    if isinstance(configurado, str):
        configurado = [h.strip() for h in configurado.split(",") if h.strip()]
    return tuple(h.lower() for h in configurado)


def _na_allowlist(host, permitidos):
    for padrao in permitidos:
        if padrao.startswith("."):
            if host.endswith(padrao):
                return True
        elif host == padrao:
            return True
    return False


def validar_endpoint(url) -> str:
    """Valida a forma do endpoint. Devolve o host em minúsculas ou levanta EndpointNaoPermitido."""
    if not isinstance(url, str) or not url or len(url) > TAMANHO_MAXIMO_ENDPOINT:
        raise EndpointNaoPermitido("Endpoint de push não permitido.")
    try:
        partes = urlsplit(url)
        porta = partes.port  # levanta ValueError para porta inválida
    except ValueError as erro:
        raise EndpointNaoPermitido("Endpoint de push não permitido.") from erro
    if partes.scheme != "https":
        raise EndpointNaoPermitido("Endpoint de push não permitido.")
    if partes.username is not None or partes.password is not None or "@" in partes.netloc:
        raise EndpointNaoPermitido("Endpoint de push não permitido.")
    if porta not in (None, PORTA_PADRAO):
        raise EndpointNaoPermitido("Endpoint de push não permitido.")
    host = (partes.hostname or "").lower().rstrip(".")
    if not host:
        raise EndpointNaoPermitido("Endpoint de push não permitido.")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass  # não é IP literal: segue
    else:
        raise EndpointNaoPermitido("Endpoint de push não permitido.")
    if not _na_allowlist(host, hosts_permitidos()):
        raise EndpointNaoPermitido("Endpoint de push não permitido.")
    return host


def _resolver(host):
    try:
        return socket.getaddrinfo(host, PORTA_PADRAO, type=socket.SOCK_STREAM)
    except socket.gaierror as erro:
        raise DnsIndisponivel(str(erro)) from erro


def ip_publico(endereco: str) -> bool:
    try:
        ip = ipaddress.ip_address(endereco.split("%", 1)[0])
    except ValueError:
        return False
    return not (
        ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
        or ip.is_multicast or ip.is_unspecified or not ip.is_global
    )


def checar_dns(host: str) -> None:
    """Recusa o envio se o host resolve para qualquer endereço não público."""
    infos = _resolver(host)
    if not infos:
        raise DnsIndisponivel("sem endereços")
    for info in infos:
        endereco = info[4][0]
        if not ip_publico(endereco):
            raise EndpointNaoPermitido("Endpoint de push não permitido.")


class SessaoPushSegura(requests.Session):
    """Sessão do envio: nunca segue redirecionamento (um 3xx não vira outro destino)."""

    def request(self, method, url, **kwargs):
        kwargs["allow_redirects"] = False
        return super().request(method, url, **kwargs)
