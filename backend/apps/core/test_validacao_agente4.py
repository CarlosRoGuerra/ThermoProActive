"""
Validação independente (Agente 4) — provas de defeitos encontrados na revisão de 03/11/2026.

V-01, V-03 e V-05 foram CORRIGIDOS: cada teste afirma agora o comportamento seguro. V-02 e V-04 seguem
como provas do defeito ainda aberto. Ver docs/24-VALIDACAO-AGENTE4.md e docs/22-ACESSO-LAUDOS-PORTAL-BI.md.
"""
import io
import struct
import zipfile
import zlib
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import CertificadoA1, Nivel, Perfil, User
from apps.cadastros.models import Empresa
from apps.coletas.anexos import validar_upload
from apps.core.models import RegistroAuditoria
from apps.notificacoes.channels import enviar_push
from apps.notificacoes.models import AssinaturaPush, StatusEntrega

from apps.notificacoes.test_web_push import CHAVES, _Resposta


def _usuario(email, perfil, nivel, **vinculo):
    return User.objects.create_user(email=email, password="uma frase senha longa 2026", nome=email,
                                    perfil=perfil, nivel=nivel, **vinculo)


class V01SsrfEndpointPushTests(TestCase):
    """
    V-01 (ALTO) — SSRF no Web Push. CORRIGIDO.

    Antes, o endpoint de push aceitava qualquer https:// e o servidor fazia POST para ele.
    Agora: registro só aceita serviços de push conhecidos (allowlist), sem IP literal, sem
    credenciais e sem porta fora do padrão; o envio revalida o DNS (recusa IP não público) e
    não segue redirecionamento.
    """

    @classmethod
    def setUpTestData(cls):
        cls.empresa = Empresa.objects.create(nome="Prestadora", cnpj="11.222.333/0001-81")
        cls.tecnico = _usuario("tec@v01.test", Perfil.TECNICO, Nivel.PLENO, empresa=cls.empresa)

    def setUp(self):
        patcher = mock.patch("apps.notificacoes.seguranca_push._resolver",
                             return_value=[(None, None, None, None, ("142.250.0.1", 443))])
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_endpoint_interno_e_recusado_no_registro(self):
        cliente = APIClient()
        cliente.force_authenticate(self.tecnico)
        recusados = (
            "https://127.0.0.1:8443/interno",
            "https://169.254.169.254/latest/meta-data/",
            "https://10.0.0.5/x",
            "https://intranet.local/x",
            "http://fcm.googleapis.com/x",
            "https://fcm.googleapis.com:8443/x",
            "https://usuario:senha@fcm.googleapis.com/x",
        )
        for alvo in recusados:
            r = cliente.post("/api/notificacoes/push/assinatura/",
                             {"endpoint": alvo, "keys": {"p256dh": "p", "auth": "a"}}, format="json")
            self.assertEqual(r.status_code, 400, f"{alvo} deveria ser recusado")
        self.assertEqual(AssinaturaPush.objects.filter(usuario=self.tecnico).count(), 0)

    def test_envio_nao_chama_host_interno_mesmo_que_ja_gravado(self):
        assinatura = AssinaturaPush.objects.create(usuario=self.tecnico, endpoint="https://127.0.0.1:8443/interno",
                                                   p256dh="p", auth="a", ativa=True)
        with self.settings(**CHAVES), mock.patch("pywebpush.webpush", return_value=_Resposta(201)) as wp:
            resultado = enviar_push(self.tecnico, "t", "m")
        wp.assert_not_called()
        self.assertNotEqual(resultado.status, StatusEntrega.ENVIADO)
        assinatura.refresh_from_db()
        self.assertFalse(assinatura.ativa)

    def test_dns_que_resolve_para_rede_interna_e_recusado(self):
        AssinaturaPush.objects.create(usuario=self.tecnico, endpoint="https://fcm.googleapis.com/fcm/send/x",
                                      p256dh="p", auth="a", ativa=True)
        with mock.patch("apps.notificacoes.seguranca_push._resolver",
                        return_value=[(None, None, None, None, ("10.0.0.5", 443))]), \
                self.settings(**CHAVES), mock.patch("pywebpush.webpush", return_value=_Resposta(201)) as wp:
            resultado = enviar_push(self.tecnico, "t", "m")
        wp.assert_not_called()
        self.assertEqual(resultado.status, StatusEntrega.FALHOU)
        self.assertFalse(resultado.temporario)




