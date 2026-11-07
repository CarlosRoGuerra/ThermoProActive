"""
Anexo I 2.6.2.2 a 2.6.2.8 — checklist, evidências, peças, tempo de execução e
assinatura do cliente, em cima da máquina de estados de `services.TRANSICOES`.

Cobre: permissões por perfil (Master cadastra checklist; equipe responde; cliente só
lê e assina), escopo por cliente (OSP de outro cliente = 404), checklist obrigatório
antes de finalizar, custo do material sem mexer no ROI, tempo registrado nas
transições, assinatura com hash do estado e imutabilidade.
"""
import base64
import io
import shutil
import tempfile
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from apps.cadastros.models import Area, Cliente, Equipamento, Setor, TipoEquipamento
from apps.osp import execucao
from apps.osp.models import (
    ApontamentoExecucao, AssinaturaOSP, EvidenciaOSP, HistoricoOSP, ItemModeloChecklist, ModeloChecklist,
    OrdemServico, PecaOSP, StatusOSP, TipoHistorico,
)

User = get_user_model()
SENHA = "SenhaSuperForte#2026!!"


def png_bytes(cor=(200, 30, 30)):
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), cor).save(buf, "PNG")
    return buf.getvalue()


def png_base64():
    return "data:image/png;base64," + base64.b64encode(png_bytes()).decode()


