"""
Entrega das notificações nos canais externos (e-mail, WhatsApp, push).

Ciclo de uma `EntregaNotificacao`:

1. Nasce PENDENTE na MESMA transação do evento (`notificar`). Se a operação
   principal sofrer rollback, a entrega some junto — nunca se avisa algo que
   não aconteceu.
2. Depois do commit, uma tentativa imediata (se `NOTIFICACOES_ENVIO_IMEDIATO`).
   Falha de canal nunca volta para quem disparou o evento: a operação principal
   já está gravada e segue.
3. `processar_pendentes()` (comando `processar_notificacoes` / `agendador`)
   reenvia o que ficou PENDENTE, com backoff, até `NOTIFICACOES_MAX_TENTATIVAS`.
   Esgotou ou o erro é definitivo → FALHOU, com o motivo (sem segredos).
4. `reprocessar()` devolve FALHOU/NAO_CONFIGURADO para a fila. ENVIADO nunca é
   reenviado.

Concorrência: a entrega é REIVINDICADA numa transação curta (lock da linha +
"lease" em `proxima_tentativa_em`) e o envio de rede acontece FORA dela. Dois
processos não enviam a mesma entrega ao mesmo tempo. Se o processo morrer entre
o envio e o registro, a entrega volta após o lease (semântica "pelo menos uma
vez"; a chave `Idempotency-Key`/`X-Notificacao-Id` permite ao provedor descartar
a repetição).
"""
import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from . import channels
from .models import Canal, EntregaNotificacao, Notificacao, StatusEntrega, STATUS_REPROCESSAVEIS

logger = logging.getLogger("notificacoes")

#: Espera antes da tentativa N+1 (minutos). A última se repete se houver mais tentativas.
BACKOFF_MINUTOS = (1, 5, 15, 60, 240)
#: Tempo em que uma entrega reivindicada fica "reservada" para quem a pegou.
LEASE = timedelta(minutes=10)


def _max_tentativas():
    return int(getattr(settings, "NOTIFICACOES_MAX_TENTATIVAS", 5))


def canais_da_preferencia(pref) -> list[str]:
    canais = []
    if pref.email:
        canais.append(Canal.EMAIL)
    if pref.whatsapp:
        canais.append(Canal.WHATSAPP)
    if pref.push:
        canais.append(Canal.PUSH)
    return canais


def criar_entregas(notif, canais) -> list[int]:
    agora = timezone.now()
    ids = []
    for canal in canais:
        entrega, _ = EntregaNotificacao.objects.get_or_create(
            notificacao=notif, canal=canal,
            defaults={"status": StatusEntrega.PENDENTE, "proxima_tentativa_em": agora},
        )
        ids.append(entrega.pk)
    return ids


def _reivindicar(entrega_id):
    """Reserva a entrega para este processo. None se outro já pegou ou não há o que fazer."""
    agora = timezone.now()
    with transaction.atomic():
        entrega = (
            EntregaNotificacao.objects.select_for_update()
            .select_related("notificacao__destinatario").filter(pk=entrega_id).first()
        )
        if entrega is None or entrega.status != StatusEntrega.PENDENTE:
            return None
        if entrega.proxima_tentativa_em and entrega.proxima_tentativa_em > agora:
            return None
        entrega.tentativas += 1
        entrega.ultima_tentativa_em = agora
        entrega.proxima_tentativa_em = agora + LEASE
        entrega.save(update_fields=["tentativas", "ultima_tentativa_em", "proxima_tentativa_em", "atualizado_em"])
        return entrega


def _destinatario_apto(user) -> str:
    """Motivo para NÃO enviar ('' = pode). Conta pode ter mudado desde o evento."""
    if not user.is_active or getattr(user, "estado", "ACTIVE") != "ACTIVE":
        return "Conta do destinatário inativa, suspensa ou bloqueada."
    return ""


