"""
Item 3.1.22 — trilha de auditoria: criar/alterar/excluir, sem segredos, append-only,
consulta só para Master interno e retenção configurável.
"""
from datetime import timedelta
from io import StringIO

from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Nivel, Perfil, User
from apps.cadastros.models import Cliente, Empresa
from apps.core.models import MODO_SANEAMENTO, RegistroAuditoria, modo_manutencao


def _usuario(email, perfil, nivel, **vinculo):
    return User.objects.create_user(email=email, password="uma frase senha longa 2026", nome=email,
                                    perfil=perfil, nivel=nivel, **vinculo)


class TrilhaAuditoriaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.empresa = Empresa.objects.create(nome="Prestadora", cnpj="11.222.333/0001-81")
        cls.master = _usuario("master@t.test", Perfil.GESTOR, Nivel.MASTER, empresa=cls.empresa)
        cls.tecnico = _usuario("tec@t.test", Perfil.TECNICO, Nivel.PLENO, empresa=cls.empresa)
        cls.cliente = Cliente.objects.create(nome="Cliente A", cnpj="45.723.174/0001-10")
        cls.cli = _usuario("cli@a.test", Perfil.CLIENTE_PCM, Nivel.PLENO, cliente=cls.cliente)

    def setUp(self):
        cache.clear()

    # --- captura -----------------------------------------------------------
    def test_criar_gera_registro_com_os_campos(self):
        registro = RegistroAuditoria.objects.filter(modelo="cadastros.Cliente", objeto_id=str(self.cliente.pk),
                                                    acao="CRIAR").first()
        self.assertIsNotNone(registro)
        self.assertEqual(registro.alteracoes["nome"], [None, "Cliente A"])

    def test_alterar_registra_antes_e_depois_so_do_que_mudou(self):
        self.cliente.nome = "Cliente A2"
        self.cliente.save()
        registro = RegistroAuditoria.objects.filter(modelo="cadastros.Cliente", acao="ALTERAR",
                                                    objeto_id=str(self.cliente.pk)).latest("id")
        self.assertEqual(registro.alteracoes["nome"], ["Cliente A", "Cliente A2"])
        self.assertEqual(set(registro.alteracoes), {"nome"})

    def test_salvar_sem_mudanca_nao_gera_registro(self):
        antes = RegistroAuditoria.objects.count()
        self.cliente.save()
        self.assertEqual(RegistroAuditoria.objects.count(), antes)

    def test_excluir_gera_registro(self):
        cliente_temp = Cliente.objects.create(nome="Temp", cnpj="33.333.333/0001-33")
        pk = str(cliente_temp.pk)
        cliente_temp.delete()
        self.assertTrue(RegistroAuditoria.objects.filter(modelo="cadastros.Cliente", acao="EXCLUIR",
                                                         objeto_id=pk).exists())

    def test_senha_nunca_e_gravada(self):
        self.master.set_password("OUTRA frase senha nova 2026")
        self.master.save()
        registro = RegistroAuditoria.objects.filter(modelo="accounts.User", objeto_id=str(self.master.pk),
                                                    acao="ALTERAR").latest("id")
        self.assertIn("password", registro.alteracoes)
        self.assertEqual(registro.alteracoes["password"], ["***", "***"])
        self.assertNotIn("pbkdf2", str(registro.alteracoes))

    def test_modelos_de_seguranca_ficam_fora_da_trilha(self):
        from apps.accounts.models import EventoSeguranca
        antes = RegistroAuditoria.objects.filter(modelo="accounts.EventoSeguranca").count()
        EventoSeguranca.objects.create(evento="TESTE", sucesso=True)
        self.assertEqual(RegistroAuditoria.objects.filter(modelo="accounts.EventoSeguranca").count(), antes)

    def test_requisicao_registra_quem_ip_e_rota(self):
        c = APIClient()
        c.force_authenticate(self.master)
        r = c.patch(f"/api/usuarios/{self.tecnico.pk}/", {"cargo": "Técnico Pleno"}, format="json")
        self.assertEqual(r.status_code, 200)
        registro = RegistroAuditoria.objects.filter(modelo="accounts.User", objeto_id=str(self.tecnico.pk),
                                                    acao="ALTERAR").latest("id")
        self.assertEqual(registro.usuario_id, self.master.pk)
        # V-03: o e-mail do ator sai mascarado; quem agiu continua identificado pelo id.
        from apps.core.auditoria import mascarar_email
        self.assertEqual(registro.usuario_email, mascarar_email(self.master.email))
        self.assertNotEqual(registro.usuario_email, self.master.email)
        self.assertEqual(registro.metodo, "PATCH")
        self.assertIn("/api/usuarios/", registro.caminho)
        self.assertIn("cargo", registro.alteracoes)

    # --- append-only -------------------------------------------------------
    def test_registro_nao_pode_ser_alterado_nem_apagado(self):
        registro = RegistroAuditoria.objects.first()
        registro.ip = "1.2.3.4"
        with self.assertRaises(PermissionError):
            registro.save()
        with self.assertRaises(PermissionError):
            RegistroAuditoria.objects.filter(pk=registro.pk).delete()
        with self.assertRaises(PermissionError):
            registro.delete()

    # --- consulta ----------------------------------------------------------
    def test_consulta_so_para_master_interno(self):
        self.assertEqual(APIClient().get("/api/auditoria/").status_code, 401)
        for usuario in (self.tecnico, self.cli):
            c = APIClient()
            c.force_authenticate(usuario)
            self.assertEqual(c.get("/api/auditoria/").status_code, 403, usuario.email)
        c = APIClient()
        c.force_authenticate(self.master)
        r = c.get("/api/auditoria/", {"modelo": "cadastros.Cliente"})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(all(i["modelo"] == "cadastros.Cliente" for i in r.data["results"]))

    # --- retenção ----------------------------------------------------------
    def test_retencao_apaga_so_o_que_passou_do_prazo(self):
        antigo = RegistroAuditoria.objects.first()
        # Retroagir a data é manutenção (modo explícito); o ORM comum não atualiza a trilha (V-05).
        with modo_manutencao(MODO_SANEAMENTO):
            RegistroAuditoria.objects.filter(pk=antigo.pk).sanear_campos(
                criado_em=timezone.now() - timedelta(days=400))
        saida = StringIO()
        call_command("purgar_auditoria", "--dias", "365", stdout=saida)
        self.assertFalse(RegistroAuditoria.objects.filter(pk=antigo.pk).exists())
        self.assertIn("1 registro", saida.getvalue())
        self.assertTrue(RegistroAuditoria.objects.exists())


