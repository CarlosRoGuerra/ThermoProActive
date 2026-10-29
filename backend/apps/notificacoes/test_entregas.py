"""
Notificações (Anexo I 2.10): os cinco eventos, os quatro canais, falhas,
retentativas, idempotência, isolamento entre clientes e sigilo de credenciais.

Nenhum teste "entrega" de verdade: o SMTP é um backend de teste que aceita,
recusa ou cai; o gateway de WhatsApp é o `urlopen` substituído. O que se prova é
que o sistema só marca ENVIADO quando o provedor aceita.
"""
import io
import json
import smtplib
import urllib.error
from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.mail.backends.base import BaseEmailBackend
from django.core.management import call_command
from django.db import transaction
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.cadastros.models import Area, Cliente, Equipamento, Setor
from apps.coletas.models import Inspecao, MedicaoTecnica
from apps.osp import services as osp_services
from apps.osp.models import OrdemServico

from . import channels, entregas
from .models import EntregaNotificacao, EventoNotificacao, Notificacao, PreferenciaNotificacao
from .services import notificar

User = get_user_model()
BACKEND = "apps.notificacoes.test_entregas.BackendTeste"
SEGREDO_SMTP = "s3nh4-SMTP-sup3r-secreta"
SEGREDO_WA = "tok-WA-9f8e7d6c5b4a"


class BackendTeste(BaseEmailBackend):
    """SMTP de mentira controlado pelo teste: 'aceita', 'zero' ou uma exceção."""

    comportamento = "aceita"
    caixa: list = []

    def send_messages(self, mensagens):
        c = type(self).comportamento
        if c == "aceita":
            type(self).caixa.extend(mensagens)
            return len(mensagens)
        if c == "zero":
            return 0
        raise c


class Resposta:
    def __init__(self, status=200, corpo=b'{"id": "wamid.123"}'):
        self.status, self._corpo = status, corpo

    def read(self, *_):
        return self._corpo

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a = Cliente.objects.create(nome="Indústria A", cnpj="11.111.111/0001-11")
        cls.b = Cliente.objects.create(nome="Indústria B", cnpj="22.222.222/0001-22")
        setor = Setor.objects.create(area=Area.objects.create(cliente=cls.a, nome="Área"), nome="Setor")
        cls.eq = Equipamento.objects.create(setor=setor, tag="AA-01", nome="Bomba")

        def u(email, perfil, cliente=None, **extra):
            return User.objects.create_user(email=email, nome=email.split("@")[0], perfil=perfil,
                                            cliente=cliente, password="SenhaSuperForte#2026!!", **extra)

        cls.gestor = u("gestor@t.com", "GESTOR")
        cls.tecnico = u("tecnico@t.com", "TECNICO", celular="(11) 98765-4321")
        cls.pcm_a = u("pcm@a.com", "CLIENTE_PCM", cls.a, celular="11987654321")
        cls.corp_a = u("corp@a.com", "CLIENTE_CORP", cls.a)
        cls.pcm_b = u("pcm@b.com", "CLIENTE_PCM", cls.b)
        cls.suspenso = u("suspenso@a.com", "CLIENTE_PCM", cls.a, estado="SUSPENDED")

    def setUp(self):
        BackendTeste.comportamento = "aceita"
        BackendTeste.caixa = []

    def avisos(self, evento):
        return set(Notificacao.objects.filter(evento=evento).values_list("destinatario__email", flat=True))

    def uma_notificacao(self, user=None, **extra):
        user = user or self.gestor
        with self.captureOnCommitCallbacks(execute=False):
            notificar(EventoNotificacao.NOVA_OSP, [user], "Título", "Mensagem", cliente=self.a, **extra)
        return Notificacao.objects.filter(destinatario=user).latest("id")

    def entrega(self, user=None, canal="EMAIL"):
        return EntregaNotificacao.objects.filter(notificacao__destinatario=user or self.gestor, canal=canal).latest("id")


# --------------------------------------------------------------------------- eventos

