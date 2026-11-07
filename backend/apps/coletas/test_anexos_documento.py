"""
Anexo I 2.3.1.3 — upload de documentos (PDF, XLSX, DOCX, CSV) além de imagens.

Cobre: validação pelo CONTEÚDO (não só extensão), limite de tamanho, nome sanitizado e
UUID no disco, vínculo somente com o cliente dono, permissões por perfil (cliente só lê o
marcado como visível) e download autenticado como `attachment` (nunca inline).
"""
import io
import os
import shutil
import tempfile
import zipfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import Nivel
from apps.cadastros.models import Area, Cliente, Equipamento, Setor, TecnologiaAnalise, TipoEquipamento
from apps.coletas import anexos
from apps.coletas.models import AnexoDocumento, Inspecao, Relatorio

User = get_user_model()

PDF = b"%PDF-1.4\n1 0 obj << /Type /Catalog >> endobj\n%%EOF\n"
CSV = "data;valor\n2026-01-01;4,5\n".encode("utf-8")


def xlsx_valido():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("xl/workbook.xml", "<workbook/>")
    return buf.getvalue()


def docx_valido():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", "<document/>")
    return buf.getvalue()


def envio(nome, conteudo, tipo="application/octet-stream"):
    return SimpleUploadedFile(nome, conteudo, content_type=tipo)