class V02ZipBombDeclaradoTests(TestCase):
    """
    V-02 (MÉDIO) — validação de XLSX/DOCX confiava no tamanho DECLARADO no diretório ZIP.

    CORRIGIDO: `_ler_ooxml` (apps/coletas/anexos.py) mede o descompactado REAL em streaming,
    membro por membro, com teto de tamanho, de entradas e de razão de compressão. Um DOCX
    com ~101 MB descompactados e cabeçalho que declara 1000 bytes é recusado.
    """

    def _docx_bomba(self, tamanho_real=101 * 1024 * 1024):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("[Content_Types].xml", "<Types/>")
            z.writestr("word/document.xml", b"\x00" * tamanho_real)
        dados = bytearray(buf.getvalue())
        alvo = b"word/document.xml"
        # Cabeçalho local (assinatura PK\x03\x04): tamanho descompactado em +22.
        pos_local = dados.find(b"PK\x03\x04")
        while pos_local != -1:
            nome_len = struct.unpack_from("<H", dados, pos_local + 26)[0]
            if bytes(dados[pos_local + 30:pos_local + 30 + nome_len]) == alvo:
                struct.pack_into("<I", dados, pos_local + 22, 1000)
                break
            pos_local = dados.find(b"PK\x03\x04", pos_local + 4)
        # Diretório central (PK\x01\x02): tamanho descompactado em +24.
        pos_central = dados.find(b"PK\x01\x02")
        while pos_central != -1:
            nome_len = struct.unpack_from("<H", dados, pos_central + 28)[0]
            if bytes(dados[pos_central + 46:pos_central + 46 + nome_len]) == alvo:
                struct.pack_into("<I", dados, pos_central + 24, 1000)
                break
            pos_central = dados.find(b"PK\x01\x02", pos_central + 4)
        return bytes(dados)

    def test_bomba_com_tamanho_declarado_forjado_e_recusada(self):
        """CORRIGIDO (V-02): o tamanho declarado é falso; o descompactado real passa de 100 MB e é recusado."""
        conteudo = self._docx_bomba()
        with zipfile.ZipFile(io.BytesIO(conteudo)) as z:
            declarado = sum(i.file_size for i in z.infolist())
        self.assertLess(declarado, 100 * 1024 * 1024)  # o cabeçalho mente, como na prova
        # Prova do tamanho real: deflate do membro document.xml descompacta para > 100 MB.
        with zipfile.ZipFile(io.BytesIO(conteudo)) as z:
            info = z.getinfo("word/document.xml")
        base = info.header_offset
        nome_len, extra_len = struct.unpack_from("<HH", conteudo, base + 26)
        inicio = base + 30 + nome_len + extra_len
        real = len(zlib.decompressobj(-15).decompress(conteudo[inicio:inicio + info.compress_size]))
        self.assertGreater(real, 100 * 1024 * 1024)
        upload = SimpleUploadedFile("laudo.docx", conteudo, content_type="application/octet-stream")
        with self.assertRaises(ValueError):
            validar_upload(upload)


class V03AuditoriaGravaSegredoCifradoTests(TestCase):
    """
    V-03 (ALTO) — trilha de auditoria gravava dados sensíveis do certificado A1. CORRIGIDO.

    Agora o PKCS#12 cifrado, titular, emissor e série do certificado não entram na trilha, e o
    e-mail de usuário sai mascarado (também no campo do ator). Registros antigos são saneados
    por `sanear_auditoria` / migração core/0002.
    """

    def test_arquivo_cifrado_do_pfx_nao_vai_para_a_trilha(self):
        empresa = Empresa.objects.create(nome="Prestadora", cnpj="11.222.333/0001-81")
        tec = _usuario("cert@v03.test", Perfil.TECNICO, Nivel.PLENO, empresa=empresa)
        CertificadoA1.objects.create(usuario=tec, arquivo_cifrado="gAAAAAB-PFX-CIFRADO-TESTE",
                                     titular="Responsavel Teste", emissor="AC Teste",
                                     numero_serie="123", valido_ate=timezone.now(),
                                     sha256_certificado="a" * 64)
        reg = RegistroAuditoria.objects.filter(modelo="accounts.CertificadoA1").first()
        self.assertIsNotNone(reg, "trilha deveria registrar a ação (sem o conteúdo)")
        self.assertNotIn("arquivo_cifrado", reg.alteracoes)
        self.assertNotIn("titular", reg.alteracoes)
        self.assertNotIn("gAAAAAB-PFX-CIFRADO-TESTE", str(reg.alteracoes))

    def test_email_de_usuario_sai_mascarado(self):
        empresa = Empresa.objects.create(nome="Prestadora2", cnpj="45.723.174/0001-10")
        _usuario("pessoa.real@v03.test", Perfil.TECNICO, Nivel.PLENO, empresa=empresa)
        reg = RegistroAuditoria.objects.filter(modelo="accounts.User", acao="CRIAR",
                                               alteracoes__has_key="email").first()
        self.assertIsNotNone(reg, "trilha deveria registrar a criação do usuário")
        self.assertNotEqual(reg.alteracoes["email"][1], "pessoa.real@v03.test")
        self.assertEqual(reg.alteracoes["email"][1], "p***@v***.test")