class CincoEventos(Base):
    def test_nova_osp_vai_ao_pcm_do_cliente_e_ao_responsavel(self):
        OrdemServico.objects.create(cliente=self.a, equipamento=self.eq, titulo="x", responsavel=self.tecnico)
        self.assertEqual(self.avisos("NOVA_OSP"), {"pcm@a.com", "tecnico@t.com"})  # suspenso e B fora

    def test_equipamento_critico_vai_ao_pcm_e_ao_tecnico_da_inspecao(self):
        insp = Inspecao.objects.create(cliente=self.a, tecnico=self.tecnico, data=date(2026, 10, 1),
                                       tipo_analise="SENSITIVA")
        MedicaoTecnica.objects.create(
            inspecao=insp, equipamento=self.eq, tipo="SENSITIVA", subtipo="SENSITIVA", ponto_medicao="P",
            grandeza="Parecer qualitativo", valor=None, parametros={"criticidade": "CRITICO", "observacao": "x"},
            coletado_por=self.tecnico,
        )
        self.assertEqual(self.avisos("EQUIPAMENTO_CRITICO"), {"pcm@a.com", "tecnico@t.com"})

    def test_laudo_concluido_usa_chave_e_cliente_do_laudo(self):
        """O disparo na emissão é coberto em laudos/test_conformidade_documentos; aqui, a regra de destino."""
        from .services import clientes_do_cliente

        for _ in range(2):  # emissão repetida
            notificar(EventoNotificacao.LAUDO_CONCLUIDO, clientes_do_cliente(self.a), "Laudo", "ok",
                      chave="laudo_emitido:1", cliente=self.a)
        self.assertEqual(self.avisos("LAUDO_CONCLUIDO"), {"pcm@a.com", "corp@a.com"})
        self.assertEqual(Notificacao.objects.filter(evento="LAUDO_CONCLUIDO").count(), 2)

    def test_sla_vencendo_vai_a_gestao_e_ao_responsavel_uma_vez(self):
        osp = OrdemServico.objects.create(cliente=self.a, equipamento=self.eq, titulo="x", responsavel=self.tecnico)
        OrdemServico.objects.filter(pk=osp.pk).update(sla_data=timezone.localdate() - timedelta(days=1))
        for _ in range(3):
            call_command("agendador", "--uma-vez", stdout=io.StringIO())
        self.assertEqual(self.avisos("SLA_VENCENDO"), {"gestor@t.com", "tecnico@t.com"})
        self.assertEqual(Notificacao.objects.filter(evento="SLA_VENCENDO").count(), 2)

    def test_aprovacao_pendente_vai_a_quem_aprova(self):
        osp = OrdemServico.objects.create(cliente=self.a, equipamento=self.eq, titulo="x", responsavel=self.tecnico)
        OrdemServico.objects.filter(pk=osp.pk).update(status="EM_EXECUCAO")
        osp_services.transicionar(osp.pk, "AGUARDANDO_APROVACAO", self.tecnico)
        self.assertEqual(self.avisos("APROVACAO_PENDENTE"), {"gestor@t.com"})

    @override_settings(OSP_APROVACAO_PELO_CLIENTE=True)
    def test_aprovacao_pendente_inclui_aprovadores_do_cliente_quando_habilitado(self):
        osp = OrdemServico.objects.create(cliente=self.a, equipamento=self.eq, titulo="x")
        OrdemServico.objects.filter(pk=osp.pk).update(status="EM_EXECUCAO")
        osp_services.transicionar(osp.pk, "AGUARDANDO_APROVACAO", self.tecnico)
        self.assertEqual(self.avisos("APROVACAO_PENDENTE"), {"gestor@t.com", "pcm@a.com", "corp@a.com"})


# ------------------------------------------------------------------- destinatários

