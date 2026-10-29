"""
Fluxo da OSP (Anexo I 2.6): geração automática, transições de status com
autorização por perfil, edição auditada e verificação de SLA.

Toda mudança de estado passa por aqui — nunca por `osp.status = ...; osp.save()`
nas views — para que regra, permissão, histórico e notificação andem juntos.
"""
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.models import Perfil
from apps.cadastros.models import Equipamento

from .models import (
    STATUS_ABERTOS,
    STATUS_ENCERRADOS,
    TRANSICOES,
    GrauRisco,
    HistoricoOSP,
    OrdemServico,
    Prioridade,
    StatusOSP,
    TipoHistorico,
)

# Criticidade da medição → prioridade da OSP.
CRITICIDADE_PARA_PRIORIDADE = {
    "CRITICO": Prioridade.ALTA,
    "ALERTA": Prioridade.MEDIA,
}

# Criticidade da medição → Grau de Risco do laudo (glossário §6.2).
# O analista pode reclassificar manualmente: quem dá o GR final é o técnico.
CRITICIDADE_PARA_GR = {
    "CRITICO": GrauRisco.GR2,
    "ALERTA": GrauRisco.GR3,
    "NORMAL": GrauRisco.GR4,
}


# --- Erros do fluxo -----------------------------------------------------------

class ErroOSP(Exception):
    """Violação de regra do fluxo; `http` diz como a API deve responder."""

    http = 400
    codigo = "osp_invalida"

    def __init__(self, mensagem, *, codigo=None, http=None):
        super().__init__(mensagem)
        self.mensagem = mensagem
        if codigo:
            self.codigo = codigo
        if http:
            self.http = http


# --- Geração automática (2.6.1.1) ---------------------------------------------

@transaction.atomic
def gerar_osp_de_medicao(medicao, tipo_label: str, *, retornar_existente=False) -> OrdemServico | None:
    """
    Cria uma OSP para uma medição crítica, caso ainda não exista OSP em aberto
    para o mesmo equipamento na mesma inspeção. Retorna a OSP criada ou None
    (ou a existente, com `retornar_existente`).

    Idempotente em três camadas: (1) lock do equipamento serializa eventos
    simultâneos no PostgreSQL; (2) consulta das OSPs em aberto; (3) restrição
    única parcial no banco — se uma corrida escapar das duas primeiras, o
    IntegrityError é convertido na OSP que ganhou a corrida.
    """
    if medicao.criticidade != "CRITICO":
        return None

    inspecao = medicao.inspecao
    equipamento = medicao.equipamento

    Equipamento.objects.select_for_update().get(pk=equipamento.pk)

    def _existente():
        return OrdemServico.objects.filter(
            equipamento=equipamento, inspecao=inspecao, status__in=STATUS_ABERTOS,
        ).order_by("pk").first()

    existente = _existente()
    if existente:
        return existente if retornar_existente else None

    try:
        with transaction.atomic():
            return OrdemServico.objects.create(
                cliente=inspecao.cliente,
                equipamento=equipamento,
                inspecao=inspecao,
                titulo=f"OSP automática — {equipamento.tag} ({tipo_label})",
                descricao=(
                    f"Gerada automaticamente a partir de medição crítica em "
                    f"{medicao.ponto_medicao}. {medicao.diagnostico_sugerido}"
                ),
                prioridade=CRITICIDADE_PARA_PRIORIDADE.get(medicao.criticidade, Prioridade.MEDIA),
                grau_risco=CRITICIDADE_PARA_GR.get(medicao.criticidade, GrauRisco.GR3),
                criticidade_origem=medicao.criticidade,
                anomalia=medicao.diagnostico_sugerido,
                componente=getattr(medicao.componente, "nome", "") or "",
                responsavel=inspecao.tecnico,
                gerada_automaticamente=True,
            )
    except IntegrityError:
        existente = _existente()
        if existente:
            return existente if retornar_existente else None
        raise


# --- Quem pode o quê ----------------------------------------------------------

INTERNOS_OPERAM = frozenset({Perfil.ADMIN, Perfil.GESTOR, Perfil.TECNICO})
INTERNOS_GESTAO = frozenset({Perfil.ADMIN, Perfil.GESTOR})
CLIENTE_APROVADORES = frozenset({Perfil.CLIENTE_CORP, Perfil.CLIENTE_LOCAL, Perfil.CLIENTE_PCM})

#: Transições que exigem justificativa (rastreabilidade de cancelar/reabrir/rejeitar).
MOTIVO_OBRIGATORIO_TIPOS = frozenset({
    TipoHistorico.CANCELAMENTO, TipoHistorico.REABERTURA, TipoHistorico.REJEICAO,
})


