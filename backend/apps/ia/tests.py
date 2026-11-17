"""
Área administrativa de IA: chaves de API dos provedores e ativação por recurso.

O que estes testes garantem: só o Master interno alcança a área; a chave é gravada cifrada
e não reaparece em resposta de API, na trilha de auditoria nem no `repr` da credencial; um
recurso só liga com uma chave legível; e remover a chave desliga quem a usava.
"""
import json

from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import Nivel, Perfil, User
from apps.cadastros.models import Cliente, Empresa
from apps.core.models import RegistroAuditoria

from .models import AtivacaoIA, ChaveApiIA, ProvedorIA, RecursoIA
from .servico import credencial_do_recurso, recurso_habilitado

SEGREDO = "sk-teste-0123456789-abcdefghij-WXYZ"


def _usuario(email, perfil, nivel, **vinculo):
    return User.objects.create_user(email=email, password="uma frase senha longa 2026", nome=email,
                                    perfil=perfil, nivel=nivel, **vinculo)


class AreaIaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.empresa = Empresa.objects.create(nome="Prestadora", cnpj="11.222.333/0001-81")
        cls.master = _usuario("master@ia.test", Perfil.GESTOR, Nivel.MASTER, empresa=cls.empresa)
        cls.senior = _usuario("senior@ia.test", Perfil.TECNICO, Nivel.SENIOR, empresa=cls.empresa)
        cls.cliente = Cliente.objects.create(nome="Cliente A", cnpj="45.723.174/0001-10")
        cls.master_cliente = _usuario("master@cliente.test", Perfil.CLIENTE_CORP, Nivel.MASTER, cliente=cls.cliente)

    def setUp(self):
        cache.clear()
        self.api = APIClient()
        self.api.force_authenticate(self.master)

    def _criar(self, **extra):
        dados = {"provedor": ProvedorIA.ANTHROPIC, "rotulo": "Conta principal", "chave": SEGREDO, **extra}
        return self.api.post("/api/ia/chaves/", dados, format="json")

    # --- acesso -------------------------------------------------------------
    def test_so_o_master_interno_alcanca_a_area(self):
        for usuario, esperado in ((None, 401), (self.senior, 403), (self.master_cliente, 403)):
            api = APIClient()
            if usuario:
                api.force_authenticate(usuario)
            for metodo, rota in (("get", "/api/ia/chaves/"), ("post", "/api/ia/chaves/"),
                                 ("get", "/api/ia/ativacoes/"),
                                 ("patch", f"/api/ia/ativacoes/{RecursoIA.LAUDO_VIBRACAO}/")):
                resposta = getattr(api, metodo)(rota, {}, format="json")
                self.assertEqual(resposta.status_code, esperado, (usuario, metodo, rota))
        self.assertEqual(ChaveApiIA.objects.count(), 0)

    # --- a chave nunca sai --------------------------------------------------
    def test_chave_e_gravada_cifrada_e_nao_volta_pela_api(self):
        resposta = self._criar()
        self.assertEqual(resposta.status_code, 201, resposta.content)
        self.assertNotIn(SEGREDO, resposta.content.decode())
        self.assertEqual(resposta.json()["chave_mascarada"], "••••WXYZ")
        self.assertNotIn("chave", resposta.json())

        gravada = ChaveApiIA.objects.get()
        self.assertNotIn(SEGREDO, gravada.chave_cifrada)
        self.assertEqual(gravada.revelar(), SEGREDO)
        self.assertEqual(gravada.criado_por, self.master)

        for rota in ("/api/ia/chaves/", f"/api/ia/chaves/{gravada.pk}/", "/api/ia/ativacoes/"):
            self.assertNotIn(SEGREDO, self.api.get(rota).content.decode(), rota)

    def test_trilha_de_auditoria_nao_guarda_a_chave(self):
        self._criar()
        gravada = ChaveApiIA.objects.get()
        self.api.patch(f"/api/ia/chaves/{gravada.pk}/", {"chave": SEGREDO + "-nova"}, format="json")
        registros = RegistroAuditoria.objects.filter(modelo="ia.ChaveApiIA")
        self.assertEqual({r.acao for r in registros}, {"CRIAR", "ALTERAR"})
        gravada.refresh_from_db()
        trilha = json.dumps([r.alteracoes for r in registros])
        for proibido in (SEGREDO, gravada.chave_cifrada, "WXYZ", "nova"):
            self.assertNotIn(proibido, trilha)

    def test_editar_sem_chave_mantem_a_gravada_e_com_chave_troca(self):
        self._criar()
        gravada = ChaveApiIA.objects.get()
        resposta = self.api.patch(f"/api/ia/chaves/{gravada.pk}/", {"rotulo": "Conta de testes"}, format="json")
        self.assertEqual(resposta.status_code, 200, resposta.content)
        gravada.refresh_from_db()
        self.assertEqual((gravada.rotulo, gravada.revelar()), ("Conta de testes", SEGREDO))

        self.api.patch(f"/api/ia/chaves/{gravada.pk}/", {"chave": "outra-chave-123456"}, format="json")
        gravada.refresh_from_db()
        self.assertEqual((gravada.revelar(), gravada.mascarada), ("outra-chave-123456", "••••3456"))

    def test_validacoes_do_cadastro_da_chave(self):
        self.assertEqual(self._criar(chave="").status_code, 400)
        self.assertEqual(self.api.post("/api/ia/chaves/", {"provedor": "ANTHROPIC", "rotulo": "x"},
                                       format="json").status_code, 400)
        self.assertEqual(self._criar(provedor="INEXISTENTE").status_code, 400)
        # Outro provedor precisa do endereço da API.
        self.assertEqual(self._criar(provedor=ProvedorIA.OUTRO).status_code, 400)
        self.assertEqual(self._criar(provedor=ProvedorIA.OUTRO, url_base="https://ia.interna.test/v1").status_code, 201)
        # Mesmo provedor + mesma identificação não se repete.
        self.assertEqual(self._criar().status_code, 201)
        self.assertEqual(self._criar().status_code, 400)

    # --- ativação -----------------------------------------------------------
    def test_recurso_nasce_desligado_e_so_liga_com_chave(self):
        lista = self.api.get("/api/ia/ativacoes/").json()
        self.assertEqual([i["recurso"] for i in lista], list(RecursoIA.values))
        self.assertTrue(all(not i["habilitado"] and not i["implementado"] for i in lista))
        self.assertEqual(AtivacaoIA.objects.count(), 0)  # listar não grava nada
        self.assertFalse(recurso_habilitado(RecursoIA.LAUDO_VIBRACAO))

        rota = f"/api/ia/ativacoes/{RecursoIA.LAUDO_VIBRACAO}/"
        self.assertEqual(self.api.patch(rota, {"habilitado": True}, format="json").status_code, 400)

        chave_id = self._criar(modelo_padrao="modelo-padrao").json()["id"]
        resposta = self.api.patch(rota, {"habilitado": True, "credencial": chave_id}, format="json")
        self.assertEqual(resposta.status_code, 200, resposta.content)
        self.assertEqual(resposta.json()["modelo_efetivo"], "modelo-padrao")

        credencial = credencial_do_recurso(RecursoIA.LAUDO_VIBRACAO)
        self.assertEqual((credencial.provedor, credencial.chave, credencial.modelo),
                         (ProvedorIA.ANTHROPIC, SEGREDO, "modelo-padrao"))
        self.assertNotIn(SEGREDO, repr(credencial))
        # O outro recurso continua desligado.
        self.assertIsNone(credencial_do_recurso(RecursoIA.LEITURA_LAUDO_FLUIDOS))

        # Modelo próprio do recurso e, depois, desligar.
        self.api.patch(rota, {"modelo": "modelo-do-recurso"}, format="json")
        self.assertEqual(credencial_do_recurso(RecursoIA.LAUDO_VIBRACAO).modelo, "modelo-do-recurso")
        self.api.patch(rota, {"habilitado": False}, format="json")
        self.assertIsNone(credencial_do_recurso(RecursoIA.LAUDO_VIBRACAO))

    def test_recurso_desconhecido_responde_404(self):
        self.assertEqual(self.api.patch("/api/ia/ativacoes/NAO_EXISTE/", {"habilitado": False},
                                        format="json").status_code, 404)

    def test_remover_a_chave_desliga_o_recurso_que_a_usava(self):
        chave_id = self._criar().json()["id"]
        rota = f"/api/ia/ativacoes/{RecursoIA.LEITURA_LAUDO_FLUIDOS}/"
        self.api.patch(rota, {"habilitado": True, "credencial": chave_id}, format="json")
        self.assertEqual(self.api.get(f"/api/ia/chaves/{chave_id}/").json()["em_uso"],
                         [RecursoIA.LEITURA_LAUDO_FLUIDOS.label])

        self.assertEqual(self.api.delete(f"/api/ia/chaves/{chave_id}/").status_code, 204)
        self.assertFalse(ChaveApiIA.objects.exists())  # exclusão de verdade: o segredo sai do banco
        ativacao = AtivacaoIA.objects.get(recurso=RecursoIA.LEITURA_LAUDO_FLUIDOS)
        self.assertEqual((ativacao.habilitado, ativacao.credencial), (False, None))
        self.assertIsNone(credencial_do_recurso(RecursoIA.LEITURA_LAUDO_FLUIDOS))

    # --- troca da chave de cifra do servidor ---------------------------------
    def test_chave_ilegivel_depois_de_trocar_a_cifra_nao_habilita_recurso(self):
        chave_id = self._criar().json()["id"]
        rota = f"/api/ia/ativacoes/{RecursoIA.LAUDO_VIBRACAO}/"
        self.api.patch(rota, {"habilitado": True, "credencial": chave_id}, format="json")
        with override_settings(IA_ENCRYPTION_KEY="outra-chave-de-cifra"):
            self.assertFalse(self.api.get(f"/api/ia/chaves/{chave_id}/").json()["legivel"])
            self.assertIsNone(credencial_do_recurso(RecursoIA.LAUDO_VIBRACAO))
            self.assertEqual(self.api.patch(rota, {"habilitado": True}, format="json").status_code, 400)
            # Cadastrar a chave de novo resolve.
            self.api.patch(f"/api/ia/chaves/{chave_id}/", {"chave": SEGREDO}, format="json")
            self.assertEqual(credencial_do_recurso(RecursoIA.LAUDO_VIBRACAO).chave, SEGREDO)
