"""
Drill-down do painel → lista de OSPs: `?criticidade_origem=CRITICO|ALERTA|NORMAL`.

Cobre: o filtro restringe ao valor pedido, valor fora da lista é 400 (não lista vazia),
sem o parâmetro nada muda, e o escopo do cliente continua valendo com o filtro.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.cadastros.models import Area, Cliente, Equipamento, Setor, TipoEquipamento
from apps.osp.models import OrdemServico

User = get_user_model()


class FiltroCriticidadeOrigemTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a = Cliente.objects.create(nome="Cliente A", cnpj="11.111.111/0001-11")
        cls.b = Cliente.objects.create(nome="Cliente B", cnpj="22.222.222/0001-22")
        tipo = TipoEquipamento.objects.create(nome="Motor")
        cls.eq_a = Equipamento.objects.create(
            setor=Setor.objects.create(area=Area.objects.create(cliente=cls.a, nome="A"), nome="S"),
            tag="A-1", nome="Motor A", tipo_equipamento=tipo)
        cls.eq_b = Equipamento.objects.create(
            setor=Setor.objects.create(area=Area.objects.create(cliente=cls.b, nome="B"), nome="S"),
            tag="B-1", nome="Motor B", tipo_equipamento=tipo)
        cls.tecnico = User.objects.create_user(email="t@thermo.test", password="x", nome="t", perfil="TECNICO")
        cls.pcm_a = User.objects.create_user(email="pa@a.test", password="x", nome="pa",
                                             perfil="CLIENTE_PCM", cliente=cls.a)
        cls.critica_a = cls.osp(cls.a, cls.eq_a, "CRITICO")
        cls.alerta_a = cls.osp(cls.a, cls.eq_a, "ALERTA")
        cls.manual_a = cls.osp(cls.a, cls.eq_a, "")
        cls.critica_b = cls.osp(cls.b, cls.eq_b, "CRITICO")

    @staticmethod
    def osp(cliente, equipamento, criticidade):
        return OrdemServico.objects.create(
            cliente=cliente, equipamento=equipamento, titulo=f"OSP {criticidade or 'manual'}",
            grau_risco="GR2", criticidade_origem=criticidade,
        )

    def ids(self, usuario, query=""):
        api = APIClient()
        api.force_authenticate(usuario)
        r = api.get(f"/api/osps/{query}")
        return r, ([o["id"] for o in r.json()["results"]] if r.status_code == 200 else None)

    def test_interno_filtra_pela_criticidade_de_origem(self):
        r, ids = self.ids(self.tecnico, "?criticidade_origem=CRITICO")
        self.assertEqual(r.status_code, 200)
        self.assertCountEqual(ids, [self.critica_a.pk, self.critica_b.pk])

    def test_alerta_e_restrito_so_a_alerta(self):
        _, ids = self.ids(self.tecnico, "?criticidade_origem=ALERTA")
        self.assertEqual(ids, [self.alerta_a.pk])

    def test_sem_parametro_lista_tudo(self):
        _, ids = self.ids(self.tecnico)
        self.assertCountEqual(ids, [self.critica_a.pk, self.alerta_a.pk, self.manual_a.pk, self.critica_b.pk])

    def test_valor_invalido_e_400_e_nao_lista_vazia(self):
        r, _ = self.ids(self.tecnico, "?criticidade_origem=URGENTISSIMO")
        self.assertEqual(r.status_code, 400)
        self.assertIn("criticidade_origem", r.json())

    def test_cliente_continua_escopado_com_o_filtro(self):
        api = APIClient()
        api.force_authenticate(self.pcm_a)
        r = api.get("/api/osps/?criticidade_origem=CRITICO")
        self.assertEqual(r.status_code, 200)
        ids = [o["id"] for o in r.json()["results"]]
        self.assertEqual(ids, [self.critica_a.pk])  # a CRITICO do cliente B não aparece

    def test_sem_login_nao_lista(self):
        self.assertIn(APIClient().get("/api/osps/?criticidade_origem=CRITICO").status_code, (401, 403))
