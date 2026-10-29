"""PDF a partir de uma base congelada. Sem rede, HTML executável ou assinatura PKI.

ReportLab/Pillow já pertencem às dependências do projeto. Imagens referenciadas
são incorporadas à base emitida, para uma alteração de arquivo não mudar a versão.
"""
import base64
import binascii
import hashlib
import io
import json
import subprocess
import warnings
from pathlib import Path
from urllib.parse import unquote, urlsplit

from django.conf import settings
from django.core.files.storage import default_storage
from PIL import Image as PillowImage


class ErroGeracaoPDF(ValueError):
    """Falha controlada: emissão deve permanecer rascunho e permitir correção."""


_CHAVES_IMAGEM = {"arquivo", "imagem", "foto", "logo", "logomarca", "assinatura", "data_uri",
                   "tecnologia_imagem", "pontos_medicao_imagem", "imagem_termica", "imagem_visual"}


def _limite(nome, padrao):
    return int(getattr(settings, nome, padrao))


def _validar_imagem(conteudo):
    if len(conteudo) > _limite("LAUDOS_MAX_IMAGEM_BYTES", 10 * 1024 * 1024):
        raise ErroGeracaoPDF("Imagem excede o limite de tamanho configurado para emissão.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", PillowImage.DecompressionBombWarning)
            with PillowImage.open(io.BytesIO(conteudo)) as imagem:
                if getattr(imagem, "is_animated", False):
                    raise ErroGeracaoPDF("Imagem animada não pode ser emitida como evidência estática.")
                mime = PillowImage.MIME.get(imagem.format)
                if mime not in {"image/png", "image/jpeg", "image/webp", "image/gif", "image/tiff", "image/bmp"}:
                    raise ErroGeracaoPDF("Formato da imagem não suportado para emissão.")
                imagem.verify()
        return mime
    except ErroGeracaoPDF:
        raise
    except Exception as exc:
        raise ErroGeracaoPDF("Evidência de imagem inválida, corrompida ou com dimensões excessivas.") from exc


