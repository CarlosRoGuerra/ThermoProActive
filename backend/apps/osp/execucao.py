"""
Itens 2.6.2.2 a 2.6.2.8 da OSP: checklist, evidências, peças, tempo de execução e
assinatura do cliente.

Tudo que muda o estado da OSP passa pelo `services.transicionar` (que chama daqui
para checar o checklist antes de finalizar e para abrir/fechar o tempo de execução),
ou por funções deste módulo que gravam no `HistoricoOSP`. Nada aqui altera o
diagnóstico técnico: o cliente só assina e devolve informação (ver `views`).
"""
import hashlib
import io
import json
from decimal import Decimal

from django.conf import settings
from django.core.files.base import ContentFile
from django.db.models import Q
from django.utils import timezone
from PIL import Image, UnidentifiedImageError

from .models import (
    ApontamentoExecucao,
    AssinaturaOSP,
    HistoricoOSP,
    ItemModeloChecklist,
    ModeloChecklist,
    OrdemServico,
    OrigemApontamento,
    PecaOSP,
    RespostaChecklist,
    StatusOSP,
    TipoHistorico,
)

#: Estados em que a OSP ainda aceita checklist, peças, fotos e apontamentos.
ESTADOS_ENCERRADOS = frozenset({StatusOSP.FINALIZADA, StatusOSP.CANCELADA})

#: Estados em que o cliente pode assinar o estado da execução.
ESTADOS_ASSINAVEIS = frozenset({StatusOSP.EXECUTADA, StatusOSP.AGUARDANDO_APROVACAO, StatusOSP.FINALIZADA})

#: Fotos: formatos aceitos (verificados pelo conteúdo, não pela extensão).
FORMATOS_FOTO = {"JPEG", "PNG", "WEBP"}
FORMATOS_ASSINATURA = {"PNG"}
LIMITE_ASSINATURA_BYTES = 512 * 1024


class ErroExecucao(Exception):
    """Violação de regra destes itens; a view traduz para `codigo`/`http`."""

    def __init__(self, mensagem, *, codigo="osp_invalida", http=400):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.codigo = codigo
        self.http = http


# --- 2.6.2.2 Checklist ----------------------------------------------------------

def _tecnologia_da_osp(osp):
    if osp.achado_id:
        return osp.achado.item.carregamento.tecnologia_id
    return None


def modelos_aplicaveis(osp):
    """Modelos ativos que valem para esta OSP (por tipo de equipamento e tecnologia)."""
    tipo = osp.equipamento.tipo_equipamento_id
    tecnologia = _tecnologia_da_osp(osp)
    return (
        ModeloChecklist.objects.filter(ativo=True)
        .filter(Q(tipo_equipamento__isnull=True) | Q(tipo_equipamento_id=tipo))
        .filter(Q(tecnologia__isnull=True) | Q(tecnologia_id=tecnologia))
        .prefetch_related("itens")
        .order_by("nome", "id")
    )


def pendencias_checklist(osp) -> list[str]:
    """Itens OBRIGATÓRIOS (de modelos que exigem) ainda sem resposta. Vazio = pode finalizar."""
    respondidos = set(osp.respostas_checklist.values_list("item_id", flat=True))
    pendentes = []
    for modelo in modelos_aplicaveis(osp):
        if not modelo.obrigatorio_para_finalizar:
            continue
        for item in modelo.itens.all():
            if item.obrigatorio and item.pk not in respondidos:
                pendentes.append(f"{modelo.nome}: {item.descricao}")
    return pendentes