class OSPExecucaoBase(TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.mkdtemp()
        cls._override = override_settings(MEDIA_ROOT=cls._tmp)
        cls._override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._override.disable()
        shutil.rmtree(cls._tmp, ignore_errors=True)

    @classmethod
    def setUpTestData(cls):
        cls.cliente = Cliente.objects.create(nome="Indústria A", cnpj="11.111.111/0001-11")
        cls.outro = Cliente.objects.create(nome="Indústria B", cnpj="22.222.222/0001-22")
        cls.tipo_motor = TipoEquipamento.objects.create(nome="Motor")
        cls.tipo_bomba = TipoEquipamento.objects.create(nome="Bomba")
        setor = Setor.objects.create(area=Area.objects.create(cliente=cls.cliente, nome="Utilidades"), nome="Bombas")
        cls.equipamento = Equipamento.objects.create(setor=setor, tag="BB-01", nome="Bomba 01",
                                                     tipo_equipamento=cls.tipo_bomba)
        setor_b = Setor.objects.create(area=Area.objects.create(cliente=cls.outro, nome="Área B"), nome="Setor B")
        cls.equipamento_b = Equipamento.objects.create(setor=setor_b, tag="BB-99", nome="Bomba B",
                                                       tipo_equipamento=cls.tipo_bomba)

        def usuario(email, perfil, cliente=None, nivel="PLENO"):
            return User.objects.create_user(email=email, password=SENHA, nome=email.split("@")[0],
                                            perfil=perfil, nivel=nivel, cliente=cliente)

        cls.master = usuario("master@thermo.com", "ADMIN", nivel="MASTER")
        cls.tecnico = usuario("tecnico@thermo.com", "TECNICO")
        cls.pcm = usuario("pcm@a.com", "CLIENTE_PCM", cls.cliente)
        cls.manut = usuario("manut@a.com", "CLIENTE_MANUT", cls.cliente)
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

    def status(self, osp, valor):
        OrdemServico.objects.filter(pk=osp.pk).update(status=valor)
        osp.refresh_from_db()
        return osp

    def mover(self, user, osp, status, motivo=None):
        corpo = {"status": status}
        if motivo is not None:
            corpo["motivo"] = motivo
        return self.logar(user).patch(f"/api/osps/{osp.pk}/status/", corpo, format="json")

    def modelo(self, nome="Checklist de bomba", tipo=None, tecnologia=None, obrigatorio=True, itens=("Conferir alinhamento",)):
        m = ModeloChecklist.objects.create(nome=nome, tipo_equipamento=tipo, tecnologia=tecnologia,
                                           obrigatorio_para_finalizar=obrigatorio)
        for ordem, desc in enumerate(itens, start=1):
            ItemModeloChecklist.objects.create(modelo=m, ordem=ordem, descricao=desc, obrigatorio=True)
        return m


# --------------------------------------------------------------------------- 2.6.2.2
class ChecklistTests(OSPExecucaoBase):
    def test_master_cadastra_modelo_e_equipe_nao_cadastra(self):
        corpo = {"nome": "Bomba", "tipo_equipamento": self.tipo_bomba.pk, "obrigatorio_para_finalizar": True,
                 "ativo": True}
        self.assertEqual(self.logar(self.tecnico).post("/api/osp-checklists/", corpo, format="json").status_code, 403)
        self.assertEqual(self.logar(self.master).post("/api/osp-checklists/", corpo, format="json").status_code, 201)

    def test_cliente_nao_le_catalogo_de_checklist(self):
        self.modelo()
        self.assertEqual(self.logar(self.pcm).get("/api/osp-checklists/").status_code, 403)

    def test_modelo_so_vale_para_o_tipo_de_equipamento_certo(self):
        osp = self.nova_osp()
        do_tipo = self.modelo("Bomba", tipo=self.tipo_bomba)
        self.modelo("Motor", tipo=self.tipo_motor)
        nomes = [m["nome"] for m in execucao.checklist_da_osp(osp)]
        self.assertEqual(nomes, [do_tipo.nome])

    def test_finalizar_bloqueado_com_item_obrigatorio_sem_resposta(self):
        osp = self.status(self.nova_osp(), StatusOSP.AGUARDANDO_APROVACAO)
        self.modelo()
        r = self.mover(self.master, osp, "FINALIZADA")
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["codigo"], "checklist_pendente")
        self.assertEqual(OrdemServico.objects.get(pk=osp.pk).status, StatusOSP.AGUARDANDO_APROVACAO)

    def test_responder_libera_a_finalizacao(self):
        osp = self.status(self.nova_osp(), StatusOSP.AGUARDANDO_APROVACAO)
        modelo = self.modelo()
        item = modelo.itens.get()
        r = self.logar(self.tecnico).post(f"/api/osps/{osp.pk}/checklist/",
                                          {"respostas": [{"item": item.pk, "situacao": "CONFORME"}]}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["pendencias"], [])
        self.assertEqual(self.mover(self.master, osp, "FINALIZADA").status_code, 200)

    def test_modelo_que_nao_exige_nao_bloqueia(self):
        osp = self.status(self.nova_osp(), StatusOSP.AGUARDANDO_APROVACAO)
        self.modelo(obrigatorio=False)
        self.assertEqual(self.mover(self.master, osp, "FINALIZADA").status_code, 200)

    def test_cliente_nao_responde_checklist(self):
        osp = self.nova_osp()
        item = self.modelo().itens.get()
        r = self.logar(self.pcm).post(f"/api/osps/{osp.pk}/checklist/",
                                      {"respostas": [{"item": item.pk, "situacao": "CONFORME"}]}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_item_de_modelo_que_nao_se_aplica_e_recusado(self):
        osp = self.nova_osp()
        outro_modelo = self.modelo("Motor", tipo=self.tipo_motor)
        item = outro_modelo.itens.get()
        r = self.logar(self.tecnico).post(f"/api/osps/{osp.pk}/checklist/",
                                          {"respostas": [{"item": item.pk, "situacao": "CONFORME"}]}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["codigo"], "item_nao_aplicavel")

    def test_resposta_em_osp_finalizada_e_recusada(self):
        osp = self.status(self.nova_osp(), StatusOSP.FINALIZADA)
        item = self.modelo().itens.get()
        r = self.logar(self.tecnico).post(f"/api/osps/{osp.pk}/checklist/",
                                          {"respostas": [{"item": item.pk, "situacao": "CONFORME"}]}, format="json")
        self.assertEqual(r.status_code, 409)

    def test_resposta_fica_no_historico_e_upsert_nao_duplica(self):
        osp = self.nova_osp()
        item = self.modelo().itens.get()
        for situacao in ("NAO_CONFORME", "CONFORME"):
            self.logar(self.tecnico).post(f"/api/osps/{osp.pk}/checklist/",
                                          {"respostas": [{"item": item.pk, "situacao": situacao}]}, format="json")
        self.assertEqual(osp.respostas_checklist.count(), 1)
        self.assertEqual(osp.respostas_checklist.get().situacao, "CONFORME")
        self.assertEqual(osp.historico.filter(tipo=TipoHistorico.EDICAO).count(), 2)

    def test_item_respondido_nao_pode_ser_apagado(self):
        osp = self.nova_osp()
        modelo = self.modelo()
        item = modelo.itens.get()
        self.logar(self.tecnico).post(f"/api/osps/{osp.pk}/checklist/",
                                      {"respostas": [{"item": item.pk, "situacao": "CONFORME"}]}, format="json")
        self.assertEqual(self.logar(self.master).delete(f"/api/osp-checklist-itens/{item.pk}/").status_code, 400)
        self.assertEqual(osp.respostas_checklist.count(), 1)


# --------------------------------------------------------------------------- 2.6.2.7
class PecasTests(OSPExecucaoBase):
    def test_pecas_somam_custo_real_e_nao_mexem_no_roi(self):
        osp = self.nova_osp(pred_mao_obra_valor=Decimal("1000"), pred_material_valor=Decimal("200"),
                            emerg_mao_obra_valor=Decimal("5000"), emerg_material_valor=Decimal("900"))
        roi_antes = OrdemServico.objects.get(pk=osp.pk).retorno_investimento
        self.logar(self.tecnico).post("/api/osp-pecas/", {"osp": osp.pk, "descricao": "Rolamento 6205",
                                                          "codigo": "R-6205", "quantidade": "2",
                                                          "unidade": "un", "custo_unitario": "150.00"}, format="json")
        self.logar(self.tecnico).post("/api/osp-pecas/", {"osp": osp.pk, "descricao": "Graxa",
                                                          "quantidade": "0.5", "unidade": "kg",
                                                          "custo_unitario": "80.00"}, format="json")
        osp.refresh_from_db()
        self.assertEqual(osp.custo_material_real, Decimal("340.00"))
        # Custo real = estimativa sem material (1000) + material aplicado (340).
        self.assertEqual(osp.custo_real, Decimal("1340.00"))
        self.assertEqual(osp.retorno_investimento, roi_antes)

    def test_remover_peca_recalcula_o_custo(self):
        osp = self.nova_osp()
        peca = PecaOSP.objects.create(osp=osp, descricao="Vedação", quantidade=Decimal("3"),
                                      custo_unitario=Decimal("10"))
        execucao.atualizar_custo_material(osp)
        # Excluir peça exige nível Master (InternoEditaClienteVisualiza): o técnico não apaga.
        self.assertEqual(self.logar(self.tecnico).delete(f"/api/osp-pecas/{peca.pk}/").status_code, 403)
        r = self.logar(self.master).delete(f"/api/osp-pecas/{peca.pk}/")
        self.assertEqual(r.status_code, 204)
        osp.refresh_from_db()
        self.assertIsNone(osp.custo_material_real)

    def test_quantidade_zero_e_recusada(self):
        osp = self.nova_osp()
        r = self.logar(self.tecnico).post("/api/osp-pecas/", {"osp": osp.pk, "descricao": "x", "quantidade": "0",
                                                              "custo_unitario": "1"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_peca_em_osp_encerrada_e_recusada(self):
        osp = self.status(self.nova_osp(), StatusOSP.CANCELADA)
        r = self.logar(self.tecnico).post("/api/osp-pecas/", {"osp": osp.pk, "descricao": "x", "quantidade": "1",
                                                              "custo_unitario": "1"}, format="json")
        self.assertEqual(r.status_code, 409)

    def test_cliente_le_so_as_pecas_do_proprio_cliente_e_nao_lanca(self):
        osp = self.nova_osp()
        PecaOSP.objects.create(osp=osp, descricao="Filtro", quantidade=Decimal("1"), custo_unitario=Decimal("5"))
        self.assertEqual(self.logar(self.pcm).get("/api/osp-pecas/").data["count"], 1)
        self.assertEqual(self.logar(self.pcm_b).get("/api/osp-pecas/").data["count"], 0)
        r = self.logar(self.pcm).post("/api/osp-pecas/", {"osp": osp.pk, "descricao": "x", "quantidade": "1",
                                                          "custo_unitario": "1"}, format="json")
        self.assertEqual(r.status_code, 403)


# --------------------------------------------------------------------------- 2.6.2.4
class EvidenciasTests(OSPExecucaoBase):
    def foto(self, nome="antes.png", conteudo=None):
        return SimpleUploadedFile(nome, conteudo if conteudo is not None else png_bytes(), content_type="image/png")

    def test_tecnico_envia_foto_antes_e_depois(self):
        osp = self.nova_osp()
        for fase in ("ANTES", "DEPOIS"):
            r = self.logar(self.tecnico).post("/api/osp-evidencias/",
                                              {"osp": osp.pk, "fase": fase, "arquivo": self.foto()},
                                              format="multipart")
            self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(osp.evidencias_osp.count(), 2)
        self.assertTrue(osp.evidencias_osp.filter(fase="ANTES").exists())

    def test_arquivo_que_nao_e_imagem_e_recusado(self):
        osp = self.nova_osp()
        r = self.logar(self.tecnico).post("/api/osp-evidencias/",
                                          {"osp": osp.pk, "fase": "ANTES",
                                           "arquivo": self.foto("falso.png", b"isto nao e imagem")},
                                          format="multipart")
        self.assertEqual(r.status_code, 400)

    def test_cliente_ve_as_fotos_da_propria_osp_e_nao_envia(self):
        osp = self.nova_osp()
        ev = EvidenciaOSP.objects.create(osp=osp, fase="DEPOIS", arquivo=self.foto("depois.png"))
        lista = self.logar(self.pcm).get("/api/osp-evidencias/").data
        self.assertEqual(lista["count"], 1)
        # URL absoluta: com front e API em origens diferentes, a relativa dava 404 no <img>.
        self.assertTrue(lista["results"][0]["url"].startswith("http://testserver/api/media/"))
        self.assertEqual(self.logar(self.pcm_b).get("/api/osp-evidencias/").data["count"], 0)
        r = self.logar(self.pcm).post("/api/osp-evidencias/",
                                      {"osp": osp.pk, "fase": "ANTES", "arquivo": self.foto()}, format="multipart")
        self.assertEqual(r.status_code, 403)
        # A foto sai pela regra de mídia, autenticada e com escopo do cliente.
        self.assertEqual(self.logar(self.pcm).get(f"/api/media/{ev.arquivo.name}").status_code, 200)
        self.assertEqual(self.logar(self.pcm_b).get(f"/api/media/{ev.arquivo.name}").status_code, 404)

    def test_foto_de_osp_encerrada_e_recusada(self):
        osp = self.status(self.nova_osp(), StatusOSP.FINALIZADA)
        r = self.logar(self.tecnico).post("/api/osp-evidencias/",
                                          {"osp": osp.pk, "fase": "ANTES", "arquivo": self.foto()}, format="multipart")
        self.assertEqual(r.status_code, 409)


# --------------------------------------------------------------------------- 2.6.2.8
class TempoExecucaoTests(OSPExecucaoBase):
    def test_entrar_e_sair_de_execucao_abre_e_fecha_intervalo(self):
        osp = self.status(self.nova_osp(), StatusOSP.EM_ANALISE)
        self.assertEqual(self.mover(self.tecnico, osp, "EM_EXECUCAO").status_code, 200)
        aberto = ApontamentoExecucao.objects.get(osp=osp)
        self.assertIsNone(aberto.fim)
        self.assertEqual(self.mover(self.tecnico, osp, "EXECUTADA").status_code, 200)
        aberto.refresh_from_db()
        self.assertIsNotNone(aberto.fim)
        self.assertGreaterEqual(aberto.duracao_minutos, 0)

    def test_rejeicao_abre_novo_intervalo_e_o_tempo_soma(self):
        osp = self.status(self.nova_osp(), StatusOSP.EM_ANALISE)
        self.assertEqual(self.mover(self.tecnico, osp, "EM_EXECUCAO").status_code, 200)
        self.assertEqual(self.mover(self.tecnico, osp, "AGUARDANDO_APROVACAO").status_code, 200)
        self.assertEqual(self.mover(self.master, osp, "EM_EXECUCAO", motivo="Refazer a vedação").status_code, 200)
        self.assertEqual(osp.apontamentos.count(), 2)  # 1 fechado + 1 aberto
        self.mover(self.tecnico, osp, "EXECUTADA")
        osp.refresh_from_db()
        self.assertEqual(osp.apontamentos.filter(fim__isnull=False).count(), 2)
        self.assertIsInstance(execucao.tempo_execucao_minutos(osp), int)

    def test_apontamento_manual_valido(self):
        osp = self.nova_osp()
        fim = timezone.now() - timedelta(hours=1)
        inicio = fim - timedelta(minutes=90)
        r = self.logar(self.tecnico).post("/api/osp-apontamentos/", {
            "osp": osp.pk, "inicio": inicio.isoformat(), "fim": fim.isoformat(), "observacao": "Troca de rolamento",
        }, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["origem"], "MANUAL")
        self.assertEqual(r.json()["duracao_minutos"], 90)
        self.assertEqual(execucao.tempo_execucao_minutos(osp), 90)

    def test_apontamento_com_fim_antes_do_inicio_ou_no_futuro_e_recusado(self):
        osp = self.nova_osp()
        agora = timezone.now()
        r = self.logar(self.tecnico).post("/api/osp-apontamentos/", {
            "osp": osp.pk, "inicio": agora.isoformat(), "fim": (agora - timedelta(hours=1)).isoformat(),
        }, format="json")
        self.assertEqual(r.status_code, 400)
        r = self.logar(self.tecnico).post("/api/osp-apontamentos/", {
            "osp": osp.pk, "inicio": agora.isoformat(), "fim": (agora + timedelta(hours=1)).isoformat(),
        }, format="json")
        self.assertEqual(r.status_code, 400)

    def test_cliente_le_tempo_do_proprio_cliente_e_nao_aponta(self):
        osp = self.nova_osp()
        fim = timezone.now() - timedelta(minutes=5)
        ApontamentoExecucao.objects.create(osp=osp, inicio=fim - timedelta(minutes=30), fim=fim,
                                           origem="MANUAL")
        self.assertEqual(self.logar(self.pcm).get("/api/osp-apontamentos/").data["count"], 1)
        self.assertEqual(self.logar(self.pcm_b).get("/api/osp-apontamentos/").data["count"], 0)
        r = self.logar(self.pcm).post("/api/osp-apontamentos/", {"osp": osp.pk, "inicio": fim.isoformat(),
                                                                  "fim": timezone.now().isoformat()}, format="json")
        self.assertEqual(r.status_code, 403)


# --------------------------------------------------------------------------- 2.6.2.6
class AssinaturaTests(OSPExecucaoBase):
    def assinar(self, user, osp, **extras):
        corpo = {"osp": osp.pk, "nome": "Maria Souza", "cargo": "Gerente de manutenção",
                 "assinatura_png": png_base64()}
        corpo.update(extras)
        return self.logar(user).post("/api/osp-assinaturas/", corpo, format="json")

    def test_cliente_assina_executada_e_registra_hash_do_estado(self):
        osp = self.status(self.nova_osp(), StatusOSP.EXECUTADA)
        esperado = execucao.estado_sha256(osp)
        r = self.assinar(self.pcm, osp, nome="Maria Souza")
        self.assertEqual(r.status_code, 201, r.content)
        assinatura = AssinaturaOSP.objects.get(osp=osp)
        self.assertEqual(assinatura.estado_sha256, esperado)
        self.assertEqual(len(assinatura.estado_sha256), 64)
        self.assertEqual(assinatura.assinado_por, self.pcm)
        self.assertTrue(assinatura.imagem.name.startswith("osp/assinaturas/"))
        historico = osp.historico.get(tipo=TipoHistorico.ASSINATURA)
        self.assertEqual(historico.alteracoes["estado_sha256"], esperado)
        self.assertEqual(historico.ator_perfil, "CLIENTE_PCM")

    def test_ip_do_cliente_e_gravado(self):
        osp = self.status(self.nova_osp(), StatusOSP.EXECUTADA)
        self.logar(self.pcm)
        r = self.api.post("/api/osp-assinaturas/", {"osp": osp.pk, "nome": "A", "cargo": "B",
                                                    "assinatura_png": png_base64()},
                          format="json", REMOTE_ADDR="10.1.2.3")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(AssinaturaOSP.objects.get(osp=osp).ip, "10.1.2.3")

    def test_assinatura_so_uma_vez(self):
        osp = self.status(self.nova_osp(), StatusOSP.EXECUTADA)
        self.assertEqual(self.assinar(self.pcm, osp).status_code, 201)
        r = self.assinar(self.pcm, osp)
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["codigo"], "ja_assinada")

    def test_assinatura_e_imutavel(self):
        osp = self.status(self.nova_osp(), StatusOSP.EXECUTADA)
        self.assinar(self.pcm, osp)
        assinatura = AssinaturaOSP.objects.get(osp=osp)
        assinatura.cargo = "Outro"
        with self.assertRaises(ValueError):
            assinatura.save()
        with self.assertRaises(ValueError):
            assinatura.delete()
        self.assertEqual(AssinaturaOSP.objects.get(pk=assinatura.pk).cargo, "Gerente de manutenção")

    def test_so_depois_da_execucao(self):
        osp = self.nova_osp()  # ABERTA
        r = self.assinar(self.pcm, osp)
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["codigo"], "estado_nao_assinavel")

    def test_perfil_que_nao_aprova_e_interno_nao_assinam(self):
        osp = self.status(self.nova_osp(), StatusOSP.EXECUTADA)
        self.assertEqual(self.assinar(self.manut, osp).status_code, 403)
        self.assertEqual(self.assinar(self.tecnico, osp).status_code, 403)

    def test_cliente_nao_assina_osp_de_outro_cliente(self):
        osp = self.status(self.nova_osp(), StatusOSP.EXECUTADA)
        r = self.assinar(self.pcm_b, osp)
        self.assertEqual(r.status_code, 404)
        self.assertFalse(AssinaturaOSP.objects.filter(osp=osp).exists())

    def test_assinatura_invalida_e_recusada(self):
        osp = self.status(self.nova_osp(), StatusOSP.EXECUTADA)
        r = self.assinar(self.pcm, osp, assinatura_png="data:image/png;base64,bm90IGEgcG5n")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["codigo"], "assinatura_invalida")

    def test_hash_muda_quando_o_estado_muda(self):
        osp = self.status(self.nova_osp(), StatusOSP.EXECUTADA)
        antes = execucao.estado_sha256(osp)
        PecaOSP.objects.create(osp=osp, descricao="Óleo", quantidade=Decimal("1"), custo_unitario=Decimal("9"))
        execucao.atualizar_custo_material(osp)
        self.assertNotEqual(antes, execucao.estado_sha256(osp))

    def test_imagem_da_assinatura_sai_so_para_o_cliente_da_osp(self):
        osp = self.status(self.nova_osp(), StatusOSP.EXECUTADA)
        self.assinar(self.pcm, osp)
        nome = AssinaturaOSP.objects.get(osp=osp).imagem.name
        self.assertEqual(self.logar(self.pcm).get(f"/api/media/{nome}").status_code, 200)
        self.assertEqual(self.logar(self.pcm_b).get(f"/api/media/{nome}").status_code, 404)

    def test_historico_registra_assinatura_sem_alterar_linhas_anteriores(self):
        osp = self.status(self.nova_osp(), StatusOSP.EXECUTADA)
        anteriores = list(osp.historico.values_list("pk", "tipo"))
        self.assinar(self.pcm, osp)
        self.assertEqual(list(osp.historico.values_list("pk", "tipo"))[:len(anteriores)], anteriores)
        self.assertTrue(HistoricoOSP.objects.filter(osp=osp, tipo=TipoHistorico.ASSINATURA).exists())
