"""Conteúdo documental congelado; nenhuma reconstrução de documento legado."""
import hashlib
import json
from django.core.serializers.json import DjangoJSONEncoder
from .templates import SECOES


def serializavel(valor):
    return json.loads(json.dumps(valor, cls=DjangoJSONEncoder))


def hash_snapshot(snapshot):
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True, separators=(",", ":"),
                                      ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()


def montar_snapshot(laudo, request=None):
    from .relatorio import montar_relatorio_tecnico
    from .services import tipo_analise_laudo
    # A emissão inclui a origem inteira; filtros de uma prévia não são aceitos.
    class RequisicaoDocumento:
        query_params = {}
        def build_absolute_uri(self, url):
            return request.build_absolute_uri(url) if request else url
    requisicao_documento = RequisicaoDocumento()
    if laudo.inspecao_id:
        relatorio = montar_relatorio_tecnico(laudo, requisicao_documento, usar_snapshot=False)
        origem = {"tipo": "inspecao", "id": laudo.inspecao_id, "cliente_id": laudo.cliente.pk}
        medicoes, graficos = [], []
        for relacionamento in ("medicoes_vibracao", "medicoes_termografia", "medicoes_tecnicas"):
            for m in getattr(laudo.inspecao, relacionamento).select_related("equipamento", "instrumento").order_by("data_hora", "id"):
                medicoes.append({"modelo": m._meta.label_lower, "id": m.pk, "equipamento_id": m.equipamento_id,
                    "equipamento_tag": m.equipamento.tag, "ponto_medicao": m.ponto_medicao,
                    "dados": {campo.name: getattr(m, campo.attname) for campo in m._meta.fields
                              if campo.name not in {"criterio_aplicado", "historico_classificacao"}},
                    "instrumento_id": m.instrumento_id, "data_hora": m.data_hora,
                    "classificacao_status": m.classificacao_status, "criticidade": m.criticidade,
                    "diagnostico": m.diagnostico_sugerido, "criterio_aplicado": m.criterio_aplicado,
                    "historico_classificacao": m.historico_classificacao})
                analise = (m.criterio_aplicado or {}).get("analise_preditiva") or {}
                if analise.get("entradas") and analise.get("atual") is not None:
                    graficos.append({"titulo": f"{m.equipamento.tag} — {m.ponto_medicao}",
                        "unidade": analise.get("unidade", ""), "regra": analise.get("versao"),
                        "pontos": [{"data": p["data_hora"], "valor": p["valor"]} for p in analise["entradas"]]
                            + [{"data": analise["instante"], "valor": analise["atual"]}]})
        evidencias = []
    else:
        from apps.coletas.relatorio_tecnico import montar_dossie
        from apps.coletas.models import AchadoImagem
        relatorio = montar_dossie(laudo.relatorio_origem, requisicao_documento)
        origem = {"tipo": "relatorio", "id": laudo.relatorio_origem_id, "cliente_id": laudo.cliente.pk}
        medicoes, graficos = [], []
        evidencias = [{"id": img.pk, "nome": img.arquivo.name, "legenda": img.legenda,
                       "url": img.arquivo.url} for img in AchadoImagem.objects.filter(
                           achado__item__carregamento__relatorio_id=laudo.relatorio_origem_id).order_by("id")]
    evidencias += [{"id": anexo.pk, "nome": anexo.nome, "legenda": anexo.legenda, "mime": anexo.mime,
                    "sha256": anexo.sha256, "data_uri": anexo.data_uri} for anexo in laudo.anexos.all()]
    template = laudo.template
    configuracao = template.configuracao if template else {"secoes": SECOES}
    titulo_documento = configuracao.get("titulo_documento") or "Relatório Técnico"
    textos_editoriais = [f"{rotulo}:\n{texto}" for rotulo, texto in (
        ("Diagnóstico técnico", laudo.diagnostico), ("Recomendações", laudo.recomendacoes),
        ("Conclusão", laudo.conclusao)) if texto.strip()]
    if laudo.inspecao_id:
        relatorio["laudo"]["titulo_documento"] = titulo_documento
        relatorio["laudo"]["data_emissao"] = laudo.data_emissao
        relatorio["laudo"]["aprovacao"] = laudo.assinatura
        relatorio["rodape"] = configuracao.get("rodape", "")
        relatorio["consideracoes"] = textos_editoriais
    else:
        relatorio["cabecalho"]["titulo_documento"] = titulo_documento
        relatorio["cabecalho"]["versao"] = laudo.versao
        relatorio["cabecalho"]["data_emissao"] = laudo.data_emissao
        relatorio["cabecalho"]["aprovacao"] = laudo.assinatura
        relatorio["cabecalho"]["rodape"] = configuracao.get("rodape", "")
        texto_origem = relatorio["cabecalho"].get("consideracoes_finais", "")
        relatorio["cabecalho"]["consideracoes_finais"] = "\n\n".join(
            ([texto_origem] if texto_origem and texto_origem != laudo.conclusao else []) + textos_editoriais)
    relatorio["evidencias_laudo"] = evidencias
    return serializavel({
        "schema": "laudo_v1", "origem": origem,
        "laudo": {"id": laudo.pk, "numero": laudo.numero, "titulo": laudo.titulo, "versao": laudo.versao,
                   "status": laudo.status, "data_emissao": laudo.data_emissao,
                   "diagnostico": laudo.diagnostico, "recomendacoes": laudo.recomendacoes,
                   "conclusao": laudo.conclusao, "criticidade_geral": laudo.criticidade_geral,
                   "data_medicao_campo": laudo.data_medicao_campo, "data_upload_osps": laudo.data_upload_osps,
                   "data_upload_relatorio": laudo.data_upload_relatorio,
                   "cliente_nome": laudo.cliente.nome, "responsavel_nome": laudo.responsavel.nome,
                   "tipo_analise": tipo_analise_laudo(laudo),
                   "responsavel_conselho": laudo.responsavel.conselho_classe},
        "assinatura": laudo.assinatura,
        "template": {"id": template.pk if template else None, "nome": template.nome if template else "Padrão",
                     "versao": template.versao if template else 1,
                     "configuracao": configuracao},
        "relatorio": relatorio, "medicoes": medicoes, "evidencias": evidencias, "graficos": graficos,
    })