class Destinatarios(Base):
    def test_usuario_do_portal_de_outra_empresa_nunca_recebe(self):
        with self.captureOnCommitCallbacks():
            notificar("NOVA_OSP", [self.pcm_a, self.pcm_b, self.gestor], "t", "m", cliente=self.a)
            notificar("NOVA_OSP", [self.pcm_a, self.pcm_b], "t", "m")  # sem cliente: nenhum do Portal
        self.assertEqual(set(Notificacao.objects.values_list("destinatario__email", flat=True)),
                         {"pcm@a.com", "gestor@t.com"})
        self.assertEqual(Notificacao.objects.filter(destinatario=self.pcm_a).count(), 1)

    def test_conta_inativa_ou_suspensa_nao_recebe(self):
        inativo = User.objects.create_user(email="ex@t.com", nome="ex", perfil="TECNICO", is_active=False)
        with self.captureOnCommitCallbacks():
            notificar("NOVA_OSP", [inativo, self.suspenso, self.gestor], "t", "m", cliente=self.a)
        self.assertEqual(list(Notificacao.objects.values_list("destinatario__email", flat=True)), ["gestor@t.com"])

    def test_conta_desativada_depois_do_evento_nao_recebe_o_canal_externo(self):
        n = self.uma_notificacao(self.tecnico)
        User.objects.filter(pk=self.tecnico.pk).update(estado="BLOCKED")
        with override_settings(EMAIL_BACKEND=BACKEND):
            entregas.processar_pendentes()
        e = self.entrega(self.tecnico)
        self.assertEqual(e.status, "IGNORADO")
        self.assertEqual(BackendTeste.caixa, [])
        self.assertTrue(Notificacao.objects.filter(pk=n.pk).exists())  # alerta interno permanece

    def test_preferencias_definem_os_canais_e_o_interno_nao_desliga(self):
        PreferenciaNotificacao.objects.create(user=self.pcm_a, email=False, whatsapp=True, push=True)
        n = self.uma_notificacao(self.pcm_a)
        self.assertEqual(set(n.entregas.values_list("canal", flat=True)), {"WHATSAPP", "PUSH"})
        api = APIClient()
        api.force_authenticate(self.pcm_a)
        r = api.put("/api/notificacoes/preferencias/", {"interno": False, "email": True}, format="json")
        self.assertEqual((r.data["interno"], r.data["email"]), (True, True))

    def test_api_mostra_estado_por_canal_sem_o_texto_do_erro(self):
        self.uma_notificacao(self.pcm_a)
        BackendTeste.comportamento = smtplib.SMTPRecipientsRefused({"pcm@a.com": (550, b"no")})
        with override_settings(EMAIL_BACKEND=BACKEND):
            entregas.processar_pendentes()
        api = APIClient()
        api.force_authenticate(self.pcm_a)
        item = api.get("/api/notificacoes/").data["results"][0]
        self.assertEqual(item["entregas"][0]["status"], "FALHOU")
        self.assertNotIn("ultimo_erro", item["entregas"][0])


# ------------------------------------------------------------------------- e-mail

class CanalEmail(Base):
    def test_backend_de_desenvolvimento_e_simulado_e_nao_conta_como_enviado(self):
        n = self.uma_notificacao()
        entregas.processar_pendentes()  # locmem do test runner
        e = self.entrega()
        self.assertEqual(e.status, "SIMULADO")
        self.assertEqual(Notificacao.objects.get(pk=n.pk).canais_enviados, ["INTERNO"])

    @override_settings(EMAIL_BACKEND=BACKEND)
    def test_smtp_aceitou_marca_enviado_com_data(self):
        n = self.uma_notificacao()
        self.assertEqual(entregas.processar_pendentes(), {"ENVIADO": 1})
        e = self.entrega()
        self.assertEqual((e.status, e.tentativas), ("ENVIADO", 1))
        self.assertIsNotNone(e.enviado_em)
        self.assertEqual(Notificacao.objects.get(pk=n.pk).canais_enviados, ["INTERNO", "EMAIL"])
        self.assertEqual(BackendTeste.caixa[0].extra_headers["X-Notificacao-Id"], f"notif-{n.pk}-EMAIL")
        # Rodar de novo não reenvia o que o provedor já aceitou.
        entregas.processar_pendentes()
        entregas.reprocessar()
        entregas.processar_pendentes()
        self.assertEqual(len(BackendTeste.caixa), 1)

    @override_settings(EMAIL_BACKEND=BACKEND, NOTIFICACOES_MAX_TENTATIVAS=3)
    def test_queda_do_smtp_tenta_de_novo_com_espera_e_depois_falha(self):
        self.uma_notificacao()
        BackendTeste.comportamento = smtplib.SMTPServerDisconnected(f"conexão perdida (senha {SEGREDO_SMTP})")
        with override_settings(EMAIL_HOST_PASSWORD=SEGREDO_SMTP):
            entregas.processar_pendentes()
            e = self.entrega()
            self.assertEqual((e.status, e.tentativas), ("PENDENTE", 1))
            self.assertGreater(e.proxima_tentativa_em, timezone.now() + timedelta(seconds=30))
            self.assertNotIn(SEGREDO_SMTP, e.ultimo_erro)
            self.assertEqual(entregas.processar_pendentes(), {})  # ainda não chegou a hora
            for _ in range(2):
                EntregaNotificacao.objects.filter(pk=e.pk).update(proxima_tentativa_em=timezone.now())
                entregas.processar_pendentes()
        e.refresh_from_db()
        self.assertEqual((e.status, e.tentativas), ("FALHOU", 3))
        self.assertIsNone(e.enviado_em)
        self.assertIn("SMTPServerDisconnected", e.ultimo_erro)

    @override_settings(EMAIL_BACKEND=BACKEND)
    def test_recusa_definitiva_nao_e_repetida(self):
        self.uma_notificacao()
        BackendTeste.comportamento = smtplib.SMTPRecipientsRefused({"gestor@t.com": (550, b"unknown user")})
        entregas.processar_pendentes()
        e = self.entrega()
        self.assertEqual((e.status, e.tentativas), ("FALHOU", 1))
        self.assertNotIn("gestor@t.com", e.ultimo_erro)

    @override_settings(EMAIL_BACKEND=BACKEND)
    def test_backend_que_nao_confirma_nao_vira_enviado(self):
        self.uma_notificacao()
        BackendTeste.comportamento = "zero"
        entregas.processar_pendentes()
        self.assertEqual(self.entrega().status, "PENDENTE")

    def test_usuario_sem_email_e_ignorado(self):
        sem = User.objects.create_user(email="x@t.com", nome="x", perfil="TECNICO")
        User.objects.filter(pk=sem.pk).update(email="")
        sem.refresh_from_db()
        self.uma_notificacao(sem)
        entregas.processar_pendentes()
        self.assertEqual(self.entrega(sem).status, "IGNORADO")


