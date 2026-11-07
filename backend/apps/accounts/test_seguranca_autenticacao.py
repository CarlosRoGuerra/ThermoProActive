"""
Regressão da auditoria de segurança de pré-homologação — autenticação e sessão.

Cobre: A-06 (login/refresh legados e Bearer sem sessão), bypass do MFA pelo
`/auth/mfa/setup/`, contagem de falhas de MFA no bloqueio, throttle que não
valia para quem já estava logado e X-Forwarded-For forjável, gestão de usuários
por Master e a aprovação de solicitações de acesso.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone
from rest_framework.settings import api_settings
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.cadastros.models import Cliente, Empresa

from .models import Convite, EstadoConta, Nivel, Perfil, SessaoAutenticacao, SolicitacaoAcesso
from .security import _codigo_totp

User = get_user_model()
SENHA = "uma frase senha longa e segura 2026"


def _usuario(email, perfil, nivel=Nivel.PLENO, **vinculo):
    return User.objects.create_user(
        email=email, password=SENHA, nome=email.split("@")[0], perfil=perfil, nivel=nivel, **vinculo
    )


class _Base(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.empresa = Empresa.objects.create(nome="Prestadora", cnpj="11.222.333/0001-81")
        cls.cliente = Cliente.objects.create(nome="Cliente A", cnpj="45.723.174/0001-10")
        cls.interno_master = _usuario("master@thermo.test", Perfil.GESTOR, Nivel.MASTER, empresa=cls.empresa)
        cls.tecnico = _usuario("tec@thermo.test", Perfil.TECNICO, Nivel.PLENO, empresa=cls.empresa)
        cls.portal = _usuario("pcm@a.test", Perfil.CLIENTE_PCM, Nivel.PLENO, cliente=cls.cliente)
        cls.portal_master = _usuario("m@a.test", Perfil.CLIENTE_CORP, Nivel.MASTER, cliente=cls.cliente)

    def setUp(self):
        cache.clear()

    def login(self, contexto, email, **extra):
        client = APIClient(enforce_csrf_checks=True)
        csrf = {"HTTP_X_CSRFTOKEN": client.get("/api/auth/csrf/").data["csrfToken"]}
        resposta = client.post(
            f"/api/auth/{contexto}/login/", {"email": email, "password": SENHA, **extra}, format="json", **csrf
        )
        return client, csrf, resposta


class LoginLegadoRemovidoTests(_Base):
    """A-06: SimpleJWT cru contornava MFA, bloqueio, throttle e revogação."""

    def test_rotas_legadas_nao_existem(self):
        for rota in ("/api/auth/login/", "/api/auth/refresh/"):
            resposta = self.client.post(rota, {"email": self.portal.email, "password": SENHA}, format="json")
            self.assertEqual(resposta.status_code, 404, rota)

    def test_login_exige_token_csrf(self):
        # "Login CSRF": sem o token, um site de terceiros loga o navegador da vítima na conta do atacante.
        client = APIClient(enforce_csrf_checks=True)
        resposta = client.post("/api/auth/portal/login/", {"email": self.portal.email, "password": SENHA},
                               format="json")
        self.assertEqual(resposta.status_code, 403)
        self.assertNotIn("tpa_access", resposta.cookies)
        _, _, com_token = self.login("portal", self.portal.email)
        self.assertEqual(com_token.status_code, 200)

    def test_bearer_sem_sid_e_rejeitado(self):
        # Token "puro" do SimpleJWT, como o login legado emitia (sem `sid`, sem SessaoAutenticacao).
        token = str(RefreshToken.for_user(self.portal).access_token)
        resposta = APIClient().get("/api/auth/me/", HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(resposta.status_code, 401)

    def test_bearer_com_sessao_revogada_e_rejeitado_e_viva_e_aceita(self):
        client, csrf, login = self.login("portal", self.portal.email)
        self.assertEqual(login.status_code, 200)
        sessao = SessaoAutenticacao.objects.get(usuario=self.portal)
        refresh = RefreshToken.for_user(self.portal)
        refresh["sid"] = str(sessao.id)
        header = {"HTTP_AUTHORIZATION": f"Bearer {refresh.access_token}"}
        self.assertEqual(APIClient().get("/api/auth/me/", **header).status_code, 200)
        sessao.revogada_em = timezone.now()
        sessao.save()
        self.assertEqual(APIClient().get("/api/auth/me/", **header).status_code, 401)

    def test_conta_suspensa_perde_acesso_mesmo_com_sessao_viva(self):
        client, _, login = self.login("portal", self.portal.email)
        self.assertEqual(client.get("/api/auth/me/").status_code, 200)
        User.objects.filter(pk=self.portal.pk).update(estado=EstadoConta.SUSPENDED)
        self.assertEqual(client.get("/api/auth/me/").status_code, 401)

    def test_refresh_nao_renova_conta_suspensa(self):
        client, csrf, _ = self.login("portal", self.portal.email)
        User.objects.filter(pk=self.portal.pk).update(estado=EstadoConta.SUSPENDED)
        resposta = client.post("/api/auth/session/refresh/", {}, format="json", **csrf)
        self.assertEqual(resposta.status_code, 401)
        self.assertFalse(SessaoAutenticacao.objects.filter(usuario=self.portal, revogada_em__isnull=True).exists())


class MfaTests(_Base):
    def _ativar_mfa(self, usuario):
        client = APIClient()
        client.force_authenticate(usuario)
        segredo = client.post("/api/auth/mfa/setup/", {}, format="json").data["secret"]
        passo = int(timezone.now().timestamp() // 30)
        confirmar = client.post("/api/auth/mfa/confirm/", {"codigo": _codigo_totp(segredo, passo)}, format="json")
        self.assertEqual(confirmar.status_code, 200)
        return client, segredo

    def test_setup_nao_desliga_mfa_ativo(self):
        client, _ = self._ativar_mfa(self.interno_master)
        # Quem tem sessão (roubada, por ex.) não pode "reconfigurar" e derrubar o 2º fator.
        resposta = client.post("/api/auth/mfa/setup/", {}, format="json")
        self.assertEqual(resposta.status_code, 409)
        self.interno_master.refresh_from_db()
        self.assertTrue(self.interno_master.mfa.ativo)
        _, _, login = self.login("admin", self.interno_master.email)
        self.assertEqual(login.status_code, 428)  # continua exigindo o código

    def test_codigo_mfa_errado_conta_para_o_bloqueio(self):
        self._ativar_mfa(self.interno_master)
        for _ in range(8):
            _, _, resposta = self.login("admin", self.interno_master.email, codigo_mfa="000000")
            self.assertEqual(resposta.status_code, 428)
            cache.clear()  # isola o bloqueio por conta do throttle por IP
        self.interno_master.refresh_from_db()
        self.assertIsNotNone(self.interno_master.bloqueado_ate)
        _, _, bloqueado = self.login("admin", self.interno_master.email)
        self.assertEqual(bloqueado.status_code, 429)

    def test_primeira_etapa_sem_codigo_nao_conta_falha(self):
        self._ativar_mfa(self.interno_master)
        for _ in range(3):
            self.login("admin", self.interno_master.email)
            cache.clear()
        self.interno_master.refresh_from_db()
        self.assertEqual(self.interno_master.tentativas_login, 0)

    def test_endpoints_de_mfa_tem_throttle_para_usuario_logado(self):
        client = APIClient()
        client.force_authenticate(self.portal)
        codigos = [client.post("/api/auth/mfa/confirm/", {"codigo": "123456"}, format="json").status_code
                   for _ in range(12)]
        self.assertIn(429, codigos)


class ThrottleLoginTests(_Base):
    def test_login_e_limitado_mesmo_para_quem_ja_esta_logado(self):
        # Antes: AnonRateThrottle ignorava requisições autenticadas — com UMA conta
        # qualquer o atacante testava senhas das outras sem limite.
        client, csrf, _ = self.login("portal", self.portal.email)
        status = [
            client.post("/api/auth/portal/login/", {"email": "alvo@x.test", "password": "x"}, format="json", **csrf)
            .status_code
            for _ in range(14)
        ]
        self.assertEqual(status[0], 401)
        self.assertIn(429, status)

    def _rajada_com_xff_forjado(self):
        status = []
        for i in range(14):
            status.append(self.client.post(
                "/api/auth/portal/login/", {"email": "alvo@x.test", "password": "x"}, format="json",
                HTTP_X_FORWARDED_FOR=f"10.9.8.{i}, 203.0.113.7",  # 1º item é do cliente; o último, do nginx
            ).status_code)
        return status

    def test_x_forwarded_for_forjado_nao_escapa_do_limite_na_configuracao_padrao(self):
        # Antes (NUM_PROXIES indefinido) o DRF usava o cabeçalho INTEIRO como identidade: bastava variá-lo.
        self.assertIn(429, self._rajada_com_xff_forjado())

    def test_x_forwarded_for_forjado_nao_escapa_do_limite_atras_do_nginx(self):
        reest = {**api_settings.user_settings, "NUM_PROXIES": 1}
        with override_settings(REST_FRAMEWORK=reest):
            self.assertIn(429, self._rajada_com_xff_forjado())

    def test_recuperacao_nao_enumera_nem_quebra_se_smtp_falhar(self):
        from unittest import mock

        existente = self.client.post("/api/auth/portal/esqueci-senha/", {"email": self.portal.email}, format="json")
        cache.clear()
        with mock.patch("apps.accounts.auth_views.enviar_email_redefinicao", side_effect=OSError("smtp fora")):
            com_falha = self.client.post(
                "/api/auth/portal/esqueci-senha/", {"email": self.portal.email}, format="json"
            )
        cache.clear()
        inexistente = self.client.post("/api/auth/portal/esqueci-senha/", {"email": "x@nao.test"}, format="json")
        self.assertEqual({existente.status_code, com_falha.status_code, inexistente.status_code}, {200})
        self.assertEqual(com_falha.data, inexistente.data)


class GestaoDeUsuariosTests(_Base):
    def _master(self):
        client = APIClient()
        client.force_authenticate(self.interno_master)
        return client

    def test_troca_de_senha_pelo_master_derruba_sessoes_do_usuario(self):
        cliente_alvo, _, login = self.login("portal", self.portal.email)
        self.assertEqual(cliente_alvo.get("/api/auth/me/").status_code, 200)
        resposta = self._master().patch(
            f"/api/usuarios/{self.portal.pk}/", {"password": "outra frase longa e segura 2026!"}, format="json"
        )
        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.assertEqual(cliente_alvo.get("/api/auth/me/").status_code, 401)

    def test_senha_curta_e_recusada(self):
        resposta = self._master().patch(
            f"/api/usuarios/{self.portal.pk}/", {"password": "curta123"}, format="json"
        )
        self.assertEqual(resposta.status_code, 400)

    def test_desativar_usuario_derruba_sessao(self):
        cliente_alvo, _, _ = self.login("portal", self.portal.email)
        resposta = self._master().patch(f"/api/usuarios/{self.portal.pk}/", {"is_active": False}, format="json")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(cliente_alvo.get("/api/auth/me/").status_code, 401)
        self.assertFalse(SessaoAutenticacao.objects.filter(usuario=self.portal, revogada_em__isnull=True).exists())

    def test_master_nao_exclui_a_propria_conta(self):
        resposta = self._master().delete(f"/api/usuarios/{self.interno_master.pk}/")
        self.assertEqual(resposta.status_code, 403)
        self.assertTrue(User.objects.filter(pk=self.interno_master.pk).exists())

    def test_tecnico_e_cliente_nao_gerenciam_usuarios_nem_convidam(self):
        for usuario in (self.tecnico, self.portal, self.portal_master):
            api = APIClient()
            api.force_authenticate(usuario)
            self.assertEqual(api.get("/api/usuarios/").status_code, 403, usuario.email)
            self.assertEqual(api.patch(f"/api/usuarios/{self.portal.pk}/", {"nivel": "MASTER"}, format="json")
                             .status_code, 403, usuario.email)
        api = APIClient()
        api.force_authenticate(self.tecnico)
        convite = api.post("/api/auth/convites/", {
            "nome": "X", "email": "x@x.test", "tipo": "admin", "perfil": Perfil.ADMIN, "nivel": Nivel.MASTER,
        }, format="json")
        self.assertEqual(convite.status_code, 403)

    def test_master_do_cliente_so_convida_para_o_proprio_cliente_e_sem_perfil_interno(self):
        outro = Cliente.objects.create(nome="Cliente B", cnpj="22.222.222/0001-22")
        api = APIClient()
        api.force_authenticate(self.portal_master)
        base = {"nome": "Novo", "email": "novo@a.test", "nivel": Nivel.JUNIOR}
        casos = [
            {**base, "tipo": "portal", "perfil": Perfil.CLIENTE_PCM, "cliente": outro.pk},      # outro tenant
            {**base, "tipo": "admin", "perfil": Perfil.ADMIN, "nivel": Nivel.MASTER},            # perfil interno
            {**base, "tipo": "portal", "perfil": Perfil.TECNICO, "cliente": self.cliente.pk},    # perfil interno no portal
            {**base, "tipo": "portal", "perfil": Perfil.CLIENTE_PCM, "cliente": self.cliente.pk,
             "nivel": Nivel.MASTER},                                                             # auto-promoção
        ]
        for corpo in casos:
            resposta = api.post("/api/auth/convites/", corpo, format="json")
            self.assertIn(resposta.status_code, (400, 403), corpo)
        self.assertFalse(Convite.objects.filter(email="novo@a.test").exists())

    def test_convite_de_cliente_nao_vincula_prestador(self):
        api = APIClient()
        api.force_authenticate(self.portal_master)
        resposta = api.post("/api/auth/convites/", {
            "nome": "Novo", "email": "novo2@a.test", "tipo": "portal", "perfil": Perfil.CLIENTE_PCM,
            "nivel": Nivel.JUNIOR, "cliente": self.cliente.pk, "empresa": self.empresa.pk,
        }, format="json")
        self.assertEqual(resposta.status_code, 201, resposta.data)
        self.assertIsNone(Convite.objects.get(pk=resposta.data["id"]).empresa_id)

    def test_usuario_nao_altera_o_proprio_perfil_por_endpoints_de_cliente(self):
        api = APIClient()
        api.force_authenticate(self.portal)
        for corpo in ({"perfil": Perfil.ADMIN}, {"nivel": Nivel.MASTER}, {"is_staff": True}):
            self.assertEqual(api.patch(f"/api/usuarios/{self.portal.pk}/", corpo, format="json").status_code, 403)
        self.portal.refresh_from_db()
        self.assertEqual(self.portal.perfil, Perfil.CLIENTE_PCM)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", FRONTEND_URL="http://testserver")
class SolicitacaoAcessoTests(_Base):
    def _solicitar(self, cnpj, email):
        return SolicitacaoAcesso.objects.create(
            nome="Fulano", email=email, telefone="11999999999", razao_social="Empresa", cnpj=cnpj,
            cargo="Gestor", aceitou_termos=True,
        )

    def test_aprovar_para_cliente_que_ja_tem_usuarios_nao_concede_master_sozinho(self):
        # O formulário é público e o CNPJ é dado público: o atacante pede acesso "como" um cliente real.
        pedido = self._solicitar(self.cliente.cnpj, "intruso@evil.test")
        api = APIClient()
        api.force_authenticate(self.interno_master)
        resposta = api.post(f"/api/solicitacoes-acesso/{pedido.pk}/aprovar/")
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(resposta.data["convite_enviado"])
        self.assertIn("aviso", resposta.data)
        self.assertFalse(Convite.objects.filter(email="intruso@evil.test").exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_aprovar_cliente_novo_continua_convidando_o_primeiro_master(self):
        pedido = self._solicitar("11.444.777/0001-61", "novo@empresa.test")
        api = APIClient()
        api.force_authenticate(self.interno_master)
        resposta = api.post(f"/api/solicitacoes-acesso/{pedido.pk}/aprovar/")
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.data["convite_enviado"])
        convite = Convite.objects.get(email="novo@empresa.test")
        self.assertEqual(convite.nivel, Nivel.MASTER)

    def test_cliente_nao_aprova_solicitacao(self):
        pedido = self._solicitar("11.444.777/0001-61", "novo@empresa.test")
        api = APIClient()
        api.force_authenticate(self.portal_master)
        self.assertEqual(api.post(f"/api/solicitacoes-acesso/{pedido.pk}/aprovar/").status_code, 403)


class DocumentacaoDaApiTests(_Base):
    @override_settings(DEBUG=False)
    def test_swagger_e_schema_exigem_usuario_interno_em_producao(self):
        for rota in ("/api/docs/", "/api/schema/"):
            self.assertIn(self.client.get(rota).status_code, (401, 403), rota)
            api = APIClient()
            api.force_authenticate(self.portal)
            self.assertEqual(api.get(rota).status_code, 403, rota)
            api.force_authenticate(self.tecnico)
            self.assertEqual(api.get(rota).status_code, 200, rota)

    @override_settings(DEBUG=True)
    def test_em_desenvolvimento_continua_aberto(self):
        self.assertEqual(self.client.get("/api/docs/").status_code, 200)
