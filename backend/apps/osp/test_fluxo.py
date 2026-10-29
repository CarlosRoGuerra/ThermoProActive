"""
Fluxo da OSP (Anexo I 2.6): geração sem duplicidade, máquina de estados com
permissão por perfil, histórico, SLA, escopo por cliente, painéis e falhas parciais.

Quando um teste fixa uma REGRA AINDA NÃO CONFIRMADA pelo cliente, o docstring diz
"PENDENTE" — se a regra mudar, é o teste que deve mudar junto (lista completa em
docs/15-OSP-FLUXO-ANEXO-I-2.6.md).
"""
import threading
from datetime import date, timedelta
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError, connection
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.cadastros.models import Area, Cliente, Equipamento, Setor
from apps.coletas.models import Inspecao, MedicaoTecnica
from apps.notificacoes.models import EventoNotificacao, EventoPreditivo, Notificacao
from apps.osp import services
from apps.osp.models import (
    TRANSICOES, HistoricoOSP, OrdemServico, StatusOSP, TipoHistorico,
)

User = get_user_model()
SENHA = "SenhaSuperForte#2026!!"


class BaseFluxo(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cliente = Cliente.objects.create(nome="Indústria A", cnpj="11.111.111/0001-11")
        cls.outro = Cliente.objects.create(nome="Indústria B", cnpj="22.222.222/0001-22")
        setor = Setor.objects.create(area=Area.objects.create(cliente=cls.cliente, nome="Utilidades"), nome="Bombas")
        cls.equipamento = Equipamento.objects.create(setor=setor, tag="BB-01", nome="Bomba 01")
        setor_b = Setor.objects.create(area=Area.objects.create(cliente=cls.outro, nome="Área B"), nome="Setor B")
        cls.equipamento_b = Equipamento.objects.create(setor=setor_b, tag="BB-99", nome="Bomba B")

        def usuario(email, perfil, cliente=None, nivel="PLENO"):
            return User.objects.create_user(
                email=email, password=SENHA, nome=email.split("@")[0], perfil=perfil,
                nivel=nivel, cliente=cliente,
            )

        cls.admin = usuario("admin@thermo.com", "ADMIN", nivel="MASTER")
        cls.gestor = usuario("gestor@thermo.com", "GESTOR")
        cls.tecnico = usuario("tecnico@thermo.com", "TECNICO")
        cls.tecnico2 = usuario("tecnico2@thermo.com", "TECNICO")
        cls.pcm = usuario("pcm@a.com", "CLIENTE_PCM", cls.cliente)
        cls.corp = usuario("corp@a.com", "CLIENTE_CORP", cls.cliente, nivel="MASTER")
        cls.manut = usuario("manut@a.com", "CLIENTE_MANUT", cls.cliente, nivel="JUNIOR")
        cls.pcm_b = usuario("pcm@b.com", "CLIENTE_PCM", cls.outro)

    def setUp(self):
        self.api = APIClient()

    def logar(self, user):
        self.api.force_authenticate(user)
        return self.api

    def nova_osp(self, **extras):
        dados = dict(cliente=self.cliente, equipamento=self.equipamento, titulo="Bomba 01 — rolamento",
                     responsavel=self.tecnico, grau_risco="GR3")
        dados.update(extras)
        return OrdemServico.objects.create(**dados)

    def forcar_status(self, osp, status):
        """Prepara o cenário sem passar pela API (atalho de teste, não do produto)."""
        OrdemServico.objects.filter(pk=osp.pk).update(status=status)
        osp.refresh_from_db()
        return osp

    def mover(self, user, osp, status, motivo=None):
        corpo = {"status": status}
        if motivo is not None:
            corpo["motivo"] = motivo
        return self.logar(user).patch(f"/api/osps/{osp.pk}/status/", corpo, format="json")


class GeracaoAutomaticaTest(BaseFluxo):
    """2.6.1.1 — uma ocorrência crítica gera a OSP esperada, uma única vez."""

    def setUp(self):
        super().setUp()
        self.inspecao = Inspecao.objects.create(
            cliente=self.cliente, tecnico=self.tecnico, data=date(2026, 10, 22), tipo_analise="SENSITIVA",
        )

    def medicao(self, criticidade, ponto="Ponto A"):
        return MedicaoTecnica.objects.create(
            inspecao=self.inspecao, equipamento=self.equipamento, tipo="SENSITIVA", subtipo="SENSITIVA",
            ponto_medicao=ponto, grandeza="Parecer qualitativo", valor=None,
            parametros={"criticidade": criticidade, "observacao": "Parecer sintético"},
            coletado_por=self.tecnico,
        )

    def test_medicao_critica_gera_osp_completa_e_com_historico(self):
        self.medicao("CRITICO")
        osp = OrdemServico.objects.get()
        self.assertTrue(osp.gerada_automaticamente)
        self.assertEqual(osp.prioridade, "ALTA")
        self.assertEqual(osp.status, "ABERTA")
        self.assertEqual(osp.equipamento_id, self.equipamento.pk)
        self.assertEqual(osp.responsavel_id, self.tecnico.pk)  # 2.6.1.1.4
        self.assertEqual(osp.criticidade_origem, "CRITICO")
        # SLA persistido e verificável: GR-2 manda (10 dias), com a origem registrada.
        self.assertEqual(osp.grau_risco, "GR2")
        self.assertEqual(osp.sla_data, timezone.localdate() + timedelta(days=10))
        self.assertEqual(osp.sla_origem, "GRAU_RISCO")
        criacao = osp.historico.get()
        self.assertEqual(criacao.tipo, TipoHistorico.CRIACAO)
        self.assertEqual(criacao.ator_nome, "Sistema")
        self.assertEqual(criacao.alteracoes["origem"], "AUTOMATICA")
        # 2.6.1.1.6 — notifica o PCM do cliente e o técnico responsável, só uma vez cada.
        nova = Notificacao.objects.filter(evento=EventoNotificacao.NOVA_OSP)
        self.assertEqual(set(nova.values_list("destinatario_id", flat=True)), {self.pcm.pk, self.tecnico.pk})
        self.assertEqual(nova.count(), 2)

    def test_alerta_e_normal_nao_geram_osp(self):
        self.medicao("ALERTA", "B")
        self.medicao("NORMAL", "C")
        self.assertFalse(OrdemServico.objects.exists())

    def test_reprocessar_e_repetir_a_chamada_nao_duplicam(self):
        medicao = self.medicao("CRITICO")
        osp = OrdemServico.objects.get()
        for _ in range(3):
            medicao.save()
            self.assertEqual(services.gerar_osp_de_medicao(medicao, "x", retornar_existente=True).pk, osp.pk)
            self.assertIsNone(services.gerar_osp_de_medicao(medicao, "x"))
        self.assertEqual(OrdemServico.objects.count(), 1)
        self.assertEqual(osp.historico.count(), 1)

    def test_pontos_diferentes_do_mesmo_equipamento_compartilham_a_osp(self):
        self.medicao("CRITICO", "Mancal LA")
        self.medicao("CRITICO", "Mancal LOA")
        self.assertEqual(OrdemServico.objects.count(), 1)
        self.assertEqual(EventoPreditivo.objects.count(), 2)  # 2 eventos, 1 ordem
        self.assertEqual(EventoPreditivo.objects.filter(osp__isnull=False).count(), 2)

    def test_restricao_do_banco_barra_segunda_osp_automatica_aberta(self):
        """Rede de segurança: mesmo que o código falhe, o banco não aceita a duplicata."""
        self.medicao("CRITICO")
        with self.assertRaises(IntegrityError):
            OrdemServico.objects.create(
                cliente=self.cliente, equipamento=self.equipamento, inspecao=self.inspecao,
                titulo="duplicada", gerada_automaticamente=True,
            )

    def test_corrida_perdida_devolve_a_osp_vencedora(self):
        """
        Duas gerações simultâneas passam juntas pela consulta (leitura velha); a
        que perde a corrida bate na restrição única e recebe a OSP que ganhou.
        """
        medicao = self.medicao("ALERTA")
        MedicaoTecnica.objects.filter(pk=medicao.pk).update(
            parametros={"criticidade": "CRITICO", "observacao": "x"}, criticidade="CRITICO",
        )
        medicao.refresh_from_db()
        vencedora = OrdemServico.objects.create(
            cliente=self.cliente, equipamento=self.equipamento, inspecao=self.inspecao,
            titulo="vencedora", gerada_automaticamente=True,
        )
        filtrar = OrdemServico.objects.filter
        leituras = []

        def primeira_leitura_e_velha(*args, **kwargs):
            leituras.append(1)
            return OrdemServico.objects.none() if len(leituras) == 1 else filtrar(*args, **kwargs)

        with patch.object(OrdemServico.objects, "filter", side_effect=primeira_leitura_e_velha):
            resultado = services.gerar_osp_de_medicao(medicao, "x", retornar_existente=True)
        self.assertEqual(resultado.pk, vencedora.pk)
        self.assertEqual(OrdemServico.objects.count(), 1)
        self.assertGreaterEqual(len(leituras), 2)  # releu depois do conflito

    def test_colisao_de_numeracao_tenta_de_novo_com_outro_numero(self):
        primeira = self.nova_osp()
        with patch.object(OrdemServico, "proximo_numero", side_effect=[primeira.numero, "OSP-2099-0001"]):
            segunda = self.nova_osp(titulo="segunda")
        self.assertEqual(segunda.numero, "OSP-2099-0001")
        self.assertNotEqual(segunda.sequencial_global, None)
        self.assertEqual(OrdemServico.objects.count(), 2)

    def test_sequencial_global_nunca_repete(self):
        a, b = self.nova_osp(), self.nova_osp(titulo="b")
        self.assertNotEqual(a.sequencial_global, b.sequencial_global)
        with self.assertRaises(IntegrityError):
            OrdemServico.objects.filter(pk=b.pk).update(sequencial_global=a.sequencial_global)

    def test_falha_parcial_nao_deixa_estado_meio_gravado_e_o_reenvio_conclui(self):
        """
        O envio da notificação cai DEPOIS da OSP ser criada: a gravação inteira
        volta atrás (sem medição sem OSP, sem OSP órfã, sem evento "consumido"),
        e o reenvio produz exatamente uma OSP.
        """
        with patch("apps.notificacoes.preditivos.notificar", side_effect=RuntimeError("fila fora do ar")):
            with self.assertRaises(RuntimeError):
                self.medicao("CRITICO")
        self.assertFalse(OrdemServico.objects.exists())
        self.assertFalse(EventoPreditivo.objects.exists())
        self.assertFalse(MedicaoTecnica.objects.exists())
        medicao = self.medicao("CRITICO")  # o cliente reenvia
        self.assertEqual(OrdemServico.objects.count(), 1)
        self.assertEqual(EventoPreditivo.objects.count(), 1)
        medicao.save()
        self.assertEqual(OrdemServico.objects.count(), 1)

    def test_osp_encerrada_libera_nova_ocorrencia_e_preserva_a_anterior(self):
        medicao = self.medicao("CRITICO")
        antiga = OrdemServico.objects.get()
        self.assertEqual(self.mover(self.gestor, antiga, "CANCELADA", "Falso positivo").status_code, 200)
        # A medição se recupera e volta a ficar crítica: nova ocorrência, nova OSP.
        for crit in ("NORMAL", "CRITICO"):
            medicao.parametros = {"criticidade": crit, "observacao": "revisão"}
            medicao.save()
        self.assertEqual(OrdemServico.objects.count(), 2)
        antiga.refresh_from_db()
        self.assertEqual(antiga.status, "CANCELADA")
        self.assertEqual(antiga.historico.filter(tipo=TipoHistorico.CANCELAMENTO).count(), 1)

    def test_reabrir_com_outra_osp_automatica_aberta_na_mesma_ocorrencia_e_rejeitado(self):
        medicao = self.medicao("CRITICO")
        antiga = OrdemServico.objects.get()
        self.mover(self.gestor, antiga, "CANCELADA", "Falso positivo")
        for crit in ("NORMAL", "CRITICO"):
            medicao.parametros = {"criticidade": crit, "observacao": "revisão"}
            medicao.save()
        r = self.mover(self.gestor, antiga, "ABERTA", "Quero de volta")
        self.assertEqual(r.status_code, 409, r.data)
        self.assertEqual(r.data["codigo"], "conflito_ocorrencia")
        antiga.refresh_from_db()
        self.assertEqual(antiga.status, "CANCELADA")


@skipUnless(connection.vendor == "postgresql", "concorrência real exige PostgreSQL (SQLite serializa tudo)")
class GeracaoConcorrenteTest(TransactionTestCase):
    """Threads de verdade contra o PostgreSQL. Não roda no SQLite do desenvolvimento."""

    def test_varias_threads_geram_uma_unica_osp(self):
        cliente = Cliente.objects.create(nome="Concorrência", cnpj="33.333.333/0001-33")
        setor = Setor.objects.create(area=Area.objects.create(cliente=cliente, nome="A"), nome="S")
        equipamento = Equipamento.objects.create(setor=setor, tag="CC-01", nome="Eq")
        tecnico = User.objects.create_user(email="t@c.com", nome="T", perfil="TECNICO")
        inspecao = Inspecao.objects.create(cliente=cliente, tecnico=tecnico, data=date(2026, 10, 22),
                                           tipo_analise="SENSITIVA")
        medicao = MedicaoTecnica(inspecao=inspecao, equipamento=equipamento, criticidade="CRITICO")
        resultados, erros = [], []

        def gerar():
            try:
                resultados.append(services.gerar_osp_de_medicao(medicao, "x", retornar_existente=True).pk)
            except Exception as exc:  # pragma: no cover - só aparece se a regra falhar
                erros.append(exc)
            finally:
                connection.close()

        threads = [threading.Thread(target=gerar) for _ in range(8)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        self.assertEqual(erros, [])
        self.assertEqual(len(set(resultados)), 1)
        self.assertEqual(OrdemServico.objects.count(), 1)


class TransicoesTest(BaseFluxo):
    """2.6.3 — toda transição válida funciona; toda inválida é rejeitada."""

    def test_matriz_completa_de_transicoes(self):
        osp = self.nova_osp()
        for de in StatusOSP:
            for para in StatusOSP:
                with self.subTest(de=de.value, para=para.value):
                    self.forcar_status(osp, de)
                    r = self.mover(self.gestor, osp, para.value, "motivo do teste")
                    if de == para:
                        self.assertEqual(r.status_code, 200, r.data)
                        self.assertFalse(r.data["alterado"])
                    elif para in TRANSICOES.get(de, ()):
                        self.assertEqual(r.status_code, 200, r.data)
                        self.assertTrue(r.data["alterado"])
                        self.assertEqual(r.data["status"], para.value)
                    else:
                        self.assertEqual(r.status_code, 409, r.data)
                        self.assertEqual(r.data["codigo"], "transicao_invalida")
                        osp.refresh_from_db()
                        self.assertEqual(osp.status, de.value)

    def test_caminho_completo_do_anexo_i(self):
        osp = self.nova_osp(responsavel=None)
        for status in ("EM_ANALISE", "EM_EXECUCAO", "AGUARDANDO_APROVACAO"):
            self.assertEqual(self.mover(self.tecnico, osp, status).status_code, 200, status)
        r = self.mover(self.gestor, osp, "FINALIZADA")
        self.assertEqual(r.status_code, 200, r.data)
        osp.refresh_from_db()
        self.assertEqual(osp.status, "FINALIZADA")
        self.assertEqual(osp.aprovado_por_id, self.gestor.pk)
        self.assertIsNotNone(osp.aprovado_em)
        self.assertEqual(osp.finalizado_por_id, self.gestor.pk)
        self.assertIsNotNone(osp.finalizada_em)
        self.assertEqual(
            list(osp.historico.values_list("tipo", flat=True)),
            ["CRIACAO", "STATUS", "STATUS", "STATUS", "APROVACAO"],
        )

    def test_ciclo_do_cliente_aberta_planejada_executada_finalizada(self):
        osp = self.nova_osp()
        for status in ("PLANEJADA", "EXECUTADA"):
            self.assertEqual(self.mover(self.tecnico, osp, status).status_code, 200)
        self.assertEqual(self.mover(self.gestor, osp, "FINALIZADA").status_code, 200)
        osp.refresh_from_db()
        self.assertIsNotNone(osp.planejado_em)
        self.assertIsNotNone(osp.executado_em)

    def test_quem_assume_a_analise_vira_o_responsavel(self):
        osp = self.nova_osp(responsavel=None)
        self.mover(self.tecnico2, osp, "EM_ANALISE")
        osp.refresh_from_db()
        self.assertEqual(osp.responsavel_id, self.tecnico2.pk)
        self.assertEqual(osp.historico.get(tipo="STATUS").alteracoes["responsavel"], [None, self.tecnico2.pk])

    def test_repetir_a_mesma_requisicao_nao_duplica_historico_nem_aviso(self):
        osp = self.nova_osp()
        self.forcar_status(osp, "EM_EXECUCAO")
        r1 = self.mover(self.tecnico, osp, "AGUARDANDO_APROVACAO")
        avisos = Notificacao.objects.filter(evento=EventoNotificacao.APROVACAO_PENDENTE).count()
        historico = osp.historico.count()
        r2 = self.mover(self.tecnico, osp, "AGUARDANDO_APROVACAO")
        self.assertTrue(r1.data["alterado"])
        self.assertFalse(r2.data["alterado"])
        self.assertEqual(osp.historico.count(), historico)
        self.assertEqual(Notificacao.objects.filter(evento=EventoNotificacao.APROVACAO_PENDENTE).count(), avisos)
        self.assertGreaterEqual(avisos, 1)

    def test_decisao_concorrente_perdida_e_rejeitada_sem_efeito(self):
        """O gestor cancela; o outro, com a tela desatualizada, tenta aprovar."""
        osp = self.nova_osp()
        self.forcar_status(osp, "AGUARDANDO_APROVACAO")
        self.assertEqual(self.mover(self.gestor, osp, "CANCELADA", "Duplicada").status_code, 200)
        r = self.mover(self.admin, osp, "FINALIZADA")
        self.assertEqual(r.status_code, 409)
        osp.refresh_from_db()
        self.assertEqual(osp.status, "CANCELADA")
        self.assertIsNone(osp.aprovado_por_id)
        self.assertEqual(osp.historico.filter(tipo="APROVACAO").count(), 0)

    def test_status_nao_muda_pelo_patch_generico(self):
        osp = self.nova_osp()
        r = self.logar(self.gestor).patch(f"/api/osps/{osp.pk}/", {"status": "FINALIZADA", "titulo": "novo"},
                                          format="json")
        self.assertEqual(r.status_code, 200)
        osp.refresh_from_db()
        self.assertEqual((osp.status, osp.titulo), ("ABERTA", "novo"))
        self.assertIsNone(osp.finalizada_em)

    def test_status_inexistente_e_rejeitado(self):
        osp = self.nova_osp()
        self.assertEqual(self.mover(self.gestor, osp, "VOANDO").status_code, 400)

    def test_falha_na_notificacao_desfaz_a_transicao(self):
        osp = self.nova_osp()
        self.forcar_status(osp, "EM_EXECUCAO")
        with patch("apps.notificacoes.services.notificar", side_effect=RuntimeError("fora do ar")):
            with self.assertRaises(RuntimeError):
                services.transicionar(osp.pk, "AGUARDANDO_APROVACAO", self.tecnico)
        osp.refresh_from_db()
        self.assertEqual(osp.status, "EM_EXECUCAO")
        self.assertEqual(osp.historico.count(), 1)  # só a criação


class CancelamentoReaberturaRejeicaoTest(BaseFluxo):
    def test_cancelar_exige_motivo_e_preserva_o_historico(self):
        osp = self.nova_osp()
        self.assertEqual(self.mover(self.gestor, osp, "CANCELADA").status_code, 400)
        self.assertEqual(self.mover(self.gestor, osp, "CANCELADA", "   ").status_code, 400)
        osp.refresh_from_db()
        self.assertEqual(osp.status, "ABERTA")
        self.assertEqual(self.mover(self.gestor, osp, "CANCELADA", "Aberta por engano").status_code, 200)
        osp.refresh_from_db()
        self.assertEqual(osp.status, "CANCELADA")
        linha = osp.historico.get(tipo="CANCELAMENTO")
        self.assertEqual((linha.motivo, linha.status_anterior, linha.status_novo, linha.ator_id),
                         ("Aberta por engano", "ABERTA", "CANCELADA", self.gestor.pk))
        self.assertEqual(osp.historico.count(), 2)

    def test_osp_cancelada_nao_e_editavel_nem_excluivel(self):
        osp = self.nova_osp()
        self.mover(self.gestor, osp, "CANCELADA", "x")
        r = self.logar(self.gestor).patch(f"/api/osps/{osp.pk}/", {"titulo": "editado"}, format="json")
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.data["codigo"], "osp_cancelada")
        r = self.logar(self.admin).delete(f"/api/osps/{osp.pk}/")
        self.assertEqual(r.status_code, 405)
        self.assertEqual(OrdemServico.objects.get(pk=osp.pk).historico.count(), 2)

    def test_historico_nao_se_edita_nem_se_apaga(self):
        osp = self.nova_osp()
        linha = osp.historico.get()
        linha.motivo = "adulterado"
        with self.assertRaises(ValueError):
            linha.save()
        with self.assertRaises(ValueError):
            linha.delete()
        from django.db.models import ProtectedError
        with self.assertRaises(ProtectedError):
            osp.delete()

    def test_reabrir_recomeca_o_ciclo_e_o_sla_sem_perder_o_que_houve(self):
        osp = self.nova_osp(prioridade="ALTA", grau_risco="")
        self.forcar_status(osp, "AGUARDANDO_APROVACAO")
        self.mover(self.gestor, osp, "FINALIZADA")
        osp.refresh_from_db()
        finalizada_em = osp.finalizada_em
        # Vencida na finalização: o prazo antigo ficou para trás.
        OrdemServico.objects.filter(pk=osp.pk).update(sla_data=timezone.localdate() - timedelta(days=5))

        self.assertEqual(self.mover(self.tecnico, osp, "ABERTA", "x").status_code, 403)
        self.assertEqual(self.mover(self.gestor, osp, "ABERTA").status_code, 400)
        self.assertEqual(self.mover(self.gestor, osp, "ABERTA", "Falha voltou").status_code, 200)

        osp.refresh_from_db()
        self.assertEqual(osp.status, "ABERTA")
        self.assertIsNone(osp.finalizada_em)
        self.assertIsNone(osp.aprovado_por_id)
        self.assertEqual(osp.sla_data, timezone.localdate() + timedelta(days=3))  # ALTA = 3 dias
        self.assertFalse(osp.sla_vencido)
        reabertura = osp.historico.get(tipo="REABERTURA")
        self.assertEqual(reabertura.motivo, "Falha voltou")
        self.assertEqual(reabertura.alteracoes["finalizada_em"][0], finalizada_em.isoformat())
        self.assertTrue(osp.historico.filter(tipo="APROVACAO").exists())  # o passado continua lá

    def test_reabrir_cancelada(self):
        osp = self.nova_osp()
        self.mover(self.gestor, osp, "CANCELADA", "x")
        self.assertEqual(self.mover(self.gestor, osp, "ABERTA", "Era válida").status_code, 200)
        self.assertEqual(OrdemServico.objects.get(pk=osp.pk).status, "ABERTA")

    def test_rejeitar_aprovacao_exige_motivo_volta_para_execucao_e_avisa_o_responsavel(self):
        osp = self.nova_osp()
        self.forcar_status(osp, "AGUARDANDO_APROVACAO")
        self.assertEqual(self.mover(self.gestor, osp, "EM_EXECUCAO").status_code, 400)
        self.assertEqual(self.mover(self.tecnico, osp, "EM_EXECUCAO", "x").status_code, 403)
        r = self.mover(self.gestor, osp, "EM_EXECUCAO", "Faltou fotografar o mancal")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["status"], "EM_EXECUCAO")
        self.assertEqual(osp.historico.get(tipo="REJEICAO").motivo, "Faltou fotografar o mancal")
        aviso = Notificacao.objects.get(destinatario=self.tecnico, evento=EventoNotificacao.OSP_STATUS)
        self.assertIn("Faltou fotografar o mancal", aviso.mensagem)
        # quem rejeitou não é notificado do próprio ato
        self.assertFalse(Notificacao.objects.filter(destinatario=self.gestor,
                                                    evento=EventoNotificacao.OSP_STATUS).exists())