# ----------------------------------------------------------------------- WhatsApp

@override_settings(NOTIFICACOES_WHATSAPP_ENABLED=True, WHATSAPP_WEBHOOK_URL="https://gw.exemplo/enviar",
                   WHATSAPP_WEBHOOK_TOKEN=SEGREDO_WA)
class CanalWhatsApp(Base):
    def setUp(self):
        super().setUp()
        PreferenciaNotificacao.objects.create(user=self.pcm_a, email=False, whatsapp=True)

    def enviar(self, resposta=None, erro=None):
        self.uma_notificacao(self.pcm_a)
        with patch("apps.notificacoes.channels.urllib.request.urlopen",
                   side_effect=erro, return_value=resposta or Resposta()) as urlopen:
            entregas.processar_pendentes()
        return self.entrega(self.pcm_a, "WHATSAPP"), urlopen

    def test_gateway_aceitou(self):
        e, urlopen = self.enviar()
        self.assertEqual((e.status, e.provedor_id), ("ENVIADO", "wamid.123"))
        req = urlopen.call_args.args[0]
        self.assertEqual(json.loads(req.data)["to"], "5511987654321")
        self.assertEqual(req.get_header("Authorization"), f"Bearer {SEGREDO_WA}")
        self.assertTrue(req.get_header("Idempotency-key").startswith("notif-"))
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 10)

    def test_gateway_respondeu_2xx_mas_recusou(self):
        e, _ = self.enviar(Resposta(200, b'{"accepted": false, "error": "numero sem WhatsApp"}'))
        self.assertEqual(e.status, "FALHOU")

    def test_erro_5xx_e_timeout_sao_temporarios(self):
        e, _ = self.enviar(erro=urllib.error.HTTPError("u", 503, "x", {}, None))
        self.assertEqual((e.status, e.tentativas), ("PENDENTE", 1))
        EntregaNotificacao.objects.filter(pk=e.pk).update(proxima_tentativa_em=timezone.now())
        with patch("apps.notificacoes.channels.urllib.request.urlopen", side_effect=TimeoutError("timed out")):
            entregas.processar_pendentes()
        e.refresh_from_db()
        self.assertEqual((e.status, e.tentativas), ("PENDENTE", 2))

    def test_erro_4xx_e_definitivo_e_nao_vaza_token(self):
        e, _ = self.enviar(erro=urllib.error.HTTPError("u", 401, f"token {SEGREDO_WA} inválido", {}, None))
        self.assertEqual((e.status, e.tentativas), ("FALHOU", 1))
        self.assertNotIn(SEGREDO_WA, e.ultimo_erro)

    def test_sem_celular_valido_e_ignorado(self):
        User.objects.filter(pk=self.pcm_a.pk).update(celular="123")
        e, urlopen = self.enviar()
        self.assertEqual(e.status, "IGNORADO")
        urlopen.assert_not_called()

    @override_settings(WHATSAPP_WEBHOOK_URL="")
    def test_sem_url_nao_configurado_sem_revelar_valores(self):
        e, urlopen = self.enviar()
        self.assertEqual(e.status, "NAO_CONFIGURADO")
        self.assertIn("WHATSAPP_WEBHOOK_URL", e.ultimo_erro)
        self.assertNotIn(SEGREDO_WA, e.ultimo_erro)
        urlopen.assert_not_called()