def checklist_da_osp(osp) -> list[dict]:
    """Modelos aplicáveis com itens e a resposta já dada a cada um (alimenta a tela)."""
    respostas = {r.item_id: r for r in osp.respostas_checklist.all()}
    saida = []
    for modelo in modelos_aplicaveis(osp):
        itens = []
        for item in modelo.itens.all():
            resposta = respostas.get(item.pk)
            itens.append({
                "id": item.pk, "ordem": item.ordem, "descricao": item.descricao,
                "obrigatorio": item.obrigatorio,
                "situacao": resposta.situacao if resposta else None,
                "observacao": resposta.observacao if resposta else "",
            })
        saida.append({
            "modelo": modelo.pk, "nome": modelo.nome,
            "obrigatorio_para_finalizar": modelo.obrigatorio_para_finalizar, "itens": itens,
        })
    return saida


def responder_checklist(osp, respostas: list[dict], ator) -> int:
    """
    Grava as respostas (upsert por item) e registra no histórico. Só vale para itens
    de modelos aplicáveis à OSP. Retorna quantas respostas foram gravadas.
    """
    if osp.status in ESTADOS_ENCERRADOS:
        raise ErroExecucao("OSP encerrada: reabra-a para alterar o checklist.", codigo="osp_encerrada", http=409)
    permitidos = {
        item.pk: item
        for modelo in modelos_aplicaveis(osp)
        for item in modelo.itens.all()
    }
    gravadas = []
    for dado in respostas:
        item_id = dado.get("item")
        if item_id not in permitidos:
            raise ErroExecucao("Item de checklist não se aplica a esta OSP.", codigo="item_nao_aplicavel")
        situacao = dado.get("situacao")
        if situacao not in {"CONFORME", "NAO_CONFORME", "NAO_SE_APLICA"}:
            raise ErroExecucao("Situação inválida.", codigo="situacao_invalida")
        observacao = (dado.get("observacao") or "").strip()[:2000]
        resposta, _ = RespostaChecklist.objects.update_or_create(
            osp=osp, item=permitidos[item_id],
            defaults={"situacao": situacao, "observacao": observacao,
                      "respondido_por": ator if getattr(ator, "pk", None) else None},
        )
        gravadas.append({"item": item_id, "situacao": situacao})
    if gravadas:
        HistoricoOSP.objects.create(
            osp=osp, tipo=TipoHistorico.EDICAO, status_anterior=osp.status, status_novo=osp.status,
            alteracoes={"checklist": gravadas}, ator=ator if getattr(ator, "pk", None) else None,
            ator_nome=getattr(ator, "nome", "") or "Sistema",
            ator_perfil=getattr(ator, "perfil", "") or "",
        )
    return len(gravadas)


# --- 2.6.2.7 Peças --------------------------------------------------------------

def atualizar_custo_material(osp) -> None:
    """
    Soma as peças e grava em `custo_material_real`. O custo real passa a ser o que
    a execução gastou: estimativa de mão de obra/serviço/produção/outros
    (`total_preditiva` sem o material estimado) + material aplicado. O ROI continua
    lendo `total_preditiva`/`total_emergencial`, então não muda.
    """
    if not osp.pecas.exists():
        OrdemServico.objects.filter(pk=osp.pk).update(custo_material_real=None)
        osp.custo_material_real = None
        return
    material = sum((p.custo_total for p in osp.pecas.all()), Decimal("0"))
    sem_material_estimado = osp.total_preditiva - (osp.pred_material_valor or Decimal("0"))
    custo_real = sem_material_estimado + material
    OrdemServico.objects.filter(pk=osp.pk).update(custo_material_real=material, custo_real=custo_real)
    osp.custo_material_real = material
    osp.custo_real = custo_real


def registrar_peca(osp, dados: dict, ator) -> PecaOSP:
    if osp.status in ESTADOS_ENCERRADOS:
        raise ErroExecucao("OSP encerrada: reabra-a para lançar peças.", codigo="osp_encerrada", http=409)
    peca = PecaOSP.objects.create(osp=osp, **dados)
    atualizar_custo_material(osp)
    _historico_peca(osp, ator, "adicionada", peca)
    return peca