def perfis_aprovadores() -> frozenset:
    """
    Quem aprova a execução/finaliza a OSP. PENDENTE DE CONFIRMAÇÃO COM O CLIENTE
    (docs/03: "quem aprova — cliente? gestor?"): por padrão só a gestão da
    CONTRATADA; `OSP_APROVACAO_PELO_CLIENTE=true` estende a PCM/Gestores do cliente.
    O Manutentor nunca aprova.
    """
    if getattr(settings, "OSP_APROVACAO_PELO_CLIENTE", False):
        return INTERNOS_GESTAO | CLIENTE_APROVADORES
    return INTERNOS_GESTAO


def tipo_da_transicao(de, para) -> str:
    if de in STATUS_ENCERRADOS:
        return TipoHistorico.REABERTURA
    if para == StatusOSP.CANCELADA:
        return TipoHistorico.CANCELAMENTO
    if para == StatusOSP.FINALIZADA:
        return TipoHistorico.APROVACAO
    if de == StatusOSP.AGUARDANDO_APROVACAO and para == StatusOSP.EM_EXECUCAO:
        return TipoHistorico.REJEICAO
    return TipoHistorico.STATUS


def perfis_da_transicao(de, para) -> frozenset:
    tipo = tipo_da_transicao(de, para)
    if tipo in (TipoHistorico.APROVACAO, TipoHistorico.REJEICAO):
        return perfis_aprovadores()
    if tipo in (TipoHistorico.CANCELAMENTO, TipoHistorico.REABERTURA):
        return INTERNOS_GESTAO
    return INTERNOS_OPERAM


def _pode(user, osp, de, para) -> bool:
    if not (user and user.is_authenticated and user.is_active):
        return False
    if user.perfil not in perfis_da_transicao(de, para):
        return False
    # Defesa em profundidade: o escopo já vem do queryset, mas a regra não pode
    # depender disso para impedir que um cliente aja na OSP de outro.
    if user.is_cliente and user.cliente_id != osp.cliente_id:
        return False
    return True


def transicoes_permitidas(user, osp) -> list[dict]:
    """O que ESTE usuário pode fazer agora com a OSP (alimenta botões da UI)."""
    saida = []
    for para in sorted(TRANSICOES.get(osp.status, ()), key=lambda s: s.value):
        if _pode(user, osp, osp.status, para):
            tipo = tipo_da_transicao(osp.status, para)
            saida.append({
                "status": para.value,
                "acao": tipo,
                "motivo_obrigatorio": tipo in MOTIVO_OBRIGATORIO_TIPOS,
            })
    return saida


# --- Transição de status (2.6.3) ----------------------------------------------

def _ator_dados(ator):
    return {
        "ator": ator if getattr(ator, "pk", None) else None,
        "ator_nome": getattr(ator, "nome", "") or "Sistema",
        "ator_perfil": getattr(ator, "perfil", "") or "",
    }


def _jsonavel(valor):
    if hasattr(valor, "pk"):
        return valor.pk
    if isinstance(valor, (datetime, date)):
        return valor.isoformat()
    if isinstance(valor, Decimal):
        return str(valor)
    return valor