class AppendOnlyNoBancoTests(TestCase):
    """V-05: a trilha não muda por queryset nem por SQL direto; só nos modos de manutenção."""

    def setUp(self):
        self.reg = RegistroAuditoria.objects.create(modelo="cadastros.Cliente", objeto_id="9", acao="CRIAR",
                                                    alteracoes={"nome": [None, "Original"]})

    def _conteudo(self):
        return RegistroAuditoria.objects.values_list("alteracoes", flat=True).get(pk=self.reg.pk)

    def test_update_por_queryset_e_bloqueado(self):
        with self.assertRaises(PermissionError):
            RegistroAuditoria.objects.filter(pk=self.reg.pk).update(alteracoes={"nome": [None, "Adulterado"]})
        self.assertEqual(self._conteudo()["nome"][1], "Original")

    def test_sql_direto_nao_altera_a_trilha(self):
        from django.db import DatabaseError, connection, transaction
        # SQLite (RAISE) -> IntegrityError; PostgreSQL (plpgsql RAISE) -> InternalError.
        with self.assertRaises(DatabaseError), transaction.atomic(), connection.cursor() as c:
            c.execute("UPDATE core_registroauditoria SET alteracoes = %s WHERE id = %s",
                      ['{"nome": [null, "Adulterado"]}', self.reg.pk])
        self.assertEqual(self._conteudo()["nome"][1], "Original")

    def test_sql_direto_nao_apaga_da_trilha(self):
        from django.db import DatabaseError, connection, transaction
        # SQLite (RAISE) -> IntegrityError; PostgreSQL (plpgsql RAISE) -> InternalError.
        with self.assertRaises(DatabaseError), transaction.atomic(), connection.cursor() as c:
            c.execute("DELETE FROM core_registroauditoria WHERE id = %s", [self.reg.pk])
        self.assertTrue(RegistroAuditoria.objects.filter(pk=self.reg.pk).exists())

    def test_apagar_usuario_nao_altera_a_trilha(self):
        from apps.accounts.models import Nivel, Perfil, User
        from apps.cadastros.models import Empresa
        empresa = Empresa.objects.create(nome="E", cnpj="11.222.333/0001-81")
        u = User.objects.create_user(email="fim@t.test", password="uma frase senha longa 2026", nome="F",
                                     perfil=Perfil.TECNICO, nivel=Nivel.PLENO, empresa=empresa)
        RegistroAuditoria.objects.filter(pk=self.reg.pk).count()  # garante a tabela
        registro_do_usuario = RegistroAuditoria.objects.create(modelo="cadastros.Cliente", objeto_id="8",
                                                               acao="CRIAR", usuario=u, alteracoes={})
        u.delete()  # não pode dar erro nem mexer na trilha (DO_NOTHING, sem UPDATE)
        self.assertTrue(RegistroAuditoria.objects.filter(pk=registro_do_usuario.pk).exists())


class SaneamentoDaTrilhaTests(TestCase):
    """V-03: registros antigos com dado sensível são saneados; o comando é idempotente."""

    def test_saneia_arquivo_cifrado_titular_e_email(self):
        from io import StringIO
        from django.core.management import call_command
        sujo = RegistroAuditoria.objects.create(
            modelo="accounts.CertificadoA1", objeto_id="1", acao="CRIAR", usuario_email="pessoa.real@x.test",
            alteracoes={"arquivo_cifrado": [None, "gAAAA-PFX"], "titular": [None, "Fulano"],
                        "email": [None, "pessoa.real@x.test"], "nome": [None, "Ciclano"]},
        )
        saida = StringIO()
        call_command("sanear_auditoria", stdout=saida)
        self.assertIn("1 registro", saida.getvalue())
        sujo.refresh_from_db()
        self.assertNotIn("arquivo_cifrado", sujo.alteracoes)
        self.assertNotIn("titular", sujo.alteracoes)
        self.assertNotIn("gAAAA-PFX", str(sujo.alteracoes))
        self.assertEqual(sujo.alteracoes["email"][1], "p***@x***.test")
        self.assertEqual(sujo.usuario_email, "p***@x***.test")
        call_command("sanear_auditoria", stdout=StringIO())  # segunda vez não muda nada
        self.assertEqual(RegistroAuditoria.objects.get(pk=sujo.pk).alteracoes["email"][1], "p***@x***.test")
