"""Integridade documental: versões, aprovação interna, acesso e arquivo emitido.

Valores e documentos QA são sintéticos. Aprovação interna não comprova assinatura
criptográfica; testes de API/bytes não substituem inspeção visual do PDF real.
"""
import hashlib
import io
import json
import tempfile
from copy import deepcopy
from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from PIL import Image

from apps.cadastros.models import Area, Cliente, Componente, Condicao, Equipamento, Instrumento, ModuloTecnico, Setor, TecnologiaAnalise
from apps.coletas.models import Achado, AchadoImagem, Carregamento, Inspecao, ItemInspecao, MedicaoTecnica, Relatorio
from apps.notificacoes.models import EventoNotificacao, Notificacao

from .models import Laudo


class ConformidadeDocumentosTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.media = tempfile.TemporaryDirectory(prefix="thermopro-laudos-qa-")
        cls.settings_override = override_settings(MEDIA_ROOT=cls.media.name)
        cls.settings_override.enable()

    @classmethod
    def tearDownClass(cls):
        cls.settings_override.disable()
        cls.media.cleanup()
        super().tearDownClass()

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.responsavel = User.objects.create_user(email="documento@thermo.test", nome="Responsável QA",
            perfil="TECNICO", nivel="MASTER", conselho_classe="CREA-QA 123", cargo="Engenheiro QA")
        cls.outro_interno = User.objects.create_user(email="outro-documento@thermo.test", nome="Outro responsável",
            perfil="TECNICO", nivel="MASTER", conselho_classe="CREA-QA 456")
        cls.sem_conselho = User.objects.create_user(email="sem-registro@thermo.test", nome="Sem registro",
            perfil="TECNICO", nivel="MASTER")
        cls.cliente = Cliente.objects.create(nome="Cliente documental QA", cnpj="10.555.555/0001-55")
        cls.outro_cliente = Cliente.objects.create(nome="Outro cliente documental", cnpj="20.666.666/0001-66")
        cls.portal = User.objects.create_user(email="portal-documento@thermo.test", nome="PCM QA",
            perfil="CLIENTE_PCM", cliente=cls.cliente)
        cls.outro_portal = User.objects.create_user(email="outro-portal-documento@thermo.test", nome="Outro PCM",
            perfil="CLIENTE_PCM", cliente=cls.outro_cliente)
        cls.sem_vinculo = User.objects.create_user(email="sem-cliente-documento@thermo.test", nome="Sem vínculo",
            perfil="CLIENTE_PCM")
        area = Area.objects.create(nome="Área QA", cliente=cls.cliente)
        setor = Setor.objects.create(nome="Setor QA", area=area)
        cls.equipamento = Equipamento.objects.create(tag="DOC-QA-01", nome="Equipamento documental", setor=setor)
        cls.componente = Componente.objects.create(equipamento=cls.equipamento, nome="Carcaça")
        cls.instrumento = Instrumento.objects.create(tipo="Coletor QA", modelo="Sintético", numero_serie="DOC-01")
        cls.inspecao = Inspecao.objects.create(cliente=cls.cliente, tecnico=cls.responsavel,
            tipo_analise="SENSITIVA", data=date(2026, 10, 20))
        cls.medicao = MedicaoTecnica.objects.create(inspecao=cls.inspecao, equipamento=cls.equipamento,
            componente=cls.componente, instrumento=cls.instrumento, tipo="SENSITIVA", subtipo="SENSITIVA",
            ponto_medicao="Carcaça", grandeza="Parecer", valor=None, unidade="",
            parametros={"criticidade": "ALERTA", "observacao": "Ruído percebido pelo técnico QA"})

    def setUp(self):
        self.api = APIClient()
        self.api.force_authenticate(self.responsavel)
        # Bytes sintéticos: domínio/persistência/hash/download; test_pdf renderiza PDF real.
        pdf = patch("apps.laudos.pdf.gerar_pdf", return_value=b"%PDF-1.4\n% QA documental sintetico\n%%EOF")
        self.renderer = pdf.start()
        self.addCleanup(pdf.stop)

    def gerar(self, **extras):
        resposta = self.api.post("/api/laudos/gerar/", {"inspecao": self.inspecao.pk, **extras}, format="json")
        self.assertEqual(resposta.status_code, 201, resposta.data)
        return Laudo.objects.get(pk=resposta.data["id"])

    def emitir(self, laudo):
        resposta = self.api.post(f"/api/laudos/{laudo.pk}/emitir/", {}, format="json")
        self.assertEqual(resposta.status_code, 200, resposta.data)
        laudo.refresh_from_db()
        return resposta

    def relatorio(self, laudo):
        resposta = self.api.get(f"/api/laudos/{laudo.pk}/relatorio-tecnico/")
        self.assertEqual(resposta.status_code, 200, resposta.data)
        return resposta.data

    def revisar(self, laudo, motivo="Corrigir observação sem apagar a emissão anterior"):
        resposta = self.api.post(f"/api/laudos/{laudo.pk}/revisar/", {"motivo": motivo}, format="json")
        self.assertIn(resposta.status_code, (200, 201), resposta.data)
        return Laudo.objects.get(pk=resposta.data["id"])

    def test_geracao_preserva_identificacoes_diagnostico_e_criticidade(self):
        laudo = self.gerar()
        self.assertEqual(laudo.inspecao_id, self.inspecao.pk)
        self.assertEqual(laudo.responsavel_id, self.responsavel.pk)
        self.assertEqual(laudo.status, "RASCUNHO")
        self.assertEqual(laudo.versao, 1)
        self.assertEqual(laudo.criticidade_geral, "ALERTA")
        self.assertIn("DOC-QA-01", laudo.diagnostico)
        self.assertIn("Ruído percebido", laudo.diagnostico)

    def test_nao_pode_emitir_por_patch_de_status(self):
        laudo = self.gerar()
        resposta = self.api.patch(f"/api/laudos/{laudo.pk}/", {"status": "EMITIDO"}, format="json")
        self.assertIn(resposta.status_code, (200, 400), resposta.data)
        laudo.refresh_from_db()
        self.assertEqual(laudo.status, "RASCUNHO")
        self.assertIsNone(laudo.data_emissao)
        self.assertFalse(Notificacao.objects.filter(evento=EventoNotificacao.LAUDO_CONCLUIDO).exists())

    def test_versao_e_origem_nao_podem_ser_adulteradas_por_patch(self):
        laudo = self.gerar()
        outra = Inspecao.objects.create(cliente=self.outro_cliente, tecnico=self.responsavel,
            tipo_analise="SENSITIVA", data=date(2026, 10, 20))
        resposta = self.api.patch(f"/api/laudos/{laudo.pk}/",
            {"versao": 99, "inspecao": outra.pk, "numero": "ADULTERADO"}, format="json")
        self.assertIn(resposta.status_code, (200, 400), resposta.data)
        laudo.refresh_from_db()
        self.assertEqual(laudo.versao, 1)
        self.assertEqual(laudo.inspecao_id, self.inspecao.pk)
        self.assertNotEqual(laudo.numero, "ADULTERADO")

    def test_rascunho_permite_correcao_editorial_antes_da_emissao(self):
        laudo = self.gerar()
        resposta = self.api.patch(f"/api/laudos/{laudo.pk}/",
            {"titulo": "Título técnico revisto", "conclusao": "Conclusão explícita QA"}, format="json")
        self.assertEqual(resposta.status_code, 200, resposta.data)
        laudo.refresh_from_db()
        self.assertEqual(laudo.titulo, "Título técnico revisto")
        self.assertEqual(laudo.conclusao, "Conclusão explícita QA")

    def test_emitir_sem_conselho_falha_sem_data_ou_notificacao(self):
        self.api.force_authenticate(self.sem_conselho)
        laudo = self.gerar()
        resposta = self.api.post(f"/api/laudos/{laudo.pk}/emitir/", {}, format="json")
        self.assertIn(resposta.status_code, (400, 403), resposta.data)
        laudo.refresh_from_db()
        self.assertEqual(laudo.status, "RASCUNHO")
        self.assertIsNone(laudo.data_emissao)
        self.assertFalse(Notificacao.objects.filter(evento=EventoNotificacao.LAUDO_CONCLUIDO).exists())

    def test_outro_usuario_com_conselho_nao_assina_pelo_responsavel(self):
        laudo = self.gerar()
        self.api.force_authenticate(self.outro_interno)
        resposta = self.api.post(f"/api/laudos/{laudo.pk}/emitir/", {}, format="json")
        self.assertIn(resposta.status_code, (400, 403), resposta.data)
        laudo.refresh_from_db()
        self.assertEqual(laudo.status, "RASCUNHO")

    def test_emissao_repetida_e_idempotente_para_data_snapshot_e_notificacoes(self):
        laudo = self.gerar()
        self.emitir(laudo)
        data = laudo.data_emissao
        documento = deepcopy(self.relatorio(laudo))
        notificacoes = list(Notificacao.objects.filter(evento=EventoNotificacao.LAUDO_CONCLUIDO)
                            .values_list("pk", flat=True))
        self.assertTrue(notificacoes)
        self.emitir(laudo)
        self.assertEqual(laudo.data_emissao, data)
        self.assertEqual(self.relatorio(laudo), documento)
        self.assertEqual(list(Notificacao.objects.filter(evento=EventoNotificacao.LAUDO_CONCLUIDO)
                              .values_list("pk", flat=True)), notificacoes)

    def test_emitido_nao_pode_ser_editado_ou_excluido(self):
        laudo = self.gerar()
        self.emitir(laudo)
        titulo = laudo.titulo
        resposta = self.api.patch(f"/api/laudos/{laudo.pk}/", {"titulo": "Alteração indevida"}, format="json")
        self.assertIn(resposta.status_code, (400, 403, 409), resposta.data)
        laudo.refresh_from_db()
        self.assertEqual(laudo.titulo, titulo)
        resposta = self.api.delete(f"/api/laudos/{laudo.pk}/")
        self.assertIn(resposta.status_code, (400, 403, 405, 409))
        self.assertTrue(Laudo.objects.filter(pk=laudo.pk).exists())

    def test_rascunho_nao_e_excluido_fisicamente(self):
        laudo = self.gerar()
        resposta = self.api.delete(f"/api/laudos/{laudo.pk}/")
        self.assertIn(resposta.status_code, (400, 403, 405, 409))
        self.assertTrue(Laudo.objects.filter(pk=laudo.pk).exists())

    def test_emissao_congela_fontes_que_mudam_posteriormente(self):
        laudo = self.gerar()
        self.emitir(laudo)
        documento = deepcopy(self.relatorio(laudo))
        Cliente.objects.filter(pk=self.cliente.pk).update(nome="Razão social alterada")
        Equipamento.objects.filter(pk=self.equipamento.pk).update(tag="TAG-NOVA", nome="Nome posterior")
        Instrumento.objects.filter(pk=self.instrumento.pk).update(numero_serie="SERIE-POSTERIOR")
        get_user_model().objects.filter(pk=self.responsavel.pk).update(nome="Nome posterior", conselho_classe="CREA POSTERIOR")
        MedicaoTecnica.objects.filter(pk=self.medicao.pk).update(diagnostico_sugerido="Texto posterior", criticidade="CRITICO")
        self.assertEqual(self.relatorio(laudo), documento)

    def test_revisao_cria_novo_rascunho_sem_alterar_versao_emitida(self):
        laudo = self.gerar()
        self.emitir(laudo)
        documento = deepcopy(self.relatorio(laudo))
        nova = self.revisar(laudo)
        self.assertNotEqual(nova.pk, laudo.pk)
        self.assertEqual(nova.versao, 2)
        self.assertEqual(nova.status, "RASCUNHO")
        self.assertIsNone(nova.data_emissao)
        laudo.refresh_from_db()
        self.assertEqual(laudo.versao, 1)
        self.assertEqual(laudo.status, "EMITIDO")
        self.assertEqual(self.relatorio(laudo), documento)

    def test_revisao_repetida_reutiliza_rascunho_aberto(self):
        laudo = self.gerar()
        self.emitir(laudo)
        primeira = self.revisar(laudo)
        segunda = self.revisar(laudo)
        self.assertEqual(primeira.pk, segunda.pk)
        self.assertEqual(Laudo.objects.count(), 2)

    def test_revisao_exige_motivo_e_documento_emitido(self):
        laudo = self.gerar()
        for dados in ({}, {"motivo": " "}):
            resposta = self.api.post(f"/api/laudos/{laudo.pk}/revisar/", dados, format="json")
            self.assertIn(resposta.status_code, (400, 409), resposta.data)
        self.emitir(laudo)
        resposta = self.api.post(f"/api/laudos/{laudo.pk}/revisar/", {"motivo": " "}, format="json")
        self.assertEqual(resposta.status_code, 400, resposta.data)
        self.assertEqual(Laudo.objects.count(), 1)

    def test_cancelamento_exige_motivo_e_preserva_documento(self):
        laudo = self.gerar()
        self.emitir(laudo)
        documento = deepcopy(self.relatorio(laudo))
        resposta = self.api.post(f"/api/laudos/{laudo.pk}/cancelar/", {}, format="json")
        self.assertEqual(resposta.status_code, 400, resposta.data)
        resposta = self.api.post(f"/api/laudos/{laudo.pk}/cancelar/", {"motivo": "Cancelamento QA justificado"}, format="json")
        self.assertEqual(resposta.status_code, 200, resposta.data)
        laudo.refresh_from_db()
        self.assertEqual(laudo.status, "CANCELADO")
        # Conteúdo técnico emitido não deve ser recalculado no cancelamento.
        depois = self.relatorio(laudo)
        self.assertEqual(depois.get("contratante"), documento.get("contratante"))
        self.assertEqual(depois.get("secao_c"), documento.get("secao_c"))
        resposta = self.api.post(f"/api/laudos/{laudo.pk}/emitir/", {}, format="json")
        self.assertIn(resposta.status_code, (400, 409), resposta.data)

    def test_historico_e_versoes_sao_consultaveis_e_somente_leitura(self):
        laudo = self.gerar()
        self.emitir(laudo)
        self.revisar(laudo)
        for acao in ("versoes", "historico"):
            resposta = self.api.get(f"/api/laudos/{laudo.pk}/{acao}/")
            self.assertEqual(resposta.status_code, 200, resposta.data)
            self.assertTrue(resposta.data)
            resposta = self.api.post(f"/api/laudos/{laudo.pk}/{acao}/", {}, format="json")
            self.assertEqual(resposta.status_code, 405)

    def test_portal_ve_emitido_proprio_mas_nao_rascunho(self):
        laudo = self.gerar()
        self.api.force_authenticate(self.portal)
        self.assertEqual(self.api.get(f"/api/laudos/{laudo.pk}/").status_code, 404)
        self.api.force_authenticate(self.responsavel)
        self.emitir(laudo)
        self.api.force_authenticate(self.portal)
        self.assertEqual(self.api.get(f"/api/laudos/{laudo.pk}/").status_code, 200)
        self.assertEqual(self.api.get(f"/api/laudos/{laudo.pk}/relatorio-tecnico/").status_code, 200)

    def test_portal_outro_cliente_sem_vinculo_e_anonimo_nao_acessam_documento(self):
        laudo = self.gerar()
        self.emitir(laudo)
        for usuario in (self.outro_portal, self.sem_vinculo, None):
            self.api.force_authenticate(user=usuario)
            for acao in ("", "relatorio-tecnico/", "pdf/", "historico/", "versoes/"):
                resposta = self.api.get(f"/api/laudos/{laudo.pk}/{acao}")
                self.assertIn(resposta.status_code, (401, 403, 404), (usuario, acao, resposta.status_code))

    def test_portal_nao_gera_emite_revisa_cancela_ou_edita(self):
        laudo = self.gerar()
        self.emitir(laudo)
        self.api.force_authenticate(self.portal)
        resposta = self.api.post("/api/laudos/gerar/", {"inspecao": self.inspecao.pk}, format="json")
        self.assertEqual(resposta.status_code, 403)
        for acao in ("emitir", "revisar", "cancelar"):
            resposta = self.api.post(f"/api/laudos/{laudo.pk}/{acao}/", {"motivo": "Tentativa portal"}, format="json")
            self.assertEqual(resposta.status_code, 403, (acao, resposta.data))
        self.assertEqual(self.api.patch(f"/api/laudos/{laudo.pk}/", {"titulo": "Tentativa"}, format="json").status_code, 403)

    def test_portal_nao_descobre_rascunho_de_revisao_por_historico(self):
        laudo = self.gerar()
        self.emitir(laudo)
        revisao = self.revisar(laudo)
        self.api.force_authenticate(self.portal)
        resposta = self.api.get(f"/api/laudos/{laudo.pk}/versoes/")
        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.assertNotIn("RASCUNHO", json.dumps(resposta.data, default=str))
        self.assertEqual(self.api.get(f"/api/laudos/{revisao.pk}/relatorio-tecnico/").status_code, 404)

    def test_pdf_emitido_e_download_e_mesmos_bytes_apos_mudanca_origem(self):
        laudo = self.gerar()
        self.emitir(laudo)
        url = f"/api/laudos/{laudo.pk}/pdf/"
        resposta = self.api.get(url)
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta["Content-Type"], "application/pdf")
        conteudo = b"".join(resposta.streaming_content) if resposta.streaming else resposta.content
        self.assertTrue(conteudo.startswith(b"%PDF-"))
        self.assertIn("attachment", resposta["Content-Disposition"])
        Cliente.objects.filter(pk=self.cliente.pk).update(nome="Outro nome depois do PDF")
        novamente = self.api.get(url)
        segundo = b"".join(novamente.streaming_content) if novamente.streaming else novamente.content
        self.assertEqual(hashlib.sha256(conteudo).hexdigest(), hashlib.sha256(segundo).hexdigest())

    def test_pdf_de_rascunho_nao_se_apresenta_como_arquivo_emitido(self):
        laudo = self.gerar()
        resposta = self.api.get(f"/api/laudos/{laudo.pk}/pdf/")
        self.assertIn(resposta.status_code, (400, 404, 409), getattr(resposta, "data", None))

    def test_geracao_com_origem_inexistente_ou_ambigua_recusa_sem_criar(self):
        for dados in ({}, {"inspecao": 999999}, {"inspecao": self.inspecao.pk, "relatorio_origem": 999999}):
            resposta = self.api.post("/api/laudos/gerar/", dados, format="json")
            self.assertIn(resposta.status_code, (400, 404), resposta.data)
        self.assertFalse(Laudo.objects.exists())

    def test_laudo_sem_medicoes_nao_afirma_normalidade(self):
        vazia = Inspecao.objects.create(cliente=self.cliente, tecnico=self.responsavel,
            tipo_analise="SENSITIVA", data=date(2026, 10, 21))
        resposta = self.api.post("/api/laudos/gerar/", {"inspecao": vazia.pk}, format="json")
        self.assertIn(resposta.status_code, (201, 400), resposta.data)
        if resposta.status_code == 201:
            self.assertEqual(resposta.data["criticidade_geral"], "")
            self.assertNotIn("classificada como Normal", resposta.data["conclusao"])

    def test_pendencia_tecnica_nao_vira_ok_na_relacao_de_equipamentos(self):
        MedicaoTecnica.objects.filter(pk=self.medicao.pk).update(criticidade="", classificacao_status="PENDENTE")
        laudo = self.gerar()
        documento = self.relatorio(laudo)
        secao = documento["secao_c"]
        condicoes = [i["condicao"] for a in secao["areas"] for s in a["setores"] for i in s["itens"]]
        self.assertTrue(condicoes)
        self.assertNotIn("OK", condicoes)

    def test_instrumento_nao_utilizado_nao_e_inserido_no_documento(self):
        Instrumento.objects.create(tipo="Instrumento não usado", modelo="QA", numero_serie="NAO-USADO")
        MedicaoTecnica.objects.filter(pk=self.medicao.pk).update(instrumento=None)
        documento = self.relatorio(self.gerar())
        self.assertEqual(documento["instrumentacao"], [])

    def test_falha_pdf_reverte_emissao_assinatura_snapshot_e_notificacao(self):
        from .pdf import ErroGeracaoPDF
        laudo = self.gerar()
        self.renderer.side_effect = ErroGeracaoPDF("Falha controlada QA na geração do PDF")
        resposta = self.api.post(f"/api/laudos/{laudo.pk}/emitir/", {}, format="json")
        self.assertIn(resposta.status_code, (400, 409, 503), resposta.data)
        laudo.refresh_from_db()
        self.assertEqual(laudo.status, "RASCUNHO")
        self.assertIsNone(laudo.data_emissao)
        self.assertFalse(laudo.snapshot_emissao)
        self.assertFalse(laudo.assinatura)
        self.assertFalse(laudo.pdf_conteudo)
        self.assertFalse(Notificacao.objects.filter(evento=EventoNotificacao.LAUDO_CONCLUIDO).exists())

    def test_emissao_registra_aprovacao_interna_sem_declarar_certificado(self):
        from .snapshots import hash_snapshot
        laudo = self.gerar()
        self.emitir(laudo)
        self.assertTrue(laudo.assinatura)
        self.assertIn("APROVACAO_ELETRONICA_INTERNA", json.dumps(laudo.assinatura, default=str))
        self.assertIn("CREA-QA 123", json.dumps(laudo.assinatura, default=str))
        self.assertEqual(laudo.snapshot_hash, hash_snapshot(laudo.snapshot_emissao))
        self.assertEqual(laudo.pdf_hash, hashlib.sha256(bytes(laudo.pdf_conteudo)).hexdigest())
        assinatura = deepcopy(laudo.assinatura)
        self.emitir(laudo)
        self.assertEqual(laudo.assinatura, assinatura)
        self.assertEqual(self.renderer.call_count, 1)

    def test_revisao_herda_autor_motivo_e_novo_conteudo_sem_mudar_arquivo_antigo(self):
        laudo = self.gerar()
        self.emitir(laudo)
        hash_antigo = laudo.snapshot_hash
        pdf_antigo = bytes(laudo.pdf_conteudo)
        nova = self.revisar(laudo, "Acrescentar conclusão revisada QA")
        resposta = self.api.patch(f"/api/laudos/{nova.pk}/", {"conclusao": "Conclusão revisada QA"}, format="json")
        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.emitir(nova)
        self.assertEqual(nova.versao, 2)
        self.assertNotEqual(nova.snapshot_hash, hash_antigo)
        laudo.refresh_from_db()
        self.assertEqual(laudo.snapshot_hash, hash_antigo)
        self.assertEqual(bytes(laudo.pdf_conteudo), pdf_antigo)
        self.assertEqual(nova.anterior_id, laudo.pk)
        self.assertEqual(nova.motivo_revisao, "Acrescentar conclusão revisada QA")

    def test_metadados_de_snapshot_e_pdf_sao_somente_leitura(self):
        laudo = self.gerar()
        resposta = self.api.patch(f"/api/laudos/{laudo.pk}/", {
            "snapshot_emissao": {"adulterado": True}, "snapshot_hash": "a" * 64,
            "pdf_hash": "b" * 64, "assinatura": {"certificado": True},
            "cancelado_em": "2026-10-21T10:00:00Z", "motivo_cancelamento": "Bypass",
        }, format="json")
        self.assertIn(resposta.status_code, (200, 400), resposta.data)
        laudo.refresh_from_db()
        self.assertFalse(laudo.snapshot_emissao)
        self.assertFalse(laudo.snapshot_hash)
        self.assertFalse(laudo.pdf_hash)
        self.assertFalse(laudo.assinatura)
        self.assertIsNone(laudo.cancelado_em)

    def test_imutabilidade_emitido_tambem_impede_edicao_direta_por_orm(self):
        from django.core.exceptions import ValidationError
        laudo = self.gerar()
        self.emitir(laudo)
        titulo = laudo.titulo
        laudo.titulo = "Mutação fora da API"
        with self.assertRaises(ValidationError):
            laudo.save()
        laudo.refresh_from_db()
        self.assertEqual(laudo.titulo, titulo)

    def origem_por_rota(self):
        tecnologia = TecnologiaAnalise.objects.create(nome="Inspeção documental QA", sigla="QA",
            modulo_tecnico=ModuloTecnico.INSPECAO_GENERICA)
        relatorio = Relatorio.objects.create(cliente=self.cliente, tecnologia=tecnologia,
            numero="RT-QA-2026-10-20-00001", data_termino=date(2026, 10, 20))
        carregamento = Carregamento.objects.create(cliente=self.cliente, tecnologia=tecnologia,
            analista=self.responsavel, relatorio=relatorio, instrumento=self.instrumento)
        condicao = Condicao.objects.create(nome="Condição QA", sigla="GR-3", gera_acao=True)
        item = ItemInspecao.objects.create(carregamento=carregamento, equipamento=self.equipamento,
            ordem=1, condicao=condicao)
        achado = Achado.objects.create(item=item, anomalia_texto="Ruído documental QA", confirmada=True)
        return relatorio, achado

    def test_laudo_de_rota_preserva_origem_e_modulo_sem_forcar_vibracao(self):
        origem, _ = self.origem_por_rota()
        resposta = self.api.post("/api/laudos/gerar/", {"relatorio_origem": origem.pk}, format="json")
        self.assertEqual(resposta.status_code, 201, resposta.data)
        laudo = Laudo.objects.get(pk=resposta.data["id"])
        self.assertIsNone(laudo.inspecao_id)
        self.assertEqual(laudo.relatorio_origem_id, origem.pk)
        self.emitir(laudo)
        self.assertEqual(laudo.snapshot_emissao["origem"]["tipo"], "relatorio")
        self.assertEqual(laudo.snapshot_emissao["relatorio"]["modulo"], ModuloTecnico.INSPECAO_GENERICA)
        self.api.force_authenticate(self.outro_portal)
        self.assertEqual(self.api.get(f"/api/laudos/{laudo.pk}/relatorio-tecnico/").status_code, 404)

    def test_editar_rota_achado_ou_cliente_nao_altera_laudo_ja_emitido(self):
        origem, achado = self.origem_por_rota()
        resposta = self.api.post("/api/laudos/gerar/", {"relatorio_origem": origem.pk}, format="json")
        self.assertEqual(resposta.status_code, 201, resposta.data)
        laudo = Laudo.objects.get(pk=resposta.data["id"])
        self.emitir(laudo)
        documento = deepcopy(self.relatorio(laudo))
        Relatorio.objects.filter(pk=origem.pk).update(consideracoes_finais="Texto de origem posterior")
        Achado.objects.filter(pk=achado.pk).update(anomalia_texto="Anomalia posterior")
        self.assertEqual(self.relatorio(laudo), documento)

    def test_usuario_inativo_nao_aprova_mesmo_com_conselho(self):
        laudo = self.gerar()
        self.responsavel.is_active = False
        self.responsavel.save(update_fields=["is_active"])
        resposta = self.api.post(f"/api/laudos/{laudo.pk}/emitir/", {}, format="json")
        self.assertIn(resposta.status_code, (400, 401, 403), resposta.data)
        laudo.refresh_from_db()
        self.assertEqual(laudo.status, "RASCUNHO")

    def test_post_generico_nao_contorna_geracao_ou_emissao(self):
        resposta = self.api.post("/api/laudos/", {"inspecao": self.inspecao.pk,
            "titulo": "Documento manual", "responsavel": self.responsavel.pk,
            "status": "EMITIDO", "versao": 99}, format="json")
        self.assertIn(resposta.status_code, (201, 400, 405), getattr(resposta, "data", None))
        if resposta.status_code == 201:
            laudo = Laudo.objects.get(pk=resposta.data["id"])
            self.assertEqual(laudo.status, "RASCUNHO")
            self.assertEqual(laudo.versao, 1)
            self.assertIsNone(laudo.data_emissao)

    def test_template_rejeita_html_codigo_secao_repetida_e_omissao_obrigatoria(self):
        configuracoes = [{"html": "<script>alert(1)</script>"}, {"rodape": "<b>Rodapé</b>"},
            {"secoes": ["capa", "diagnostico", "conclusao"]},
            {"secoes": ["capa", "diagnostico", "recomendacoes", "conclusao", "conclusao"]},
            {"secoes": ["capa", "diagnostico", "recomendacoes", "conclusao", "codigo_injetado"]}]
        for config in configuracoes:
            with self.subTest(config=config):
                resposta = self.api.post("/api/templates-laudo/", {"nome": "Template QA", "configuracao": config}, format="json")
                self.assertEqual(resposta.status_code, 400, resposta.data)

    def test_template_preserva_configuracao_da_versao_emitida(self):
        resposta = self.api.post("/api/templates-laudo/", {"nome": "Template QA", "cliente": self.cliente.pk,
            "tipo_analise": "SENSITIVA", "configuracao": {"rodape": "Rodapé original QA"}}, format="json")
        self.assertEqual(resposta.status_code, 201, resposta.data)
        template_id = resposta.data["id"]
        laudo = self.gerar()
        resposta = self.api.patch(f"/api/laudos/{laudo.pk}/", {"template": template_id}, format="json")
        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.emitir(laudo)
        snapshot = deepcopy(laudo.snapshot_emissao)
        resposta = self.api.patch(f"/api/templates-laudo/{template_id}/", {"configuracao": {"rodape": "Rodapé posterior"}}, format="json")
        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.assertEqual(resposta.data["versao"], 2)
        laudo.refresh_from_db()
        self.assertEqual(laudo.snapshot_emissao, snapshot)
        self.assertEqual(snapshot["template"]["versao"], 1)
        self.assertEqual(snapshot["template"]["configuracao"]["rodape"], "Rodapé original QA")

    def test_template_de_outro_cliente_modalidade_ou_inativo_nao_e_aplicavel(self):
        for extras in ({"cliente": self.outro_cliente.pk}, {"tipo_analise": "TERMOGRAFIA"}, {"ativo": False}):
            with self.subTest(extras=extras):
                resposta = self.api.post("/api/templates-laudo/", {"nome": "Template incompatível", "configuracao": {}, **extras}, format="json")
                self.assertEqual(resposta.status_code, 201, resposta.data)
                laudo = self.gerar()
                resposta = self.api.patch(f"/api/laudos/{laudo.pk}/", {"template": resposta.data["id"]}, format="json")
                self.assertEqual(resposta.status_code, 400, resposta.data)

    def test_template_exige_master_e_portal_nao_acessa_catalogo_interno(self):
        self.outro_interno.nivel = "PLENO"
        self.outro_interno.save(update_fields=["nivel"])
        self.api.force_authenticate(self.outro_interno)
        self.assertEqual(self.api.get("/api/templates-laudo/").status_code, 200)
        resposta = self.api.post("/api/templates-laudo/", {"nome": "Sem permissão", "configuracao": {}}, format="json")
        self.assertEqual(resposta.status_code, 403)
        self.api.force_authenticate(self.portal)
        self.assertEqual(self.api.get("/api/templates-laudo/").status_code, 403)

    def test_pdf_com_hash_divergente_nao_e_entregue(self):
        laudo = self.gerar()
        self.emitir(laudo)
        # Simula corrupção do armazenamento; hash não substitui controle do banco.
        Laudo.objects.filter(pk=laudo.pk).update(pdf_conteudo=b"%PDF-1.4\nArquivo alterado")
        resposta = self.api.get(f"/api/laudos/{laudo.pk}/pdf/")
        self.assertEqual(resposta.status_code, 400, getattr(resposta, "data", None))
        self.assertIn("integridade", str(resposta.data).lower())

    def test_parametros_de_previa_nao_recortam_documento_emitido_de_rota(self):
        origem, _ = self.origem_por_rota()
        resposta = self.api.post("/api/laudos/gerar/", {"relatorio_origem": origem.pk}, format="json")
        self.assertEqual(resposta.status_code, 201, resposta.data)
        laudo = Laudo.objects.get(pk=resposta.data["id"])
        resposta = self.api.post(f"/api/laudos/{laudo.pk}/emitir/?carregamento=999999&somente_desvios=true", {}, format="json")
        self.assertEqual(resposta.status_code, 200, resposta.data)
        laudo.refresh_from_db()
        self.assertIn("DOC-QA-01", json.dumps(laudo.snapshot_emissao["relatorio"], default=str))

    def test_historico_preserva_autor_datas_motivo_e_hash_emissao(self):
        laudo = self.gerar()
        self.emitir(laudo)
        nova = self.revisar(laudo, "Motivo rastreável QA")
        resposta = self.api.get(f"/api/laudos/{laudo.pk}/historico/")
        self.assertEqual(resposta.status_code, 200, resposta.data)
        emitidos = [e for e in resposta.data if e["acao"] == "EMITIDO"]
        self.assertEqual(len(emitidos), 1)
        self.assertEqual(emitidos[0]["autor"], self.responsavel.pk)
        self.assertTrue(emitidos[0]["criado_em"])
        self.assertEqual(emitidos[0]["dados"]["snapshot_hash"], laudo.snapshot_hash)
        eventos_revisao = [e for e in resposta.data if e["motivo"] == "Motivo rastreável QA"]
        self.assertTrue(eventos_revisao)
        self.assertEqual(eventos_revisao[0]["dados"]["nova_versao_id"], nova.pk)

    def test_snapshot_corrompido_nao_e_servido_como_documento_integro(self):
        laudo = self.gerar()
        self.emitir(laudo)
        adulterado = deepcopy(laudo.snapshot_emissao)
        adulterado["relatorio"]["laudo"]["conclusao"] = "Adulteração QA"
        Laudo.objects.filter(pk=laudo.pk).update(snapshot_emissao=adulterado)
        resposta = self.api.get(f"/api/laudos/{laudo.pk}/relatorio-tecnico/")
        self.assertEqual(resposta.status_code, 400, resposta.data)
        self.assertIn("integridade", str(resposta.data).lower())

    def test_emissao_incorpora_foto_e_preserva_evidencia_apos_remover_arquivo_original(self):
        origem, achado = self.origem_por_rota()
        buffer = io.BytesIO()
        Image.new("RGB", (800, 600), color=(10, 30, 50)).save(buffer, format="PNG")
        nome = default_storage.save("qa/evidencia-documental.png", ContentFile(buffer.getvalue()))
        AchadoImagem.objects.create(achado=achado, arquivo=nome, legenda="Evidência original QA")
        resposta = self.api.post("/api/laudos/gerar/", {"relatorio_origem": origem.pk}, format="json")
        self.assertEqual(resposta.status_code, 201, resposta.data)
        laudo = Laudo.objects.get(pk=resposta.data["id"])
        self.emitir(laudo)
        snapshot = deepcopy(laudo.snapshot_emissao)
        documento = deepcopy(self.relatorio(laudo))
        self.assertIn("data:image/png;base64,", json.dumps(snapshot))
        self.assertIn("Evidência original QA", json.dumps(snapshot, ensure_ascii=False))
        default_storage.delete(nome)
        self.assertEqual(self.relatorio(laudo), documento)
        laudo.refresh_from_db()
        self.assertEqual(laudo.snapshot_emissao, snapshot)

    def anexo_qa(self, laudo, legenda="Anexo privado QA"):
        buffer = io.BytesIO()
        Image.new("RGB", (800, 600), color=(30, 60, 90)).save(buffer, format="PNG")
        conteudo = buffer.getvalue()
        resposta = self.api.post(f"/api/laudos/{laudo.pk}/anexos/", {
            "imagem": SimpleUploadedFile("evidencia-qa.png", conteudo, content_type="image/png"),
            "legenda": legenda,
        }, format="multipart")
        self.assertEqual(resposta.status_code, 201, resposta.data)
        return resposta.data, conteudo

    def test_upload_anexo_registra_bytes_hash_autoria_e_acesso_privado(self):
        laudo = self.gerar()
        anexo, conteudo = self.anexo_qa(laudo)
        self.assertEqual(anexo["sha256"], hashlib.sha256(conteudo).hexdigest())
        self.assertEqual(anexo["criado_por"], self.responsavel.pk)
        self.assertEqual(anexo["tamanho"], len(conteudo))
        self.assertTrue(anexo["data_uri"].startswith("data:image/png;base64,"))
        self.assertNotIn("url", anexo)
        self.api.force_authenticate(self.portal)
        self.assertEqual(self.api.get(f"/api/laudos/{laudo.pk}/anexos/").status_code, 404)
        self.api.force_authenticate(self.responsavel)
        self.emitir(laudo)
        self.api.force_authenticate(self.portal)
        self.assertEqual(self.api.get(f"/api/laudos/{laudo.pk}/anexos/").status_code, 200)
        self.api.force_authenticate(self.outro_portal)
        self.assertEqual(self.api.get(f"/api/laudos/{laudo.pk}/anexos/").status_code, 404)

    def test_anexos_emitidos_sao_imutaveis_e_revisao_preserva_copia(self):
        laudo = self.gerar()
        anexo, conteudo = self.anexo_qa(laudo)
        self.emitir(laudo)
        resposta = self.api.delete(f"/api/laudos/{laudo.pk}/anexos/{anexo['id']}/")
        self.assertEqual(resposta.status_code, 400, resposta.data)
        resposta = self.api.post(f"/api/laudos/{laudo.pk}/anexos/", {
            "imagem": SimpleUploadedFile("posterior.png", conteudo, content_type="image/png"), "legenda": "Posterior",
        }, format="multipart")
        self.assertEqual(resposta.status_code, 400, resposta.data)
        revisao = self.revisar(laudo)
        resposta = self.api.get(f"/api/laudos/{revisao.pk}/anexos/")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(len(resposta.data), 1)
        self.assertEqual(resposta.data[0]["sha256"], anexo["sha256"])
        self.assertNotEqual(resposta.data[0]["id"], anexo["id"])

    def test_anexo_invalido_ou_excedente_e_recusado_sem_persistir(self):
        laudo = self.gerar()
        resposta = self.api.post(f"/api/laudos/{laudo.pk}/anexos/", {
            "imagem": SimpleUploadedFile("falso.png", b"arquivo invalido", content_type="image/png")}, format="multipart")
        self.assertEqual(resposta.status_code, 400, resposta.data)
        with override_settings(LAUDOS_MAX_IMAGEM_BYTES=10):
            buffer = io.BytesIO()
            Image.new("RGB", (800, 600)).save(buffer, format="PNG")
            resposta = self.api.post(f"/api/laudos/{laudo.pk}/anexos/", {
                "imagem": SimpleUploadedFile("grande.png", buffer.getvalue(), content_type="image/png")}, format="multipart")
            self.assertEqual(resposta.status_code, 400, resposta.data)
        self.assertFalse(laudo.anexos.exists())

    def test_remocao_de_anexo_draft_registra_hash_e_autor_na_trilha(self):
        laudo = self.gerar()
        anexo, _ = self.anexo_qa(laudo)
        resposta = self.api.delete(f"/api/laudos/{laudo.pk}/anexos/{anexo['id']}/")
        self.assertEqual(resposta.status_code, 204)
        self.assertFalse(laudo.anexos.exists())
        evento = laudo.eventos.get(acao="ANEXO_REMOVIDO")
        self.assertEqual(evento.autor_id, self.responsavel.pk)
        self.assertEqual(evento.dados["sha256"], anexo["sha256"])

    def test_mudar_cliente_na_origem_nao_move_documento_emitido_para_outro_portal(self):
        laudo = self.gerar()
        self.emitir(laudo)
        Inspecao.objects.filter(pk=self.inspecao.pk).update(cliente=self.outro_cliente)
        self.api.force_authenticate(self.portal)
        self.assertEqual(self.api.get(f"/api/laudos/{laudo.pk}/").status_code, 200)
        self.assertEqual(self.api.get(f"/api/laudos/{laudo.pk}/pdf/").status_code, 200)
        self.api.force_authenticate(self.outro_portal)
        self.assertEqual(self.api.get(f"/api/laudos/{laudo.pk}/").status_code, 404)
        self.assertEqual(self.api.get(f"/api/laudos/{laudo.pk}/pdf/").status_code, 404)

    def test_rascunho_cancelado_nao_e_publicado_no_portal(self):
        laudo = self.gerar()
        resposta = self.api.post(f"/api/laudos/{laudo.pk}/cancelar/", {"motivo": "Rascunho incorreto QA"}, format="json")
        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.api.force_authenticate(self.portal)
        self.assertEqual(self.api.get(f"/api/laudos/{laudo.pk}/").status_code, 404)

    def test_emissao_recusa_origem_que_mudou_de_cliente_apos_geracao(self):
        laudo = self.gerar()
        Inspecao.objects.filter(pk=self.inspecao.pk).update(cliente=self.outro_cliente)
        resposta = self.api.post(f"/api/laudos/{laudo.pk}/emitir/", {}, format="json")
        self.assertEqual(resposta.status_code, 400, resposta.data)
        laudo.refresh_from_db()
        self.assertEqual(laudo.status, "RASCUNHO")
