"""Geração automática de laudo a partir de uma inspeção (Anexo I 2.5.1.1)."""
from apps.coletas.models import Inspecao
from django.db import models, transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import Laudo, StatusLaudo, EventoLaudo

ORDEM_CRITICIDADE = {"NORMAL": 0, "ALERTA": 1, "CRITICO": 2}
LABEL_CRITICIDADE = {"NORMAL": "Normal", "ALERTA": "Alerta", "CRITICO": "Crítico", "": "Pendente de critério técnico"}


def _diagnostico_rastreavel(m):
    criterio = m.criterio_aplicado or {}
    motor = criterio.get("motor")
    if not motor:
        return m.diagnostico_sugerido
    analise = criterio.get("analise_preditiva") or {}
    ids = [str(p["id"]) for p in analise.get("entradas", [])]
    cadastro = criterio.get("cadastro") or {}
    rastreio = f"Regra: {motor}. Medição: {m._meta.label_lower}#{m.pk}."
    if cadastro.get("id"):
        rastreio += f" Critério registrado: #{cadastro['id']}."
    if ids:
        rastreio += f" Histórico utilizado: {', '.join(ids)}."
    else:
        rastreio += " Sem histórico comparável utilizado."
    return f"{m.diagnostico_sugerido} {rastreio}"


def _linha_vibracao(m):
    ponto = f"{m.equipamento.tag} — {m.ponto_medicao} ({m.get_direcao_display()})"
    leituras = [f"{valor} {unidade}" for valor, unidade in (
        (m.velocidade_rms, "mm/s RMS"), (m.aceleracao_rms, "g RMS"), (m.deslocamento_pp, "µm pico a pico"),
    ) if valor is not None]
    if m.zona_iso:
        leituras.append(f"Zona {m.zona_iso}")
    valor = " | ".join(leituras) or "Amplitude não informada"
    return ponto, valor, m.criticidade, _diagnostico_rastreavel(m)


def _linha_termografia(m):
    ponto = f"{m.equipamento.tag} — {m.ponto_medicao} ({m.get_sistema_display()})"
    valor = f"ΔT {m.delta_t}°C"
    return ponto, valor, m.criticidade, _diagnostico_rastreavel(m)


def _linha_tecnica(m):
    ponto = f"{m.equipamento.tag} — {m.ponto_medicao} ({m.grandeza})"
    if m.tipo == "SENSITIVA":
        valor = "Parecer qualitativo"
    else:
        valor = f"{m.valor} {m.unidade}".strip() if m.valor is not None else "Leitura não informada"
    return ponto, valor, m.criticidade, _diagnostico_rastreavel(m)


@transaction.atomic
def gerar_laudo_de_inspecao(inspecao: Inspecao, responsavel) -> Laudo:
    """Cria um laudo em rascunho consolidando o diagnóstico das medições da inspeção."""
    medicoes = [
        _linha_vibracao(m)
        for m in inspecao.medicoes_vibracao.select_related("equipamento", "componente")
    ] + [
        _linha_termografia(m)
        for m in inspecao.medicoes_termografia.select_related("equipamento", "componente")
    ] + [
        _linha_tecnica(m)
        for m in inspecao.medicoes_tecnicas.select_related("equipamento", "componente")
    ]

    criticidade_geral = inspecao.criticidade_maxima if medicoes else ""
    pendentes = sum(1 for _, _, crit, _ in medicoes if not crit)

    linhas_diag, recomendacoes = [], []
    for ponto, valor, crit, diag in medicoes:
        linhas_diag.append(
            f"• {ponto}: {valor} | {LABEL_CRITICIDADE.get(crit, crit)}. {diag}"
        )
        if crit == "CRITICO":
            recomendacoes.append(f"• {ponto}: encaminhar a classificação e a OSP ao responsável técnico para definir as providências conforme o critério registrado.")
        elif crit == "ALERTA":
            recomendacoes.append(f"• {ponto}: revisar as leituras, o contexto e o critério aplicado com o responsável técnico.")
        elif not crit:
            recomendacoes.append(f"• {ponto}: validar critério técnico aplicável antes de concluir a condição.")

    if not recomendacoes:
        recomendacoes.append("• Seguir o plano de inspeção definido pelo responsável técnico.")

    conclusao = (
        f"Foram analisadas {len(medicoes)} medições ({inspecao.get_tipo_analise_display()}). "
        f"Condição geral classificada como {LABEL_CRITICIDADE.get(criticidade_geral)}."
    )
    if pendentes:
        conclusao += f" Há {pendentes} medições com classificação pendente; a avaliação não está concluída."

    laudo = Laudo.objects.create(
        inspecao=inspecao,
        titulo=f"Laudo de {inspecao.get_tipo_analise_display()} — {inspecao.cliente.nome}",
        criticidade_geral=criticidade_geral,
        diagnostico="\n".join(linhas_diag) or "Sem medições registradas.",
        recomendacoes="\n".join(recomendacoes),
        conclusao=conclusao,
        responsavel=responsavel,
    )
    EventoLaudo.objects.create(laudo=laudo, acao="GERADO", autor=responsavel)
    return laudo


