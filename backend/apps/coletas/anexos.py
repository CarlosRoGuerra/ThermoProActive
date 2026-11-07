"""
Anexos de documento (Anexo I 2.3.1.3 — upload de arquivos além de imagens).

Aceita PDF (laudo de laboratório), XLSX, DOCX e CSV, vinculados à inspeção, ao
equipamento e/ou ao relatório de inspeção.

Regras de segurança:

* a extensão NÃO basta: o conteúdo é conferido pela assinatura do formato
  (PDF = `%PDF-`; XLSX/DOCX = conteiner ZIP com as partes obrigatórias do OOXML;
  CSV = texto sem bytes de controle);
* o nome no disco é um UUID gerado pelo servidor (`ArmazenamentoAnexo`): nenhum
  caminho ou nome vindo do usuário chega ao sistema de arquivos;
* o nome original é guardado só como rótulo, depois de `sanitizar_nome`;
* tamanho máximo configurável (`ANEXOS_MAX_BYTES`, padrão 20 MB) e limite de
  tamanho descompactado para XLSX/DOCX (proteção contra zip bomb);
* o download é sempre `Content-Disposition: attachment` (ver `apps.core.midia`).
* OOXML (XLSX/DOCX): mede o descompactado REAL em streaming, com teto de tamanho, de entradas e de
  razão de compressão; recusa macros (vbaProject, content types habilitados) e relações externas.
* CSV: os bytes são guardados e devolvidos INTACTOS (o SHA-256 confere com o original). O sistema não
  exibe nem exporta o conteúdo do CSV: ele só volta como anexo. Neutralizar fórmulas (`=`, `+`, `-`,
  `@`) alteraria o arquivo do usuário, então não é feito aqui. Quem abrir o CSV no Excel deve tratar
  o arquivo como dado não confiável.
"""
import hashlib
import io
import posixpath
import re
import uuid
import zipfile
import zlib

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible

from apps.core.midia import TIPOS_DOCUMENTO

#: Partes que todo OOXML válido tem (além de [Content_Types].xml).
PARTES_OOXML = {".xlsx": "xl/workbook.xml", ".docx": "word/document.xml"}

LIMITE_PADRAO_BYTES = 20 * 1024 * 1024
LIMITE_DESCOMPACTADO_BYTES = 100 * 1024 * 1024
#: Entradas do contêiner OOXML. Um XLSX/DOCX real tem dezenas; milhares indicam abuso.
LIMITE_ENTRADAS_ZIP = 2000
#: Razão descompactado real ÷ tamanho do arquivo. Só vale acima de `MINIMO_RAZAO_BYTES`, para
#: não recusar planilha pequena e legítima. Compressão desse nível é de arquivo forjado.
RAZAO_MAXIMA_COMPRESSAO = 200
MINIMO_RAZAO_BYTES = 10 * 1024 * 1024
_TOKENS_MACRO_CONTENT_TYPES = (b"macroenabled", b"vbaproject")
_RELACAO_EXTERNA = re.compile(rb'TargetMode\s*=\s*"External"', re.IGNORECASE)

_CONTROLE_CSV = re.compile(rb"[\x01-\x08\x0b\x0c\x0e-\x1f]")


def limite_bytes() -> int:
    return int(getattr(settings, "ANEXOS_MAX_BYTES", LIMITE_PADRAO_BYTES))


def extensao_de(nome: str) -> str:
    return posixpath.splitext(nome or "")[1].lower()


def sanitizar_nome(nome: str) -> str:
    """Rótulo seguro para exibir e para o cabeçalho de download (sem caminho, sem controle)."""
    nome = posixpath.basename(str(nome or "").replace("\\", "/")).strip()
    nome = "".join(c for c in nome if c.isprintable() and c not in '"<>:|?*;')
    nome = re.sub(r"\s+", " ", nome).strip(" .")
    raiz, ext = posixpath.splitext(nome)
    return ((raiz[:100] or "anexo") + ext.lower())[:120]


def _ler_ooxml(dados: bytes, formato: str):
    """
    Lê o contêiner OOXML medindo o descompactado REAL, em streaming, membro por membro. O
    `file_size` do diretório central não é usado: quem escreve o arquivo também escreve esse valor.
    Devolve (nomes, conteúdo dos .rels e de [Content_Types].xml, que são pequenos).
    """
    invalido = ValueError(f"O conteúdo do arquivo não é um {formato} válido.")
    total = 0
    guardados = {}
    try:
        with zipfile.ZipFile(io.BytesIO(dados)) as conteiner:
            infos = conteiner.infolist()
            if len(infos) > LIMITE_ENTRADAS_ZIP:
                raise ValueError("O arquivo tem entradas demais.")
            for info in infos:
                guardar = info.filename.lower().endswith((".rels", "[content_types].xml"))
                partes = [] if guardar else None
                with conteiner.open(info) as membro:
                    while True:
                        bloco = membro.read(64 * 1024)
                        if not bloco:
                            break
                        total += len(bloco)
                        if total > LIMITE_DESCOMPACTADO_BYTES:
                            raise ValueError("O arquivo é grande demais quando descompactado.")
                        if partes is not None:
                            partes.append(bloco)
                if guardar:
                    guardados[info.filename] = b"".join(partes)
            nomes = {info.filename for info in infos}
    except (zipfile.BadZipFile, zlib.error, NotImplementedError, RuntimeError, EOFError):
        raise invalido
    if total > MINIMO_RAZAO_BYTES and total > RAZAO_MAXIMA_COMPRESSAO * len(dados):
        raise ValueError("Razão de compressão suspeita: o arquivo parece uma bomba de descompactação.")
    return nomes, guardados