def remover_peca(peca, ator) -> None:
    osp = peca.osp
    if osp.status in ESTADOS_ENCERRADOS:
        raise ErroExecucao("OSP encerrada: reabra-a para alterar peças.", codigo="osp_encerrada", http=409)
    registro = {"descricao": peca.descricao, "quantidade": str(peca.quantidade)}
    peca.delete()
    atualizar_custo_material(osp)
    _historico_peca(osp, ator, "removida", None, registro)


def _historico_peca(osp, ator, acao, peca, registro=None):
    dados = registro or {"descricao": peca.descricao, "quantidade": str(peca.quantidade),
                         "custo_total": str(peca.custo_total)}
    HistoricoOSP.objects.create(
        osp=osp, tipo=TipoHistorico.EDICAO, status_anterior=osp.status, status_novo=osp.status,
        alteracoes={"peca": acao, **dados}, ator=ator if getattr(ator, "pk", None) else None,
        ator_nome=getattr(ator, "nome", "") or "Sistema", ator_perfil=getattr(ator, "perfil", "") or "",
    )


# --- 2.6.2.8 Tempo de execução ----------------------------------------------------

def tempo_execucao_minutos(osp) -> int:
    """Soma dos intervalos fechados (transição ou apontamento manual)."""
    return sum(
        (a.duracao_minutos or 0) for a in osp.apontamentos.all() if a.fim is not None
    )


def registrar_transicao_execucao(osp, de, para, ator, agora) -> None:
    """
    Chamado por `services.transicionar` depois de gravar o status. Entrar em
    EM_EXECUCAO abre um intervalo; sair dele (ou cancelar) fecha o aberto.
    Rejeição (AGUARDANDO_APROVACAO → EM_EXECUCAO) abre outro intervalo: o tempo
    de retrabalho conta.
    """
    if para == StatusOSP.EM_EXECUCAO:
        ApontamentoExecucao.objects.create(
            osp=osp, inicio=agora, origem=OrigemApontamento.TRANSICAO,
            ator=ator if getattr(ator, "pk", None) else None,
        )
    elif de == StatusOSP.EM_EXECUCAO:
        ApontamentoExecucao.objects.filter(osp=osp, fim__isnull=True).update(fim=agora)


def apontar_tempo(osp, inicio, fim, observacao, ator) -> ApontamentoExecucao:
    if osp.status in ESTADOS_ENCERRADOS:
        raise ErroExecucao("OSP encerrada: reabra-a para apontar horas.", codigo="osp_encerrada", http=409)
    if fim <= inicio:
        raise ErroExecucao("O fim deve ser posterior ao início.", codigo="intervalo_invalido")
    if fim > timezone.now():
        raise ErroExecucao("O apontamento não pode terminar no futuro.", codigo="intervalo_futuro")
    apontamento = ApontamentoExecucao.objects.create(
        osp=osp, inicio=inicio, fim=fim, origem=OrigemApontamento.MANUAL,
        ator=ator if getattr(ator, "pk", None) else None, observacao=(observacao or "")[:200],
    )
    HistoricoOSP.objects.create(
        osp=osp, tipo=TipoHistorico.EDICAO, status_anterior=osp.status, status_novo=osp.status,
        alteracoes={"apontamento": {"inicio": inicio.isoformat(), "fim": fim.isoformat()}},
        ator=ator if getattr(ator, "pk", None) else None,
        ator_nome=getattr(ator, "nome", "") or "Sistema", ator_perfil=getattr(ator, "perfil", "") or "",
    )
    return apontamento


# --- 2.6.2.4 Evidências -----------------------------------------------------------

def validar_foto(arquivo, formatos=FORMATOS_FOTO, limite=None) -> None:
    """Confere pelo conteúdo que é imagem de formato aceito e que cabe no limite. Levanta ValueError."""
    limite = limite or int(getattr(settings, "LAUDOS_MAX_IMAGEM_BYTES", 10 * 1024 * 1024))
    if arquivo.size > limite:
        raise ValueError(f"A imagem excede {limite // (1024 * 1024)} MB.")
    arquivo.seek(0)
    try:
        with Image.open(arquivo) as img:
            img.verify()
            formato = (img.format or "").upper()
    except (UnidentifiedImageError, OSError, SyntaxError):
        raise ValueError("O arquivo não é uma imagem válida.")
    finally:
        arquivo.seek(0)
    if formato not in formatos:
        raise ValueError(f"Formato não aceito ({formato or 'desconhecido'}).")


