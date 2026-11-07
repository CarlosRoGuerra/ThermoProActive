"""
Mídia (uploads) servida SOMENTE a quem tem direito — achado A-03.

Antes o nginx entregava `/media/` direto do volume, sem autenticação e com o
nome original do arquivo na URL: fotos de achados, placas de identificação e a
assinatura digital do responsável técnico eram baixáveis por qualquer pessoa
que adivinhasse (ou enumerasse) o nome. Agora:

* a URL pública é `/api/media/<arquivo>` (MEDIA_URL) — dentro de `/api/`, que é
  o escopo do cookie `tpa_access`, então `<img src>` na mesma origem continua
  funcionando sem token na URL;
* cada arquivo é resolvido para o REGISTRO DONO (modelo + campo); arquivo sem
  dono no banco, ou com prefixo desconhecido, é 404 (nega por padrão);
* perfil cliente só recebe o arquivo se o dono pertencer ao seu cliente
  (mesma regra de `escopo_cliente`, falhando FECHADO sem `cliente_id`);
* a entrega do binário é do nginx via `X-Accel-Redirect` (location `internal`);
  sem proxy (dev/DEBUG) o próprio Django responde com `FileResponse`.

Para adicionar um novo `upload_to`, registre-o em `REGRAS` — esquecer = 404.
"""
import mimetypes
import posixpath
from urllib.parse import quote

from django.apps import apps
from django.conf import settings
from django.core.files.storage import default_storage
from django.http import FileResponse, Http404, HttpResponse
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

#: (prefixo do upload_to, "app.Modelo", campo do arquivo, caminho ORM até o Cliente).
#: caminho None = arquivo global (catálogo/identidade visual do prestador), liberado a
#: qualquer usuário autenticado. Prefixos não registrados aqui NÃO são servidos.
REGRAS = (
    ("achados/", "coletas.AchadoImagem", "arquivo", "achado__item__carregamento__cliente"),
    ("ensaios/inspecao_visual/", "ensaios.InspecaoVisualColeta", "foto", "coleta__item__carregamento__cliente"),
    ("equipamentos/placas/motor/", "cadastros.DadosTecnicosMotor", "foto_placa", "equipamento__setor__area__cliente"),
    ("equipamentos/placas/transformador/", "cadastros.DadosTecnicosTransformador", "foto_placa",
     "equipamento__setor__area__cliente"),
    ("logos/clientes/", "cadastros.Cliente", "logomarca", "id"),
    # Logomarca do PRESTADOR (papel timbrado dos relatórios que o cliente recebe).
    # Não é usada nas telas de login, então não precisa ser pública.
    ("logos/empresas/", "cadastros.Empresa", "logomarca", None),
    ("tecnologias/", "cadastros.TecnologiaAnalise", ("imagem", "imagem_pontos_medicao"), None),
    # Assinatura do analista: interno vê todas; cliente só a de quem assinou trabalho dele
    # (tratado à parte em `_assinatura_visivel`).
    ("assinaturas/", "accounts.User", "assinatura_digital", "__assinatura__"),
    # Anexos de documento (Anexo I 2.3.1.3): PDF/XLSX/DOCX/CSV. Sempre download
    # (`attachment`); cliente só vê os marcados como `visivel_cliente` (FILTRO_EXTRA_CLIENTE).
    ("anexos/documentos/", "coletas.AnexoDocumento", "arquivo", "cliente"),
    # Fotos de execução e assinatura do cliente na OSP (Anexo I 2.6.2.4 e 2.6.2.6).
    ("osp/evidencias/", "osp.EvidenciaOSP", "arquivo", "osp__cliente"),
    ("osp/assinaturas/", "osp.AssinaturaOSP", "imagem", "osp__cliente"),
)

#: Filtro adicional aplicado ao perfil cliente, por prefixo (além do escopo do cliente).
#: Mesma regra de liberação de `apps.core.escopo.liberado_ao_cliente`: foto de achado só
#: sai para o cliente depois da confirmação/liberação (`visivel_cliente`).
FILTRO_EXTRA_CLIENTE = {
    "achados/": {"achado__visivel_cliente": True},
    "anexos/documentos/": {"visivel_cliente": True},
}

#: Caminho do ORM até o Setor, por prefixo, para a restrição de setor (2.1.1.6).
SETOR_CLIENTE = {
    "achados/": "achado__item__equipamento__setor",
    "ensaios/inspecao_visual/": "coleta__item__equipamento__setor",
    "equipamentos/placas/motor/": "equipamento__setor",
    "equipamentos/placas/transformador/": "equipamento__setor",
    "anexos/documentos/": "equipamento__setor",
    "osp/evidencias/": "osp__equipamento__setor",
    "osp/assinaturas/": "osp__equipamento__setor",
}

#: Só imagens (o upload é ImageField). Qualquer outra extensão não é servida.
TIPOS_SERVIDOS = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif",
    ".webp": "image/webp", ".bmp": "image/bmp", ".tif": "image/tiff", ".tiff": "image/tiff",
}

#: Documentos (Anexo I 2.3.1.3). Nunca são servidos inline: sempre `attachment`.
TIPOS_DOCUMENTO = {
    ".pdf": "application/pdf",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".csv": "text/csv",
}
PREFIXOS_DOCUMENTO = ("anexos/documentos/",)


