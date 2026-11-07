"""
Item 2.1.1.6 — restrição de usuário de cliente a setores do próprio cliente.

Sem restrição = cliente inteiro (compatível). Com restrição = só os setores listados.
Testa: leitura de equipamentos e medições, a varredura de listas, o isolamento entre
clientes e quem pode configurar (Master interno, Master do mesmo cliente, nunca a si mesmo).
"""
from datetime import date

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import Nivel, Perfil, RestricaoSetorUsuario, User
from apps.cadastros.models import Area, Cliente, Empresa, Equipamento, Setor, TipoEquipamento
from apps.coletas.models import Inspecao, MedicaoVibracao


def _usuario(email, perfil, nivel, **vinculo):
    return User.objects.create_user(email=email, password="uma frase senha longa 2026", nome=email,
                                    perfil=perfil, nivel=nivel, **vinculo)


class EscopoPorSetorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.empresa = Empresa.objects.create(nome="Prestadora", cnpj="11.222.333/0001-81")
        cls.cliente_a = Cliente.objects.create(nome="A", cnpj="11.111.111/0001-11")
        cls.cliente_b = Cliente.objects.create(nome="B", cnpj="22.222.222/0001-22")
        tipo = TipoEquipamento.objects.create(nome="Motor")
        area_a = Area.objects.create(cliente=cls.cliente_a, codigo="A1", nome="Planta")
        cls.setor1 = Setor.objects.create(area=area_a, codigo="S1", nome="Setor 1")
        cls.setor2 = Setor.objects.create(area=area_a, codigo="S2", nome="Setor 2")
        cls.eq1 = Equipamento.objects.create(setor=cls.setor1, tag="E-1", nome="Motor 1", tipo_equipamento=tipo)
        cls.eq2 = Equipamento.objects.create(setor=cls.setor2, tag="E-2", nome="Motor 2", tipo_equipamento=tipo)
        area_b = Area.objects.create(cliente=cls.cliente_b, codigo="B1", nome="Outra")
        setor_b = Setor.objects.create(area=area_b, codigo="SB", nome="Setor B")
        cls.eq_b = Equipamento.objects.create(setor=setor_b, tag="B-1", nome="Motor B", tipo_equipamento=tipo)
        cls.interno = _usuario("int@t.test", Perfil.GESTOR, Nivel.MASTER, empresa=cls.empresa)
        cls.livre = _usuario("livre@a.test", Perfil.CLIENTE_PCM, Nivel.PLENO, cliente=cls.cliente_a)
        cls.restrito = _usuario("restrito@a.test", Perfil.CLIENTE_PCM, Nivel.PLENO, cliente=cls.cliente_a)
        RestricaoSetorUsuario.objects.create(usuario=cls.restrito, setor=cls.setor1)
        cls.master_a = _usuario("master@a.test", Perfil.CLIENTE_CORP, Nivel.MASTER, cliente=cls.cliente_a)
        cls.outro_b = _usuario("b@b.test", Perfil.CLIENTE_PCM, Nivel.PLENO, cliente=cls.cliente_b)

    def setUp(self):
        cache.clear()

    def api(self, usuario):
        c = APIClient()
        c.force_authenticate(usuario)
        return c

    def ids(self, usuario, url="/api/equipamentos/"):
        return {e["id"] for e in self.api(usuario).get(url, {"page_size": 100}).data["results"]}

    # --- leitura -----------------------------------------------------------
    def test_cliente_sem_restricao_ve_todo_o_cliente(self):
        self.assertEqual(self.ids(self.livre), {self.eq1.pk, self.eq2.pk})

    def test_cliente_restrito_so_ve_o_setor_permitido(self):
        self.assertEqual(self.ids(self.restrito), {self.eq1.pk})
        self.assertEqual(self.api(self.restrito).get(f"/api/equipamentos/{self.eq2.pk}/").status_code, 404)

    def test_interno_nunca_e_restringido(self):
        self.assertEqual(self.ids(self.interno), {self.eq1.pk, self.eq2.pk, self.eq_b.pk})

    def test_cliente_de_outra_empresa_nao_ve_o_parque_alheio(self):
        self.assertEqual(self.ids(self.outro_b), {self.eq_b.pk})

    def test_medicoes_do_setor_fora_da_restricao_somem(self):
        insp = Inspecao.objects.create(cliente=self.cliente_a, tecnico=self.interno, data=date(2026, 10, 1),
                                       tipo_analise="VIBRACAO")
        m1 = MedicaoVibracao.objects.create(inspecao=insp, equipamento=self.eq1, ponto_medicao="P1", direcao="V",
                                            velocidade_rms="1.00", rotacao_rpm=1800)
        m2 = MedicaoVibracao.objects.create(inspecao=insp, equipamento=self.eq2, ponto_medicao="P2", direcao="V",
                                            velocidade_rms="1.00", rotacao_rpm=1800)
        ids_livre = self.ids(self.livre, "/api/medicoes-vibracao/")
        ids_restrito = self.ids(self.restrito, "/api/medicoes-vibracao/")
        self.assertEqual(ids_livre, {m1.pk, m2.pk})
        self.assertEqual(ids_restrito, {m1.pk})

    # --- configuração ------------------------------------------------------
    def test_master_interno_configura_setores_do_cliente(self):
        r = self.api(self.interno).put(f"/api/usuarios/{self.livre.pk}/setores/",
                                       {"setores": [self.setor2.pk]}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.ids(self.livre), {self.eq2.pk})
        # remover a restrição volta ao cliente inteiro
        self.api(self.interno).put(f"/api/usuarios/{self.livre.pk}/setores/", {"setores": []}, format="json")
        self.assertEqual(self.ids(self.livre), {self.eq1.pk, self.eq2.pk})

    def test_master_do_cliente_restringe_colega_da_propria_empresa(self):
        r = self.api(self.master_a).put(f"/api/minha-equipe/{self.livre.pk}/setores/",
                                        {"setores": [self.setor1.pk]}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.ids(self.livre), {self.eq1.pk})

    def test_master_do_cliente_nao_restringe_a_si_mesmo(self):
        r = self.api(self.master_a).put(f"/api/minha-equipe/{self.master_a.pk}/setores/",
                                        {"setores": [self.setor1.pk]}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_cliente_nao_master_nao_configura(self):
        r = self.api(self.livre).put(f"/api/minha-equipe/{self.restrito.pk}/setores/",
                                     {"setores": []}, format="json")
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.ids(self.restrito), {self.eq1.pk})

    def test_setor_de_outro_cliente_e_recusado(self):
        r = self.api(self.interno).put(f"/api/usuarios/{self.livre.pk}/setores/",
                                       {"setores": [self.eq_b.setor.pk]}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertFalse(self.livre.restricoes_setor.exists())

    def test_master_de_outro_cliente_nao_configura(self):
        outro_master = _usuario("mb@b.test", Perfil.CLIENTE_CORP, Nivel.MASTER, cliente=self.cliente_b)
        r = self.api(outro_master).put(f"/api/minha-equipe/{self.livre.pk}/setores/",
                                       {"setores": []}, format="json")
        self.assertEqual(r.status_code, 404)  # minha-equipe só lista colegas da própria empresa

    def test_payload_invalido_e_400(self):
        r = self.api(self.interno).put(f"/api/usuarios/{self.livre.pk}/setores/", {"setores": "x"}, format="json")
        self.assertEqual(r.status_code, 400)


class VarreduraSetorListasTests(EscopoPorSetorTests):
    # Herda os testes da classe-base; os novos chamam _preparar() para não alterar a fixture antiga.
    """Varredura: nenhuma rota de lista (ou detalhe) de dado de cliente mostra item de setor fora da restrição."""

    def _preparar(self):
        from apps.coletas.models import Inspecao
        self.insp_fora = Inspecao.objects.create(cliente=self.cliente_a, tecnico=self.interno,
                                                 data=date(2026, 10, 1), tipo_analise="VIBRACAO")
        self.insp_dentro = Inspecao.objects.create(cliente=self.cliente_a, tecnico=self.interno,
                                                   data=date(2026, 10, 2), tipo_analise="VIBRACAO")
        MedicaoVibracao.objects.create(inspecao=self.insp_fora, equipamento=self.eq2, ponto_medicao="P",
                                       direcao="V", velocidade_rms="1.00", rotacao_rpm=1800)
        MedicaoVibracao.objects.create(inspecao=self.insp_dentro, equipamento=self.eq1, ponto_medicao="P",
                                       direcao="V", velocidade_rms="1.00", rotacao_rpm=1800)

    def test_inspecao_so_aparece_se_tem_medicao_no_setor_permitido(self):
        self._preparar()
        ids_livre = self.ids(self.livre, "/api/inspecoes/")
        ids_restrito = self.ids(self.restrito, "/api/inspecoes/")
        self.assertEqual(ids_livre, {self.insp_fora.pk, self.insp_dentro.pk})
        self.assertEqual(ids_restrito, {self.insp_dentro.pk})
        self.assertEqual(self.api(self.restrito).get(f"/api/inspecoes/{self.insp_fora.pk}/").status_code, 404)

    def test_detalhe_de_medicao_fora_do_setor_da_404(self):
        self._preparar()
        m_fora = MedicaoVibracao.objects.get(inspecao=self.insp_fora)
        self.assertEqual(self.api(self.restrito).get(f"/api/medicoes-vibracao/{m_fora.pk}/").status_code, 404)

    def test_varredura_de_listas_nao_vaza_equipamento_de_outro_setor(self):
        self._preparar()
        for url in ("/api/equipamentos/", "/api/inspecoes/", "/api/medicoes-vibracao/",
                    "/api/itens-inspecao/", "/api/carregamentos/", "/api/achados/"):
            resposta = self.api(self.restrito).get(url, {"page_size": 100})
            self.assertEqual(resposta.status_code, 200, url)
            corpo = resposta.content.decode()
            self.assertNotIn('"E-2"', corpo, url)


class IndicadoresPorSetorTests(EscopoPorSetorTests):
    """2.1.1.6 nos painéis e relatórios: filtros centrais (`relatorios.filtros`) respeitam o setor."""

    def test_equipamentos_do_indicador_respeitam_o_setor(self):
        from apps.relatorios import filtros as F
        f = F.ler_filtros({})
        self.assertEqual(set(F.equipamentos(self.livre, f).values_list("pk", flat=True)), {self.eq1.pk, self.eq2.pk})
        self.assertEqual(set(F.equipamentos(self.restrito, f).values_list("pk", flat=True)), {self.eq1.pk})

    def test_painel_operacional_responde_ao_restrito_sem_vazar(self):
        from apps.relatorios import filtros as F
        from apps.relatorios.indicadores import operacional
        f = F.ler_filtros({})
        resultado = operacional(self.restrito, f)
        self.assertIsInstance(resultado, dict)
        r = self.api(self.restrito).get("/api/dashboard/")
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("E-2", r.content.decode())

    def test_restrito_sem_setor_nao_ve_nada_no_parque(self):
        from apps.relatorios import filtros as F
        RestricaoSetorUsuario.objects.filter(usuario=self.restrito).delete()
        RestricaoSetorUsuario.objects.create(usuario=self.restrito, setor=self.setor2)
        f = F.ler_filtros({})
        self.assertEqual(set(F.equipamentos(self.restrito, f).values_list("pk", flat=True)), {self.eq2.pk})


class NotificacoesPorSetorTests(EscopoPorSetorTests):
    """2.1.1.6 em notificações: aviso de equipamento de outro setor some para o restrito; aviso do sistema fica."""

    def test_aviso_de_equipamento_fora_do_setor_nao_aparece(self):
        from apps.coletas.models import Inspecao
        from apps.notificacoes.models import EventoNotificacao, EventoPreditivo, Notificacao
        insp = Inspecao.objects.create(cliente=self.cliente_a, tecnico=self.interno, data=date(2026, 10, 3),
                                       tipo_analise="VIBRACAO")
        evento_fora = EventoPreditivo.objects.create(
            medicao_tipo="vibracao", medicao_id=1, sequencia=1, inspecao=insp, equipamento=self.eq2,
            regra_versao="t", criticidade="CRITICO",
        )
        evento_dentro = EventoPreditivo.objects.create(
            medicao_tipo="vibracao", medicao_id=2, sequencia=1, inspecao=insp, equipamento=self.eq1,
            regra_versao="t", criticidade="CRITICO",
        )
        tipo = EventoNotificacao.values[0] if hasattr(EventoNotificacao, "values") else EventoNotificacao.choices[0][0]
        fora = Notificacao.objects.create(destinatario=self.restrito, evento=tipo, titulo="F", mensagem="f",
                                          evento_preditivo=evento_fora, chave="n-fora")
        dentro = Notificacao.objects.create(destinatario=self.restrito, evento=tipo, titulo="D", mensagem="d",
                                            evento_preditivo=evento_dentro, chave="n-dentro")
        sistema = Notificacao.objects.create(destinatario=self.restrito, evento=tipo, titulo="S", mensagem="s",
                                             chave="n-sistema")
        ids = {n["id"] for n in self.api(self.restrito).get("/api/notificacoes/", {"page_size": 100}).data["results"]}
        self.assertIn(dentro.pk, ids)
        self.assertIn(sistema.pk, ids)
        self.assertNotIn(fora.pk, ids)
        livre_ids = {n["id"] for n in self.api(self.livre).get("/api/notificacoes/", {"page_size": 100}).data["results"]}
        self.assertEqual(livre_ids, set())  # livre não é destinatário de nada: escopo por destinatário continua


class RestricaoSetorOspEAnexosTests(TestCase):
    """2.1.1.6 aplicada às OSPs (e sub-recursos), aos anexos de documento e à mídia de evidências e assinaturas."""

    @classmethod
    def setUpTestData(cls):
        from apps.coletas.models import AnexoDocumento
        from apps.osp.models import EvidenciaOSP, OrdemServico, PecaOSP

        cls.cli_a = Cliente.objects.create(nome="A", cnpj="11.111.111/0001-11")
        cls.cli_b = Cliente.objects.create(nome="B", cnpj="22.222.222/0001-22")
        tipo = TipoEquipamento.objects.create(nome="Motor")
        cls.s1 = Setor.objects.create(area=Area.objects.create(cliente=cls.cli_a, codigo="A", nome="A"), codigo="S1", nome="Setor 1")
        cls.s2 = Setor.objects.create(area=Area.objects.create(cliente=cls.cli_a, codigo="B", nome="B"), codigo="S2", nome="Setor 2")
        setor_b = Setor.objects.create(area=Area.objects.create(cliente=cls.cli_b, codigo="C", nome="C"), codigo="SB", nome="Setor B")
        cls.eq1 = Equipamento.objects.create(setor=cls.s1, tag="E-1", nome="M1", tipo_equipamento=tipo)
        cls.eq2 = Equipamento.objects.create(setor=cls.s2, tag="E-2", nome="M2", tipo_equipamento=tipo)
        cls.eqb = Equipamento.objects.create(setor=setor_b, tag="B-1", nome="MB", tipo_equipamento=tipo)

        cls.restrito = _usuario("restrito@a.test", "CLIENTE_PCM", "PLENO", cliente=cls.cli_a)
        RestricaoSetorUsuario.objects.create(usuario=cls.restrito, setor=cls.s1)
        cls.livre = _usuario("livre@a.test", "CLIENTE_PCM", "PLENO", cliente=cls.cli_a)
        cls.pcm_b = _usuario("pcm@b.test", "CLIENTE_PCM", "PLENO", cliente=cls.cli_b)
        cls.tecnico = _usuario("tec@t.test", "TECNICO", "PLENO")

        cls.os1 = OrdemServico.objects.create(cliente=cls.cli_a, equipamento=cls.eq1, titulo="OS 1", grau_risco="GR3")
        cls.os2 = OrdemServico.objects.create(cliente=cls.cli_a, equipamento=cls.eq2, titulo="OS 2", grau_risco="GR3")
        cls.osb = OrdemServico.objects.create(cliente=cls.cli_b, equipamento=cls.eqb, titulo="OS B", grau_risco="GR3")
        cls.peca1 = PecaOSP.objects.create(osp=cls.os1, descricao="Filtro", quantidade=1, custo_unitario=5)
        cls.peca2 = PecaOSP.objects.create(osp=cls.os2, descricao="Óleo", quantidade=1, custo_unitario=5)
        cls.ev1 = EvidenciaOSP.objects.create(osp=cls.os1, fase="DEPOIS", arquivo="osp/evidencias/ev1.png")
        cls.ev2 = EvidenciaOSP.objects.create(osp=cls.os2, fase="DEPOIS", arquivo="osp/evidencias/ev2.png")
        cls.an1 = AnexoDocumento.objects.create(cliente=cls.cli_a, equipamento=cls.eq1, nome_original="a1.pdf",
                                                tamanho_bytes=1, sha256="0" * 64, arquivo="anexos/documentos/a1.pdf",
                                                visivel_cliente=True)
        cls.an2 = AnexoDocumento.objects.create(cliente=cls.cli_a, equipamento=cls.eq2, nome_original="a2.pdf",
                                                tamanho_bytes=1, sha256="0" * 64, arquivo="anexos/documentos/a2.pdf",
                                                visivel_cliente=True)

    def api(self, usuario):
        c = APIClient()
        c.force_authenticate(usuario)
        return c

    def ids(self, usuario, url):
        return [x["id"] for x in self.api(usuario).get(url).json()["results"]]

    def test_restrito_ve_so_as_osps_do_proprio_setor(self):
        ids = self.ids(self.restrito, "/api/osps/")
        self.assertIn(self.os1.pk, ids)
        self.assertNotIn(self.os2.pk, ids)

    def test_setor_fora_da_restricao_da_404_no_detalhe(self):
        self.assertEqual(self.api(self.restrito).get(f"/api/osps/{self.os1.pk}/").status_code, 200)
        self.assertEqual(self.api(self.restrito).get(f"/api/osps/{self.os2.pk}/").status_code, 404)

    def test_sem_restricao_o_cliente_ve_todas_as_osps_do_cliente(self):
        ids = self.ids(self.livre, "/api/osps/")
        self.assertIn(self.os1.pk, ids)
        self.assertIn(self.os2.pk, ids)
        self.assertNotIn(self.osb.pk, ids)

    def test_outro_cliente_da_404_na_osp_alheia(self):
        self.assertEqual(self.api(self.pcm_b).get(f"/api/osps/{self.os1.pk}/").status_code, 404)

    def test_interno_nao_e_restringido(self):
        ids = self.ids(self.tecnico, "/api/osps/")
        self.assertIn(self.os1.pk, ids)
        self.assertIn(self.os2.pk, ids)

    def test_subrecursos_de_osp_respeitam_o_setor(self):
        self.assertEqual(self.ids(self.restrito, "/api/osp-evidencias/"), [self.ev1.pk])
        self.assertEqual(self.api(self.restrito).get(f"/api/osp-evidencias/{self.ev2.pk}/").status_code, 404)
        self.assertEqual(self.ids(self.restrito, "/api/osp-pecas/"), [self.peca1.pk])
        self.assertEqual(self.api(self.restrito).get(f"/api/osp-pecas/{self.peca2.pk}/").status_code, 404)

    def test_anexo_de_documento_respeita_o_setor_do_equipamento(self):
        self.assertEqual(self.ids(self.restrito, "/api/anexos-documentos/"), [self.an1.pk])
        self.assertEqual(self.api(self.restrito).get(f"/api/anexos-documentos/{self.an2.pk}/").status_code, 404)
        self.assertEqual(sorted(self.ids(self.livre, "/api/anexos-documentos/")), sorted([self.an1.pk, self.an2.pk]))

    def test_midia_de_evidencia_e_documento_segue_o_setor(self):
        from apps.core import midia
        self.assertTrue(midia.pode_ver(self.restrito, self.ev1.arquivo.name))
        self.assertFalse(midia.pode_ver(self.restrito, self.ev2.arquivo.name))
        self.assertTrue(midia.pode_ver(self.restrito, self.an1.arquivo.name))
        self.assertFalse(midia.pode_ver(self.restrito, self.an2.arquivo.name))
        self.assertTrue(midia.pode_ver(self.livre, self.ev2.arquivo.name))
        self.assertFalse(midia.pode_ver(self.pcm_b, self.ev1.arquivo.name))
