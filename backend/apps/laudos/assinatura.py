"""
Item 2.5.1.3 — assinatura digital PAdES (ISO 32000 / ETSI EN 319 142) do PDF do laudo com
certificado A1 (PKCS#12), via pyHanko (MIT). Assinatura INVISÍVEL: nenhuma aparência é
desenhada, então o layout aprovado do PDF não muda.
"""
from io import BytesIO

from asn1crypto import x509 as asn1_x509
from asn1crypto.pem import unarmor
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.sign import fields, signers
from pyhanko.sign.validation import validate_pdf_signature
from pyhanko_certvalidator import ValidationContext

NOME_CAMPO = "AssinaturaResponsavelTecnico"


class AssinaturaInvalida(ValueError):
    """PDF ilegível como PDF assinável (corrompido ou não é PDF)."""


def assinar_pades(pdf: bytes, pfx: bytes, senha: str, *, motivo: str, local: str) -> bytes:
    """Devolve o PDF com uma assinatura PAdES incremental. Levanta ValueError se o .pfx não abrir."""
    # load_pkcs12_data recebe os bytes: o .pfx não vai para disco.
    signer = signers.SimpleSigner.load_pkcs12_data(pfx, other_certs=set(), passphrase=senha.encode("utf-8"))
    if signer is None:
        raise ValueError("Certificado não carregou.")
    meta = signers.PdfSignatureMetadata(
        field_name=NOME_CAMPO, reason=motivo, location=local,
        subfilter=fields.SigSeedSubFilter.PADES,
    )
    saida = signers.PdfSigner(meta, signer=signer).sign_pdf(IncrementalPdfFileWriter(BytesIO(pdf)))
    return saida.getvalue()


def _raizes_confiaveis(raizes_pem: list[bytes]) -> list:
    certificados = []
    for pem in raizes_pem:
        der = unarmor(pem)[2] if pem.lstrip().startswith(b"-----") else pem
        certificados.append(asn1_x509.Certificate.load(der))
    return certificados


def verificar_pades(pdf: bytes, raizes_pem: list[bytes] | None = None) -> list[dict]:
    """
    Verifica cada assinatura do PDF. `intacto` = o conteúdo não mudou desde a assinatura.
    `confiavel` só é verdadeiro se a cadeia chegar a uma das raízes informadas (ex.: a AC
    ICP-Brasil configurada em ambiente). Sem raízes, a cadeia não é avaliada como confiável.
    """
    try:
        leitor = PdfFileReader(BytesIO(pdf))
    except Exception as erro:  # pyHanko levanta PdfError/PdfStrictReadError conforme o defeito
        raise AssinaturaInvalida("O arquivo não é um PDF legível.") from erro
    contexto = ValidationContext(trust_roots=_raizes_confiaveis(raizes_pem or []), allow_fetching=False)
    resultado = []
    for embutida in leitor.embedded_signatures:
        status = validate_pdf_signature(embutida, contexto)
        resultado.append({
            "campo": embutida.field_name,
            "intacto": bool(status.intact),
            "valido": bool(status.valid),
            "confiavel": bool(status.trusted),
        })
    return resultado