def nome_seguro(nome: str) -> str | None:
    """Normaliza o caminho relativo; None se tentar sair da pasta de mídia."""
    if not nome or "\x00" in nome or "\\" in nome:
        return None
    limpo = posixpath.normpath(nome)
    if limpo != nome or limpo.startswith(("/", "../")) or limpo == "..":
        return None
    return limpo


def _assinatura_visivel(usuario, nome: str) -> bool:
    from apps.accounts.models import User
    from apps.coletas.models import Carregamento

    donos = User.objects.filter(assinatura_digital=nome)
    if usuario.is_interno:
        return donos.exists()
    if not usuario.cliente_id:
        return False
    # A assinatura aparece no relatório do cliente como "analista" dos carregamentos dele.
    return Carregamento.objects.filter(cliente_id=usuario.cliente_id, analista__in=donos).exists()


def pode_ver(usuario, nome: str) -> bool:
    """O usuário pode baixar `nome`? (já normalizado)"""
    for prefixo, rotulo, campos, caminho_cliente in REGRAS:
        if not nome.startswith(prefixo):
            continue
        campos = (campos,) if isinstance(campos, str) else campos
        if caminho_cliente == "__assinatura__":
            return _assinatura_visivel(usuario, nome)
        modelo = apps.get_model(rotulo)
        for campo in campos:
            qs = modelo._default_manager.filter(**{campo: nome})
            if caminho_cliente is not None and getattr(usuario, "is_cliente", False):
                if not usuario.cliente_id:
                    continue  # falha fechada
                qs = qs.filter(**{caminho_cliente: usuario.cliente_id})
                qs = qs.filter(**FILTRO_EXTRA_CLIENTE.get(prefixo, {}))
                # 2.1.1.6: cliente com restrição de setor só baixa foto de equipamento desses setores.
                # Prefixo sem equipamento (documentos, OSP) fica FECHADO para quem tem restrição.
                from apps.core.escopo import setores_restritos
                restricao = setores_restritos(usuario)
                if restricao is not None:
                    caminho_setor = SETOR_CLIENTE.get(prefixo)
                    if caminho_setor is None:
                        return False
                    qs = qs.filter(**{f"{caminho_setor}__in": restricao})
            if qs.exists():
                return True
        return False
    return False


def _nome_download(nome: str) -> str:
    """Nome que o usuário vê ao baixar: o rótulo sanitizado do anexo (o arquivo no disco é UUID)."""
    modelo = apps.get_model("coletas.AnexoDocumento")
    rotulo = modelo._default_manager.filter(arquivo=nome).values_list("nome_original", flat=True).first()
    return rotulo or posixpath.basename(nome)


def _disposicao_anexo(nome: str) -> str:
    """`attachment` com fallback ASCII e nome UTF-8 (RFC 6266). Nunca `inline`."""
    fallback = nome.encode("ascii", "replace").decode().replace('"', "_").replace("?", "_")
    return f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{quote(nome, safe='')}"


class MidiaView(APIView):
    """GET /api/media/<arquivo> — autenticado, com escopo por dono do arquivo."""

    permission_classes = [IsAuthenticated]
    # Download direto de <img>/<a>: não negocia formato nem pagina.
    pagination_class = None

    def get(self, request, nome):
        nome = nome_seguro(nome)
        extensao = posixpath.splitext(nome or "")[1].lower()
        documento = bool(nome) and nome.startswith(PREFIXOS_DOCUMENTO)
        if not nome:
            raise Http404
        if documento and extensao not in TIPOS_DOCUMENTO:
            raise Http404
        if not documento and extensao not in TIPOS_SERVIDOS:
            raise Http404
        if not pode_ver(request.user, nome):
            raise Http404  # fora do escopo = "não existe" (não confirma que o arquivo existe)
        if documento:
            tipo = TIPOS_DOCUMENTO[extensao]
        else:
            tipo = TIPOS_SERVIDOS.get(extensao) or mimetypes.guess_type(nome)[0] or "application/octet-stream"
        prefixo_interno = getattr(settings, "MEDIA_ACCEL_PREFIX", "")
        if prefixo_interno:
            resposta = HttpResponse(content_type=tipo)
            # Percent-encoding (UTF-8): cabeçalho HTTP sai em latin-1, e o nginx não acharia
            # "inspeção_01.jpg" — o nome com acento é válido no upload (revisão R-01).
            resposta["X-Accel-Redirect"] = quote(f"{prefixo_interno.rstrip('/')}/{nome}")
        else:
            if not default_storage.exists(nome):
                raise Http404
            resposta = FileResponse(default_storage.open(nome, "rb"), content_type=tipo)
        if documento:
            resposta["Content-Disposition"] = _disposicao_anexo(_nome_download(nome))
        resposta["Cache-Control"] = "private, max-age=300"
        resposta["X-Content-Type-Options"] = "nosniff"
        # Mesmo sendo imagem, nada do arquivo executa nem carrega subrecurso.
        resposta["Content-Security-Policy"] = "default-src 'none'; sandbox"
        return resposta
