"""
Regressão da auditoria de segurança — cadastros: M2M de Rota (A-02), `/empresas/` só interno (A-05)
e o filtro de tenant único em servicos (A-04).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.cadastros.models import Area, Cliente, Empresa, Equipamento, Rota, Setor, TecnologiaAnalise
from apps.coletas.models import Carregamento, ItemInspecao

User = get_user_model()


class RotaEEmpresaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a = Cliente.objects.create(nome="Cliente A", cnpj="11.111.111/0001-11")
        cls.b = Cliente.objects.create(nome="Cliente B", cnpj="22.222.222/0001-22")
        setor = lambda c, cod: Setor.objects.create(  # noqa: E731
            area=Area.objects.create(cliente=c, codigo=cod, nome=f"Area {cod}"), codigo=cod, nome=f"Setor {cod}")
        cls.eq_a = Equipamento.objects.create(setor=setor(cls.a, "A"), tag="A-001", nome="Motor A")
        cls.eq_b = Equipamento.objects.create(setor=setor(cls.b, "B"), tag="B-001", nome="Motor B")
        cls.tec = TecnologiaAnalise.objects.create(nome="Vibração", sigla="VIB")
        cls.tecnico = User.objects.create_user(email="t@x.test", password="x", nome="T", perfil="TECNICO")
        cls.cliente_a = User.objects.create_user(email="c@a.test", password="x", nome="C", perfil="CLIENTE_CORP",
                                                 nivel="MASTER", cliente=cls.a)
        Empresa.objects.create(nome="Prestadora", cnpj="39.923.567/0001-75")

    def api(self, usuario):
        api = APIClient()
        api.force_authenticate(usuario)
        return api

    def test_rota_recusa_equipamento_de_outro_cliente_ate_para_interno(self):
        api = self.api(self.tecnico)
        r = api.post("/api/rotas/", {"cliente": self.a.pk, "nome": "R", "equipamentos": [self.eq_a.pk, self.eq_b.pk]},
                     format="json")
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn("B-001", str(r.data))
        self.assertFalse(Rota.objects.filter(nome="R").exists())

    def test_rota_do_proprio_cliente_continua_valida_e_patch_revalida(self):
        api = self.api(self.tecnico)
        r = api.post("/api/rotas/", {"cliente": self.a.pk, "nome": "R", "equipamentos": [self.eq_a.pk]}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        rota = Rota.objects.get(pk=r.data["id"])
        self.assertEqual(api.patch(f"/api/rotas/{rota.pk}/", {"equipamentos": [self.eq_a.pk, self.eq_b.pk]},
                                   format="json").status_code, 400)
        # trocar o cliente da rota com equipamento do antigo também é recusado
        self.assertEqual(api.patch(f"/api/rotas/{rota.pk}/", {"cliente": self.b.pk}, format="json").status_code, 400)
        self.assertEqual(list(rota.equipamentos.all()), [self.eq_a])

    def test_carregamento_nao_copia_equipamento_alheio_nem_aceita_rota_de_outro_cliente(self):
        rota = Rota.objects.create(cliente=self.a, nome="Suja")
        rota.equipamentos.set([self.eq_a, self.eq_b])  # contornando a API (dado legado/admin)
        api = self.api(self.tecnico)
        r = api.post("/api/carregamentos/", {
            "cliente": self.a.pk, "tecnologia": self.tec.pk, "rota": rota.pk, "data_termino_novo": "2026-10-01",
        }, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        tags = set(ItemInspecao.objects.filter(carregamento_id=r.data["id"]).values_list("equipamento__tag", flat=True))
        self.assertEqual(tags, {"A-001"})
        outro = api.post("/api/carregamentos/", {
            "cliente": self.b.pk, "tecnologia": self.tec.pk, "rota": rota.pk, "data_termino_novo": "2026-10-01",
        }, format="json")
        self.assertEqual(outro.status_code, 400)

    def test_empresas_so_equipe_interna(self):
        self.assertEqual(self.api(self.tecnico).get("/api/empresas/").status_code, 200)
        self.assertEqual(self.api(self.cliente_a).get("/api/empresas/").status_code, 403)
        self.assertEqual(self.api(self.cliente_a).post("/api/empresas/", {}, format="json").status_code, 403)

    def test_servicos_e_atividades_falham_fechado_para_cliente_sem_vinculo(self):
        orfao = User.objects.create_user(email="o@x.test", password="x", nome="O", perfil="CLIENTE_PCM")
        carreg = Carregamento.objects.create(cliente=self.a, tecnologia=self.tec, analista=self.tecnico,
                                             tipo_corretiva="BALANCEAMENTO")
        for url in ("/api/servicos/", "/api/atividades-corretivas/", "/api/balanceamento-planos/",
                    "/api/balanceamento-pontos/", "/api/economias/"):
            r = self.api(orfao).get(url)
            self.assertEqual(r.status_code, 200, url)
            self.assertEqual(r.data["count"], 0, url)
        self.assertEqual(self.api(orfao).get(f"/api/atividades-corretivas/{carreg.pk}/").status_code, 404)


class VinculoCruzadoTests(TestCase):
    """Folha de campo e OSP do cliente A não aceitam equipamento/inspeção/análise do cliente B (nem do interno)."""

    @classmethod
    def setUpTestData(cls):
        from apps.coletas.models import Inspecao

        cls.a = Cliente.objects.create(nome="Cliente A", cnpj="11.111.111/0001-11")
        cls.b = Cliente.objects.create(nome="Cliente B", cnpj="22.222.222/0001-22")
        setor = lambda c, cod: Setor.objects.create(  # noqa: E731
            area=Area.objects.create(cliente=c, codigo=cod, nome=f"Area {cod}"), codigo=cod, nome=f"Setor {cod}")
        cls.eq_a = Equipamento.objects.create(setor=setor(cls.a, "A"), tag="A-001", nome="Motor A")
        cls.eq_b = Equipamento.objects.create(setor=setor(cls.b, "B"), tag="B-001", nome="Motor B")
        cls.tec = TecnologiaAnalise.objects.create(nome="Vibração", sigla="VIB")
        cls.tecnico = User.objects.create_user(email="t@x.test", password="x", nome="T", perfil="TECNICO")
        cls.carreg = Carregamento.objects.create(cliente=cls.a, tecnologia=cls.tec, analista=cls.tecnico)
        cls.insp_a = Inspecao.objects.create(cliente=cls.a, tecnico=cls.tecnico, data="2026-10-01",
                                             tipo_analise="VIBRACAO")
        cls.insp_b = Inspecao.objects.create(cliente=cls.b, tecnico=cls.tecnico, data="2026-10-01",
                                             tipo_analise="VIBRACAO")
        cls.api = APIClient()
        cls.api.force_authenticate(cls.tecnico)

    def test_item_da_folha_recusa_equipamento_de_outro_cliente(self):
        r = self.api.post("/api/itens-inspecao/", {
            "carregamento": self.carreg.pk, "equipamento": self.eq_b.pk, "ordem": 1}, format="json")
        self.assertEqual(r.status_code, 400, r.data)
        ok = self.api.post("/api/itens-inspecao/", {
            "carregamento": self.carreg.pk, "equipamento": self.eq_a.pk, "ordem": 1}, format="json")
        self.assertEqual(ok.status_code, 201, ok.data)
        trocar = self.api.patch(f"/api/itens-inspecao/{ok.data['id']}/", {"equipamento": self.eq_b.pk}, format="json")
        self.assertEqual(trocar.status_code, 400)

    def test_osp_recusa_equipamento_ou_inspecao_de_outro_cliente(self):
        base = {"cliente": self.a.pk, "titulo": "OSP", "inspecao": self.insp_a.pk}
        self.assertEqual(self.api.post("/api/osps/", {**base, "equipamento": self.eq_b.pk}, format="json")
                         .status_code, 400)
        self.assertEqual(self.api.post("/api/osps/", {**base, "equipamento": self.eq_a.pk, "inspecao": self.insp_b.pk},
                                       format="json").status_code, 400)
        ok = self.api.post("/api/osps/", {**base, "equipamento": self.eq_a.pk}, format="json")
        self.assertEqual(ok.status_code, 201, ok.data)
        mover = self.api.patch(f"/api/osps/{ok.data['id']}/", {"equipamento": self.eq_b.pk}, format="json")
        self.assertEqual(mover.status_code, 400)