class CanalWhatsAppDesligadoEPush(Base):
    def test_whatsapp_desligado_e_push_nunca_dizem_enviado(self):
        PreferenciaNotificacao.objects.create(user=self.pcm_a, email=False, whatsapp=True, push=True)
        self.uma_notificacao(self.pcm_a)
        with override_settings(NOTIFICACOES_PUSH_ENABLED=True):
            entregas.processar_pendentes()
        self.assertEqual(self.entrega(self.pcm_a, "WHATSAPP").status, "NAO_CONFIGURADO")
        self.assertEqual(self.entrega(self.pcm_a, "PUSH").status, "NAO_CONFIGURADO")
        self.assertEqual(Notificacao.objects.get(destinatario=self.pcm_a).canais_enviados, ["INTERNO"])

    @override_settings(EMAIL_BACKEND=BACKEND, NOTIFICACOES_WHATSAPP_ENABLED=True,
                       WHATSAPP_WEBHOOK_URL="https://gw", WHATSAPP_WEBHOOK_TOKEN="t0k3n")
    def test_reprocessar_depois_de_configurar(self):
        PreferenciaNotificacao.objects.create(user=self.pcm_a, email=False, whatsapp=True)
        with override_settings(NOTIFICACOES_WHATSAPP_ENABLED=False):
            self.uma_notificacao(self.pcm_a)
            entregas.processar_pendentes()
        e = self.entrega(self.pcm_a, "WHATSAPP")
        self.assertEqual(e.status, "NAO_CONFIGURADO")
        out = io.StringIO()
        with patch("apps.notificacoes.channels.urllib.request.urlopen", return_value=Resposta()):
            call_command("processar_notificacoes", "--reprocessar", "--canal", "WHATSAPP", stdout=out)
        e.refresh_from_db()
        self.assertEqual(e.status, "ENVIADO")


# --------------------------------------------------- idempotência e concorrência

