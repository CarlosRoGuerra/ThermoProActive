"""
Item 3.1.22 — trilha de auditoria genérica (criar/alterar/excluir) dos dados de negócio.

Como funciona
-------------
* `ContextoAuditoriaMiddleware` guarda a requisição da thread. O usuário JWT só é
  definido pelo DRF depois do middleware; por isso o sinal lê `request.user` na hora
  da gravação (o DRF também o copia para o request do Django).
* Sinais `pre_save`/`post_save`/`post_delete` gravam em `RegistroAuditoria` só o que
  mudou. Alteração sem diferença real não gera registro.
* Não rastreia: `bulk_create`/`bulk_update`/`QuerySet.update` (não disparam sinais).

O que NÃO é gravado (V-03)
--------------------------
* Campo BINÁRIO ou de ARQUIVO (BinaryField, FileField, ImageField): conteúdo nunca vai à
  trilha. Ex.: o PKCS#12 cifrado do certificado A1.
* Campo com nome de segredo ou certificado (senha, token, hash, chave, cifrado, pfx, pem,
  certificado, CPF, RG, CTPS, nascimento, endereço): omitido.
* Campo de identificação pessoal (titular, emissor, telefone, celular, nome de usuário):
  mascarado como "***".
* E-mail (qualquer campo de e-mail, inclusive o do usuário que fez a ação): mascarado
  (`p***@v***.test`). A identificação de quem agiu continua pelo id do usuário.
* Modelos de segurança/autenticação (sessões, MFA, eventos de segurança, o próprio registro).

Os registros JÁ gravados antes desta correção são sanados por `sanear_registros()`, usado
pela migração `core/0002` e pelo comando `sanear_auditoria` (única correção permitida ao
append-only, feita em modo de manutenção).
"""
import json
import re
import threading

from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.db.models.signals import post_delete, post_save, pre_save

_contexto = threading.local()

# Apps de negócio rastreados. accounts entra só pelos modelos não sensíveis.
APPS_RASTREADOS = {"cadastros", "coletas", "ensaios", "servicos", "osp", "laudos", "relatorios",
                   "notificacoes", "preditiva", "accounts"}
MODELOS_EXCLUIDOS = {
    "accounts.SessaoAutenticacao", "accounts.EventoSeguranca", "accounts.DispositivoMFA",
    "accounts.CodigoRecuperacaoMFA", "accounts.DadosPessoaisUsuario", "accounts.SolicitacaoAcesso",
    "accounts.Convite", "core.RegistroAuditoria",
}

# Lista negativa GLOBAL (por nome): substring para termos longos, token exato para siglas
# (evita pegar "organização" por causa de "rg").
EXCLUIR_POR_SUBSTRING = ("senha", "password", "segredo", "secret", "token", "chave", "cifrad",
                         "certificado", "nascimento", "logradouro", "endereco")
EXCLUIR_POR_TOKEN = ("rg", "cpf", "ctps", "pfx", "pem", "hash")
#: Campos de segredo: na trilha aparecem como "***" (mostra que mudaram, sem o valor).
SEGREDO_MARCADO = ("senha", "password", "segredo", "secret", "token", "chave", "hash")
MASCARAR_POR_NOME = ("titular", "emissor", "telefone", "celular")

# Lista negativa POR MODELO (nome do campo -> excluído ou mascarado).
MODELO_EXCLUIR = {
    "accounts.CertificadoA1": ("titular", "emissor", "numero_serie", "sha256_certificado", "valido_ate"),
}
MODELO_MASCARAR = {
    "accounts.User": ("nome",),
}

_TOKEN = re.compile(r"[a-z0-9]+")
_MASCARA = "***"

class ContextoAuditoriaMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _contexto.request = request
        try:
            return self.get_response(request)
        finally:
            _contexto.request = None


# --- Tratamento de valores ------------------------------------------------------------

def mascarar_email(valor):
    """`pessoa.real@v03.test` -> `p***@v***.test`. Sem @ vira `***`."""
    if not isinstance(valor, str) or not valor:
        return valor
    if "@" not in valor:
        return _MASCARA
    local, dominio = valor.rsplit("@", 1)
    rotulos = dominio.split(".")
    tld = rotulos[-1] if len(rotulos) > 1 else ""
    return f"{local[:1]}{_MASCARA}@{dominio[:1]}{_MASCARA}" + (f".{tld}" if tld else "")