class AnexoDocumentoBase(TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.mkdtemp()
        cls._override = override_settings(MEDIA_ROOT=cls._tmp)
        cls._override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._override.disable()
        shutil.rmtree(cls._tmp, ignore_errors=True)

    @classmethod
    def setUpTestData(cls):
        cls.a = Cliente.objects.create(nome="Cliente A", cnpj="11.111.111/0001-11")
        cls.b = Cliente.objects.create(nome="Cliente B", cnpj="22.222.222/0001-22")
        mk = lambda e, p, **kw: User.objects.create_user(email=e, password="x", nome=e, perfil=p, **kw)  # noqa: E731
        cls.tecnico = mk("tec@thermo.test", "TECNICO")
        cls.master = mk("master@thermo.test", "TECNICO", nivel=Nivel.MASTER)
        cls.cli_a = mk("a@a.test", "CLIENTE_PCM", cliente=cls.a)
        cls.cli_b = mk("b@b.test", "CLIENTE_PCM", cliente=cls.b)
        tec = TecnologiaAnalise.objects.create(nome="Vibração", sigla="VIB")
        tipo = TipoEquipamento.objects.create(nome="Motor")
        cls.setor_a = Setor.objects.create(
            area=Area.objects.create(cliente=cls.a, codigo="A", nome="A"), codigo="A", nome="A")
        cls.setor_b = Setor.objects.create(
            area=Area.objects.create(cliente=cls.b, codigo="B", nome="B"), codigo="B", nome="B")
        cls.eq_a = Equipamento.objects.create(setor=cls.setor_a, tag="A-001", nome="Motor A", tipo_equipamento=tipo)
        cls.eq_b = Equipamento.objects.create(setor=cls.setor_b, tag="B-001", nome="Motor B", tipo_equipamento=tipo)
        cls.insp_a = Inspecao.objects.create(cliente=cls.a, tecnico=cls.tecnico, data="2026-10-01")
        cls.insp_b = Inspecao.objects.create(cliente=cls.b, tecnico=cls.tecnico, data="2026-10-01")
        cls.rel_a = Relatorio.objects.create(
            cliente=cls.a, tecnologia=tec, numero="RT-A-1", data_termino="2026-10-01")
        cls.rel_b = Relatorio.objects.create(
            cliente=cls.b, tecnologia=tec, numero="RT-B-1", data_termino="2026-10-01")

    def api(self, usuario=None):
        cliente = APIClient()
        if usuario is not None:
            cliente.force_authenticate(usuario)
        return cliente

    def enviar(self, usuario, nome, conteudo, **dados):
        payload = {"cliente": self.a.pk, "inspecao": self.insp_a.pk, "arquivo": envio(nome, conteudo), **dados}
        # multipart não aceita None: campo nulo é simplesmente omitido (equivale a não vincular).
        payload = {k: v for k, v in payload.items() if v is not None}
        return self.api(usuario).post("/api/anexos-documentos/", payload, format="multipart")


class ValidacaoConteudoTests(AnexoDocumentoBase):
    """Assinatura de bytes, não extensão."""

    def test_pdf_valido_e_aceito(self):
        r = self.enviar(self.tecnico, "laudo.pdf", PDF)
        self.assertEqual(r.status_code, 201, r.content)

    def test_pdf_falso_com_extensao_pdf_e_recusado(self):
        r = self.enviar(self.tecnico, "laudo.pdf", b"isto nao e um pdf")
        self.assertEqual(r.status_code, 400)
        self.assertIn("arquivo", r.json())

    def test_pdf_com_javascript_e_recusado(self):
        conteudo = b"%PDF-1.4\n/OpenAction << /S /JavaScript /JS (app.alert(1)) >>\n%%EOF"
        self.assertEqual(self.enviar(self.tecnico, "x.pdf", conteudo).status_code, 400)

    def test_xlsx_valido_e_aceito(self):
        r = self.enviar(self.tecnico, "planilha.xlsx", xlsx_valido())
        self.assertEqual(r.status_code, 201, r.content)

    def test_zip_sem_partes_do_xlsx_e_recusado(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("qualquer.txt", "x")
        self.assertEqual(self.enviar(self.tecnico, "planilha.xlsx", buf.getvalue()).status_code, 400)

    def test_docx_valido_e_aceito_e_docx_com_conteudo_de_xlsx_recusado(self):
        self.assertEqual(self.enviar(self.tecnico, "relatorio.docx", docx_valido()).status_code, 201)
        self.assertEqual(self.enviar(self.tecnico, "errado.docx", xlsx_valido()).status_code, 400)

    def test_csv_texto_e_aceito_csv_binario_e_recusado(self):
        self.assertEqual(self.enviar(self.tecnico, "dados.csv", CSV).status_code, 201)
        self.assertEqual(self.enviar(self.tecnico, "bin.csv", b"a;b\x00\x01\x02").status_code, 400)

    def test_extensao_fora_da_lista_e_recusada(self):
        for nome in ("malware.exe", "pagina.html", "macro.xlsm", "semextensao"):
            with self.subTest(nome=nome):
                self.assertEqual(self.enviar(self.tecnico, nome, PDF).status_code, 400)

    def test_arquivo_vazio_e_recusado(self):
        self.assertEqual(self.enviar(self.tecnico, "vazio.pdf", b"").status_code, 400)

    @override_settings(ANEXOS_MAX_BYTES=100)
    def test_limite_de_tamanho_configuravel(self):
        grande = PDF + b"%" * 200
        r = self.enviar(self.tecnico, "grande.pdf", grande)
        self.assertEqual(r.status_code, 400)
        self.assertIn("excede", str(r.json()["arquivo"]))

    def test_limite_de_descompactado_barra_zip_bomba(self):
        with override_settings():
            antigo = anexos.LIMITE_DESCOMPACTADO_BYTES
            anexos.LIMITE_DESCOMPACTADO_BYTES = 10
            try:
                self.assertEqual(self.enviar(self.tecnico, "bomba.xlsx", xlsx_valido()).status_code, 400)
            finally:
                anexos.LIMITE_DESCOMPACTADO_BYTES = antigo


class NomeETamanhoTests(AnexoDocumentoBase):
    def test_nome_com_caminho_e_sanitizado_e_disco_usa_uuid(self):
        r = self.enviar(self.tecnico, "../../etc/laudo \"x\".pdf", PDF)
        self.assertEqual(r.status_code, 201, r.content)
        anexo = AnexoDocumento.objects.get(pk=r.json()["id"])
        self.assertNotIn("..", anexo.nome_original)
        self.assertNotIn('"', anexo.nome_original)
        self.assertEqual(anexo.nome_original, "laudo x.pdf")
        nome_disco = os.path.basename(anexo.arquivo.name)
        self.assertRegex(nome_disco, r"^[0-9a-f]{32}\.pdf$")
        self.assertTrue(anexo.arquivo.name.startswith("anexos/documentos/"))

    def test_metadados_gravados(self):
        r = self.enviar(self.tecnico, "dados.csv", CSV)
        anexo = AnexoDocumento.objects.get(pk=r.json()["id"])
        self.assertEqual(anexo.tamanho_bytes, len(CSV))
        self.assertEqual(len(anexo.sha256), 64)
        self.assertEqual(anexo.enviado_por, self.tecnico)


class VinculoEscopoTests(AnexoDocumentoBase):
    def test_sem_vinculo_e_recusado(self):
        r = self.api(self.tecnico).post(
            "/api/anexos-documentos/",
            {"cliente": self.a.pk, "arquivo": envio("x.pdf", PDF)}, format="multipart")
        self.assertEqual(r.status_code, 400)

    def test_inspecao_de_outro_cliente_e_recusada(self):
        r = self.enviar(self.tecnico, "x.pdf", PDF, inspecao=self.insp_b.pk)
        self.assertEqual(r.status_code, 400)
        self.assertIn("inspecao", r.json())

    def test_equipamento_de_outro_cliente_e_recusado(self):
        r = self.enviar(self.tecnico, "x.pdf", PDF, inspecao=None, equipamento=self.eq_b.pk)
        self.assertEqual(r.status_code, 400)
        self.assertIn("equipamento", r.json())

    def test_relatorio_de_outro_cliente_e_recusado(self):
        r = self.enviar(self.tecnico, "x.pdf", PDF, relatorio=self.rel_b.pk)
        self.assertEqual(r.status_code, 400)
        self.assertIn("relatorio", r.json())

    def test_vinculos_do_mesmo_cliente_sao_aceitos(self):
        r = self.enviar(self.tecnico, "x.pdf", PDF, equipamento=self.eq_a.pk, relatorio=self.rel_a.pk)
        self.assertEqual(r.status_code, 201, r.content)

    def test_arquivo_nao_pode_ser_trocado_e_cliente_nao_muda(self):
        anexo = AnexoDocumento.objects.get(pk=self.enviar(self.tecnico, "x.pdf", PDF).json()["id"])
        cli = self.api(self.tecnico)
        r = cli.patch(f"/api/anexos-documentos/{anexo.pk}/",
                      {"arquivo": envio("y.pdf", PDF)}, format="multipart")
        self.assertEqual(r.status_code, 400)
        r = cli.patch(f"/api/anexos-documentos/{anexo.pk}/", {"cliente": self.b.pk}, format="json")
        self.assertEqual(r.status_code, 400)
        r = cli.patch(f"/api/anexos-documentos/{anexo.pk}/", {"descricao": "Laudo lab"}, format="json")
        self.assertEqual(r.status_code, 200)

    def test_cliente_nao_envia_nem_altera(self):
        self.assertEqual(self.enviar(self.cli_a, "x.pdf", PDF).status_code, 403)
        anexo = AnexoDocumento.objects.get(pk=self.enviar(self.tecnico, "x.pdf", PDF).json()["id"])
        r = self.api(self.cli_a).patch(
            f"/api/anexos-documentos/{anexo.pk}/", {"descricao": "x"}, format="json")
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.api(self.cli_a).delete(f"/api/anexos-documentos/{anexo.pk}/").status_code, 403)

    def test_listagem_do_cliente_so_mostra_visiveis_do_proprio_cliente(self):
        oculto = self.enviar(self.tecnico, "oculto.pdf", PDF).json()["id"]
        visivel = self.enviar(self.tecnico, "visivel.pdf", PDF, visivel_cliente=True).json()["id"]
        outro = self.enviar(self.tecnico, "outro.pdf", PDF, cliente=self.b.pk, inspecao=self.insp_b.pk,
                            visivel_cliente=True).json()["id"]
        ids = [x["id"] for x in self.api(self.cli_a).get("/api/anexos-documentos/").json()["results"]]
        self.assertIn(visivel, ids)
        self.assertNotIn(oculto, ids)
        self.assertNotIn(outro, ids)
        self.assertEqual(self.api(self.cli_a).get(f"/api/anexos-documentos/{oculto}/").status_code, 404)
        self.assertEqual(self.api(self.cli_b).get(f"/api/anexos-documentos/{visivel}/").status_code, 404)

    def test_cliente_sem_vinculo_de_cliente_ve_nada(self):
        sem = User.objects.create_user(email="s@s.test", password="x", nome="s", perfil="CLIENTE_PCM")
        self.enviar(self.tecnico, "x.pdf", PDF, visivel_cliente=True)
        self.assertEqual(self.api(sem).get("/api/anexos-documentos/").json()["count"], 0)

    def test_sem_login_nao_acessa(self):
        self.assertIn(self.api(None).get("/api/anexos-documentos/").status_code, (401, 403))


class DownloadTests(AnexoDocumentoBase):
    def baixar(self, usuario, anexo):
        return self.api(usuario).get(f"/api/media/{anexo.arquivo.name}")

    def test_documento_sai_como_attachment_nunca_inline(self):
        anexo = AnexoDocumento.objects.get(pk=self.enviar(self.tecnico, "Laudo final.pdf", PDF).json()["id"])
        r = self.baixar(self.tecnico, anexo)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "application/pdf")
        disposicao = r["Content-Disposition"]
        self.assertTrue(disposicao.startswith("attachment"), disposicao)
        self.assertIn("filename*=UTF-8''Laudo%20final.pdf", disposicao)
        self.assertNotIn("inline", disposicao)
        self.assertEqual(r["X-Content-Type-Options"], "nosniff")
        self.assertIn("sandbox", r["Content-Security-Policy"])

    def test_cliente_baixa_so_o_visivel_do_proprio_cliente(self):
        visivel = AnexoDocumento.objects.get(pk=self.enviar(
            self.tecnico, "v.pdf", PDF, visivel_cliente=True).json()["id"])
        oculto = AnexoDocumento.objects.get(pk=self.enviar(self.tecnico, "o.pdf", PDF).json()["id"])
        self.assertEqual(self.baixar(self.cli_a, visivel).status_code, 200)
        self.assertEqual(self.baixar(self.cli_a, oculto).status_code, 404)
        self.assertEqual(self.baixar(self.cli_b, visivel).status_code, 404)

    def test_tipo_de_documento_com_extensao_de_imagem_nao_e_servido(self):
        anexo = AnexoDocumento.objects.get(pk=self.enviar(self.tecnico, "x.pdf", PDF).json()["id"])
        AnexoDocumento.objects.filter(pk=anexo.pk).update(arquivo="anexos/documentos/x.png")
        self.assertEqual(self.api(self.tecnico).get("/api/media/anexos/documentos/x.png").status_code, 404)

    def test_sem_login_nao_baixa(self):
        anexo = AnexoDocumento.objects.get(pk=self.enviar(self.tecnico, "x.pdf", PDF).json()["id"])
        self.assertIn(self.baixar(None, anexo).status_code, (401, 403))