class V04RestricaoSetorNaoAplicadaNaPreditivaTests(TestCase):
    """
    V-04 (ALTO) — restrição de setor (2.1.1.6) não aplicada nas rotas de preditiva.

    CORRIGIDO para `apps/preditiva` (testes de ranking e tendência invertidos para o
    comportamento correto): as views aplicam `restringe_setor` depois do escopo de
    cliente; fora do setor, o ranking omite o equipamento e o detalhe responde 404.
    Casos novos em `apps/preditiva/test_escopo_setor_preditiva.py`.

    PENDENTE (fora deste escopo): `/api/sensores/` continua sem restrição de setor,
    porque `SensorViewSet` herda `BaseCadastroViewSet`, que só aplica o escopo de cliente.
    O teste de sensor abaixo ainda confirma o defeito até essa correção.
    """

    @classmethod
    def setUpTestData(cls):
        from datetime import date
        from apps.accounts.models import RestricaoSetorUsuario
        from apps.cadastros.models import Area, Cliente, Equipamento, Setor, TipoEquipamento
        from apps.coletas.models import Inspecao
        cls.empresa = Empresa.objects.create(nome="Prestadora", cnpj="11.222.333/0001-81")
        cls.cliente = Cliente.objects.create(nome="A", cnpj="11.111.111/0001-11")
        tipo = TipoEquipamento.objects.create(nome="Motor")
        area = Area.objects.create(cliente=cls.cliente, codigo="A1", nome="Planta")
        cls.setor1 = Setor.objects.create(area=area, codigo="S1", nome="Setor 1")
        cls.setor2 = Setor.objects.create(area=area, codigo="S2", nome="Setor 2")
        cls.eq1 = Equipamento.objects.create(setor=cls.setor1, tag="E-SETOR1", nome="Motor 1", tipo_equipamento=tipo)
        cls.eq2 = Equipamento.objects.create(setor=cls.setor2, tag="E-SETOR2", nome="Motor 2", tipo_equipamento=tipo)
        cls.restrito = _usuario("restrito@v04.test", Perfil.CLIENTE_PCM, Nivel.PLENO, cliente=cls.cliente)
        RestricaoSetorUsuario.objects.create(usuario=cls.restrito, setor=cls.setor1)
        cls.insp = Inspecao.objects.create(cliente=cls.cliente, tecnico=cls.restrito, data=date(2026, 10, 1),
                                           tipo_analise="VIBRACAO")

    def api(self):
        c = APIClient()
        c.force_authenticate(self.restrito)
        return c

    def test_ranking_de_risco_vaza_equipamento_de_outro_setor(self):
        r = self.api().get("/api/preditiva/risco/ranking/")
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("E-SETOR2", str(r.data), "V-04 corrigido: ranking omite setor fora da restrição")
        self.assertIn("E-SETOR1", str(r.data))

    def test_sensor_de_outro_setor_aparece_na_lista(self):
        """CORRIGIDO (V-04, sensores): `SensorViewSet` aplica `restringe_setor` pelo setor do equipamento.
        Sensor do setor fora da restrição não aparece na lista, e o detalhe responde 404."""
        from apps.cadastros.models import Sensor
        fora = Sensor.objects.create(equipamento=self.eq2, ponto_instalacao="Mancal LA", tipo="ACELEROMETRO")
        dentro = Sensor.objects.create(equipamento=self.eq1, ponto_instalacao="Mancal LB", tipo="ACELEROMETRO")
        r = self.api().get("/api/sensores/", {"page_size": 100})
        self.assertEqual(r.status_code, 200)
        ids = {s["id"] for s in r.data["results"]}
        self.assertIn(dentro.pk, ids)
        self.assertNotIn(fora.pk, ids, "V-04: sensor do setor fora da restrição não pode aparecer")
        self.assertEqual(self.api().get(f"/api/sensores/{fora.pk}/").status_code, 404)

    def test_tendencia_de_medicao_de_outro_setor_responde_200(self):
        from apps.coletas.models import MedicaoVibracao
        m = MedicaoVibracao.objects.create(inspecao=self.insp, equipamento=self.eq2, ponto_medicao="P2",
                                           direcao="V", velocidade_rms="1.00", rotacao_rpm=1800)
        r = self.api().get(f"/api/preditiva/tendencias/vibracao/{m.pk}/")
        self.assertEqual(r.status_code, 404, "V-04 corrigido: tendência de medição fora do setor → 404")


