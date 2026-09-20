import re
from datetime import timedelta

from django.core import mail
from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from apps.cadastros.models import Cliente, Empresa

from .models import Convite, Nivel, Perfil, SessaoAutenticacao, TokenUsoUnico
from .security import _codigo_totp


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    FRONTEND_URL="http://testserver",
)
class AuthenticationFlowTests(APITestCase):
    senha = "uma frase senha longa e segura 2026"

    @classmethod
    def setUpTestData(cls):
        cls.empresa = Empresa.objects.create(nome="ThermoProActive", cnpj="11.222.333/0001-81")
        cls.cliente = Cliente.objects.create(nome="Indústria Cliente", cnpj="45.723.174/0001-10")
        cls.admin = cls._user("admin@thermo.test", Perfil.ADMIN, Nivel.MASTER, empresa=cls.empresa)
        cls.portal = cls._user("pcm@cliente.test", Perfil.CLIENTE_PCM, Nivel.PLENO, cliente=cls.cliente)
        cls.cliente_master = cls._user(
            "master@cliente.test", Perfil.CLIENTE_CORP, Nivel.MASTER, cliente=cls.cliente
        )

    @classmethod
    def _user(cls, email, perfil, nivel, **vinculo):
        from django.contrib.auth import get_user_model
        return get_user_model().objects.create_user(
            email=email, password=cls.senha, nome=email.split("@")[0],
            perfil=perfil, nivel=nivel, **vinculo,
        )

    def setUp(self):
        cache.clear()

    def csrf_client(self):
        client = APIClient(enforce_csrf_checks=True)
        response = client.get("/api/auth/csrf/")
        self.assertEqual(response.status_code, 200)
        token = response.data["csrfToken"]
        return client, {"HTTP_X_CSRFTOKEN": token}

    def login(self, contexto, email, senha=None, **extra):
        client, csrf = self.csrf_client()
        response = client.post(
            f"/api/auth/{contexto}/login/",
            {"email": email, "password": senha or self.senha, **extra},
            format="json", **csrf,
        )
        return client, csrf, response

    def test_logins_sao_separados_e_cookie_e_httponly(self):
        client, _, response = self.login("portal", self.portal.email, lembrar=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.cookies["tpa_access"]["httponly"])
        self.assertTrue(response.cookies["tpa_refresh"]["httponly"])
        self.assertNotIn("access", response.data)
        self.assertEqual(client.get("/api/auth/me/").status_code, 200)

        _, _, errado = self.login("admin", self.portal.email)
        self.assertEqual(errado.status_code, 401)
        _, _, errado_admin = self.login("portal", self.admin.email)
        self.assertEqual(errado_admin.status_code, 401)

    def test_cliente_master_nao_administra_usuarios_da_plataforma(self):
        client = APIClient()
        client.force_authenticate(self.cliente_master)
        resposta = client.get("/api/usuarios/")
        self.assertEqual(resposta.status_code, 403)

    def test_logout_revoga_sessao(self):
        client, csrf, response = self.login("portal", self.portal.email)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(SessaoAutenticacao.objects.filter(usuario=self.portal, revogada_em__isnull=True).count(), 1)
        logout = client.post("/api/auth/logout/", {}, format="json", **csrf)
        self.assertEqual(logout.status_code, 204)
        self.assertFalse(SessaoAutenticacao.objects.filter(usuario=self.portal, revogada_em__isnull=True).exists())
        self.assertEqual(client.get("/api/auth/me/").status_code, 401)

    def test_conta_bloqueada_nao_autentica_e_sessao_expirada_e_rejeitada(self):
        self.portal.bloqueado_ate = timezone.now() + timedelta(minutes=10)
        self.portal.save(update_fields=["bloqueado_ate", "atualizado_em"])
        _, _, bloqueado = self.login("portal", self.portal.email)
        self.assertEqual(bloqueado.status_code, 429)
        self.assertFalse(SessaoAutenticacao.objects.filter(usuario=self.portal).exists())

        self.portal.bloqueado_ate = None
        self.portal.save(update_fields=["bloqueado_ate", "atualizado_em"])
        client, _, login = self.login("portal", self.portal.email)
        self.assertEqual(login.status_code, 200)
        SessaoAutenticacao.objects.filter(usuario=self.portal).update(
            expira_em=timezone.now() - timedelta(seconds=1)
        )
        self.assertEqual(client.get("/api/auth/me/").status_code, 401)

    def test_recuperacao_nao_enumera_e_token_e_uso_unico(self):
        existente = self.client.post(
            "/api/auth/portal/esqueci-senha/", {"email": self.portal.email}, format="json"
        )
        inexistente = self.client.post(
            "/api/auth/portal/esqueci-senha/", {"email": "naoexiste@example.test"}, format="json"
        )
        self.assertEqual(existente.status_code, 200)
        self.assertEqual(existente.data, inexistente.data)
        self.assertEqual(len(mail.outbox), 1)
        token = re.search(r"token=([^\s]+)", mail.outbox[0].body).group(1)
        self.assertFalse(TokenUsoUnico.objects.filter(token_hash=token).exists())

        with self.captureOnCommitCallbacks(execute=True):
            redefinir = self.client.post(
                "/api/auth/redefinir-senha/",
                {"token": token, "nova_senha": "outra frase senha longa e segura 2026"},
                format="json",
            )
        self.assertEqual(redefinir.status_code, 200)
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn("senha foi alterada", mail.outbox[-1].subject.lower())
        reutilizar = self.client.post(
            "/api/auth/redefinir-senha/",
            {"token": token, "nova_senha": "terceira frase senha longa segura 2026"},
            format="json",
        )
        self.assertEqual(reutilizar.status_code, 400)

    def test_convite_define_contexto_e_impede_auto_promocao(self):
        client = APIClient()
        client.force_authenticate(self.admin)
        resposta = client.post(
            "/api/auth/convites/",
            {
                "nome": "Nova pessoa", "email": "nova@cliente.test", "tipo": "portal",
                "perfil": Perfil.CLIENTE_PCM, "nivel": Nivel.JUNIOR, "cliente": self.cliente.pk,
                "empresa": None,
            }, format="json",
        )
        self.assertEqual(resposta.status_code, 201)
        convite = Convite.objects.get(pk=resposta.data["id"])
        self.assertEqual(convite.perfil, Perfil.CLIENTE_PCM)
        token = re.search(r"convite/([^\s]+)", mail.outbox[-1].body).group(1)
        aceitar = self.client.post(
            f"/api/auth/convites/{token}/",
            {"senha": "senha pessoal longa e segura para 2026", "aceitou_termos": True},
            format="json",
        )
        self.assertEqual(aceitar.status_code, 201)
        usuario = type(self.portal).objects.get(email="nova@cliente.test")
        self.assertEqual(usuario.perfil, Perfil.CLIENTE_PCM)
        self.assertEqual(usuario.nivel, Nivel.JUNIOR)
        self.assertEqual(usuario.cliente, self.cliente)
        repetido = self.client.post(
            f"/api/auth/convites/{token}/",
            {"senha": "senha pessoal longa e segura para 2026", "aceitou_termos": True},
            format="json",
        )
        self.assertEqual(repetido.status_code, 400)

    def test_solicitacao_rejeita_cnpj_invalido_e_nao_cria_usuario(self):
        resposta = self.client.post(
            "/api/auth/solicitacoes-acesso/",
            {
                "nome": "Responsável", "email": "responsavel@empresa.test", "telefone": "11999999999",
                "razao_social": "Empresa", "cnpj": "11.111.111/1111-11", "cargo": "Gestor",
                "aceitou_termos": True, "aceita_marketing": False,
            }, format="json",
        )
        self.assertEqual(resposta.status_code, 400)
        self.assertFalse(type(self.portal).objects.filter(email="responsavel@empresa.test").exists())

    def test_mfa_totp_exige_codigo_no_login(self):
        client = APIClient()
        client.force_authenticate(self.admin)
        inicio = client.post("/api/auth/mfa/setup/", {}, format="json")
        self.assertEqual(inicio.status_code, 200)
        segredo = inicio.data["secret"]
        passo = int(timezone.now().timestamp() // 30)
        confirmacao = client.post(
            "/api/auth/mfa/confirm/", {"codigo": _codigo_totp(segredo, passo)}, format="json"
        )
        self.assertEqual(confirmacao.status_code, 200)

        _, _, sem_codigo = self.login("admin", self.admin.email)
        self.assertEqual(sem_codigo.status_code, 428)
        _, _, com_codigo = self.login(
            "admin", self.admin.email, codigo_mfa=confirmacao.data["recovery_codes"][0]
        )
        self.assertEqual(com_codigo.status_code, 200)