def transicionar(osp_id, novo_status, ator, motivo="") -> tuple[OrdemServico, bool]:
    """
    Move a OSP para `novo_status`. Devolve `(osp, alterou)`.

    * Pedir o status em que a OSP já está é um no-op (`alterou=False`): repetir a
      requisição (duplo clique, retry de rede) não duplica histórico nem aviso.
    * A linha é travada e o status é relido DENTRO da transação, então duas
      requisições concorrentes não aplicam a mesma transição duas vezes.
    * Transição fora de `TRANSICOES` → 409; sem permissão → 403; sem motivo
      quando exigido → 400.
    """
    novo_status = StatusOSP(novo_status)
    motivo = (motivo or "").strip()
    with transaction.atomic():
        osp = OrdemServico.objects.select_for_update().select_related(
            "cliente", "equipamento", "responsavel"
        ).get(pk=osp_id)
        de = StatusOSP(osp.status)
        if de == novo_status:
            return osp, False
        # Permissão primeiro: quem não pode agir não descobre, pelo erro, quais
        # transições existem.
        if not _pode(ator, osp, de, novo_status):
            raise ErroOSP(
                "Seu perfil não pode executar esta transição.", codigo="sem_permissao", http=403,
            )
        if novo_status not in TRANSICOES.get(de, ()):
            raise ErroOSP(
                f"Transição inválida: {de.label} → {novo_status.label}.",
                codigo="transicao_invalida", http=409,
            )
        tipo = tipo_da_transicao(de, novo_status)
        if tipo in MOTIVO_OBRIGATORIO_TIPOS and not motivo:
            raise ErroOSP("Informe o motivo.", codigo="motivo_obrigatorio", http=400)

        agora = timezone.now()
        antes = {}

        def _mudar(campo, valor):
            atual = getattr(osp, campo)
            if _jsonavel(atual) != _jsonavel(valor):
                antes[campo] = [_jsonavel(atual), _jsonavel(valor)]
                setattr(osp, campo, valor)

        _mudar("status", novo_status.value)
        if tipo == TipoHistorico.APROVACAO:
            _mudar("finalizada_em", agora)
            if osp.finalizado_por_id is None:
                _mudar("finalizado_por", ator)
            _mudar("aprovado_por", ator)
            _mudar("aprovado_em", agora)
        elif tipo == TipoHistorico.REABERTURA:
            # O que foi encerrado fica registrado no histórico; a OSP recomeça o
            # ciclo e o prazo é recontado a partir da reabertura.
            for campo in ("finalizada_em", "finalizado_por", "aprovado_por", "aprovado_em"):
                _mudar(campo, None)
            sla_anterior = osp.sla_data
            osp.sla_iniciado_em = agora
            osp.recalcular_sla(agora)
            if sla_anterior != osp.sla_data:
                antes["sla_data"] = [_jsonavel(sla_anterior), _jsonavel(osp.sla_data)]
        elif (
            novo_status == StatusOSP.EM_ANALISE
            and osp.responsavel_id is None
            and getattr(ator, "is_interno", False)
        ):
            # Quem assume a análise passa a ser o técnico responsável.
            _mudar("responsavel", ator)

        try:
            with transaction.atomic():
                osp.save()
        except IntegrityError:
            raise ErroOSP(
                "Já existe outra OSP automática em aberto para esta ocorrência; "
                "conclua ou cancele aquela antes de reabrir esta.",
                codigo="conflito_ocorrencia", http=409,
            )
        historico = HistoricoOSP.objects.create(
            osp=osp, tipo=tipo, status_anterior=de.value, status_novo=novo_status.value,
            alteracoes=antes, motivo=motivo, **_ator_dados(ator),
        )
        _notificar_transicao(osp, de, novo_status, ator, motivo, tipo, historico.pk)
    return osp, True


def _notificar_transicao(osp, de, para, ator, motivo, tipo, historico_id):
    """Avisa quem precisa agir/saber; chamado dentro da transação da transição."""
    from apps.notificacoes.models import EventoNotificacao, Nivel
    from apps.notificacoes.services import (
        aprovadores_do_cliente, gestores, notificar, pcm_do_cliente,
    )

    rotulo = para.label
    if para == StatusOSP.AGUARDANDO_APROVACAO:
        destinatarios = list(gestores())
        if CLIENTE_APROVADORES & perfis_aprovadores():
            destinatarios += list(aprovadores_do_cliente(osp.cliente))
        evento, nivel = EventoNotificacao.APROVACAO_PENDENTE, Nivel.ALERTA
        titulo = f"Aprovação pendente: OSP {osp.numero}"
        mensagem = f"A OSP {osp.numero} ({osp.equipamento.tag}) aguarda aprovação da execução."
    else:
        destinatarios = list(pcm_do_cliente(osp.cliente))
        if osp.responsavel_id:
            destinatarios.append(osp.responsavel)
        if tipo in MOTIVO_OBRIGATORIO_TIPOS:
            destinatarios += list(gestores())
        evento = EventoNotificacao.OSP_STATUS
        nivel = Nivel.ALERTA if tipo in MOTIVO_OBRIGATORIO_TIPOS else Nivel.INFO
        titulo = f"OSP {osp.numero}: {rotulo}"
        mensagem = f"A OSP {osp.numero} ({osp.equipamento.tag}) passou de {de.label} para {rotulo}."
        if motivo:
            mensagem += f" Motivo: {motivo}"
    ator_pk = getattr(ator, "pk", None)
    destinatarios = [u for u in destinatarios if u.pk != ator_pk]
    if destinatarios:
        # Chave = a linha do histórico: cada transição avisa uma vez por destinatário.
        notificar(evento, destinatarios, titulo=titulo, mensagem=mensagem, url="/osps", nivel=nivel,
                  chave=f"osp_transicao:{historico_id}", cliente=osp.cliente)


# --- Edição auditada ----------------------------------------------------------

#: Campos cuja alteração só a gestão da CONTRATADA faz (o prazo é a régua do SLA).
CAMPOS_SO_GESTAO = frozenset({"sla_data"})