class ExclusaoTests(AnexoDocumentoBase):
    def test_excluir_remove_arquivo_do_disco_apos_commit(self):
        anexo = AnexoDocumento.objects.get(pk=self.enviar(self.tecnico, "x.pdf", PDF).json()["id"])
        caminho = anexo.arquivo.path
        self.assertTrue(os.path.exists(caminho))
        with self.captureOnCommitCallbacks(execute=True):
            r = self.api(self.master).delete(f"/api/anexos-documentos/{anexo.pk}/")
        self.assertEqual(r.status_code, 204)
        self.assertFalse(os.path.exists(caminho))


class ModeloTests(TestCase):
    def test_nome_sanitizado_remove_caminho_e_controle(self):
        self.assertEqual(anexos.sanitizar_nome("C:\\temp\\laudo.pdf"), "laudo.pdf")
        self.assertEqual(anexos.sanitizar_nome("a\x00b<c>.PDF"), "abc.pdf")
        self.assertEqual(len(anexos.sanitizar_nome("x" * 500 + ".pdf")), 104)

    def test_regra_de_midia_registrada(self):
        from apps.core import midia
        prefixos = [r[0] for r in midia.REGRAS]
        self.assertIn("anexos/documentos/", prefixos)


class MidiaAchadoLiberacaoTests(AnexoDocumentoBase):
    """S-24 aplicado à mídia: foto de achado não liberado não sai para o cliente."""

    def setUp(self):
        from apps.coletas.models import Achado, AchadoImagem, Carregamento, ItemInspecao
        from django.core.files.uploadedfile import SimpleUploadedFile
        import io
        from PIL import Image
        buf = io.BytesIO()
        Image.new("RGB", (4, 4), (1, 2, 3)).save(buf, "PNG")
        carreg = Carregamento.objects.create(cliente=self.a, tecnologia=TecnologiaAnalise.objects.first(),
                                             analista=self.tecnico)
        item = ItemInspecao.objects.create(carregamento=carreg, equipamento=self.eq_a, ordem=1)
        self.nao_liberado = AchadoImagem.objects.create(
            achado=Achado.objects.create(item=item, visivel_cliente=False), tipo="REAL",
            arquivo=SimpleUploadedFile("n.png", buf.getvalue(), content_type="image/png"))
        self.liberado = AchadoImagem.objects.create(
            achado=Achado.objects.create(item=item, visivel_cliente=True), tipo="REAL",
            arquivo=SimpleUploadedFile("l.png", buf.getvalue(), content_type="image/png"))

    def test_cliente_nao_recebe_foto_de_achado_nao_liberado(self):
        r = self.api(self.cli_a).get(f"/api/media/{self.nao_liberado.arquivo.name}")
        self.assertEqual(r.status_code, 404)

    def test_cliente_recebe_foto_de_achado_liberado(self):
        r = self.api(self.cli_a).get(f"/api/media/{self.liberado.arquivo.name}")
        self.assertEqual(r.status_code, 200)

    def test_interno_recebe_foto_nao_liberada(self):
        r = self.api(self.tecnico).get(f"/api/media/{self.nao_liberado.arquivo.name}")
        self.assertEqual(r.status_code, 200)

    def test_outro_cliente_nao_recebe_foto_liberada(self):
        r = self.api(self.cli_b).get(f"/api/media/{self.liberado.arquivo.name}")
        self.assertEqual(r.status_code, 404)


