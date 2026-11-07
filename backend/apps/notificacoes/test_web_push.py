"""
Item 2.10.1.3 / 2.7.1.1.8 — Web Push (VAPID). ENVIADO só com 2xx do push service.
Sem chaves configuradas o canal responde NAO_CONFIGURADO. O envio real é substituído por mock.
"""
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import Nivel, Perfil, User
from apps.cadastros.models import Empresa

from .channels import Resultado, enviar_push, push_configurado
from .models import AssinaturaPush, StatusEntrega

CHAVES = {
    "VAPID_PUBLIC_KEY": "BPublicaDeTeste",
    "VAPID_PRIVATE_KEY": "-----BEGIN PRIVATE KEY-----\nteste\n-----END PRIVATE KEY-----",
    "NOTIFICACOES_PUSH_ENABLED": True,
}


class _Resposta:
    def __init__(self, codigo):
        self.status_code = codigo


def _erro_webpush(codigo):
    from pywebpush import WebPushException
    return WebPushException(f"HTTP {codigo}", response=_Resposta(codigo))


class PushCanalTests(TestCase):
    def setUp(self):
        # V-01: o envio confere o DNS do host; em teste, o host resolve para um IP público.
        patcher = mock.patch("apps.notificacoes.seguranca_push._resolver",
                             return_value=[(None, None, None, None, ("142.250.0.1", 443))])
        patcher.start()
        self.addCleanup(patcher.stop)

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(email="u@t.test", password="uma frase senha longa 2026", nome="U",
                                            perfil=Perfil.TECNICO, nivel=Nivel.PLENO,
                                            empresa=Empresa.objects.create(nome="E", cnpj="11.222.333/0001-81"))

    def _assinar(self, endpoint="https://fcm.googleapis.com/abc", ativa=True):
        return AssinaturaPush.objects.create(usuario=self.user, endpoint=endpoint, p256dh="p", auth="a", ativa=ativa)

    def test_sem_chaves_responde_nao_configurado_e_nunca_enviado(self):
        with override_settings(VAPID_PUBLIC_KEY="", VAPID_PRIVATE_KEY="", NOTIFICACOES_PUSH_ENABLED=False):
            self.assertFalse(push_configurado()[0])
            self._assinar()
            r = enviar_push(self.user, "t", "m")
            self.assertEqual(r.status, StatusEntrega.NAO_CONFIGURADO)

    def test_sem_dispositivo_registrado_e_ignorado(self):
        with override_settings(**CHAVES):
            self.assertEqual(enviar_push(self.user, "t", "m").status, StatusEntrega.IGNORADO)

    def test_2xx_do_push_service_e_enviado(self):
        self._assinar()
        with override_settings(**CHAVES), mock.patch("pywebpush.webpush", return_value=_Resposta(201)):
            r = enviar_push(self.user, "t", "m")
        self.assertEqual(r.status, StatusEntrega.ENVIADO)
        self.assertIsNotNone(AssinaturaPush.objects.get().ultimo_envio_em)

    def test_assinatura_expirada_410_e_desativada_sem_erro(self):
        assinatura = self._assinar()
        with override_settings(**CHAVES), mock.patch("pywebpush.webpush", side_effect=_erro_webpush(410)):
            r = enviar_push(self.user, "t", "m")
        self.assertEqual(r.status, StatusEntrega.IGNORADO)
        assinatura.refresh_from_db()
        self.assertFalse(assinatura.ativa)

    def test_erro_do_servidor_e_falha_temporaria(self):
        self._assinar()
        with override_settings(**CHAVES), mock.patch("pywebpush.webpush", side_effect=_erro_webpush(503)):
            r = enviar_push(self.user, "t", "m")
        self.assertEqual(r.status, StatusEntrega.FALHOU)
        self.assertTrue(r.temporario)

    def test_erro_definitivo_nao_e_temporario(self):
        self._assinar()
        with override_settings(**CHAVES), mock.patch("pywebpush.webpush", side_effect=_erro_webpush(400)):
            r = enviar_push(self.user, "t", "m")
        self.assertEqual(r.status, StatusEntrega.FALHOU)
        self.assertFalse(r.temporario)

    def test_assinatura_inativa_nao_recebe(self):
        self._assinar(ativa=False)
        with override_settings(**CHAVES), mock.patch("pywebpush.webpush") as envio:
            self.assertEqual(enviar_push(self.user, "t", "m").status, StatusEntrega.IGNORADO)
        envio.assert_not_called()


class PushApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        empresa = Empresa.objects.create(nome="E", cnpj="11.222.333/0001-81")
        cls.a = User.objects.create_user(email="a@t.test", password="uma frase senha longa 2026", nome="A",
                                         perfil=Perfil.TECNICO, nivel=Nivel.PLENO, empresa=empresa)
        cls.b = User.objects.create_user(email="b@t.test", password="uma frase senha longa 2026", nome="B",
                                         perfil=Perfil.TECNICO, nivel=Nivel.PLENO, empresa=empresa)
        cls.payload = {"endpoint": "https://fcm.googleapis.com/dispositivo-1",
                       "keys": {"p256dh": "chave", "auth": "segredo"}}

    def api(self, usuario):
        c = APIClient()
        c.force_authenticate(usuario)
        return c

    def test_chave_publica_so_com_canal_pronto(self):
        with override_settings(VAPID_PUBLIC_KEY="", VAPID_PRIVATE_KEY="", NOTIFICACOES_PUSH_ENABLED=False):
            self.assertFalse(self.api(self.a).get("/api/notificacoes/push/chave/").data["configurado"])
        with override_settings(**CHAVES):
            r = self.api(self.a).get("/api/notificacoes/push/chave/")
        self.assertTrue(r.data["configurado"])
        self.assertEqual(r.data["chave"], "BPublicaDeTeste")

    def test_registra_e_remove_assinatura_do_proprio_usuario(self):
        r = self.api(self.a).post("/api/notificacoes/push/assinatura/", self.payload, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(AssinaturaPush.objects.get().usuario, self.a)
        # outro usuário não remove a assinatura alheia
        self.api(self.b).delete("/api/notificacoes/push/assinatura/", {"endpoint": self.payload["endpoint"]},
                                format="json")
        self.assertTrue(AssinaturaPush.objects.exists())
        self.api(self.a).delete("/api/notificacoes/push/assinatura/", {"endpoint": self.payload["endpoint"]},
                                format="json")
        self.assertFalse(AssinaturaPush.objects.exists())

    def test_assinatura_incompleta_ou_http_e_recusada(self):
        self.assertEqual(self.api(self.a).post("/api/notificacoes/push/assinatura/",
                                               {"endpoint": "https://x", "keys": {}}, format="json").status_code, 400)
        self.assertEqual(self.api(self.a).post("/api/notificacoes/push/assinatura/",
                                               {"endpoint": "http://x", "keys": {"p256dh": "a", "auth": "b"}},
                                               format="json").status_code, 400)

    def test_anonimo_nao_registra(self):
        self.assertIn(APIClient().post("/api/notificacoes/push/assinatura/", self.payload,
                                       format="json").status_code, (401, 403))


class GerarChavesTests(TestCase):
    def test_comando_gera_par_utilizavel(self):
        saida = StringIO()
        call_command("gerar_vapid_keys", stdout=saida)
        texto = saida.getvalue()
        self.assertIn("VAPID_PUBLIC_KEY=", texto)
        self.assertIn("VAPID_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----", texto)
        privada = [l for l in texto.splitlines() if l.startswith("VAPID_PRIVATE_KEY=")][0].split("=", 1)[1]
        self.assertNotIn("\n", privada)  # uma linha só no ambiente
        self.assertTrue(privada.replace("\\n", "\n").strip().endswith("-----END PRIVATE KEY-----"))
