"""
Item 3.1.2 — dados pessoais da equipe técnica (LGPD, Cl. 13).

Visíveis/editáveis só pelo próprio usuário e pelo Master interno. Fora de listas, de
respostas de outros usuários e de logs (valores).
"""
from datetime import date

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import DadosPessoaisUsuario, EventoSeguranca, Nivel, Perfil, User
from apps.cadastros.models import Cliente, Empresa

SEGREDO_RG = "MG-12.345.678"


def _usuario(email, perfil, nivel, **vinculo):
    return User.objects.create_user(email=email, password="uma frase senha longa 2026", nome=email,
                                    perfil=perfil, nivel=nivel, **vinculo)


class DadosPessoaisTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.empresa = Empresa.objects.create(nome="Prestadora", cnpj="11.222.333/0001-81")
        cls.cliente = Cliente.objects.create(nome="A", cnpj="11.111.111/0001-11")
        cls.master = _usuario("master@t.test", Perfil.GESTOR, Nivel.MASTER, empresa=cls.empresa)
        cls.tecnico = _usuario("tec@t.test", Perfil.TECNICO, Nivel.PLENO, empresa=cls.empresa)
        cls.eu = _usuario("eu@t.test", Perfil.TECNICO, Nivel.PLENO, empresa=cls.empresa)
        cls.cli = _usuario("cli@a.test", Perfil.CLIENTE_PCM, Nivel.PLENO, cliente=cls.cliente)
        cls.cli_master = _usuario("cm@a.test", Perfil.CLIENTE_CORP, Nivel.MASTER, cliente=cls.cliente)

    def setUp(self):
        cache.clear()

    def api(self, usuario):
        c = APIClient()
        c.force_authenticate(usuario)
        return c

    def test_proprio_usuario_le_e_edita_os_proprios_dados(self):
        r = self.api(self.eu).put("/api/auth/dados-pessoais/", {
            "data_nascimento": "1990-05-10", "rg": SEGREDO_RG, "estado_civil": "CASADO",
            "quantidade_filhos": 2, "cidade": "Belo Horizonte", "uf": "MG", "cep": "30000-000",
        }, format="json")
        self.assertEqual(r.status_code, 200)
        leitura = self.api(self.eu).get("/api/auth/dados-pessoais/").data
        self.assertEqual(leitura["rg"], SEGREDO_RG)
        self.assertEqual(leitura["data_nascimento"], "1990-05-10")
        self.assertEqual(DadosPessoaisUsuario.objects.get(usuario=self.eu).quantidade_filhos, 2)

    def test_cliente_tambem_so_le_os_proprios(self):
        self.assertEqual(self.api(self.cli).get("/api/auth/dados-pessoais/").status_code, 200)

    def test_master_interno_le_e_edita_de_outro_usuario(self):
        self.api(self.tecnico).put("/api/auth/dados-pessoais/", {"rg": "TEC-1"}, format="json")
        r = self.api(self.master).get(f"/api/usuarios/{self.tecnico.pk}/dados-pessoais/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["rg"], "TEC-1")
        self.assertEqual(self.api(self.master).put(f"/api/usuarios/{self.tecnico.pk}/dados-pessoais/",
                                                   {"ctps": "123"}, format="json").status_code, 200)

    def test_interno_comum_e_cliente_nao_leem_dados_de_outro(self):
        self.api(self.tecnico).put("/api/auth/dados-pessoais/", {"rg": "SEGREDO"}, format="json")
        self.assertEqual(self.api(self.eu).get(f"/api/usuarios/{self.tecnico.pk}/dados-pessoais/").status_code, 403)
        self.assertEqual(self.api(self.cli_master).get(f"/api/usuarios/{self.tecnico.pk}/dados-pessoais/").status_code,
                         403)

    def test_dados_nao_aparecem_em_listas_nem_em_respostas_de_perfil(self):
        self.api(self.eu).put("/api/auth/dados-pessoais/", {"rg": SEGREDO_RG, "cidade": "X"}, format="json")
        for cliente, url in (
            (self.master, f"/api/usuarios/{self.eu.pk}/"),
            (self.master, "/api/usuarios/"),
            (self.cli_master, "/api/minha-equipe/"),
            (self.cli, "/api/auth/me/"),
        ):
            corpo = self.api(cliente).get(url).content.decode()
            self.assertNotIn(SEGREDO_RG, corpo, url)
            self.assertNotIn('"rg"', corpo, url)

    def test_valores_nao_vao_para_o_log_de_seguranca(self):
        self.api(self.eu).put("/api/auth/dados-pessoais/", {"rg": SEGREDO_RG}, format="json")
        registros = EventoSeguranca.objects.filter(evento="DADOS_PESSOAIS_ALTERADOS")
        self.assertTrue(registros.exists())
        self.assertNotIn(SEGREDO_RG, str([r.detalhes for r in registros]))
        self.assertEqual(registros.first().detalhes["campos"], ["rg"])

    def test_data_invalida_e_recusada(self):
        r = self.api(self.eu).put("/api/auth/dados-pessoais/", {"data_nascimento": "nao-e-data"}, format="json")
        self.assertEqual(r.status_code, 400)
