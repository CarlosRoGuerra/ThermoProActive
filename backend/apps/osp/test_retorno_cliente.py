"""
O Portal consulta e devolve informação — nada além disso.

Regra de 2026-09-21, que reverte a de 2026-09-18 (quando o Master do cliente
passou a cadastrar o próprio parque). Estes testes existem porque a regra já
afrouxou uma vez: se alguém trocar a permission_class de volta, a suíte quebra
aqui e explica o porquê, em vez de o vazamento só aparecer em produção.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.cadastros.models import Area, Cliente, Equipamento, Rota, Setor
from apps.osp.models import OrdemServico

User = get_user_model()
SENHA = "SenhaSuperForte#2026!!"


class BaseOSP(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(nome="Indústria A", cnpj="11.111.111/0001-11")
        self.outro = Cliente.objects.create(nome="Indústria B", cnpj="22.222.222/0001-22")
        area = Area.objects.create(cliente=self.cliente, nome="Utilidades")
        setor = Setor.objects.create(area=area, nome="Casa de bombas")
        self.equipamento = Equipamento.objects.create(setor=setor, tag="BB-01", nome="Bomba 01")

        self.master = User.objects.create_user(
            email="master@a.com", password=SENHA, nome="Master do cliente",
            perfil="CLIENTE_CORP", nivel="MASTER", cliente=self.cliente,
        )
        self.manutentor = User.objects.create_user(
            email="manutentor@a.com", password=SENHA, nome="Manutentor",
            perfil="CLIENTE_MANUT", nivel="JUNIOR", cliente=self.cliente,
        )
        self.de_fora = User.objects.create_user(
            email="master@b.com", password=SENHA, nome="Master da outra empresa",
            perfil="CLIENTE_CORP", nivel="MASTER", cliente=self.outro,
        )
        self.tecnico = User.objects.create_user(
            email="tecnico@thermo.com", password=SENHA, nome="Técnico",
            perfil="TECNICO", nivel="PLENO",
        )

        self.osp = OrdemServico.objects.create(
            numero=OrdemServico.proximo_numero(),
            cliente=self.cliente, equipamento=self.equipamento,
            titulo="Bomba 01 — rolamento", grau_risco="GR2",
            anomalia="Desgaste de rolamento no mancal LA.",
            recomendacao="Substituir rolamento.",
        )
        self.api = APIClient()
        self.api.force_authenticate(self.master)


class ClienteDevolveInformacao(BaseOSP):
    def test_preenche_etapas_da_execucao(self):
        r = self.api.patch(f"/api/osps/{self.osp.pk}/", {
            "planejado_em": "2026-09-21T08:00:00-03:00",
            "executado_em": "2026-09-22T14:30:00-03:00",
            "executado_por": self.manutentor.pk,
            "descricao_corretiva": "Rolamento 6308 substituído; alinhamento conferido.",
            "resultado_confirmacao": "CONFIRMADO",
        }, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.osp.refresh_from_db()
        self.assertEqual(self.osp.executado_por, self.manutentor)
        self.assertEqual(self.osp.resultado_confirmacao, "CONFIRMADO")
        self.assertIn("6308", self.osp.descricao_corretiva)

    def test_preenche_avaliacao_de_resultados(self):
        r = self.api.patch(f"/api/osps/{self.osp.pk}/", {
            "pred_mao_obra_h": "4.00", "pred_mao_obra_valor": "600.00",
            "pred_material_valor": "900.00",
            "emerg_mao_obra_h": "16.00", "emerg_mao_obra_valor": "2400.00",
            "emerg_producao_valor": "18000.00",
            "custo_real": "1500.00",
        }, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.osp.refresh_from_db()
        self.assertEqual(str(self.osp.pred_mao_obra_valor), "600.00")
        # O ROI da Seção D é justamente o que esses números alimentam.
        self.assertEqual(self.osp.total_preditiva, 1500)
        self.assertEqual(self.osp.total_emergencial, 20400)
        self.assertEqual(self.osp.retorno_investimento, 18900)

    def test_qualquer_nivel_do_portal_responde_nao_so_o_master(self):
        api = APIClient()
        api.force_authenticate(self.manutentor)
        r = api.patch(f"/api/osps/{self.osp.pk}/",
                      {"descricao_corretiva": "Troca feita pelo turno da noite."},
                      format="json")
        self.assertEqual(r.status_code, 200, r.data)


class ClienteNaoTocaNoDiagnostico(BaseOSP):
    def test_campos_tecnicos_sao_ignorados_no_patch(self):
        r = self.api.patch(f"/api/osps/{self.osp.pk}/", {
            "titulo": "TÍTULO REESCRITO PELO CLIENTE",
            "grau_risco": "GR4",
            "anomalia": "Nada de errado, pode ignorar.",
            "recomendacao": "Nenhuma.",
            "status": "CANCELADA",
            "acompanhamento": "CORRIGIDA",
            "descricao_corretiva": "Rolamento substituído.",
        }, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.osp.refresh_from_db()
        # O que era dele passou; o diagnóstico da CONTRATADA ficou intacto.
        self.assertEqual(self.osp.descricao_corretiva, "Rolamento substituído.")
        self.assertEqual(self.osp.titulo, "Bomba 01 — rolamento")
        self.assertEqual(self.osp.grau_risco, "GR2")
        self.assertEqual(self.osp.anomalia, "Desgaste de rolamento no mancal LA.")
        self.assertEqual(self.osp.status, "ABERTA")

    def test_nao_abre_osp(self):
        r = self.api.post("/api/osps/", {
            "cliente": self.cliente.pk, "equipamento": self.equipamento.pk,
            "titulo": "OSP inventada pelo cliente",
        }, format="json")
        self.assertEqual(r.status_code, 403)

    def test_nao_exclui_osp(self):
        r = self.api.delete(f"/api/osps/{self.osp.pk}/")
        self.assertEqual(r.status_code, 403)
        self.assertTrue(OrdemServico.objects.filter(pk=self.osp.pk).exists())

    def test_nao_move_o_status_pelo_endpoint_dedicado(self):
        r = self.api.patch(f"/api/osps/{self.osp.pk}/status/",
                           {"status": "FINALIZADA"}, format="json")
        self.assertEqual(r.status_code, 403)
        self.osp.refresh_from_db()
        self.assertEqual(self.osp.status, "ABERTA")

    def test_interno_continua_movendo_o_status(self):
        api = APIClient()
        api.force_authenticate(self.tecnico)
        r = api.patch(f"/api/osps/{self.osp.pk}/status/",
                      {"status": "FINALIZADA"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)


class RetornoNaoVazaEntreInquilinos(BaseOSP):
    def test_nao_aponta_executor_de_outra_empresa(self):
        r = self.api.patch(f"/api/osps/{self.osp.pk}/",
                           {"executado_por": self.de_fora.pk}, format="json")
        self.assertEqual(r.status_code, 400)
        self.osp.refresh_from_db()
        self.assertIsNone(self.osp.executado_por_id)

    def test_nao_responde_osp_de_outra_empresa(self):
        alheia = OrdemServico.objects.create(
            numero=OrdemServico.proximo_numero(),
            cliente=self.outro, equipamento=self.equipamento, titulo="OSP da outra empresa",
        )
        r = self.api.patch(f"/api/osps/{alheia.pk}/",
                           {"descricao_corretiva": "invadindo"}, format="json")
        self.assertEqual(r.status_code, 404)


class ListaDaEquipeAlimentaOsSelects(BaseOSP):
    """
    O retorno pede "quem planejou/executou/finalizou", e as opções vêm de
    /minha-equipe/. Se a lista truncar, o colaborador simplesmente não aparece
    para ser escolhido — e ninguém percebe.
    """

    def test_entrega_a_equipe_inteira_mesmo_acima_da_pagina_padrao(self):
        for i in range(30):
            User.objects.create_user(
                email=f"colab{i}@a.com", password=SENHA, nome=f"Colaborador {i:02d}",
                perfil="CLIENTE_MANUT", nivel="JUNIOR", cliente=self.cliente,
            )
        r = self.api.get("/api/minha-equipe/?page_size=200")
        self.assertEqual(r.status_code, 200)
        # 30 criados aqui + master e manutentor do setUp.
        self.assertEqual(r.data["count"], 32)
        self.assertEqual(len(r.data["results"]), 32)

    def test_nao_lista_gente_de_outra_empresa(self):
        r = self.api.get("/api/minha-equipe/?page_size=200")
        emails = {u["email"] for u in r.data["results"]}
        self.assertNotIn(self.de_fora.email, emails)
        self.assertNotIn(self.tecnico.email, emails)


class PortalSoConsulta(BaseOSP):
    """O parque, as rotas, as inspeções e as análises voltaram a ser só leitura."""

    def test_le_o_proprio_parque(self):
        for rota in ("/api/equipamentos/", "/api/rotas/", "/api/inspecoes/", "/api/achados/"):
            with self.subTest(rota=rota):
                self.assertEqual(self.api.get(rota).status_code, 200)

    def test_nao_cadastra_equipamento(self):
        setor = Setor.objects.get(nome="Casa de bombas")
        r = self.api.post("/api/equipamentos/",
                          {"setor": setor.pk, "tag": "BB-99", "nome": "Bomba fantasma"},
                          format="json")
        self.assertEqual(r.status_code, 403)
        self.assertFalse(Equipamento.objects.filter(tag="BB-99").exists())

    def test_nao_edita_equipamento(self):
        r = self.api.patch(f"/api/equipamentos/{self.equipamento.pk}/",
                           {"nome": "renomeado"}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_nao_cria_rota(self):
        r = self.api.post("/api/rotas/",
                          {"cliente": self.cliente.pk, "nome": "Rota do cliente",
                           "equipamentos": [self.equipamento.pk]},
                          format="json")
        self.assertEqual(r.status_code, 403)
        self.assertFalse(Rota.objects.exists())

    def test_nao_cria_inspecao(self):
        r = self.api.post("/api/inspecoes/",
                          {"cliente": self.cliente.pk, "data": "2026-09-21",
                           "tipo_analise": "VIBRACAO"},
                          format="json")
        self.assertEqual(r.status_code, 403)

    def test_interno_continua_cadastrando(self):
        api = APIClient()
        api.force_authenticate(self.tecnico)
        setor = Setor.objects.get(nome="Casa de bombas")
        r = api.post("/api/equipamentos/",
                     {"setor": setor.pk, "tag": "BB-02", "nome": "Bomba 02"},
                     format="json")
        self.assertEqual(r.status_code, 201, r.data)