def tipo_analise_laudo(laudo):
    if laudo.inspecao_id:
        return laudo.inspecao.tipo_analise
    return {"VIBRACAO": "VIBRACAO", "TERMOGRAFIA": "TERMOGRAFIA", "BALANCEAMENTO": "CORRETIVA",
            "OLEO_ISOLANTE": "FLUIDOS", "FLUIDO_LUBRIFICANTE": "FLUIDOS",
            "ENSAIO_ELETRICO": "ENSAIO_ELETRICO"}.get(laudo.relatorio_origem.tecnologia.modulo_tecnico, "")


def validar_template(laudo):
    template = laudo.template
    if template and (not template.ativo or template.cliente_id not in (None, laudo.cliente.pk)
                     or template.tipo_analise not in ("", tipo_analise_laudo(laudo))):
        raise ValidationError({"template": "O template deve estar ativo e pertencer ao cliente e à modalidade deste laudo."})
    if template and laudo.relatorio_origem_id and template.configuracao.get("rodape", "").strip():
        raise ValidationError({"template": "O layout modular não possui espaço textual de rodapé. Use um template sem rodapé para preservar o desenho do PDF."})


def validar_responsavel(laudo, usuario):
    if not usuario.is_authenticated or not usuario.is_active or not usuario.is_interno:
        raise PermissionDenied("A ação exige um usuário interno ativo.")
    if laudo.responsavel_id != usuario.pk:
        raise PermissionDenied("Somente o responsável técnico atribuído pode aprovar a emissão.")
    if not usuario.conselho_classe.strip():
        raise ValidationError("O responsável técnico precisa de Conselho de Classe cadastrado.")


@transaction.atomic
def emitir_laudo(laudo, usuario, request=None):
    import hashlib
    from .snapshots import montar_snapshot, hash_snapshot
    from .pdf import congelar_imagens, gerar_pdf, ErroGeracaoPDF

    laudo = Laudo.objects.select_for_update().select_related("responsavel", "template", "inspecao__cliente",
                                                             "relatorio_origem__cliente").get(pk=laudo.pk)
    validar_responsavel(laudo, usuario)
    if laudo.status == StatusLaudo.EMITIDO:
        return laudo, False
    if laudo.status != StatusLaudo.RASCUNHO:
        raise ValidationError("Documento cancelado não pode ser emitido. Gere uma revisão.")
    validar_template(laudo)
    cliente_origem = laudo.inspecao.cliente_id if laudo.inspecao_id else laudo.relatorio_origem.cliente_id
    if cliente_origem != laudo.cliente.pk:
        raise ValidationError("O cliente da origem foi alterado após a geração. Preserve este registro e revise a vinculação antes de emitir.")
    agora = timezone.now()
    laudo.status, laudo.data_emissao = StatusLaudo.EMITIDO, agora
    laudo.assinatura = {
        "metodo": "APROVACAO_ELETRONICA_INTERNA", "usuario_id": usuario.pk,
        "nome": usuario.nome, "conselho": usuario.conselho_classe, "data": agora.isoformat(),
        "data_hora": agora.isoformat(), "assinatura_criptografica": False,
        "limitacao": "Registro de aprovação por usuário autenticado. Assinatura digital criptográfica não implementada; imagem e hash não a substituem.",
    }
    try:
        snapshot = congelar_imagens(montar_snapshot(laudo, request))
        laudo.snapshot_hash = hash_snapshot(snapshot)
        pdf = gerar_pdf(snapshot)
    except (ErroGeracaoPDF, ValueError, OSError) as erro:
        raise ValidationError({"documento": str(erro)}) from erro
    if not isinstance(pdf, bytes) or not pdf.startswith(b"%PDF"):
        raise ValidationError("A geração do PDF não produziu um documento válido.")
    laudo.snapshot_emissao, laudo.pdf_conteudo = snapshot, pdf
    laudo.pdf_hash = hashlib.sha256(pdf).hexdigest()
    laudo._operacao_autorizada = "emitir"
    laudo.save(update_fields=["status", "data_emissao", "assinatura", "snapshot_emissao", "snapshot_hash",
                             "pdf_conteudo", "pdf_hash", "atualizado_em"])
    EventoLaudo.objects.create(laudo=laudo, acao="EMITIDO", autor=usuario,
                               dados={"snapshot_hash": laudo.snapshot_hash, "pdf_hash": laudo.pdf_hash,
                                      "assinatura": laudo.assinatura})
    from apps.notificacoes.models import EventoNotificacao, Nivel
    from apps.notificacoes.services import clientes_do_cliente, notificar
    notificar(EventoNotificacao.LAUDO_CONCLUIDO, clientes_do_cliente(laudo.cliente),
              titulo=f"Laudo {laudo.numero} disponível",
              mensagem=f"O laudo '{laudo.titulo}' foi emitido e está disponível para consulta.",
              url=f"/laudos/{laudo.pk}", nivel=Nivel.INFO,
              chave=f"laudo_emitido:{laudo.pk}", cliente=laudo.cliente)
    return laudo, True