class IdempotenciaEFalhas(Base):
    def test_mesma_chave_nao_duplica_notificacao_nem_entrega(self):
        for _ in range(3):
            self.uma_notificacao(chave="nova_osp:7")
        self.assertEqual(Notificacao.objects.filter(chave="nova_osp:7").count(), 1)
        self.assertEqual(EntregaNotificacao.objects.count(), 1)
        self.uma_notificacao(chave="nova_osp:8")
        self.assertEqual(Notificacao.objects.count(), 2)

    @override_settings(EMAIL_BACKEND=BACKEND)
    def test_entrega_reivindicada_nao_e_enviada_por_outro_processo(self):
        self.uma_notificacao()
        e = self.entrega()
        self.assertIsNotNone(entregas._reivindicar(e.pk))   # processo 1 pegou (lease)
        self.assertIsNone(entregas._reivindicar(e.pk))      # processo 2 não pega
        self.assertIsNone(entregas.processar_entrega(e.pk))
        self.assertEqual(BackendTeste.caixa, [])

    def test_rollback_da_operacao_nao_deixa_aviso_nem_envio(self):
        with patch("apps.notificacoes.channels.enviar_email") as email:
            with self.captureOnCommitCallbacks(execute=True):
                try:
                    with transaction.atomic():
                        notificar("NOVA_OSP", [self.gestor], "t", "m", cliente=self.a, chave="x:1")
                        raise RuntimeError("operação principal falhou")
                except RuntimeError:
                    pass
        email.assert_not_called()
        self.assertFalse(Notificacao.objects.exists())
        self.assertFalse(EntregaNotificacao.objects.exists())

    @override_settings(EMAIL_BACKEND=BACKEND)
    def test_email_fora_do_ar_nao_interrompe_a_operacao_ja_gravada(self):
        BackendTeste.comportamento = ConnectionRefusedError("smtp fora do ar")
        osp = OrdemServico.objects.create(cliente=self.a, equipamento=self.eq, titulo="x")
        OrdemServico.objects.filter(pk=osp.pk).update(status="EM_EXECUCAO")
        api = APIClient()
        api.force_authenticate(self.tecnico)
        with self.captureOnCommitCallbacks(execute=True):
            r = api.patch(f"/api/osps/{osp.pk}/status/", {"status": "AGUARDANDO_APROVACAO"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(OrdemServico.objects.get(pk=osp.pk).status, "AGUARDANDO_APROVACAO")
        e = self.entrega(self.gestor)  # aviso de aprovação pendente ao gestor
        self.assertEqual((e.status, e.tentativas), ("PENDENTE", 1))  # fica para o agendador

    @override_settings(EMAIL_BACKEND=BACKEND)
    def test_adaptador_com_defeito_nao_derruba_o_lote(self):
        self.uma_notificacao(self.gestor)
        self.uma_notificacao(self.tecnico)
        original = channels.enviar_email

        def quebra_no_gestor(user, *a, **k):
            if user.pk == self.gestor.pk:
                raise KeyError("bug")
            return original(user, *a, **k)

        with patch("apps.notificacoes.channels.enviar_email", side_effect=quebra_no_gestor):
            entregas.processar_pendentes()
        self.assertEqual(self.entrega(self.gestor).status, "PENDENTE")
        self.assertEqual(self.entrega(self.tecnico).status, "ENVIADO")

    def test_reprocessar_so_mexe_em_falha_e_nao_configurado(self):
        n = self.uma_notificacao()
        e = self.entrega()
        for status in ("ENVIADO", "SIMULADO", "IGNORADO", "PENDENTE"):
            EntregaNotificacao.objects.filter(pk=e.pk).update(status=status)
            self.assertEqual(entregas.reprocessar(), 0, status)
        EntregaNotificacao.objects.filter(pk=e.pk).update(status="FALHOU", tentativas=5)
        self.assertEqual(entregas.reprocessar(), 1)
        e.refresh_from_db()
        self.assertEqual((e.status, e.tentativas), ("PENDENTE", 0))
        self.assertTrue(n.pk)

    def test_falha_no_log_nao_expoe_destinatario(self):
        self.uma_notificacao()
        with override_settings(EMAIL_BACKEND=BACKEND, NOTIFICACOES_MAX_TENTATIVAS=1):
            BackendTeste.comportamento = smtplib.SMTPServerDisconnected("caiu para gestor@t.com")
            with self.assertLogs("notificacoes", level="WARNING") as logs:
                entregas.processar_pendentes()
        self.assertNotIn("gestor@t.com", "\n".join(logs.output))


# --------------------------------------------------------------- credenciais

class Credenciais(Base):
    @override_settings(EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend", EMAIL_HOST="smtp.exemplo",
                       EMAIL_HOST_USER="robo@exemplo", EMAIL_HOST_PASSWORD=SEGREDO_SMTP,
                       NOTIFICACOES_WHATSAPP_ENABLED=True, WHATSAPP_WEBHOOK_URL="https://gw.secreto/x",
                       WHATSAPP_WEBHOOK_TOKEN=SEGREDO_WA)
    def test_diagnostico_mostra_estado_sem_valores(self):
        out = io.StringIO()
        call_command("verificar_canais", stdout=out)
        texto = out.getvalue()
        self.assertIn("EMAIL     OPERACIONAL", texto)
        self.assertIn("WHATSAPP  OPERACIONAL", texto)
        self.assertIn("PUSH      NÃO CONFIGURADO", texto)
        for segredo in (SEGREDO_SMTP, SEGREDO_WA, "robo@exemplo", "smtp.exemplo", "gw.secreto"):
            self.assertNotIn(segredo, texto)

    def test_diagnostico_em_desenvolvimento(self):
        out = io.StringIO()
        call_command("verificar_canais", stdout=out)
        self.assertIn("EMAIL     NÃO CONFIGURADO", out.getvalue())
        self.assertIn("WHATSAPP  NÃO CONFIGURADO", out.getvalue())

    def test_sanitizar(self):
        with override_settings(EMAIL_HOST_PASSWORD=SEGREDO_SMTP):
            texto = channels.sanitizar(
                f"auth {SEGREDO_SMTP} Bearer abc.def token=xyz para fulano@empresa.com tel +55 (11) 98765-4321"
            )
        for proibido in (SEGREDO_SMTP, "abc.def", "xyz", "fulano@empresa.com", "98765-4321"):
            self.assertNotIn(proibido, texto)
