"""
Escopo multi-tenant dos cadastros.

Regressão de uma falha real: `InternoEditaClienteVisualiza` libera leitura a
qualquer usuário autenticado (correto para tabelas de referência), mas os
ViewSets de dados de cliente não filtravam por empresa. Resultado: um usuário do
Portal do Cliente listava `/api/equipamentos/` e `/api/clientes/` e recebia o
parque, os contatos e o CNPJ de TODOS os clientes da base.

Estes testes fixam o contrato: perfil cliente só enxerga o próprio cliente;
perfil interno continua enxergando tudo; catálogos globais seguem visíveis a
todos.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.cadastros.models import (
    Area,
    Cliente,
    Componente,
    Equipamento,
    Norma,
    Rota,
    Setor,
)

User = get_user_model()


class EscopoClienteCadastrosTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Dois clientes concorrentes na mesma base.
        cls.cliente_a = Cliente.objects.create(nome="Indústria A", cnpj="11.111.111/0001-11")
        cls.cliente_b = Cliente.objects.create(nome="Indústria B", cnpj="22.222.222/0001-22")

        cls.area_a = Area.objects.create(cliente=cls.cliente_a, codigo="A1", nome="Fiação")
        cls.area_b = Area.objects.create(cliente=cls.cliente_b, codigo="B1", nome="Extrusão")
        cls.setor_a = Setor.objects.create(area=cls.area_a, codigo="S1", nome="Cardas")
        cls.setor_b = Setor.objects.create(area=cls.area_b, codigo="S1", nome="Prensas")

        cls.equip_a = Equipamento.objects.create(setor=cls.setor_a, tag="MOT-A-001", nome="Motor A")
        cls.equip_b = Equipamento.objects.create(setor=cls.setor_b, tag="MOT-B-001", nome="Motor B")

        Componente.objects.create(equipamento=cls.equip_a, nome="Rolamento LOA")
        Componente.objects.create(equipamento=cls.equip_b, nome="Rolamento LOA")

        Rota.objects.create(cliente=cls.cliente_a, nome="Rota mensal A")
        Rota.objects.create(cliente=cls.cliente_b, nome="Rota mensal B")

        # Tabela de referência global: ninguém deve perdê-la de vista.
        Norma.objects.create(nome="ISO 10816-3", codigo="ISO 10816-3", orgao="ISO")

        cls.usuario_cliente_a = User.objects.create_user(
            email="pcm@a.com", password="x", nome="PCM da A",
            perfil="CLIENTE_PCM", cliente=cls.cliente_a,
        )
        cls.usuario_interno = User.objects.create_user(
            email="tecnico@thermo.com", password="x", nome="Técnico",
            perfil="TECNICO",
        )
        cls.cliente_sem_vinculo = User.objects.create_user(
            email="orfao@x.com", password="x", nome="Sem vínculo", perfil="CLIENTE_PCM",
        )

    def listar(self, usuario, rota):
        api = APIClient()
        api.force_authenticate(usuario)
        resposta = api.get(rota)
        self.assertEqual(resposta.status_code, 200, resposta.data)
        dados = resposta.data
        return dados["results"] if isinstance(dados, dict) and "results" in dados else dados

    # --- Perfil cliente: só o próprio parque ------------------------------

    def test_cliente_ve_somente_a_propria_empresa(self):
        nomes = [c["nome"] for c in self.listar(self.usuario_cliente_a, "/api/clientes/")]
        self.assertEqual(nomes, ["Indústria A"])

    def test_cliente_ve_somente_os_proprios_equipamentos(self):
        tags = [e["tag"] for e in self.listar(self.usuario_cliente_a, "/api/equipamentos/")]
        self.assertEqual(tags, ["MOT-A-001"])

    def test_cliente_ve_somente_as_proprias_areas_e_setores(self):
        areas = self.listar(self.usuario_cliente_a, "/api/areas/")
        setores = self.listar(self.usuario_cliente_a, "/api/setores/")
        self.assertEqual([a["nome"] for a in areas], ["Fiação"])
        self.assertEqual([s["nome"] for s in setores], ["Cardas"])

    def test_cliente_ve_somente_os_proprios_componentes_e_rotas(self):
        componentes = self.listar(self.usuario_cliente_a, "/api/componentes/")
        rotas = self.listar(self.usuario_cliente_a, "/api/rotas/")
        self.assertEqual([c["equipamento"] for c in componentes], [self.equip_a.id])
        self.assertEqual([r["nome"] for r in rotas], ["Rota mensal A"])

    def test_cliente_nao_acessa_equipamento_de_outro_por_id(self):
        api = APIClient()
        api.force_authenticate(self.usuario_cliente_a)
        self.assertEqual(api.get(f"/api/equipamentos/{self.equip_b.id}/").status_code, 404)

    def test_cliente_sem_vinculo_nao_ve_nada(self):
        # Falha fechada: usuário cliente sem `cliente` preenchido não vaza base.
        self.assertEqual(self.listar(self.cliente_sem_vinculo, "/api/equipamentos/"), [])
        self.assertEqual(self.listar(self.cliente_sem_vinculo, "/api/clientes/"), [])

    def test_cliente_nao_escreve(self):
        api = APIClient()
        api.force_authenticate(self.usuario_cliente_a)
        resposta = api.post(
            "/api/equipamentos/", {"setor": self.setor_a.id, "tag": "X", "nome": "X"}, format="json"
        )
        self.assertEqual(resposta.status_code, 403)

    # --- Perfil interno e catálogos ---------------------------------------

    def test_interno_continua_vendo_todos_os_clientes(self):
        tags = [e["tag"] for e in self.listar(self.usuario_interno, "/api/equipamentos/")]
        self.assertCountEqual(tags, ["MOT-A-001", "MOT-B-001"])

    def test_catalogo_global_permanece_visivel_ao_cliente(self):
        normas = self.listar(self.usuario_cliente_a, "/api/normas/")
        self.assertEqual([n["codigo"] for n in normas], ["ISO 10816-3"])
