from unittest.mock import patch

from django.test import TestCase

from apps.cadastros.models import TipoAnomalia, TipoComponente, TipoRecomendacao
from apps.coletas.models import Achado, Carregamento, Relatorio, StatusCarregamento
from . import test_atividades as fixtures
from .models import BalanceamentoPlano, ServicoCampo, TipoServico


class AnaliseBalanceamentoTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        fixtures.AtividadeCorretivaTest.setUpTestData.__func__(cls)
        cls.componente = TipoComponente.objects.create(nome="Rotor")
        cls.componente.tecnologias.add(cls.tecnologia)
        cls.componente_outro = TipoComponente.objects.create(nome="Disjuntor")
        cls.componente_outro.tecnologias.add(cls.vibracao)
        cls.componente_sem_vinculo = TipoComponente.objects.create(nome="Sem vínculo")
        cls.anomalia = TipoAnomalia.objects.create(nome="Desbalanceamento")
        cls.anomalia.tecnologias.add(cls.tecnologia)
        cls.anomalia_outra = TipoAnomalia.objects.create(nome="Outra tecnologia")
        cls.anomalia_outra.tecnologias.add(cls.vibracao)
        cls.anomalia_alternativa = TipoAnomalia.objects.create(nome="Outra anomalia de balanceamento")
        cls.anomalia_alternativa.tecnologias.add(cls.tecnologia)
        cls.recomendacao = TipoRecomendacao.objects.create(nome="Balancear rotor")
        cls.recomendacao.tecnologias.add(cls.tecnologia)
        cls.recomendacao.anomalias.add(cls.anomalia)
        cls.recomendacao_outra = TipoRecomendacao.objects.create(nome="Outra tecnologia")
        cls.recomendacao_outra.tecnologias.add(cls.vibracao)
        cls.recomendacao_outra.anomalias.add(cls.anomalia)
        cls.recomendacao_sem_anomalia = TipoRecomendacao.objects.create(nome="Sem anomalia vinculada")
        cls.recomendacao_sem_anomalia.tecnologias.add(cls.tecnologia)

    abrir = fixtures.AtividadeCorretivaTest.abrir
    urls_item = fixtures.AtividadeCorretivaTest.urls_item

    def setUp(self):
        fixtures.AtividadeCorretivaTest.setUp(self)
        self.atividade = self.abrir()
        base = self.urls_item(self.atividade)
        self.api.patch(base + "/condicao/", {"condicao": self.condicao.pk}, format="json")
        self.servico_id = self.api.post(base + "/analise/", {}, format="json").data["id"]
        self.url = base + "/balanceamento/"
        self.tecnica = {
            "condicao": self.condicao.pk, "tipo_componente": self.componente.pk,
            "componente_texto": "Rotor do exaustor", "detalhe": "Lado do acoplamento",
            "tipo_anomalia": self.anomalia.pk, "recomendacao": self.recomendacao.pk,
        }

    def salvar(self, **alteracoes):
        return self.api.patch(self.url, {
            "tecnica": {**self.tecnica, **alteracoes}, "rotacao_hz": "29.74",
        }, format="json")

    def test_catalogos_somente_da_tecnologia_e_recomendacao_da_anomalia(self):
        resposta = self.api.get(self.url + "catalogos/")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual([x["id"] for x in resposta.data["tipos_componente"]], [self.componente.pk])
        self.assertNotIn(self.anomalia_outra.pk, [x["id"] for x in resposta.data["tipos_anomalia"]])
        self.assertEqual(resposta.data["recomendacoes"], [])
        resposta = self.api.get(self.url + f"catalogos/?anomalia={self.anomalia.pk}")
        self.assertEqual([x["id"] for x in resposta.data["recomendacoes"]], [self.recomendacao.pk])
        self.assertEqual(self.api.get(self.url + f"catalogos/?anomalia={self.anomalia_outra.pk}").status_code, 400)
        self.assertEqual(self.api.get(self.url + "catalogos/?anomalia=abc").status_code, 400)

    def test_salva_campos_existentes_e_mantem_atividade_e_equipamento(self):
        resposta = self.salvar()
        self.assertEqual(resposta.status_code, 200, resposta.data)
        achado = Achado.objects.get(pk=resposta.data["tecnica"]["id"])
        servico = ServicoCampo.objects.get(pk=self.servico_id)
        self.assertEqual(achado.item_id, servico.item_id)
        self.assertEqual(achado.tipo_componente, self.componente)
        self.assertEqual(achado.componente_texto, "Rotor do exaustor")
        self.assertEqual(achado.detalhe, "Lado do acoplamento")
        self.assertEqual(achado.recomendacao, self.recomendacao)
        self.assertEqual(servico.analise_tecnica, achado)
        self.assertIsNone(servico.achado)  # A análise de origem não é sobrescrita.
        self.assertEqual(servico.rotacao_rpm, 1784)
        self.assertEqual(Carregamento.objects.count(), 1)
        self.assertEqual(Relatorio.objects.count(), 1)
        self.assertEqual(ServicoCampo.objects.count(), 1)
        self.assertEqual(self.api.get(self.url).data["tecnica"]["id"], achado.pk)

    def test_rejeita_componente_de_outra_tecnologia_e_sem_vinculo(self):
        for componente in [self.componente_outro, self.componente_sem_vinculo]:
            with self.subTest(componente=componente.pk):
                resposta = self.salvar(tipo_componente=componente.pk)
                self.assertEqual(resposta.status_code, 400)
                self.assertIn("tipo_componente", resposta.data)
        self.assertFalse(Achado.objects.exists())

    def test_rejeita_anomalia_e_recomendacoes_incompativeis(self):
        for dados in [
            {"tipo_anomalia": self.anomalia_outra.pk},
            {"tipo_anomalia": self.anomalia_alternativa.pk},
            {"recomendacao": self.recomendacao_outra.pk},
            {"recomendacao": self.recomendacao_sem_anomalia.pk},
        ]:
            with self.subTest(dados=dados):
                self.assertEqual(self.salvar(**dados).status_code, 400)
        self.assertFalse(Achado.objects.exists())

    def test_edicao_parcial_valida_combinacao_final_e_nao_duplica(self):
        primeira = self.salvar()
        resposta = self.api.patch(self.url, {"tecnica": {"detalhe": "Novo detalhe"}}, format="json")
        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.assertEqual(resposta.data["tecnica"]["id"], primeira.data["tecnica"]["id"])
        self.assertEqual(resposta.data["tecnica"]["detalhe"], "Novo detalhe")
        resposta = self.api.patch(self.url, {"tecnica": {"tipo_anomalia": self.anomalia_alternativa.pk}}, format="json")
        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(Achado.objects.count(), 1)
        self.assertEqual(Achado.objects.get().tipo_anomalia_id, self.anomalia.pk)

    def test_catalogo_desativado_nao_e_aceito_em_edicao(self):
        self.salvar()
        self.componente.ativo = False
        self.componente.save()
        self.assertEqual(self.api.patch(self.url, {"tecnica": {"detalhe": "Mudança"}}, format="json").status_code, 400)

    def test_endpoints_preditivos_nao_contornam_validacao(self):
        # A visibilidade é unificada (Análise final precisa enxergar o achado), mas os
        # campos técnicos com validação cruzada continuam só editáveis pelo endpoint
        # especializado de balanceamento — e não dá para criar/realocar achados
        # corretivos pelo endpoint genérico.
        resposta = self.salvar()
        achado_id = resposta.data["tecnica"]["id"]
        self.assertEqual(self.api.get("/api/achados/").data["count"], 1)
        self.assertEqual(self.api.get(f"/api/achados/{achado_id}/").status_code, 200)
        self.assertEqual(
            self.api.patch(f"/api/achados/{achado_id}/", {"tipo_componente": self.componente_outro.pk}, format="json").status_code,
            400,
        )
        self.assertEqual(self.api.post("/api/achados/", {**self.tecnica, "item": self.atividade["itens"][0]["id"]}, format="json").status_code, 400)
        # Campos de escritório (fora da lista técnica) continuam editáveis normalmente.
        resposta_ok = self.api.patch(f"/api/achados/{achado_id}/", {"observacoes": "Revisado no escritório"}, format="json")
        self.assertEqual(resposta_ok.status_code, 200, resposta_ok.data)

    def test_permissoes_e_escopo_por_cliente(self):
        self.salvar()
        self.api.force_authenticate(self.leitor)
        self.assertEqual(self.api.get(self.url).status_code, 200)
        self.assertEqual(self.api.get(self.url + "catalogos/").status_code, 200)
        self.assertEqual(self.salvar().status_code, 403)
        self.assertEqual(self.api.post("/api/balanceamento-planos/", {"servico": self.servico_id, "numero": 1}, format="json").status_code, 403)
        self.leitor.cliente = self.outro
        self.leitor.save()
        self.assertEqual(self.api.get(self.url).status_code, 404)
        self.assertEqual(self.api.get(self.url + "catalogos/").status_code, 404)

    def test_medicoes_reutilizam_modelos_e_rejeitam_plano_de_outro_servico(self):
        plano = self.api.post("/api/balanceamento-planos/", {
            "servico": self.servico_id, "numero": 1, "massa_teste_g": "30", "angulo_teste": "0",
            "massa_final_g": "100", "angulo_final": "110",
        }, format="json")
        self.assertEqual(plano.status_code, 201, plano.data)
        medicao = {
            "servico": self.servico_id, "plano": plano.data["id"], "numero_mancal": 2, "direcao": "H",
            "reference_mms": "12.31", "reference_fase": "110",
        }
        ponto = self.api.post("/api/balanceamento-pontos/", medicao, format="json")
        self.assertEqual(ponto.status_code, 201, ponto.data)
        self.assertFalse(ponto.data["completo"])
        # Trial Run só no ponto de foco — precisa ser designado antes de poder gravá-lo.
        foco = self.api.patch(f"/api/servicos/{self.servico_id}/", {"ponto_foco": ponto.data["id"]}, format="json")
        self.assertEqual(foco.status_code, 200, foco.data)
        trial = self.api.patch(f'/api/balanceamento-pontos/{ponto.data["id"]}/', {"trial_mms": "23.95", "trial_fase": "133"}, format="json")
        self.assertEqual(trial.status_code, 200, trial.data)
        final = self.api.patch(f'/api/balanceamento-pontos/{ponto.data["id"]}/', {"trim_mms": "1.70", "trim_fase": "136"}, format="json")
        self.assertEqual(final.status_code, 200, final.data)
        self.assertTrue(final.data["completo"])
        self.assertAlmostEqual(float(final.data["reducao_pct"]), 86.2, delta=0.1)
        outra = self.abrir()
        base = self.urls_item(outra)
        self.api.patch(base + "/condicao/", {"condicao": self.condicao.pk}, format="json")
        outro_id = self.api.post(base + "/analise/", {}, format="json").data["id"]
        outro_plano = BalanceamentoPlano.objects.create(servico_id=outro_id, numero=1)
        self.assertEqual(self.api.post("/api/balanceamento-pontos/", {**medicao, "plano": outro_plano.pk}, format="json").status_code, 400)
        self.assertEqual(self.api.patch(f'/api/balanceamento-pontos/{ponto.data["id"]}/', {"plano": outro_plano.pk}, format="json").status_code, 400)
        self.assertEqual(self.api.patch(f'/api/balanceamento-planos/{plano.data["id"]}/', {"servico": outro_id}, format="json").status_code, 400)

    def test_atividade_fechada_bloqueia_salvamento_e_medicoes(self):
        self.salvar()
        Carregamento.objects.filter(pk=self.atividade["id"]).update(status=StatusCarregamento.TRANSFERIDA)
        self.assertEqual(self.salvar().status_code, 400)
        self.assertEqual(self.api.post("/api/balanceamento-planos/", {"servico": self.servico_id, "numero": 1}, format="json").status_code, 400)
        self.assertEqual(self.api.patch(f"/api/servicos/{self.servico_id}/", {"rotacao_hz": "30"}, format="json").status_code, 400)

    def test_alinhamento_nao_abre_balanceamento(self):
        Carregamento.objects.filter(pk=self.atividade["id"]).update(tipo_corretiva=TipoServico.ALINHAMENTO)
        self.assertEqual(self.api.get(self.url).status_code, 400)
        self.assertEqual(self.salvar().status_code, 400)

    def test_falha_no_servico_reverte_criacao_da_analise(self):
        with patch("apps.servicos.models.ServicoCampo.save", side_effect=RuntimeError("falha")):
            with self.assertRaises(RuntimeError):
                self.salvar()
        self.assertFalse(Achado.objects.exists())
