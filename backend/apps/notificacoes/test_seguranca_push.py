"""
V-01 — regras do endpoint de Web Push: forma, allowlist, DNS público e sem redirecionamento.
"""
from unittest import mock

import requests
from django.test import SimpleTestCase, override_settings

from .seguranca_push import (
    DnsIndisponivel,
    EndpointNaoPermitido,
    SessaoPushSegura,
    checar_dns,
    ip_publico,
    validar_endpoint,
)


class FormaDoEndpointTests(SimpleTestCase):
    def test_servicos_conhecidos_sao_aceitos(self):
        for url in (
            "https://fcm.googleapis.com/fcm/send/abc",
            "https://updates.push.services.mozilla.com/wpush/v2/abc",
            "https://web.push.apple.com/QAbc",
            "https://wns2-par02p.notify.windows.com/w/?token=abc",
        ):
            self.assertTrue(validar_endpoint(url), url)

    def test_fora_da_allowlist_e_recusado(self):
        for url in ("https://push.example/abc", "https://evil.fcm.googleapis.com.attacker.test/x",
                    "https://fcm.googleapis.com.evil.test/x"):
            with self.assertRaises(EndpointNaoPermitido, msg=url):
                validar_endpoint(url)

    def test_forma_insegura_e_recusada(self):
        for url in (
            "http://fcm.googleapis.com/x",             # sem TLS
            "https://127.0.0.1/x",                     # IP literal (loopback)
            "https://[::1]/x",                         # IPv6 literal
            "https://10.1.2.3/x",                      # IP privado
            "https://fcm.googleapis.com:8443/x",       # porta fora do padrão
            "https://user:pass@fcm.googleapis.com/x",  # credenciais na URL
            "https://fcm.googleapis.com@127.0.0.1/x",  # truque de host
            "fcm.googleapis.com/x",                    # sem esquema
            "",
            None,
        ):
            with self.assertRaises(EndpointNaoPermitido, msg=repr(url)):
                validar_endpoint(url)

    @override_settings(PUSH_HOSTS_PERMITIDOS="meu.push.test")
    def test_allowlist_configuravel_por_ambiente(self):
        self.assertEqual(validar_endpoint("https://meu.push.test/x"), "meu.push.test")
        with self.assertRaises(EndpointNaoPermitido):
            validar_endpoint("https://fcm.googleapis.com/x")


class DnsPublicoTests(SimpleTestCase):
    def _dns(self, *enderecos):
        return [(None, None, None, None, (e, 443)) for e in enderecos]

    def test_ip_nao_publico_e_detectado(self):
        for ip in ("127.0.0.1", "10.0.0.5", "192.168.1.1", "172.16.0.9", "169.254.169.254",
                   "100.64.0.1", "0.0.0.0", "224.0.0.1", "::1", "fe80::1", "fc00::1"):
            self.assertFalse(ip_publico(ip), ip)
        self.assertTrue(ip_publico("142.250.0.1"))

    def test_dns_com_um_so_endereco_interno_recusa(self):
        with mock.patch("apps.notificacoes.seguranca_push._resolver",
                        return_value=self._dns("142.250.0.1", "10.0.0.5")):
            with self.assertRaises(EndpointNaoPermitido):
                checar_dns("fcm.googleapis.com")

    def test_dns_publico_passa(self):
        with mock.patch("apps.notificacoes.seguranca_push._resolver", return_value=self._dns("142.250.0.1")):
            checar_dns("fcm.googleapis.com")

    def test_falha_de_dns_e_temporaria(self):
        with mock.patch("apps.notificacoes.seguranca_push._resolver", side_effect=DnsIndisponivel("x")):
            with self.assertRaises(DnsIndisponivel):
                checar_dns("fcm.googleapis.com")


class SemRedirecionamentoTests(SimpleTestCase):
    def test_sessao_do_envio_nunca_segue_redirecionamento(self):
        with mock.patch.object(requests.Session, "request") as pedido:
            SessaoPushSegura().post("https://fcm.googleapis.com/fcm/send/abc", data=b"x")
        self.assertIs(pedido.call_args.kwargs["allow_redirects"], False)