class PermissoesTest(BaseFluxo):
    """Aprovação e demais atos só para quem tem perfil — nunca pelo front."""

    def test_perfis_internos_e_o_que_cada_um_pode(self):
        osp = self.nova_osp()
        # Técnico opera o fluxo, mas não cancela, não aprova, não reabre.
        self.assertEqual(self.mover(self.tecnico, osp, "CANCELADA", "x").status_code, 403)
        self.forcar_status(osp, "AGUARDANDO_APROVACAO")
        self.assertEqual(self.mover(self.tecnico, osp, "FINALIZADA").status_code, 403)
        self.assertEqual(OrdemServico.objects.get(pk=osp.pk).status, "AGUARDANDO_APROVACAO")
        # Gestor e Admin aprovam.
        self.assertEqual(self.mover(self.admin, osp, "FINALIZADA").status_code, 200)

    def test_cliente_nao_move_status_por_padrao(self):
        """PENDENTE: quem aprova (docs/03). Padrão = só a gestão da CONTRATADA."""
        osp = self.nova_osp()
        for usuario in (self.pcm, self.corp, self.manut):
            for alvo in ("EM_ANALISE", "PLANEJADA", "CANCELADA", "FINALIZADA"):
                with self.subTest(usuario=usuario.perfil, alvo=alvo):
                    self.assertEqual(self.mover(usuario, osp, alvo, "x").status_code, 403)
        self.forcar_status(osp, "AGUARDANDO_APROVACAO")
        self.assertEqual(self.mover(self.pcm, osp, "FINALIZADA").status_code, 403)
        self.assertEqual(OrdemServico.objects.get(pk=osp.pk).status, "AGUARDANDO_APROVACAO")
        self.assertEqual(self.logar(self.pcm).get(f"/api/osps/{osp.pk}/").data["transicoes_permitidas"], [])

    @override_settings(OSP_APROVACAO_PELO_CLIENTE=True)
    def test_com_aprovacao_pelo_cliente_so_pcm_e_gestores_da_propria_empresa(self):
        osp = self.nova_osp()
        self.forcar_status(osp, "AGUARDANDO_APROVACAO")
        self.assertEqual(self.mover(self.manut, osp, "FINALIZADA").status_code, 403)   # manutentor nunca
        self.assertEqual(self.mover(self.pcm, osp, "CANCELADA", "x").status_code, 403)  # nem cancela
        self.assertEqual(self.mover(self.pcm_b, osp, "FINALIZADA").status_code, 404)    # outra empresa
        self.assertEqual(OrdemServico.objects.get(pk=osp.pk).status, "AGUARDANDO_APROVACAO")
        self.assertEqual(self.mover(self.pcm, osp, "FINALIZADA").status_code, 200)
        osp.refresh_from_db()
        self.assertEqual(osp.aprovado_por_id, self.pcm.pk)
        self.assertEqual(osp.historico.get(tipo="APROVACAO").ator_perfil, "CLIENTE_PCM")

    @override_settings(OSP_APROVACAO_PELO_CLIENTE=True)
    def test_defesa_em_profundidade_service_recusa_cliente_de_outra_empresa(self):
        osp = self.nova_osp()
        self.forcar_status(osp, "AGUARDANDO_APROVACAO")
        with self.assertRaises(services.ErroOSP) as ctx:
            services.transicionar(osp.pk, "FINALIZADA", self.pcm_b)
        self.assertEqual(ctx.exception.http, 403)

    def test_usuario_inativo_ou_anonimo_nao_transiciona(self):
        osp = self.nova_osp()
        self.assertIn(self.api.patch(f"/api/osps/{osp.pk}/status/", {"status": "EM_ANALISE"},
                                     format="json").status_code, (401, 403))
        self.tecnico.is_active = False
        with self.assertRaises(services.ErroOSP):
            services.transicionar(osp.pk, "EM_ANALISE", self.tecnico)

    def test_transicoes_permitidas_refletem_o_perfil(self):
        osp = self.nova_osp()
        self.forcar_status(osp, "AGUARDANDO_APROVACAO")
        gestor = {t["status"]: t for t in self.logar(self.gestor).get(f"/api/osps/{osp.pk}/").data["transicoes_permitidas"]}
        tecnico = self.logar(self.tecnico).get(f"/api/osps/{osp.pk}/").data["transicoes_permitidas"]
        self.assertEqual(set(gestor), {"FINALIZADA", "EM_EXECUCAO", "CANCELADA"})
        self.assertTrue(gestor["EM_EXECUCAO"]["motivo_obrigatorio"])
        self.assertFalse(gestor["FINALIZADA"]["motivo_obrigatorio"])
        self.assertEqual(tecnico, [])