def _recusar_macros_e_links(nomes, guardados, formato: str) -> None:
    """Macro (vbaProject, content types habilitados para macro) e relações externas não são aceitas."""
    if any(n.lower().endswith("vbaproject.bin") for n in nomes):
        raise ValueError(f"O {formato} contém macros, que não são aceitas. Salve sem macros.")
    if any(n.lower().startswith("xl/externallinks/") for n in nomes):
        raise ValueError(f"O {formato} contém vínculos com outros arquivos, que não são aceitos.")
    ct = guardados.get("[Content_Types].xml", b"").lower()
    if any(token in ct for token in _TOKENS_MACRO_CONTENT_TYPES):
        raise ValueError(f"O {formato} está marcado como habilitado para macros, que não são aceitas.")
    for nome, conteudo in guardados.items():
        if nome.lower().endswith(".rels") and _RELACAO_EXTERNA.search(conteudo):
            raise ValueError(f"O {formato} referencia conteúdo externo, que não é aceito.")


def conferir_conteudo(extensao: str, dados: bytes) -> None:
    """Levanta ValueError (mensagem para o usuário) se o conteúdo não bate com a extensão."""
    if extensao == ".pdf":
        if not dados[:1024].lstrip(b"\xef\xbb\xbf").startswith(b"%PDF-"):
            raise ValueError("O conteúdo do arquivo não é um PDF válido.")
        # Heurística: PDF que declara ação automática em texto é recusado. Não substitui
        # antivírus; PDFs com objetos comprimidos podem escapar desta checagem.
        if re.search(rb"/(JavaScript|Launch|EmbeddedFile)\b", dados):
            raise ValueError("PDF com JavaScript, ação de inicialização ou arquivo embutido não é aceito.")
        return
    if extensao in PARTES_OOXML:
        formato = extensao[1:].upper()
        if not dados.startswith(b"PK\x03\x04"):
            raise ValueError(f"O conteúdo do arquivo não é um {formato} válido.")
        nomes, guardados = _ler_ooxml(dados, formato)
        if "[Content_Types].xml" not in nomes or PARTES_OOXML[extensao] not in nomes:
            raise ValueError(f"O conteúdo do arquivo não é um {formato} válido.")
        _recusar_macros_e_links(nomes, guardados, formato)
        return
    if extensao == ".csv":
        if b"\x00" in dados or _CONTROLE_CSV.search(dados):
            raise ValueError("O CSV contém bytes binários; envie um arquivo de texto.")
        for codificacao in ("utf-8-sig", "cp1252"):
            try:
                dados.decode(codificacao)
                return
            except UnicodeDecodeError:
                continue
        raise ValueError("Não foi possível ler o CSV (codificação não reconhecida).")
    raise ValueError("Tipo de arquivo não aceito.")


def validar_upload(arquivo) -> dict:
    """
    Valida o UploadedFile e devolve os metadados a gravar:
    `nome_original`, `tamanho_bytes`, `sha256`. Levanta ValueError.
    """
    nome = sanitizar_nome(getattr(arquivo, "name", ""))
    extensao = extensao_de(nome)
    if extensao not in TIPOS_DOCUMENTO:
        raise ValueError("Tipo não aceito. Envie PDF, XLSX, DOCX ou CSV.")
    tamanho = int(getattr(arquivo, "size", 0) or 0)
    if tamanho == 0:
        raise ValueError("O arquivo está vazio.")
    limite = limite_bytes()
    if tamanho > limite:
        raise ValueError(f"O arquivo excede {limite // (1024 * 1024)} MB.")
    arquivo.seek(0)
    dados = arquivo.read()
    arquivo.seek(0)
    conferir_conteudo(extensao, dados)
    return {
        "nome_original": nome,
        "tamanho_bytes": tamanho,
        "sha256": hashlib.sha256(dados).hexdigest(),
    }


@deconstructible
class ArmazenamentoAnexo(FileSystemStorage):
    """Grava o anexo como `<pasta>/<uuid><ext>`: o nome do usuário nunca vai ao disco."""

    def get_available_name(self, name, max_length=None):
        # No Windows o Django monta o caminho com "\\": normaliza antes, senão a pasta se perde.
        pasta, nome = posixpath.split(str(name).replace("\\", "/"))
        ext = posixpath.splitext(nome)[1].lower()
        return super().get_available_name(posixpath.join(pasta, uuid.uuid4().hex + ext), max_length=max_length)