def _nome_excluido(nome):
    nome = nome.lower()
    if any(p in nome for p in EXCLUIR_POR_SUBSTRING):
        return True
    return any(t in EXCLUIR_POR_TOKEN for t in _TOKEN.findall(nome))


def _parece_email(nome):
    return "email" in nome.lower() or nome.lower().endswith("_mail")


def _json_seguro(valor):
    try:
        return json.loads(json.dumps(valor, cls=DjangoJSONEncoder))
    except (TypeError, ValueError):
        return str(valor)


def tratar_valor(modelo, nome, valor, *, binario=False):
    """
    Devolve (incluir, valor_tratado) para um campo. `modelo` é o rótulo 'app.Modelo'.
    Regras (V-03): binário/arquivo sai; segredo/certificado/dado pessoal sensível sai;
    identificação pessoal e e-mail saem mascarados; o resto segue como JSON.
    """
    if binario:
        return False, None
    if nome in MODELO_EXCLUIR.get(modelo, ()) or _nome_excluido(nome):
        # Segredo mostra só que MUDOU ("***"); certificado e dado pessoal saem por completo.
        if valor is not None and any(p in nome for p in SEGREDO_MARCADO):
            return True, _MASCARA
        return False, None
    if nome in MASCARAR_POR_NOME or nome in MODELO_MASCARAR.get(modelo, ()):
        return True, None if valor is None else _MASCARA
    if _parece_email(nome):
        return True, None if valor is None else mascarar_email(_json_seguro(valor))
    return True, _json_seguro(valor)


def _campo_binario(campo):
    return isinstance(campo, (models.BinaryField, models.FileField))


def _snapshot(instance):
    # Arquivo/imagem: após o save vira FieldFile; compara-se o nome gravado (como no banco).
    return {c.attname: _bruto(getattr(instance, c.attname)) for c in instance._meta.concrete_fields}


def _bruto(valor):
    from django.db.models.fields.files import FieldFile
    return valor.name if isinstance(valor, FieldFile) else valor


# --- Captura ----------------------------------------------------------------------------

def _rastreado(sender):
    if sender._meta.app_label not in APPS_RASTREADOS:
        return False
    return f"{sender._meta.app_label}.{sender.__name__}" not in MODELOS_EXCLUIDOS


def _quem_e_onde():
    from apps.accounts.security import ip_do_cliente
    req = getattr(_contexto, "request", None)
    if req is None:
        return {"usuario": None, "usuario_email": "", "ip": "", "metodo": "", "caminho": ""}
    user = getattr(req, "user", None)
    autenticado = bool(user and user.is_authenticated)
    return {
        "usuario": user if autenticado else None,
        "usuario_email": mascarar_email(user.email)[:254] if autenticado else "",
        "ip": ip_do_cliente(req)[:45],
        "metodo": req.method[:10],
        "caminho": req.path[:255],
    }


_tabela_ok = False


def _tabela_existe():
    """
    Durante `migrate` (e na criação do banco de teste) outras apps podem salvar antes de
    a tabela de auditoria existir. Nesse caso não há o que gravar: pula. Checa uma vez.
    """
    global _tabela_ok
    if not _tabela_ok:
        from django.db import connection
        from apps.core.models import RegistroAuditoria
        _tabela_ok = RegistroAuditoria._meta.db_table in connection.introspection.table_names()
    return _tabela_ok


def _gravar(sender, instance, acao, alteracoes):
    from apps.core.models import RegistroAuditoria
    if not _tabela_existe():
        return
    if not alteracoes and acao == RegistroAuditoria.Acao.ALTERAR:
        return
    RegistroAuditoria.objects.create(
        acao=acao, modelo=f"{sender._meta.app_label}.{sender.__name__}",
        objeto_id=str(instance.pk), alteracoes=alteracoes, **_quem_e_onde(),
    )


def _pre_save(sender, instance, raw=False, **kwargs):
    if raw or instance._state.adding or not _rastreado(sender):
        return
    anterior = sender._base_manager.filter(pk=instance.pk).first()
    instance._auditoria_antes = _snapshot(anterior) if anterior else None