@transaction.atomic
def revisar_laudo(laudo, usuario, motivo):
    laudo = Laudo.objects.select_for_update().get(pk=laudo.pk)
    if not usuario.is_interno or not usuario.is_active:
        raise PermissionDenied("A revisão exige usuário interno ativo.")
    if laudo.status == StatusLaudo.RASCUNHO:
        raise ValidationError("Edite o rascunho antes da emissão; revisão exige versão emitida ou cancelada.")
    existente = Laudo.objects.filter(anterior=laudo).first()
    if existente:
        return existente, False
    raiz_id = laudo.documento_raiz_id or laudo.pk
    raiz = Laudo.objects.select_for_update().get(pk=raiz_id)
    ultima = Laudo.objects.filter(models.Q(pk=raiz.pk) | models.Q(documento_raiz=raiz)).order_by("-versao").first()
    if ultima.pk != laudo.pk:
        raise ValidationError("Revise a versão mais recente do documento.")
    dados = {campo: getattr(laudo, campo) for campo in (
        "inspecao_id", "relatorio_origem_id", "cliente_documento_id", "titulo", "criticidade_geral", "diagnostico", "recomendacoes",
        "conclusao", "template_id", "data_medicao_campo", "data_upload_osps", "data_upload_relatorio")}
    revisao = Laudo.objects.create(**dados, responsavel=usuario, documento_raiz=raiz, anterior=laudo,
                                   versao=laudo.versao + 1, motivo_revisao=motivo,
                                   numero=f"{raiz.numero}-V{laudo.versao + 1}")
    from .models import AnexoLaudo
    AnexoLaudo.objects.bulk_create([AnexoLaudo(laudo=revisao, nome=a.nome, legenda=a.legenda, mime=a.mime,
        sha256=a.sha256, tamanho=a.tamanho, conteudo=a.conteudo, criado_por=a.criado_por) for a in laudo.anexos.all()])
    EventoLaudo.objects.create(laudo=laudo, acao="REVISAO_ABERTA", autor=usuario, motivo=motivo,
                               dados={"nova_versao_id": revisao.pk})
    EventoLaudo.objects.create(laudo=revisao, acao="REVISAO_CRIADA", autor=usuario, motivo=motivo,
                               dados={"anterior_id": laudo.pk})
    return revisao, True


@transaction.atomic
def cancelar_laudo(laudo, usuario, motivo):
    laudo = Laudo.objects.select_for_update().get(pk=laudo.pk)
    if not usuario.is_interno or not usuario.is_active or (usuario.pk != laudo.responsavel_id and not usuario.is_master):
        raise PermissionDenied("Somente o responsável ou um Master interno pode cancelar o documento.")
    if laudo.status == StatusLaudo.CANCELADO:
        return laudo
    laudo.status, laudo.cancelado_em, laudo.cancelado_por = StatusLaudo.CANCELADO, timezone.now(), usuario
    laudo.motivo_cancelamento, laudo._operacao_autorizada = motivo, "cancelar"
    laudo.save(update_fields=["status", "cancelado_em", "cancelado_por", "motivo_cancelamento", "atualizado_em"])
    EventoLaudo.objects.create(laudo=laudo, acao="CANCELADO", autor=usuario, motivo=motivo,
                               dados={"snapshot_hash": laudo.snapshot_hash})
    return laudo