def aplicar_edicao(osp_id, dados: dict, ator) -> OrdemServico:
    """
    Aplica uma edição de campos e registra no histórico o que mudou (antes →
    depois), quem mudou e com qual perfil. Editar nunca apaga histórico.

    * OSP cancelada é imutável: reabra primeiro.
    * Mudar prioridade ou grau de risco recalcula o prazo, a menos que ele tenha
      sido fixado manualmente.
    * Fixar `sla_data` à mão é restrito à gestão e zera os avisos de SLA.
    """
    with transaction.atomic():
        osp = OrdemServico.objects.select_for_update().get(pk=osp_id)
        if osp.status == StatusOSP.CANCELADA:
            raise ErroOSP(
                "OSP cancelada não pode ser editada; reabra-a primeiro.",
                codigo="osp_cancelada", http=409,
            )
        if CAMPOS_SO_GESTAO & dados.keys() and ator.perfil not in INTERNOS_GESTAO:
            if any(_jsonavel(getattr(osp, c)) != _jsonavel(dados[c]) for c in CAMPOS_SO_GESTAO & dados.keys()):
                raise ErroOSP(
                    "Apenas a gestão pode alterar o prazo (SLA).", codigo="sem_permissao", http=403,
                )
        mudancas = {}
        for campo, valor in dados.items():
            atual = getattr(osp, campo)
            if _jsonavel(atual) != _jsonavel(valor):
                mudancas[campo] = [_jsonavel(atual), _jsonavel(valor)]
                setattr(osp, campo, valor)
        if not mudancas:
            return osp

        sla_antes = osp.sla_data
        if "sla_data" in mudancas:
            osp.sla_origem = "MANUAL"
            osp.sla_aviso_vencendo_em = osp.sla_aviso_vencido_em = None
        elif ({"prioridade", "grau_risco"} & mudancas.keys()) and osp.sla_origem in ("GRAU_RISCO", "PRIORIDADE"):
            osp.recalcular_sla()
            if osp.sla_data != sla_antes:
                mudancas["sla_data"] = [_jsonavel(sla_antes), _jsonavel(osp.sla_data)]
        osp.save()

        if getattr(ator, "is_cliente", False):
            tipo = TipoHistorico.RETORNO_CLIENTE
        elif "sla_data" in mudancas:
            tipo = TipoHistorico.SLA
        else:
            tipo = TipoHistorico.EDICAO
        HistoricoOSP.objects.create(
            osp=osp, tipo=tipo, status_anterior=osp.status, status_novo=osp.status,
            alteracoes=mudancas, **_ator_dados(ator),
        )
    return osp


# --- SLA (2.6.1.1.5 / 2.10.2.4) -----------------------------------------------

def verificar_slas(dias=2, hoje=None) -> dict:
    """
    Avisa sobre OSPs com SLA vencendo (dentro de `dias`) ou vencido.

    Idempotente: cada aviso sai UMA vez por prazo — a marca é reivindicada com
    UPDATE condicional na mesma transação do aviso, então rodar o job várias
    vezes ou duas instâncias ao mesmo tempo não duplica notificação, e uma
    falha no envio desfaz a marca (o próximo ciclo tenta de novo). Mudar o
    prazo (reabertura, edição) zera as marcas.

    Vencido NÃO altera o status: a OSP segue aberta, sinalizada (`sla_vencido`)
    e contada nos painéis; quem decide é a gestão.
    """
    from apps.notificacoes.models import EventoNotificacao, Nivel
    from apps.notificacoes.services import gestores, notificar

    hoje = hoje or timezone.localdate()
    limite = hoje + timedelta(days=dias)
    resumo = {"vencendo": 0, "vencido": 0}
    candidatas = OrdemServico.objects.filter(
        status__in=STATUS_ABERTOS, sla_data__isnull=False, sla_data__lte=limite,
    ).select_related("equipamento", "cliente", "responsavel")
    for osp in candidatas:
        vencido = osp.sla_data < hoje
        campo = "sla_aviso_vencido_em" if vencido else "sla_aviso_vencendo_em"
        if getattr(osp, campo) is not None:
            continue
        with transaction.atomic():
            reivindicada = OrdemServico.objects.filter(
                pk=osp.pk, status__in=STATUS_ABERTOS, sla_data=osp.sla_data,
                **{f"{campo}__isnull": True},
            ).update(**{campo: timezone.now()})
            if not reivindicada:
                continue
            destinatarios = list(gestores())
            if osp.responsavel_id:
                destinatarios.append(osp.responsavel)
            notificar(
                EventoNotificacao.SLA_VENCENDO,
                destinatarios,
                titulo=f"SLA {'vencido' if vencido else 'vencendo'}: OSP {osp.numero}",
                mensagem=(
                    f"A OSP {osp.numero} ({osp.equipamento.tag}) tem SLA em {osp.sla_data}. "
                    f"Status atual: {osp.get_status_display()}."
                ),
                url="/osps",
                nivel=Nivel.CRITICO if vencido else Nivel.ALERTA,
                # Um aviso por OSP, por fase e por prazo: mudar o prazo gera chave nova.
                chave=f"sla:{osp.pk}:{'vencido' if vencido else 'vencendo'}:{osp.sla_data.isoformat()}",
                cliente=osp.cliente,
            )
        resumo["vencido" if vencido else "vencendo"] += 1
    return resumo
