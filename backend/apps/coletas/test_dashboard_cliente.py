"""
Painel recortado pelo cliente ativo.

Com um cliente ativado na barra lateral o painel fala só dele; sem nenhum
ativado, fala da operação inteira. O recorte é UX — quem garante o isolamento
continua sendo `escopo_cliente`, e o teste do Portal abaixo prova que o
parâmetro não serve de atalho para ampliar o que o usuário pode ver.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.cadastros.models import Area, Cliente, Equipamento, Setor
from apps.coletas.models import Inspecao
from apps.osp.models import OrdemServico

User = get_user_model()
SENHA = "SenhaSuperForte#2026!!"


class RecorteDoPainel(TestCase):
    def setUp(self):
        self.a = Cliente.objects.create(nome="Indústria A", cnpj="11.111.111/0001-11")
        self.b = Cliente.objects.create(nome="Indústria B", cnpj="22.222.222/0001-22")
        self.tecnico = User.objects.create_user(
            email="tecnico@thermo.com", password=SENHA, nome="Técnico",
            perfil="TECNICO", nivel="PLENO",
        )
        for cliente, quantas in ((self.a, 3), (self.b, 2)):
            area = Area.objects.create(cliente=cliente, nome=f"Área {cliente.nome}")
            setor = Setor.objects.create(area=area, nome=f"Setor {cliente.nome}")
            equip = Equipamento.objects.create(
                setor=setor, tag=f"TAG-{cliente.pk}", nome=f"Equip {cliente.nome}"
            )
            for i in range(quantas):
                Inspecao.objects.create(
                    cliente=cliente, data="2026-09-01", tipo_analise="VIBRACAO",
                    tecnico=self.tecnico,
                )
                OrdemServico.objects.create(
                    numero=OrdemServico.proximo_numero(),
                    cliente=cliente, equipamento=equip, titulo=f"OSP {cliente.nome} {i}",
                )
        self.api = APIClient()
        self.api.force_authenticate(self.tecnico)

    def test_sem_cliente_ativo_mostra_o_todo(self):
        r = self.api.get("/api/dashboard/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["total_inspecoes"], 5)
        self.assertEqual(r.data["osps_total"], 5)

    def test_com_cliente_ativo_mostra_so_ele(self):
        r = self.api.get(f"/api/dashboard/?cliente={self.a.pk}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["total_inspecoes"], 3)
        self.assertEqual(r.data["osps_total"], 3)

        r = self.api.get(f"/api/dashboard/?cliente={self.b.pk}")
        self.assertEqual(r.data["total_inspecoes"], 2)
        self.assertEqual(r.data["osps_total"], 2)

    def test_painel_executivo_recorta_a_performance_por_unidade(self):
        r = self.api.get("/api/dashboard/executivo/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual({p["cliente"] for p in r.data["performance"]},
                         {"Indústria A", "Indústria B"})

        r = self.api.get(f"/api/dashboard/executivo/?cliente={self.a.pk}")
        self.assertEqual([p["cliente"] for p in r.data["performance"]], ["Indústria A"])
        self.assertEqual(r.data["kpis"]["osps_total"], 3)

    def test_parametro_invalido_nao_derruba_o_painel(self):
        for valor in ("", "abc", "-1", "99999"):
            with self.subTest(cliente=valor):
                self.assertEqual(self.api.get(f"/api/dashboard/?cliente={valor}").status_code, 200)


class PortalNaoAmpliaComOParametro(TestCase):
    def setUp(self):
        self.a = Cliente.objects.create(nome="Indústria A", cnpj="11.111.111/0001-11")
        self.b = Cliente.objects.create(nome="Indústria B (vítima)", cnpj="22.222.222/0001-22")
        tecnico = User.objects.create_user(
            email="tecnico@thermo.com", password=SENHA, nome="Técnico",
            perfil="TECNICO", nivel="PLENO",
        )
        for cliente in (self.a, self.b):
            Inspecao.objects.create(
                cliente=cliente, data="2026-09-01", tipo_analise="VIBRACAO", tecnico=tecnico
            )
        self.do_portal = User.objects.create_user(
            email="pcm@a.com", password=SENHA, nome="PCM",
            perfil="CLIENTE_PCM", nivel="PLENO", cliente=self.a,
        )
        self.api = APIClient()
        self.api.force_authenticate(self.do_portal)

    def test_ve_apenas_a_propria_empresa(self):
        r = self.api.get("/api/dashboard/")
        self.assertEqual(r.data["total_inspecoes"], 1)

    def test_apontar_para_outro_cliente_nao_traz_nada(self):
        r = self.api.get(f"/api/dashboard/?cliente={self.b.pk}")
        self.assertEqual(r.status_code, 200)
        # O recorte só estreita o que o escopo já permitiu: nunca amplia.
        self.assertEqual(r.data["total_inspecoes"], 0)