class V05AuditoriaNaoEAppendOnlyNoBancoTests(TestCase):
    """
    V-05 (MÉDIO) — append-only só valia no ORM. CORRIGIDO: `QuerySet.update()` levanta erro e o
    trigger do banco (PostgreSQL e SQLite, migração core/0002) recusa UPDATE/DELETE fora dos modos
    de manutenção. Só o expurgo de retenção e o saneamento relaxam o bloqueio, por caminho explícito.
    """

    def test_update_por_queryset_e_bloqueado(self):
        reg = RegistroAuditoria.objects.create(modelo="cadastros.Cliente", objeto_id="1", acao="CRIAR",
                                               alteracoes={"nome": [None, "Original"]})
        with self.assertRaises(PermissionError):
            RegistroAuditoria.objects.filter(pk=reg.pk).update(alteracoes={"nome": [None, "Adulterado"]})
        reg.refresh_from_db()
        self.assertEqual(reg.alteracoes["nome"][1], "Original")

    def test_sql_direto_e_bloqueado_pelo_banco(self):
        from django.db import connection, transaction
        reg = RegistroAuditoria.objects.create(modelo="cadastros.Cliente", objeto_id="2", acao="CRIAR",
                                               alteracoes={"nome": [None, "Original"]})
        # Rodada 2: no PostgreSQL o RAISE do trigger chega como ProgrammingError; no SQLite, como
        # IntegrityError. Qualquer DatabaseError serve: o que importa é o banco recusar.
        from django.db import DatabaseError
        with self.assertRaises(DatabaseError), transaction.atomic(), connection.cursor() as c:
            c.execute("UPDATE core_registroauditoria SET alteracoes = %s WHERE id = %s",
                      ['{"nome": [null, "Adulterado"]}', reg.pk])
        reg.refresh_from_db()
        self.assertEqual(reg.alteracoes["nome"][1], "Original")


class V08LockForUpdateNoPostgresTests(TestCase):
    """
    V-08 (CRÍTICO para produção PostgreSQL) — código base (143042f), não introduzido pelos agentes.

    `OrdemServico.objects.select_for_update().select_related("cliente", "equipamento", "responsavel")`
    (apps/osp/services.py:224-226, transição de status) e o equivalente em
    `apps/laudos/services.py:141-142` (emissão de laudo) falham no PostgreSQL com
    NotSupportedError: "FOR UPDATE cannot be applied to the nullable side of an outer join".
    O SQLite ignora `select_for_update`, por isso a suíte local passa. Só roda no PostgreSQL.
    Prova: a consulta atual falha; com `select_for_update(of=("self",))` a consulta compila.
    """

    def setUp(self):
        from django.db import connection
        if connection.vendor != "postgresql":
            self.skipTest("prova exclusiva de PostgreSQL")

    def test_consulta_de_transicao_da_osp_falha_no_postgres(self):
        from django.db import NotSupportedError
        from apps.osp.models import OrdemServico
        with self.assertRaises(NotSupportedError):
            list(OrdemServico.objects.select_for_update().select_related(
                "cliente", "equipamento", "responsavel").filter(pk=0))

    def test_consulta_de_emissao_do_laudo_falha_no_postgres(self):
        from django.db import NotSupportedError
        from apps.laudos.models import Laudo
        with self.assertRaises(NotSupportedError):
            list(Laudo.objects.select_for_update().select_related(
                "responsavel", "template", "inspecao__cliente", "relatorio_origem__cliente").filter(pk=0))

    def test_correcao_of_self_compila_no_postgres(self):
        from apps.osp.models import OrdemServico
        self.assertEqual(list(OrdemServico.objects.select_for_update(of=("self",)).select_related(
            "cliente", "equipamento", "responsavel").filter(pk=0)), [])