def _dados_uri(uri):
    try:
        cabecalho, texto = uri.split(",", 1)
        if not cabecalho.startswith("data:image/") or not cabecalho.endswith(";base64"):
            raise ValueError
        limite = _limite("LAUDOS_MAX_IMAGEM_BYTES", 10 * 1024 * 1024)
        if len(texto) > 4 * ((limite + 2) // 3):
            raise ErroGeracaoPDF("Imagem excede o limite de tamanho configurado para emissão.")
        dados = base64.b64decode(texto, validate=True)
    except ErroGeracaoPDF:
        raise
    except (ValueError, binascii.Error) as exc:
        raise ErroGeracaoPDF("Imagem incorporada tem codificação inválida.") from exc
    _validar_imagem(dados)
    return dados


def congelar_imagens(snapshot):
    """Copia a estrutura e substitui referências MEDIA por imagens incorporadas.

    Nem hosts externos nem caminhos fora do armazenamento de mídia são lidos.
    Limites são operacionais/configuráveis; nunca representam limites normativos.
    """
    media = "/" + urlsplit(settings.MEDIA_URL).path.strip("/") + "/"
    cache, hashes, total = {}, set(), 0
    nos = 0

    def incorporar(texto):
        nonlocal total
        if texto in cache:
            return cache[texto]
        if texto.startswith("data:"):
            dados = _dados_uri(texto)
        else:
            partes = urlsplit(texto)
            caminho = unquote(partes.path)
            if not caminho.startswith(media):
                raise ErroGeracaoPDF("Imagem externa ou fora do armazenamento de mídia. Importe a evidência antes de emitir.")
            nome = caminho[len(media):]
            if not nome or "\\" in nome or any(p in (".", "..") for p in nome.split("/")):
                raise ErroGeracaoPDF("Caminho da evidência não permitido.")
            # A API de storage mantém a compatibilidade com armazenamento remoto,
            # sem aceitar uma URL arbitrária como origem de requisição.
            try:
                limite = _limite("LAUDOS_MAX_IMAGEM_BYTES", 10 * 1024 * 1024)
                if default_storage.size(nome) > limite:
                    raise ErroGeracaoPDF("Imagem excede o limite de tamanho configurado para emissão.")
                with default_storage.open(nome, "rb") as arquivo:
                    dados = arquivo.read(limite + 1)
            except ErroGeracaoPDF:
                raise
            except Exception as exc:
                raise ErroGeracaoPDF("Evidência referenciada não está disponível. Corrija o arquivo antes de emitir.") from exc
        mime = _validar_imagem(dados)
        digest = hashlib.sha256(dados).hexdigest()
        if digest not in hashes:
            total += len(dados)
            hashes.add(digest)
        if total > _limite("LAUDOS_MAX_IMAGENS_BYTES", 40 * 1024 * 1024):
            raise ErroGeracaoPDF("Conjunto de imagens excede o limite configurado para emissão.")
        uri = f"data:{mime};base64,{base64.b64encode(dados).decode('ascii')}"
        cache[texto] = uri
        return uri

    def visitar(valor, chave="", profundidade=0):
        nonlocal nos
        nos += 1
        if profundidade > 40 or nos > _limite("LAUDOS_MAX_SNAPSHOT_NOS", 150000):
            raise ErroGeracaoPDF("Documento excede o limite de complexidade configurado.")
        if isinstance(valor, dict):
            return {k: visitar(v, k, profundidade + 1) for k, v in valor.items()}
        if isinstance(valor, (list, tuple)):
            return [visitar(v, chave, profundidade + 1) for v in valor]
        if isinstance(valor, str):
            if valor.startswith("data:image/"):
                return incorporar(valor)
            caminho = urlsplit(valor).path if valor.startswith(("/", "http://", "https://")) else ""
            if caminho.startswith(media) or (chave in _CHAVES_IMAGEM and valor.startswith(("/", "http://", "https://"))):
                return incorporar(valor)
        return valor

    return visitar(snapshot)



def gerar_pdf(snapshot):
    """Chromium imprime as mesmas rotas/CSS usados atualmente pelo t?cnico.

    Nenhum fallback troca o design. A indisponibilidade do renderer mant?m o
    rascunho e n?o produz documento incompleto. Node/Chromium s?o depend?ncias
    locais de implanta??o, sem servi?o pago ou envio de dados a terceiros.
    """
    helper = Path(__file__).with_name("render-layout.cjs")
    if not helper.is_file():
        raise ErroGeracaoPDF("Renderizador do layout original n?o est? instalado.")
    origem = getattr(settings, "LAUDOS_FRONTEND_URL", "http://127.0.0.1:3000")
    url = urlsplit(origem)
    if url.scheme not in {"http", "https"} or url.hostname not in {"127.0.0.1", "localhost", "::1", "frontend"} or url.username or url.password or url.query or url.fragment or url.path not in {"", "/"}:
        raise ErroGeracaoPDF("Configure LAUDOS_FRONTEND_URL com a origem local do frontend de impress?o.")
    try:
        entrada = json.dumps({"snapshot": snapshot, "frontend": origem.rstrip("/"),
            "timeout": _limite("LAUDOS_RENDER_TIMEOUT_SEGUNDOS", 90) * 1000,
            "maxPaginas": _limite("LAUDOS_MAX_PAGINAS", 1000)}, ensure_ascii=False, allow_nan=False).encode("utf-8")
        resultado = subprocess.run([getattr(settings, "LAUDOS_NODE_BIN", "node"), str(helper)],
            input=entrada, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=settings.BASE_DIR,
            timeout=_limite("LAUDOS_RENDER_TIMEOUT_SEGUNDOS", 90) + 10, check=False)
    except (OSError, subprocess.TimeoutExpired, ValueError, TypeError) as exc:
        raise ErroGeracaoPDF("N?o foi poss?vel gerar o PDF com o layout original. Verifique o renderizador local.") from exc
    if resultado.returncode or not resultado.stdout.startswith(b"%PDF-"):
        raise ErroGeracaoPDF("Falha ao imprimir o layout original. Verifique frontend, Chromium, imagens e pagina??o; o rascunho foi preservado.")
    if len(resultado.stdout) > _limite("LAUDOS_MAX_PDF_BYTES", 50 * 1024 * 1024):
        raise ErroGeracaoPDF("PDF excede o limite de tamanho configurado para emiss?o.")
    return resultado.stdout
