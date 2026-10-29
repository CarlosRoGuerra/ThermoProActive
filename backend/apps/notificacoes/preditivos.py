"""Eventos idempotentes de classificação. Chamado pela gravação, nunca por leitura."""
from django.db import transaction

from apps.ensaios.contexto import serializavel

from .models import EstadoEventoPreditivo, EventoNotificacao, EventoPreditivo, Nivel
from .services import notificar, pcm_do_cliente


@transaction.atomic
def processar_medicao(medicao):
    modelo = medicao._meta.label_lower
    autor_alteracao = getattr(medicao, "_autor_edicao", None)
    # O save pode ter update_fields; a classificação persistida é a fonte.
    medicao = type(medicao).objects.select_related("inspecao__cliente", "equipamento").get(pk=medicao.pk)
    # A decisão usa a versão persistida, mesmo se o chamador traz instância antiga.
    if medicao.classificacao_status == "LEGADO" or not (medicao.criterio_aplicado or {}).get("motor"):
        return None
    estado, _ = EstadoEventoPreditivo.objects.get_or_create(medicao_tipo=modelo, medicao_id=medicao.pk)
    estado = EstadoEventoPreditivo.objects.select_for_update().get(pk=estado.pk)
    atual = medicao.criticidade or ""
    anterior = estado.ultima_criticidade
    if atual == anterior:
        return None
    estado.ultima_criticidade = atual
    estado.sequencia += 1
    estado.save(update_fields=["ultima_criticidade", "sequencia", "atualizado_em"])
    if atual not in ("ALERTA", "CRITICO") and anterior not in ("ALERTA", "CRITICO"):
        return None

    criterio = medicao.criterio_aplicado or {}
    analise = criterio.get("analise_preditiva") or {}
    versao = str(criterio.get("motor") or analise.get("versao") or criterio.get("versao") or "classificacao-registrada-v1")
    orientacao = (
        "Encaminhar a classificação, as leituras e o critério registrado para avaliação do responsável técnico."
        if atual in ("ALERTA", "CRITICO") else
        "Conferir a nova avaliação registrada; a transição não encerra automaticamente uma OSP existente."
    )
    evento = EventoPreditivo.objects.create(
        medicao_tipo=modelo, medicao_id=medicao.pk, sequencia=estado.sequencia,
        inspecao=medicao.inspecao, equipamento=medicao.equipamento,
        criticidade_anterior=anterior, criticidade=atual, regra_versao=versao,
        evidencias=serializavel({
            "criterio_aplicado": criterio, "classificacao_status": medicao.classificacao_status,
            "diagnostico": medicao.diagnostico_sugerido, "data_hora": medicao.data_hora,
            "ponto_medicao": medicao.ponto_medicao, "instrumento_id": medicao.instrumento_id,
            "autor_coleta_id": medicao.coletado_por_id,
            "autor_alteracao_id": autor_alteracao,
        }), orientacao=orientacao,
    )
    tipo_label = medicao.inspecao.get_tipo_analise_display()
    if atual == "CRITICO":
        from apps.osp.services import gerar_osp_de_medicao
        evento.osp = gerar_osp_de_medicao(medicao, tipo_label, retornar_existente=True)
        evento.save(update_fields=["osp", "atualizado_em"])
    if atual in ("ALERTA", "CRITICO"):
        destinatarios = list(pcm_do_cliente(medicao.inspecao.cliente))
        if medicao.inspecao.tecnico_id:
            destinatarios.append(medicao.inspecao.tecnico)
        notificar(
            EventoNotificacao.EQUIPAMENTO_CRITICO if atual == "CRITICO" else EventoNotificacao.ALERTA_PREDITIVO,
            destinatarios, titulo=f"{atual.title()}: {medicao.equipamento.tag}",
            mensagem=f"Evento preditivo #{evento.pk}. {medicao.diagnostico_sugerido} {orientacao}",
            url=f"/inspecoes/{medicao.inspecao_id}",
            nivel=Nivel.CRITICO if atual == "CRITICO" else Nivel.ALERTA, evento_preditivo=evento,
            cliente=medicao.inspecao.cliente,
        )
    return evento