def processar_entrega(entrega_id) -> str | None:
    """Uma tentativa. Devolve o status final da tentativa (ou None se não tentou)."""
    entrega = _reivindicar(entrega_id)
    if entrega is None:
        return None
    notif = entrega.notificacao
    user = notif.destinatario
    motivo = _destinatario_apto(user)
    if motivo:
        resultado = channels.Resultado(StatusEntrega.IGNORADO, motivo)
    else:
        try:
            resultado = getattr(channels, channels.ADAPTADORES[entrega.canal])(
                user, notif.titulo, notif.mensagem, chave_envio=f"notif-{notif.pk}-{entrega.canal}",
            )
        except Exception as erro:  # adaptador com defeito não derruba o lote
            logger.exception("Erro inesperado no canal %s (entrega %s)", entrega.canal, entrega.pk)
            resultado = channels.Resultado(StatusEntrega.FALHOU, f"{type(erro).__name__}: {channels.sanitizar(erro)}",
                                           temporario=True)
    return _registrar(entrega, resultado)


def _registrar(entrega, resultado):
    agora = timezone.now()
    with transaction.atomic():
        entrega = EntregaNotificacao.objects.select_for_update().get(pk=entrega.pk)
        entrega.ultimo_erro = channels.sanitizar(resultado.erro)
        entrega.provedor_id = resultado.provedor_id or entrega.provedor_id
        if resultado.status == StatusEntrega.FALHOU and resultado.temporario and entrega.tentativas < _max_tentativas():
            espera = BACKOFF_MINUTOS[min(entrega.tentativas - 1, len(BACKOFF_MINUTOS) - 1)]
            entrega.status = StatusEntrega.PENDENTE
            entrega.proxima_tentativa_em = agora + timedelta(minutes=espera)
        else:
            entrega.status = resultado.status
            entrega.proxima_tentativa_em = None
            if resultado.status in (StatusEntrega.ENVIADO, StatusEntrega.SIMULADO):
                entrega.enviado_em = agora
        entrega.save()
        if entrega.status == StatusEntrega.ENVIADO:
            notif = Notificacao.objects.select_for_update().get(pk=entrega.notificacao_id)
            canais = list(notif.canais_enviados or [Canal.INTERNO])
            if entrega.canal not in canais:
                canais.append(entrega.canal)
                Notificacao.objects.filter(pk=notif.pk).update(canais_enviados=canais)
    if entrega.status == StatusEntrega.FALHOU:
        # Só ids e o motivo sanitizado: nada de e-mail, telefone ou credencial no log.
        logger.warning("Entrega %s (%s) falhou após %s tentativa(s): %s",
                       entrega.pk, entrega.canal, entrega.tentativas, entrega.ultimo_erro)
    return entrega.status


def processar_imediatamente(ids):
    """Callback pós-commit: tenta já, sem nunca propagar erro para a operação principal."""
    if not getattr(settings, "NOTIFICACOES_ENVIO_IMEDIATO", True):
        return
    for entrega_id in ids:
        try:
            processar_entrega(entrega_id)
        except Exception:
            logger.exception("Falha ao processar a entrega %s; fica para o agendador.", entrega_id)


def processar_pendentes(limite=200) -> dict:
    """Uma rodada do agendador: tenta as entregas vencidas. Seguro rodar em paralelo."""
    agora = timezone.now()
    ids = list(
        EntregaNotificacao.objects.filter(status=StatusEntrega.PENDENTE, proxima_tentativa_em__lte=agora)
        .order_by("proxima_tentativa_em", "id").values_list("id", flat=True)[:limite]
    )
    resumo = {}
    for entrega_id in ids:
        status = processar_entrega(entrega_id)
        if status:
            resumo[status] = resumo.get(status, 0) + 1
    return resumo


def reprocessar(queryset=None, *, canal=None) -> int:
    """Devolve FALHOU/NAO_CONFIGURADO para a fila (tentativas zeradas). Nunca toca em ENVIADO."""
    qs = queryset if queryset is not None else EntregaNotificacao.objects.all()
    qs = qs.filter(status__in=STATUS_REPROCESSAVEIS)
    if canal:
        qs = qs.filter(canal=canal)
    return qs.update(status=StatusEntrega.PENDENTE, tentativas=0, proxima_tentativa_em=timezone.now(),
                     atualizado_em=timezone.now())