class EdicaoEHistoricoTest(BaseFluxo):
    def test_edicao_registra_antes_depois_autor_e_perfil(self):
        osp = self.nova_osp(prioridade="MEDIA")
        r = self.logar(self.tecnico).patch(
            f"/api/osps/{osp.pk}/", {"titulo": "Rolamento do mancal LA", "recomendacao": "Trocar"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        linha = osp.historico.get(tipo="EDICAO")
        self.assertEqual(linha.alteracoes["titulo"], ["Bomba 01 — rolamento", "Rolamento do mancal LA"])
        self.assertEqual((linha.ator_id, linha.ator_perfil), (self.tecnico.pk, "TECNICO"))
        # Reenviar o mesmo valor não polui o histórico.
        self.api.patch(f"/api/osps/{osp.pk}/", {"titulo": "Rolamento do mancal LA"}, format="json")
        self.assertEqual(osp.historico.filter(tipo="EDICAO").count(), 1)

    def test_retorno_do_cliente_fica_registrado_como_tal(self):
        osp = self.nova_osp()
        r = self.logar(self.pcm).patch(
            f"/api/osps/{osp.pk}/",
            {"descricao_corretiva": "Trocado o rolamento", "pred_mao_obra_h": "6.00"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        linha = osp.historico.get(tipo="RETORNO_CLIENTE")
        self.assertEqual(linha.ator_id, self.pcm.pk)
        self.assertEqual(linha.alteracoes["descricao_corretiva"], ["", "Trocado o rolamento"])
        self.assertEqual(linha.alteracoes["pred_mao_obra_h"], [None, "6.00"])

    def test_historico_endpoint_ordem_cronologica_e_escopo(self):
        osp = self.nova_osp()
        self.mover(self.tecnico, osp, "EM_ANALISE")
        self.mover(self.gestor, osp, "CANCELADA", "x")
        tipos = [h["tipo"] for h in self.logar(self.pcm).get(f"/api/osps/{osp.pk}/historico/").data]
        self.assertEqual(tipos, ["CRIACAO", "STATUS", "CANCELAMENTO"])
        self.assertEqual(self.logar(self.pcm_b).get(f"/api/osps/{osp.pk}/historico/").status_code, 404)

    def test_responsavel_precisa_ser_da_equipe_interna(self):
        osp = self.nova_osp()
        r = self.logar(self.gestor).patch(f"/api/osps/{osp.pk}/", {"responsavel": self.pcm.pk}, format="json")
        self.assertEqual(r.status_code, 400)
        r = self.api.patch(f"/api/osps/{osp.pk}/", {"responsavel": self.tecnico2.pk}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(osp.historico.get(tipo="EDICAO").alteracoes["responsavel"], [self.tecnico.pk, self.tecnico2.pk])

    def test_evidencias_vem_da_analise_de_origem(self):
        osp = self.nova_osp()
        self.assertEqual(self.logar(self.gestor).get(f"/api/osps/{osp.pk}/").data["evidencias"], [])


class SlaTest(BaseFluxo):
    """2.6.1.1.2/2.6.1.1.5 — prioridade e SLA persistidos, recalculados e verificáveis."""

    def test_sla_pelo_grau_de_risco_e_pela_prioridade(self):
        hoje = timezone.localdate()
        for gr, dias in (("GR1", 3), ("GR2", 10), ("GR3", 20), ("GR4", 30)):
            osp = self.nova_osp(grau_risco=gr, titulo=gr)
            self.assertEqual((osp.sla_data, osp.sla_origem), (hoje + timedelta(days=dias), "GRAU_RISCO"), gr)
        for prio, dias in (("URGENTE", 1), ("ALTA", 3), ("MEDIA", 7), ("BAIXA", 15)):
            osp = self.nova_osp(grau_risco="", prioridade=prio, titulo=prio)
            self.assertEqual((osp.sla_data, osp.sla_origem), (hoje + timedelta(days=dias), "PRIORIDADE"), prio)

    def test_mudar_prioridade_recalcula_a_partir_da_abertura(self):
        osp = self.nova_osp(grau_risco="", prioridade="BAIXA")
        antes = osp.sla_data
        r = self.logar(self.tecnico).patch(f"/api/osps/{osp.pk}/", {"prioridade": "URGENTE"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        osp.refresh_from_db()
        self.assertEqual(osp.sla_data, timezone.localdate() + timedelta(days=1))
        self.assertEqual(osp.historico.get(tipo="SLA").alteracoes["sla_data"], [str(antes), str(osp.sla_data)])

    def test_prazo_manual_so_a_gestao_e_nao_e_sobrescrito_pela_prioridade(self):
        osp = self.nova_osp(grau_risco="", prioridade="MEDIA")
        alvo = str(timezone.localdate() + timedelta(days=40))
        r = self.logar(self.tecnico).patch(f"/api/osps/{osp.pk}/", {"sla_data": alvo}, format="json")
        self.assertEqual((r.status_code, r.data["codigo"]), (403, "sem_permissao"))
        r = self.logar(self.gestor).patch(f"/api/osps/{osp.pk}/", {"sla_data": alvo}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        osp.refresh_from_db()
        self.assertEqual((str(osp.sla_data), osp.sla_origem), (alvo, "MANUAL"))
        self.assertTrue(osp.historico.filter(tipo="SLA").exists())
        self.api.patch(f"/api/osps/{osp.pk}/", {"prioridade": "URGENTE"}, format="json")
        osp.refresh_from_db()
        self.assertEqual(str(osp.sla_data), alvo)  # prazo fixado à mão permanece

    def test_cliente_nao_altera_prazo_nem_prioridade(self):
        osp = self.nova_osp()
        antes = (osp.sla_data, osp.prioridade)
        r = self.logar(self.pcm).patch(f"/api/osps/{osp.pk}/",
                                       {"sla_data": "2030-01-01", "prioridade": "BAIXA"}, format="json")
        self.assertEqual(r.status_code, 200)
        osp.refresh_from_db()
        self.assertEqual((osp.sla_data, osp.prioridade), antes)

    def test_vencido_so_para_abertas_nao_muda_status_e_filtra(self):
        vencida = self.nova_osp(titulo="vencida")
        no_prazo = self.nova_osp(titulo="no prazo")
        finalizada = self.nova_osp(titulo="finalizada")
        ontem = timezone.localdate() - timedelta(days=1)
        OrdemServico.objects.filter(pk__in=[vencida.pk, finalizada.pk]).update(sla_data=ontem)
        self.forcar_status(finalizada, "FINALIZADA")
        lista = self.logar(self.gestor).get("/api/osps/?sla_vencido=true").data
        ids = [o["id"] for o in (lista["results"] if isinstance(lista, dict) else lista)]
        self.assertEqual(ids, [vencida.pk])
        vencida.refresh_from_db()
        self.assertEqual(vencida.status, "ABERTA")  # vencer não cancela nem fecha
        self.assertFalse(OrdemServico.objects.get(pk=no_prazo.pk).sla_vencido)

    def test_sla_cumprido_na_finalizacao(self):
        osp = self.nova_osp()
        self.forcar_status(osp, "AGUARDANDO_APROVACAO")
        self.mover(self.gestor, osp, "FINALIZADA")
        osp.refresh_from_db()
        self.assertTrue(osp.sla_cumprido)
        OrdemServico.objects.filter(pk=osp.pk).update(sla_data=timezone.localdate() - timedelta(days=1))
        osp.refresh_from_db()
        self.assertFalse(osp.sla_cumprido)
        self.assertFalse(osp.sla_vencido)  # encerrada não "vence"

    def test_verificar_slas_e_idempotente_e_so_reavisa_quando_o_prazo_muda(self):
        hoje = timezone.localdate()
        osp = self.nova_osp()
        OrdemServico.objects.filter(pk=osp.pk).update(sla_data=hoje - timedelta(days=2))

        def avisos():
            return Notificacao.objects.filter(evento=EventoNotificacao.SLA_VENCENDO).count()

        self.assertEqual(services.verificar_slas(hoje=hoje), {"vencendo": 0, "vencido": 1})
        primeiro = avisos()
        self.assertGreaterEqual(primeiro, 2)  # gestão + responsável
        for _ in range(3):
            self.assertEqual(services.verificar_slas(hoje=hoje), {"vencendo": 0, "vencido": 0})
        self.assertEqual(avisos(), primeiro)
        self.assertEqual(OrdemServico.objects.get(pk=osp.pk).status, "ABERTA")

        # A gestão estende o prazo: zera as marcas; "vencendo" sai uma vez, depois "vencido" de novo.
        self.logar(self.gestor).patch(f"/api/osps/{osp.pk}/", {"sla_data": str(hoje + timedelta(days=1))}, format="json")
        self.assertEqual(services.verificar_slas(hoje=hoje), {"vencendo": 1, "vencido": 0})
        self.assertEqual(services.verificar_slas(hoje=hoje), {"vencendo": 0, "vencido": 0})
        self.assertEqual(services.verificar_slas(hoje=hoje + timedelta(days=3)), {"vencendo": 0, "vencido": 1})

    def test_verificar_slas_ignora_encerradas_e_falha_de_envio_nao_consome_o_aviso(self):
        hoje = timezone.localdate()
        encerrada = self.nova_osp(titulo="enc")
        aberta = self.nova_osp(titulo="aberta")
        OrdemServico.objects.filter(pk__in=[encerrada.pk, aberta.pk]).update(sla_data=hoje - timedelta(days=1))
        self.forcar_status(encerrada, "FINALIZADA")
        with patch("apps.notificacoes.services.notificar", side_effect=RuntimeError("fora do ar")):
            with self.assertRaises(RuntimeError):
                services.verificar_slas(hoje=hoje)
        self.assertIsNone(OrdemServico.objects.get(pk=aberta.pk).sla_aviso_vencido_em)  # marca desfeita
        self.assertEqual(services.verificar_slas(hoje=hoje), {"vencendo": 0, "vencido": 1})  # reenvio ok

    def test_comando_do_cron_usa_o_mesmo_caminho_idempotente(self):
        from django.core.management import call_command
        osp = self.nova_osp()
        OrdemServico.objects.filter(pk=osp.pk).update(sla_data=timezone.localdate() - timedelta(days=1))
        call_command("verificar_slas", stdout=__import__("io").StringIO())
        n = Notificacao.objects.filter(evento=EventoNotificacao.SLA_VENCENDO).count()
        call_command("verificar_slas", stdout=__import__("io").StringIO())
        self.assertEqual(Notificacao.objects.filter(evento=EventoNotificacao.SLA_VENCENDO).count(), n)


class EscopoPorClienteTest(BaseFluxo):
    def test_cliente_so_ve_as_ordens_do_proprio_escopo(self):
        a = self.nova_osp(titulo="da A")
        b = self.nova_osp(titulo="da B", cliente=self.outro, equipamento=self.equipamento_b, responsavel=None)
        lista = self.logar(self.pcm).get("/api/osps/").data
        ids = {o["id"] for o in (lista["results"] if isinstance(lista, dict) else lista)}
        self.assertEqual(ids, {a.pk})
        self.assertEqual(self.api.get(f"/api/osps/{b.pk}/").status_code, 404)
        self.assertEqual(self.api.patch(f"/api/osps/{b.pk}/", {"descricao_corretiva": "x"}, format="json").status_code, 404)
        self.assertEqual(self.mover(self.pcm, b, "EM_ANALISE").status_code, 404)
        filtrado = self.api.get(f"/api/osps/?cliente={self.outro.pk}").data  # filtro não fura o escopo
        self.assertEqual(len(filtrado["results"] if isinstance(filtrado, dict) else filtrado), 0)

    def test_notificacoes_da_osp_nao_cruzam_clientes(self):
        osp = self.nova_osp()
        self.assertFalse(Notificacao.objects.filter(destinatario=self.pcm_b).exists())
        self.forcar_status(osp, "EM_EXECUCAO")
        self.mover(self.tecnico, osp, "AGUARDANDO_APROVACAO")
        self.mover(self.gestor, osp, "FINALIZADA")
        self.assertFalse(Notificacao.objects.filter(destinatario=self.pcm_b).exists())
        self.assertTrue(Notificacao.objects.filter(destinatario=self.pcm, evento=EventoNotificacao.OSP_STATUS).exists())

    def test_cliente_ve_o_estado_real_e_o_historico_da_propria_osp(self):
        osp = self.nova_osp()
        self.mover(self.gestor, osp, "CANCELADA", "x")
        dados = self.logar(self.pcm).get(f"/api/osps/{osp.pk}/").data
        self.assertEqual(dados["status"], "CANCELADA")


class PaineisTest(BaseFluxo):
    """Dashboards e laudos refletem o estado real: cancelada não é anomalia."""

    def test_executivo_exclui_canceladas_e_conta_sla_vencido(self):
        viva = self.nova_osp(titulo="viva")
        cancelada = self.nova_osp(titulo="cancelada")
        finalizada = self.nova_osp(titulo="finalizada")
        self.mover(self.gestor, cancelada, "CANCELADA", "x")
        self.forcar_status(finalizada, "AGUARDANDO_APROVACAO")
        self.mover(self.gestor, finalizada, "FINALIZADA")
        OrdemServico.objects.filter(pk=viva.pk).update(sla_data=timezone.localdate() - timedelta(days=1))
        kpis = self.logar(self.gestor).get("/api/dashboard/executivo/").data["kpis"]
        self.assertEqual(kpis["osps_total"], 2)
        self.assertEqual(kpis["osps_canceladas"], 1)
        self.assertEqual(kpis["osps_finalizadas"], 1)
        self.assertEqual(kpis["taxa_conclusao"], 50)
        self.assertEqual(kpis["osps_sla_vencido"], 1)
        self.assertEqual(kpis["sla_cumprido_pct"], 100)

    def test_painel_operacional_e_portal_respeitam_escopo(self):
        viva = self.nova_osp()
        outra = self.nova_osp(titulo="B", cliente=self.outro, equipamento=self.equipamento_b, responsavel=None)
        OrdemServico.objects.filter(pk__in=[viva.pk, outra.pk]).update(sla_data=timezone.localdate() - timedelta(days=1))
        portal = self.logar(self.pcm).get("/api/portal/visao-geral/").data["indicadores"]
        self.assertEqual((portal["osps_abertas"], portal["osps_sla_vencido"]), (1, 1))
        operacional = self.logar(self.gestor).get("/api/dashboard/").data
        self.assertEqual((operacional["osps_abertas"], operacional["osps_sla_vencido"]), (2, 2))
        self.assertEqual(operacional["osps_por_status"], {"ABERTA": 2})
        self.mover(self.gestor, viva, "CANCELADA", "x")
        operacional = self.api.get("/api/dashboard/").data
        self.assertEqual((operacional["osps_total"], operacional["osps_abertas"]), (1, 1))
        self.assertEqual(operacional["osps_por_status"], {"ABERTA": 1, "CANCELADA": 1})

    def test_laudo_e_estatisticas_ignoram_osp_cancelada(self):
        from apps.laudos.estatisticas import montar_secao_b
        inspecao = Inspecao.objects.create(cliente=self.cliente, tecnico=self.tecnico, data=date(2026, 10, 22),
                                           tipo_analise="VIBRACAO")
        viva = self.nova_osp(titulo="viva", inspecao=inspecao, acompanhamento="ABERTA")
        cancelada = self.nova_osp(titulo="cancelada", inspecao=inspecao, equipamento=self.equipamento)
        antes = montar_secao_b(inspecao)["resumo"]["anomalias_detectadas"]
        self.mover(self.gestor, cancelada, "CANCELADA", "x")
        depois = montar_secao_b(inspecao)["resumo"]["anomalias_detectadas"]
        self.assertEqual((antes, depois), (2, 1))
        self.assertEqual(list(OrdemServico.objects.validas().filter(inspecao=inspecao)), [viva])