def _post_save(sender, instance, created, raw=False, **kwargs):
    if raw or not _rastreado(sender):
        return
    from apps.core.models import RegistroAuditoria
    modelo = f"{sender._meta.app_label}.{sender.__name__}"
    atual = _snapshot(instance)
    if created:
        alteracoes = {}
        for c in instance._meta.concrete_fields:
            if atual[c.attname] is None:
                continue
            incluir, valor = tratar_valor(modelo, c.name, atual[c.attname], binario=_campo_binario(c))
            if incluir:
                alteracoes[c.name] = [None, valor]
        _gravar(sender, instance, RegistroAuditoria.Acao.CRIAR, alteracoes)
        return
    antes = getattr(instance, "_auditoria_antes", None)
    if antes is None:
        return
    alteracoes = {}
    for c in instance._meta.concrete_fields:
        if getattr(c, "auto_now", False):  # carimbo automático (atualizado_em) não é alteração
            continue
        # None e "" (campo de arquivo/texto vazio) não são alteração.
        if ("" if antes.get(c.attname) is None else antes.get(c.attname)) == (
            "" if atual[c.attname] is None else atual[c.attname]
        ):
            continue
        binario = _campo_binario(c)
        incluir_a, valor_a = tratar_valor(modelo, c.name, antes.get(c.attname), binario=binario)
        incluir_d, valor_d = tratar_valor(modelo, c.name, atual[c.attname], binario=binario)
        if incluir_a or incluir_d:
            alteracoes[c.name] = [valor_a, valor_d]
    _gravar(sender, instance, RegistroAuditoria.Acao.ALTERAR, alteracoes)


def _post_delete(sender, instance, **kwargs):
    if not _rastreado(sender):
        return
    from apps.core.models import RegistroAuditoria
    _gravar(sender, instance, RegistroAuditoria.Acao.EXCLUIR, {})


def conectar():
    pre_save.connect(_pre_save, dispatch_uid="auditoria_pre_save")
    post_save.connect(_post_save, dispatch_uid="auditoria_post_save")
    post_delete.connect(_post_delete, dispatch_uid="auditoria_post_delete")


# --- Saneamento de registros já gravados (V-03) ----------------------------------------

def _sanear_alteracoes(modelo, alteracoes):
    """Aplica as mesmas regras a um JSON já gravado. Devolve o novo dict."""
    from django.apps import apps as django_apps
    try:
        classe = django_apps.get_model(modelo)
    except (LookupError, ValueError):
        classe = None
    novo = {}
    for nome, par in (alteracoes or {}).items():
        campo = None
        if classe is not None:
            try:
                campo = classe._meta.get_field(nome)
            except Exception:
                campo = None
        binario = campo is not None and _campo_binario(campo)
        if isinstance(par, list) and len(par) == 2:
            incluir_a, a = tratar_valor(modelo, nome, par[0], binario=binario)
            incluir_d, d = tratar_valor(modelo, nome, par[1], binario=binario)
            if incluir_a or incluir_d:
                novo[nome] = [a, d]
        else:
            incluir, v = tratar_valor(modelo, nome, par, binario=binario)
            if incluir:
                novo[nome] = v
    return novo


def sanear_registros(modelo_registro):
    """
    Corrige, em modo de saneamento, os registros gravados antes do V-03. Idempotente.
    Recebe a classe do registro (a real ou a histórica das migrações). Devolve a contagem.
    """
    alterados = 0
    for reg in modelo_registro.objects.all().only("id", "modelo", "alteracoes", "usuario_email").iterator():
        novo_alter = _sanear_alteracoes(reg.modelo, reg.alteracoes)
        novo_email = mascarar_email(reg.usuario_email) if reg.usuario_email else reg.usuario_email
        if novo_alter == reg.alteracoes and novo_email == reg.usuario_email:
            continue
        qs = modelo_registro.objects.filter(pk=reg.pk)
        if hasattr(qs, "sanear_campos"):
            qs.sanear_campos(alteracoes=novo_alter, usuario_email=novo_email)
        else:  # modelo histórico (migração): sem o queryset customizado
            from django.db.models import QuerySet
            from apps.core.models import MODO_SANEAMENTO, modo_manutencao
            with modo_manutencao(MODO_SANEAMENTO):
                QuerySet.update(qs, alteracoes=novo_alter, usuario_email=novo_email)
        alterados += 1
    return alterados
