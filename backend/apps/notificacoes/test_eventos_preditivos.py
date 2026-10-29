"""Eventos lógicos, isolamento e integração; severidades são pareceres de teste."""
from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import TestCase
from rest_framework.test import APIClient

from apps.cadastros.models import Area, Cliente, Equipamento, Setor
from apps.coletas.models import Inspecao, MedicaoTecnica
from apps.osp.models import OrdemServico

from .models import EstadoEventoPreditivo, EventoNotificacao, EventoPreditivo, Notificacao
from .preditivos import processar_medicao
from .services import notificar


class EventosPreditivosTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cliente = Cliente.objects.create(nome="Cliente dos testes", cnpj="10.222.333/0001-10")
        cls.outro = Cliente.objects.create(nome="Outro cliente", cnpj="20.222.333/0001-20")
        cls.tecnico = get_user_model().objects.create_user(
            email="preditivo@teste.local", nome="Analista", perfil="TECNICO", nivel="MASTER",
        )
        cls.pcm = get_user_model().objects.create_user(
            email="pcm-preditivo@teste.local", nome="PCM", perfil="CLIENTE_PCM", cliente=cls.cliente,
        )
        cls.portal_outro = get_user_model().objects.create_user(
            email="outro-preditivo@teste.local", nome="Outro PCM", perfil="CLIENTE_PCM", cliente=cls.outro,
        )
        setor = Setor.objects.create(area=Area.objects.create(cliente=cls.cliente, nome="Área"), nome="Setor")
        cls.equipamento = Equipamento.objects.create(setor=setor, tag="EQ-EVENTO", nome="Equipamento")
        cls.inspecao = Inspecao.objects.create(
            cliente=cls.cliente, tecnico=cls.tecnico, data=date(2026, 10, 22), tipo_analise="SENSITIVA",
        )

    def medicao(self, criticidade="", **extras):
        dados = dict(
            inspecao=self.inspecao, equipamento=self.equipamento, tipo="SENSITIVA", subtipo="SENSITIVA",
            ponto_medicao="Ponto A", grandeza="Parecer qualitativo", valor=None,
            parametros={"criticidade": criticidade, "observacao": "Parecer sintético do teste"},
            coletado_por=self.tecnico,
        )
        dados.update(extras)
        return MedicaoTecnica.objects.create(**dados)

    def transicao(self, medicao, criticidade):
        medicao.parametros = {"criticidade": criticidade, "observacao": "Parecer revisado do teste"}
        medicao._autor_edicao = self.tecnico.pk
        medicao.save()
        medicao.refresh_from_db()

    def test_pendente_e_normal_nao_geram_alerta_ou_osp(self):
        self.medicao()
        self.medicao("NORMAL", ponto_medicao="B")
        self.assertFalse(EventoPreditivo.objects.exists())
        self.assertFalse(Notificacao.objects.exists())
        self.assertFalse(OrdemServico.objects.exists())

    def test_alerta_preventivo_tem_evidencia_e_destinatarios_unicos_sem_osp(self):
        medicao = self.medicao("ALERTA")
        evento = EventoPreditivo.objects.get()
        self.assertEqual(evento.criticidade, "ALERTA")
        self.assertEqual(evento.medicao_id, medicao.pk)
        self.assertEqual(evento.equipamento_id, self.equipamento.pk)
        self.assertEqual(evento.evidencias["criterio_aplicado"], medicao.criterio_aplicado)
        self.assertEqual(evento.regra_versao, "sensitiva_manual_v2")
        self.assertIn("responsável técnico", evento.orientacao)
        self.assertFalse(OrdemServico.objects.exists())
        notifs = Notificacao.objects.filter(evento_preditivo=evento)
        self.assertEqual(set(notifs.values_list("destinatario_id", flat=True)), {self.tecnico.pk, self.pcm.pk})
        self.assertEqual(notifs.count(), 2)
        notificar(EventoNotificacao.ALERTA_PREDITIVO, [self.tecnico, self.tecnico], "Título", "Mensagem",
                  evento_preditivo=evento)
        self.assertEqual(notifs.count(), 2)

    def test_salvar_recalcular_e_consultar_mesma_criticidade_nao_duplicam(self):
        medicao = self.medicao("CRITICO")
        evento = EventoPreditivo.objects.get()
        evento_antes = evento.evidencias
        contagens = (EventoPreditivo.objects.count(), Notificacao.objects.count(), OrdemServico.objects.count())
        for _ in range(3):
            medicao.save()
            self.assertIsNone(processar_medicao(medicao))
        api = APIClient()
        api.force_authenticate(self.tecnico)
        for _ in range(2):
            self.assertEqual(api.get(f"/api/medicoes-tecnicas/{medicao.pk}/analise-preditiva/").status_code, 200)
            self.assertEqual(api.get(f"/api/eventos-preditivos/{evento.pk}/").status_code, 200)
        self.assertEqual(contagens, (EventoPreditivo.objects.count(), Notificacao.objects.count(), OrdemServico.objects.count()))
        evento.refresh_from_db()
        self.assertEqual(evento.evidencias, evento_antes)

    def test_edicao_para_critico_gera_osp_e_evento_com_autoria(self):
        medicao = self.medicao("NORMAL")
        self.transicao(medicao, "ALERTA")
        self.assertFalse(OrdemServico.objects.exists())
        self.transicao(medicao, "CRITICO")
        self.assertEqual(EventoPreditivo.objects.count(), 2)
        critico = EventoPreditivo.objects.get(criticidade="CRITICO")
        self.assertEqual(critico.criticidade_anterior, "ALERTA")
        self.assertEqual(critico.osp_id, OrdemServico.objects.get().pk)
        self.assertEqual(critico.evidencias["autor_alteracao_id"], self.tecnico.pk)
        self.assertEqual(critico.evidencias["autor_coleta_id"], self.tecnico.pk)

    def test_recuperacao_nao_fecha_osp_e_reincidencia_e_outro_evento(self):
        medicao = self.medicao("CRITICO")
        osp = OrdemServico.objects.get()
        primeiro = EventoPreditivo.objects.get()
        self.transicao(medicao, "NORMAL")
        osp.refresh_from_db()
        self.assertEqual(osp.status, "ABERTA")
        self.transicao(medicao, "CRITICO")
        self.assertEqual(EventoPreditivo.objects.count(), 3)
        self.assertEqual(OrdemServico.objects.count(), 1)
        self.assertEqual(EventoPreditivo.objects.filter(criticidade="CRITICO", osp=osp).count(), 2)
        primeiro.refresh_from_db()
        self.assertEqual(primeiro.criticidade_anterior, "")
        self.assertEqual(primeiro.evidencias["diagnostico"], "Parecer sintético do teste")

    def test_recalculo_de_critico_apos_osp_finalizada_nao_reabre_evento(self):
        medicao = self.medicao("CRITICO")
        osp = OrdemServico.objects.get()
        osp.status = "FINALIZADA"
        osp.save()
        medicao.save()
        processar_medicao(medicao)
        self.assertEqual(OrdemServico.objects.count(), 1)
        self.assertEqual(EventoPreditivo.objects.count(), 1)

    def test_pontos_criticos_distintos_compartilham_osp_aberta_da_inspecao(self):
        self.medicao("CRITICO")
        self.medicao("CRITICO", ponto_medicao="Ponto B")
        self.assertEqual(OrdemServico.objects.count(), 1)
        self.assertEqual(EventoPreditivo.objects.count(), 2)
        self.assertEqual(set(EventoPreditivo.objects.values_list("osp_id", flat=True)), {OrdemServico.objects.get().pk})

    def test_rollback_remove_medicao_evento_notificacao_osp_e_nao_envia_canal(self):
        with patch("apps.notificacoes.channels.enviar_email") as email:
            with self.captureOnCommitCallbacks(execute=True):
                with self.assertRaises(RuntimeError):
                    with transaction.atomic():
                        self.medicao("CRITICO")
                        raise RuntimeError("Simula falha posterior no lançamento")
            email.assert_not_called()
        self.assertFalse(MedicaoTecnica.objects.exists())
        self.assertFalse(EventoPreditivo.objects.exists())
        self.assertFalse(EstadoEventoPreditivo.objects.exists())
        self.assertFalse(Notificacao.objects.exists())
        self.assertFalse(OrdemServico.objects.exists())

    def test_falha_no_evento_reverte_gravacao_da_medicao(self):
        with patch("apps.notificacoes.preditivos.EventoPreditivo.objects.create", side_effect=RuntimeError("Falha")):
            with self.assertRaises(RuntimeError):
                self.medicao("CRITICO")
        self.assertFalse(MedicaoTecnica.objects.exists())
        self.assertFalse(EstadoEventoPreditivo.objects.exists())

    def test_canais_externos_somente_apos_commit_e_uma_vez_por_evento(self):
        from .channels import Resultado

        with patch("apps.notificacoes.channels.enviar_email", return_value=Resultado("ENVIADO")) as email:
            with self.captureOnCommitCallbacks(execute=False) as callbacks:
                medicao = self.medicao("ALERTA")
                email.assert_not_called()
            # Um callback por evento, cobrindo as entregas dos 2 destinatários.
            self.assertEqual(len(callbacks), 1)
            for callback in callbacks:
                callback()
                callback()  # Reexecução do mesmo callback não repete canal confirmado.
            self.assertEqual(email.call_count, 2)
            with self.captureOnCommitCallbacks(execute=True):
                medicao.save()
                processar_medicao(medicao)
            self.assertEqual(email.call_count, 2)

    def test_consulta_eventos_isola_cliente_e_nao_permite_escrita(self):
        self.medicao("ALERTA")
        evento = EventoPreditivo.objects.get()
        api = APIClient()
        api.force_authenticate(self.pcm)
        self.assertEqual(api.get(f"/api/eventos-preditivos/{evento.pk}/").status_code, 200)
        self.assertEqual(api.post("/api/eventos-preditivos/", {}, format="json").status_code, 405)
        api.force_authenticate(self.portal_outro)
        self.assertEqual(api.get(f"/api/eventos-preditivos/{evento.pk}/").status_code, 404)
        self.assertEqual(api.get("/api/eventos-preditivos/").data["count"], 0)

    def test_legado_nao_dispara_alerta_retroativo_ao_salvar_metadados(self):
        medicao = self.medicao()
        MedicaoTecnica.objects.filter(pk=medicao.pk).update(criticidade="CRITICO", classificacao_status="LEGADO")
        medicao.refresh_from_db()
        medicao.save()
        self.assertFalse(EventoPreditivo.objects.exists())
        self.assertFalse(Notificacao.objects.exists())

    def test_replay_sensitivo_usa_parecer_original_apos_correcao(self):
        from apps.coletas.analise_preditiva import replay_medicao
        medicao = self.medicao("ALERTA")
        snapshot = medicao.criterio_aplicado
        self.transicao(medicao, "CRITICO")
        replay = replay_medicao(snapshot)
        self.assertEqual(replay["criticidade"], "ALERTA")
        self.assertEqual(replay["diagnostico_sugerido"], snapshot["saida"]["diagnostico_sugerido"])
        with self.assertRaises(ValueError):
            replay_medicao(dict(snapshot, motor="versao_desconhecida"))

    def test_replay_termico_e_tecnico_inconclusivos_nao_inventam_severidade(self):
        from apps.coletas.analise_preditiva import replay_medicao
        from apps.coletas.models import MedicaoTermografia
        inspecao = Inspecao.objects.create(
            cliente=self.cliente, tecnico=self.tecnico, data=date(2026, 10, 22), tipo_analise="TERMOGRAFIA",
        )
        termo = MedicaoTermografia.objects.create(
            inspecao=inspecao, equipamento=self.equipamento, ponto_medicao="Ponto térmico",
            temperatura_ponto=50, temperatura_referencia=20, emissividade="0.80",
        )
        for medicao in (termo, self.medicao()):
            with self.subTest(motor=medicao.criterio_aplicado["motor"]):
                replay = replay_medicao(medicao.criterio_aplicado)
                self.assertEqual(replay["criticidade"], "")
                self.assertEqual(replay["diagnostico_sugerido"], medicao.diagnostico_sugerido)

    def test_laudo_rastreia_regra_sem_prescrever_intervencao_generica(self):
        from apps.laudos.services import gerar_laudo_de_inspecao
        self.medicao("CRITICO")
        laudo = gerar_laudo_de_inspecao(self.inspecao, self.tecnico)
        self.assertIn("sensitiva_manual_v2", laudo.diagnostico)
        self.assertIn("coletas.medicaotecnica#", laudo.diagnostico)
        self.assertNotIn("imediata", laudo.recomendacoes.lower())
        self.assertIn("responsável técnico", laudo.recomendacoes)
        api = APIClient()
        api.force_authenticate(self.tecnico)
        dashboard = api.get("/api/dashboard/")
        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(dashboard.data["medicoes_por_criticidade"]["CRITICO"], 1)

    def test_unicidade_no_banco_impede_evento_e_notificacao_duplicados(self):
        from django.db import IntegrityError
        self.medicao("ALERTA")
        evento = EventoPreditivo.objects.get()
        with self.assertRaises(IntegrityError), transaction.atomic():
            EventoPreditivo.objects.create(
                medicao_tipo=evento.medicao_tipo, medicao_id=evento.medicao_id, sequencia=evento.sequencia,
                inspecao=evento.inspecao, equipamento=evento.equipamento, regra_versao=evento.regra_versao,
            )
        with self.assertRaises(IntegrityError), transaction.atomic():
            Notificacao.objects.create(destinatario=self.tecnico, evento_preditivo=evento,
                                        evento=EventoNotificacao.ALERTA_PREDITIVO, titulo="Repetido", mensagem="Repetido")

    def test_instancia_desatualizada_nao_emite_alerta_de_resultado_legado(self):
        for status in ("LEGADO", "CLASSIFICADA"):
            with self.subTest(status=status):
                medicao = self.medicao()
                MedicaoTecnica.objects.filter(pk=medicao.pk).update(
                    criticidade="CRITICO", classificacao_status=status, criterio_aplicado={"origem": "acervo anterior"},
                )
                self.assertIsNone(processar_medicao(medicao))
                self.assertFalse(EventoPreditivo.objects.exists())
