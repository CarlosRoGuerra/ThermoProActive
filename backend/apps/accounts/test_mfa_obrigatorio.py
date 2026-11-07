"""
S-25 — MFA obrigatório (`mfa_obrigatorio=True`) sem trancar a conta.

Regra: o login de quem tem o flag e ainda não configurou o 2º fator entrega uma sessão
RESTRITA (`SessaoAutenticacao.mfa_pendente`). Ela só alcança as rotas de configuração
do MFA, renovação, saída e leitura do próprio usuário. Concluir o MFA libera a sessão.
"""
from django.utils import timezone


from apps.accounts.security import _codigo_totp
from apps.accounts.models import Nivel, Perfil


from .test_seguranca_autenticacao import SENHA, _Base, _usuario


class MfaObrigatorioTests(_Base):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.admin = _usuario("admin.mfa@thermo.test", Perfil.GESTOR, Nivel.MASTER, empresa=cls.empresa)
        cls.admin.mfa_obrigatorio = True
        cls.admin.save(update_fields=["mfa_obrigatorio"])

    def _login_admin(self):
        client, csrf, resposta = self.login("admin", self.admin.email)
        self.assertEqual(resposta.status_code, 200, resposta.content)
        return client, csrf, resposta

    def test_login_entrega_sessao_restrita_e_avisa(self):
        _, _, resposta = self._login_admin()
        self.assertTrue(resposta.data["mfa_setup_required"])
        self.assertTrue(_sessoes_pendentes(self.admin) == 1)

    def test_sessao_restrita_nao_alcanca_rotas_comuns(self):
        client, _, _ = self._login_admin()
        self.assertIn(client.get("/api/auth/seguranca/sessoes/").status_code, (401, 403))
        self.assertIn(client.get("/api/auth/seguranca/eventos/").status_code, (401, 403))
        self.assertIn(client.get("/api/clientes/").status_code, (401, 403))

    def test_sessao_restrita_alcanca_me_e_configuracao_do_mfa(self):
        client, csrf, _ = self._login_admin()
        me = client.get("/api/auth/me/")
        self.assertEqual(me.status_code, 200)
        self.assertFalse(me.data["mfa_ativo"])
        self.assertTrue(me.data["mfa_obrigatorio"])
        setup = client.post("/api/auth/mfa/setup/", {}, format="json", **csrf)
        self.assertEqual(setup.status_code, 200)

    def test_concluir_mfa_libera_a_sessao(self):
        client, csrf, _ = self._login_admin()
        segredo = client.post("/api/auth/mfa/setup/", {}, format="json", **csrf).data["secret"]
        passo = int(timezone.now().timestamp() // 30)
        confirma = client.post("/api/auth/mfa/confirm/", {"codigo": _codigo_totp(segredo, passo)},
                               format="json", **csrf)
        self.assertEqual(confirma.status_code, 200)
        self.assertEqual(_sessoes_pendentes(self.admin), 0)
        self.assertEqual(client.get("/api/auth/seguranca/sessoes/").status_code, 200)

    def test_sessao_restrita_pode_sair(self):
        client, csrf, _ = self._login_admin()
        self.assertEqual(client.post("/api/auth/logout/", {}, format="json", **csrf).status_code, 204)

    def test_com_mfa_ja_ativo_login_pede_codigo_e_nao_fica_restrito(self):
        cliente_mfa, segredo = self._ativar_mfa_do_admin()
        self.assertIsNotNone(cliente_mfa)
        _, _, sem_codigo = self.login("admin", self.admin.email)
        self.assertEqual(sem_codigo.status_code, 428)
        passo = int(timezone.now().timestamp() // 30) + 1
        _, _, com_codigo = self.login("admin", self.admin.email, codigo_mfa=_codigo_totp(segredo, passo))
        self.assertEqual(com_codigo.status_code, 200)
        self.assertFalse(com_codigo.data["mfa_setup_required"])

    def test_usuario_sem_o_flag_nao_recebe_sessao_restrita(self):
        _, _, resposta = self.login("portal", self.portal.email)
        self.assertFalse(resposta.data["mfa_setup_required"])
        client, _, _ = self.login("portal", self.portal.email)
        self.assertIn(client.get("/api/auth/seguranca/sessoes/").status_code, (200,))

    def _ativar_mfa_do_admin(self):
        client, csrf, _ = self._login_admin()
        segredo = client.post("/api/auth/mfa/setup/", {}, format="json", **csrf).data["secret"]
        passo = int(timezone.now().timestamp() // 30)
        self.assertEqual(
            client.post("/api/auth/mfa/confirm/", {"codigo": _codigo_totp(segredo, passo)}, format="json",
                        **csrf).status_code, 200)
        return client, segredo


def _sessoes_pendentes(usuario):
    from apps.accounts.models import SessaoAutenticacao
    return SessaoAutenticacao.objects.filter(usuario=usuario, mfa_pendente=True, revogada_em__isnull=True).count()
