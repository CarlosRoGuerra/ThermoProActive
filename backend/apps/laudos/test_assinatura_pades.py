"""
Item 2.5.1.3 — assinatura digital PAdES (invisível) do PDF do laudo com certificado A1.

Os certificados são autoassinados e gerados no próprio teste (nenhum arquivo real).
Cobre: assinatura e verificação, adulteração, cadeia confiável x não confiável, upload
do .pfx (senha validada e não guardada), permissões e os casos sem certificado.
"""
import datetime
import hashlib
from datetime import date
from io import BytesIO

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import CertificadoA1, Nivel, Perfil, User
from apps.coletas.models import Inspecao
from apps.cadastros.models import Cliente, Empresa
from apps.laudos.assinatura import AssinaturaInvalida, assinar_pades, verificar_pades
from apps.laudos.models import Laudo, StatusLaudo

SENHA_PFX = "senha-do-certificado-2026"


def pdf_minimo(texto="Laudo de teste"):
    """PDF de uma página, com xref correto — suficiente para assinar e verificar."""
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        None,
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    fluxo = f"BT /F1 12 Tf 72 720 Td ({texto}) Tj ET".encode()
    objs[3] = b"<< /Length %d >>\nstream\n" % len(fluxo) + fluxo + b"\nendstream"
    saida = bytearray(b"%PDF-1.4\n")
    deslocamentos = []
    for i, corpo in enumerate(objs, start=1):
        deslocamentos.append(len(saida))
        saida += b"%d 0 obj\n" % i + corpo + b"\nendobj\n"
    xref = len(saida)
    saida += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for off in deslocamentos:
        saida += b"%010d 00000 n \n" % off
    saida += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    return bytes(saida)


def gerar_pfx(dias=30, senha=SENHA_PFX, cn="Responsavel Tecnico Teste"):
    chave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    nome = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])
    agora = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder().subject_name(nome).issuer_name(nome).public_key(chave.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(agora - datetime.timedelta(days=400))
        .not_valid_after(agora + datetime.timedelta(days=dias))
        .sign(chave, hashes.SHA256())
    )
    pfx = pkcs12.serialize_key_and_certificates(
        b"rt", chave, cert, None, serialization.BestAvailableEncryption(senha.encode())
    )
    return pfx, cert


class AssinaturaPadesUnitTests(TestCase):
    def test_assinar_e_verificar_com_raiz_confiavel(self):
        pfx, cert = gerar_pfx()
        assinado = assinar_pades(pdf_minimo(), pfx, SENHA_PFX, motivo="Laudo", local="Brasil")
        raiz = cert.public_bytes(serialization.Encoding.PEM)
        resultado = verificar_pades(assinado, [raiz])
        self.assertEqual(len(resultado), 1)
        self.assertTrue(resultado[0]["intacto"])
        self.assertTrue(resultado[0]["valido"])
        self.assertTrue(resultado[0]["confiavel"])

    def test_sem_raiz_a_cadeia_nao_e_confiavel_mas_o_conteudo_e_integro(self):
        pfx, _ = gerar_pfx()
        assinado = assinar_pades(pdf_minimo(), pfx, SENHA_PFX, motivo="Laudo", local="Brasil")
        resultado = verificar_pades(assinado, [])
        self.assertTrue(resultado[0]["intacto"])
        self.assertFalse(resultado[0]["confiavel"])

    def test_adulteracao_quebra_a_integridade(self):
        pfx, _ = gerar_pfx()
        assinado = assinar_pades(pdf_minimo("Laudo de teste"), pfx, SENHA_PFX, motivo="Laudo", local="Brasil")
        adulterado = assinado.replace(b"Laudo de teste", b"Laudo de tests")  # mesmo tamanho
        self.assertEqual(len(adulterado), len(assinado))
        resultado = verificar_pades(adulterado, [])
        self.assertFalse(resultado[0]["intacto"])

    def test_pdf_ilegivel_levanta_erro_tratado(self):
        with self.assertRaises(AssinaturaInvalida):
            verificar_pades(b"isto nao e um pdf", [])

    def test_assinatura_invisivel_nao_cria_aparencia(self):
        pfx, _ = gerar_pfx()
        assinado = assinar_pades(pdf_minimo(), pfx, SENHA_PFX, motivo="Laudo", local="Brasil")
        # Assinatura invisível: o widget do campo tem retângulo zero e nenhuma aparência desenhada.
        self.assertIn(b"/Rect [ 0 0 0 0 ]", assinado)
        self.assertIn(b"/ByteRange", assinado)


class CertificadoEAssinaturaApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.empresa = Empresa.objects.create(nome="Prestadora", cnpj="11.222.333/0001-81")
        cls.cliente = Cliente.objects.create(nome="Cliente A", cnpj="45.723.174/0001-10")
        cls.rt = User.objects.create_user(email="rt@t.test", password="uma frase senha longa 2026", nome="RT",
                                          perfil=Perfil.GESTOR, nivel=Nivel.MASTER, empresa=cls.empresa)
        cls.outro = User.objects.create_user(email="outro@t.test", password="uma frase senha longa 2026",
                                             nome="Outro", perfil=Perfil.TECNICO, nivel=Nivel.PLENO,
                                             empresa=cls.empresa)
        cls.cli = User.objects.create_user(email="cli@a.test", password="uma frase senha longa 2026",
                                           nome="Cli", perfil=Perfil.CLIENTE_PCM, nivel=Nivel.PLENO,
                                           cliente=cls.cliente)

    def setUp(self):
        cache.clear()

    def api(self, usuario):
        c = APIClient()
        c.force_authenticate(usuario)
        return c

    def emitir_laudo(self, responsavel=None):
        pdf = pdf_minimo()
        inspecao = Inspecao.objects.create(cliente=self.cliente, tecnico=self.rt, data=date(2026, 10, 1),
                                           tipo_analise="VIBRACAO")
        # Todo laudo nasce como rascunho; a emissão (estado EMITIDO + PDF) é levada por update.
        laudo = Laudo.objects.create(inspecao=inspecao, titulo="Laudo de teste", responsavel=responsavel or self.rt)
        Laudo.objects.filter(pk=laudo.pk).update(
            status=StatusLaudo.EMITIDO, pdf_conteudo=pdf, pdf_hash=hashlib.sha256(pdf).hexdigest(),
            data_emissao=timezone.now(),
        )
        laudo.refresh_from_db()
        return laudo

    def cadastrar_certificado(self, usuario=None, pfx=None, senha=SENHA_PFX):
        pfx = pfx or gerar_pfx()[0]
        return self.api(usuario or self.rt).post(
            "/api/auth/certificado-a1/",
            {"arquivo": SimpleUploadedFile("rt.pfx", pfx, content_type="application/x-pkcs12"), "senha": senha},
            format="multipart",
        )

    # --- upload -----------------------------------------------------------
    def test_upload_valida_senha_guarda_cifrado_e_nao_guarda_senha(self):
        pfx, _ = gerar_pfx()
        r = self.cadastrar_certificado(pfx=pfx)
        self.assertEqual(r.status_code, 201)
        cert = CertificadoA1.objects.get(usuario=self.rt)
        self.assertNotIn(SENHA_PFX, str(cert.__dict__))
        self.assertNotEqual(cert.arquivo_cifrado.encode(), pfx)
        self.assertNotIn(b"PKCS", cert.arquivo_cifrado.encode())
        self.assertNotIn("senha", [f.name for f in CertificadoA1._meta.fields])

    def test_upload_com_senha_errada_e_recusado(self):
        self.assertEqual(self.cadastrar_certificado(senha="errada").status_code, 400)
        self.assertFalse(CertificadoA1.objects.filter(usuario=self.rt).exists())

    def test_certificado_vencido_e_recusado(self):
        pfx, _ = gerar_pfx(dias=-5)
        self.assertEqual(self.cadastrar_certificado(pfx=pfx).status_code, 400)

    def test_somente_interno_cadastra_certificado(self):
        self.assertEqual(self.cadastrar_certificado(usuario=self.cli).status_code, 403)

    def test_consulta_e_remocao(self):
        self.cadastrar_certificado()
        self.assertEqual(self.api(self.rt).get("/api/auth/certificado-a1/").data["vencido"], False)
        self.assertEqual(self.api(self.rt).delete("/api/auth/certificado-a1/").status_code, 204)
        self.assertIsNone(self.api(self.rt).get("/api/auth/certificado-a1/").data["certificado"])

    # --- assinatura -------------------------------------------------------
    def test_responsavel_assina_e_verifica(self):
        self.cadastrar_certificado()
        laudo = self.emitir_laudo()
        r = self.api(self.rt).post(f"/api/laudos/{laudo.pk}/assinar-digitalmente/", {"senha": SENHA_PFX},
                                   format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertTrue(r.data["invisivel"])
        laudo.refresh_from_db()
        self.assertEqual(laudo.pdf_hash, hashlib.sha256(pdf_minimo()).hexdigest())  # original preservado
        self.assertEqual(laudo.pdf_assinado_sha256, hashlib.sha256(bytes(laudo.pdf_assinado_conteudo)).hexdigest())
        dl = self.api(self.rt).get(f"/api/laudos/{laudo.pk}/pdf-assinado/")
        self.assertEqual(dl.status_code, 200)
        v = self.api(self.rt).get(f"/api/laudos/{laudo.pk}/verificar-assinatura/")
        self.assertTrue(v.data["assinado"])
        self.assertTrue(v.data["sha256_confere"])
        self.assertTrue(v.data["assinaturas"][0]["intacto"])
        self.assertFalse(v.data["raiz_configurada"])

    def test_sem_certificado_mantem_aprovacao_eletronica(self):
        laudo = self.emitir_laudo()
        r = self.api(self.rt).post(f"/api/laudos/{laudo.pk}/assinar-digitalmente/", {"senha": SENHA_PFX},
                                   format="json")
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.data["codigo"], "SEM_CERTIFICADO")
        laudo.refresh_from_db()
        self.assertEqual(laudo.status, StatusLaudo.EMITIDO)  # emissão intacta

    def test_senha_errada_nao_assina(self):
        self.cadastrar_certificado()
        laudo = self.emitir_laudo()
        r = self.api(self.rt).post(f"/api/laudos/{laudo.pk}/assinar-digitalmente/", {"senha": "errada"},
                                   format="json")
        self.assertEqual(r.status_code, 400)
        laudo.refresh_from_db()
        self.assertFalse(laudo.pdf_assinado_conteudo)

    def test_so_o_responsavel_do_laudo_assina(self):
        self.cadastrar_certificado(usuario=self.outro)
        laudo = self.emitir_laudo()
        r = self.api(self.outro).post(f"/api/laudos/{laudo.pk}/assinar-digitalmente/", {"senha": SENHA_PFX},
                                      format="json")
        self.assertEqual(r.status_code, 403)

    def test_cliente_nao_assina_e_so_le_o_pdf_assinado(self):
        self.cadastrar_certificado()
        laudo = self.emitir_laudo()
        self.api(self.rt).post(f"/api/laudos/{laudo.pk}/assinar-digitalmente/", {"senha": SENHA_PFX}, format="json")
        self.assertIn(self.api(self.cli).post(f"/api/laudos/{laudo.pk}/assinar-digitalmente/",
                                              {"senha": SENHA_PFX}, format="json").status_code, (403, 404))
        self.assertEqual(self.api(self.cli).get(f"/api/laudos/{laudo.pk}/pdf-assinado/").status_code, 200)

    def test_nao_assina_duas_vezes(self):
        self.cadastrar_certificado()
        laudo = self.emitir_laudo()
        self.api(self.rt).post(f"/api/laudos/{laudo.pk}/assinar-digitalmente/", {"senha": SENHA_PFX}, format="json")
        r = self.api(self.rt).post(f"/api/laudos/{laudo.pk}/assinar-digitalmente/", {"senha": SENHA_PFX},
                                   format="json")
        self.assertEqual(r.status_code, 409)

    def test_laudo_sem_assinatura_nao_tem_pdf_assinado(self):
        laudo = self.emitir_laudo()
        self.assertEqual(self.api(self.rt).get(f"/api/laudos/{laudo.pk}/pdf-assinado/").status_code, 404)
        self.assertEqual(self.api(self.rt).get(f"/api/laudos/{laudo.pk}/verificar-assinatura/").data["assinado"],
                         False)