# --- 2.6.2.6 Assinatura do cliente ------------------------------------------------

def estado_da_osp(osp) -> dict:
    """Retrato canônico do estado da OSP usado no hash da assinatura."""
    return {
        "numero": osp.numero,
        "status": osp.status,
        "titulo": osp.titulo,
        "descricao": osp.descricao,
        "prioridade": osp.prioridade,
        "grau_risco": osp.grau_risco,
        "sla_data": str(osp.sla_data),
        "equipamento": osp.equipamento.tag,
        "custo_real": str(osp.custo_real),
        "custo_material_real": str(osp.custo_material_real),
        "pecas": [
            [p.descricao, p.codigo, str(p.quantidade), p.unidade, str(p.custo_unitario)]
            for p in osp.pecas.order_by("id")
        ],
        "checklist": [
            [r.item_id, r.situacao, r.observacao]
            for r in osp.respostas_checklist.order_by("item_id")
        ],
        "evidencias": [[e.pk, e.fase, e.arquivo.name] for e in osp.evidencias_osp.order_by("id")],
        "apontamentos": [[str(a.inicio), str(a.fim)] for a in osp.apontamentos.order_by("id")],
        "ultimo_historico": osp.historico.order_by("-id").values_list("id", flat=True).first(),
    }


def estado_sha256(osp) -> str:
    canonico = json.dumps(estado_da_osp(osp), sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()


def validar_assinatura_png(dados: bytes) -> None:
    if len(dados) > LIMITE_ASSINATURA_BYTES:
        raise ValueError("A assinatura excede o tamanho permitido.")
    try:
        with Image.open(io.BytesIO(dados)) as img:
            img.verify()
            formato = (img.format or "").upper()
    except (UnidentifiedImageError, OSError, SyntaxError):
        raise ValueError("A assinatura não é uma imagem válida.")
    if formato not in FORMATOS_ASSINATURA:
        raise ValueError("A assinatura deve ser PNG.")


def registrar_assinatura(osp, usuario, *, nome, cargo, ip, png: bytes) -> AssinaturaOSP:
    """
    Assinatura do cliente sobre o estado atual da OSP. Uma por OSP, imutável.
    Grava o hash do estado, o IP, o nome/cargo e a imagem; registra no histórico.
    """
    if osp.status not in ESTADOS_ASSINAVEIS:
        raise ErroExecucao(
            "A assinatura só é registrada depois da execução (executada, aguardando aprovação ou finalizada).",
            codigo="estado_nao_assinavel", http=409,
        )
    if AssinaturaOSP.objects.filter(osp=osp).exists():
        raise ErroExecucao("Esta OSP já foi assinada.", codigo="ja_assinada", http=409)
    agora = timezone.now()
    digest = estado_sha256(osp)
    assinatura = AssinaturaOSP(
        osp=osp, nome=nome, cargo=cargo, assinado_em=agora, ip=ip or None,
        estado_sha256=digest, assinado_por=usuario,
    )
    assinatura.imagem.save(f"{osp.pk}-{digest[:12]}.png", ContentFile(png), save=False)
    assinatura.save()
    HistoricoOSP.objects.create(
        osp=osp, tipo=TipoHistorico.ASSINATURA, status_anterior=osp.status, status_novo=osp.status,
        alteracoes={"estado_sha256": digest, "signatario": nome, "cargo": cargo, "ip": ip or ""},
        ator=usuario, ator_nome=nome, ator_perfil=getattr(usuario, "perfil", "") or "",
    )
    return assinatura