def ooxml(membros):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for nome, conteudo in membros.items():
            z.writestr(nome, conteudo)
    return buf.getvalue()


class OOXMLMacrosELinksTests(AnexoDocumentoBase):
    """V-06: macro, vínculo externo e content type de macro são recusados; XLSX legítimo continua aceito."""

    base = {
        "[Content_Types].xml": "<Types/>",
        "xl/workbook.xml": "<workbook/>",
    }

    def test_xlsx_legitimo_continua_aceito(self):
        self.assertEqual(self.enviar(self.tecnico, "ok.xlsx", ooxml(self.base)).status_code, 201)

    def test_vbaproject_e_recusado(self):
        conteudo = ooxml({**self.base, "xl/vbaProject.bin": "macro"})
        self.assertEqual(self.enviar(self.tecnico, "macro.xlsx", conteudo).status_code, 400)

    def test_content_type_habilitado_para_macro_e_recusado(self):
        ct = "<Types>application/vnd.ms-excel.sheet.macroEnabled.main+xml</Types>"
        conteudo = ooxml({**self.base, "[Content_Types].xml": ct})
        self.assertEqual(self.enviar(self.tecnico, "x.xlsx", conteudo).status_code, 400)

    def test_relacao_externa_e_recusada(self):
        rels = '<Relationships><Relationship Id="r1" Type="x" Target="file:///etc/passwd" TargetMode="External"/></Relationships>'
        conteudo = ooxml({**self.base, "xl/_rels/workbook.xml.rels": rels})
        self.assertEqual(self.enviar(self.tecnico, "link.xlsx", conteudo).status_code, 400)

    def test_external_link_part_e_recusado(self):
        conteudo = ooxml({**self.base, "xl/externalLinks/externalLink1.xml": "<x/>"})
        self.assertEqual(self.enviar(self.tecnico, "ext.xlsx", conteudo).status_code, 400)

    def test_entradas_demais_sao_recusadas(self):
        with override_settings():
            antigo = anexos.LIMITE_ENTRADAS_ZIP
            anexos.LIMITE_ENTRADAS_ZIP = 3
            try:
                self.assertEqual(self.enviar(self.tecnico, "muitas.xlsx", ooxml(
                    {**self.base, "a.xml": "1", "b.xml": "2"})).status_code, 400)
            finally:
                anexos.LIMITE_ENTRADAS_ZIP = antigo

    def test_csv_com_formula_e_guardado_e_devolvido_intacto(self):
        """V-06 (CSV): o sistema não neutraliza nem altera o arquivo; o hash confere com o original."""
        import hashlib
        conteudo = b"item;valor\n=HYPERLINK(\"http://x\");+2\n"
        r = self.enviar(self.tecnico, "f.csv", conteudo)
        self.assertEqual(r.status_code, 201)
        anexo = AnexoDocumento.objects.get(pk=r.json()["id"])
        self.assertEqual(anexo.sha256, hashlib.sha256(conteudo).hexdigest())
        with anexo.arquivo.storage.open(anexo.arquivo.name, "rb") as f:
            self.assertEqual(f.read(), conteudo)
