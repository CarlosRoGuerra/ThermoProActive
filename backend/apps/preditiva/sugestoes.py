"""Sugestões técnicas assistidas — Anexo I 2.4.2.4 (complemento).

Duas fontes, sempre mostradas com a justificativa:
- REGRA: `RegraSugestao` cadastrada pelo Master (tecnologia + anomalia + componente
  opcional + criticidade mínima do equipamento). Aplica-se só com criticidade conhecida.
- HISTORICO: recomendações que os técnicos escolheram para a mesma combinação
  tecnologia + componente + anomalia, nos achados DO MESMO CLIENTE, quando a
  escolha aparece pelo menos `MIN_OCORRENCIAS` vezes. Mostra a contagem (n de N);
  não é probabilidade de acerto.

Nada é aplicado sozinho. O analista aceita, edita ou rejeita. A decisão é gravada
em `AceitacaoSugestao` com a evidência do momento, e serve para medir aderência.
Sem regra nem histórico, a lista fica vazia com o motivo: nunca há texto genérico.
"""
from collections import Counter

from django.db.models import Q

from apps.cadastros.models import TipoRecomendacao
from apps.coletas.models import Achado

from .models import AceitacaoSugestao, DecisaoSugestao, OrigemSugestao, RegraSugestao
from .risco import SEVERIDADE_SCORE, severidade_atual

#: Ocorrências mínimas de uma recomendação no histórico para virar sugestão.
#: Parâmetro provisório; o cliente confirma (docs/23).
MIN_OCORRENCIAS = 3
MAX_HISTORICO = 3


def _regras_aplicaveis(achado, cliente_id, criticidade, data=None):
    from django.utils import timezone

    if criticidade is None:
        return []
    data = data or timezone.localdate()
    carregamento = achado.item.carregamento
    qs = RegraSugestao.objects.filter(
        ativo=True, tecnologia_id=carregamento.tecnologia_id, tipo_anomalia_id=achado.tipo_anomalia_id,
    ).filter(
        Q(tipo_componente__isnull=True) | Q(tipo_componente_id=achado.tipo_componente_id),
        Q(cliente__isnull=True) | Q(cliente_id=cliente_id),
        Q(vigencia_inicio__isnull=True) | Q(vigencia_inicio__lte=data),
        Q(vigencia_fim__isnull=True) | Q(vigencia_fim__gte=data),
    ).select_related("recomendacao")
    return [r for r in qs.order_by("prioridade", "nome")
            if SEVERIDADE_SCORE[criticidade] >= SEVERIDADE_SCORE.get(r.criticidade_minima, 99)]


def _historico(achado, cliente_id):
    """Contagem das recomendações escolhidas em achados comparáveis do mesmo cliente."""
    carregamento = achado.item.carregamento
    qs = Achado.objects.filter(
        ativo=True, recomendacao__isnull=False, tipo_anomalia_id=achado.tipo_anomalia_id,
        item__carregamento__tecnologia_id=carregamento.tecnologia_id,
        item__carregamento__cliente_id=cliente_id,
    ).exclude(pk=achado.pk)
    qs = qs.filter(tipo_componente_id=achado.tipo_componente_id) if achado.tipo_componente_id \
        else qs.filter(tipo_componente__isnull=True)
    contagem = Counter(qs.values_list("recomendacao_id", flat=True))
    total = sum(contagem.values())
    return contagem, total


def sugestoes_para_achado(achado):
    """Lista de sugestões do achado e o motivo quando ela estiver vazia."""
    carregamento = achado.item.carregamento
    cliente_id = carregamento.cliente_id
    base = {"achado_id": achado.pk, "recomendacao_atual_id": achado.recomendacao_id}
    if achado.tipo_anomalia_id is None:
        return {**base, "sugestoes": [], "motivo": "anomalia_nao_classificada"}

    criticidade = severidade_atual(achado.item.equipamento_id)
    sugestoes = []
    for regra in _regras_aplicaveis(achado, cliente_id, criticidade):
        sugestoes.append({
            "origem": OrigemSugestao.REGRA,
            "recomendacao": {"id": regra.recomendacao_id, "nome": regra.recomendacao.nome},
            "regra": {"id": regra.pk, "nome": regra.nome, "validacao": regra.validacao, "fonte": regra.fonte},
            "contagem": None, "total": None, "frequencia": None,
            "justificativa": (
                f"Regra “{regra.nome}” ({regra.get_validacao_display().lower()}): anomalia "
                f"{achado.tipo_anomalia.nome}, criticidade atual {criticidade} "
                f"(regra a partir de {regra.get_criticidade_minima_display()})."
            ),
            "ja_selecionada": regra.recomendacao_id == achado.recomendacao_id,
        })

    contagem, total = _historico(achado, cliente_id)
    for recomendacao_id, n in contagem.most_common(MAX_HISTORICO):
        if n < MIN_OCORRENCIAS:
            break
        recomendacao = _recomendacao(recomendacao_id)
        sugestoes.append({
            "origem": OrigemSugestao.HISTORICO,
            "recomendacao": {"id": recomendacao_id, "nome": recomendacao.nome},
            "regra": None, "contagem": n, "total": total, "frequencia": round(n / total, 2),
            "justificativa": (
                f"Escolhida em {n} de {total} achados comparáveis deste cliente (mesma tecnologia, "
                f"componente e anomalia). Frequência histórica, não probabilidade de acerto."
            ),
            "ja_selecionada": recomendacao_id == achado.recomendacao_id,
        })

    motivo = "" if sugestoes else (
        "sem_regra_nem_historico" if criticidade is not None else "sem_condicao_classificada_e_sem_historico"
    )
    return {**base, "sugestoes": sugestoes, "motivo": motivo,
            "criticidade_atual": criticidade, "historico_total": total}


def _recomendacao(recomendacao_id):
    return TipoRecomendacao.objects.get(pk=recomendacao_id)


def registrar_decisao(achado, recomendacao_sugerida_id, origem, decisao, usuario,
                      recomendacao_final_id=None, justificativa=""):
    """Grava a decisão se a sugestão existir agora no achado. ValueError caso contrário."""
    atuais = sugestoes_para_achado(achado)
    alvo = next((s for s in atuais["sugestoes"]
                 if s["recomendacao"]["id"] == recomendacao_sugerida_id and s["origem"] == origem), None)
    if alvo is None:
        raise ValueError("Esta sugestão não existe mais para o achado; atualize a lista antes de decidir.")
    if decisao == DecisaoSugestao.EDITADA and recomendacao_final_id in (None, recomendacao_sugerida_id):
        raise ValueError("Uma decisão editada precisa de outra recomendação final.")
    if decisao == DecisaoSugestao.ACEITA:
        recomendacao_final_id = recomendacao_sugerida_id
    if decisao == DecisaoSugestao.REJEITADA:
        recomendacao_final_id = None
    regra_id = alvo["regra"]["id"] if alvo["regra"] else None
    return AceitacaoSugestao.objects.create(
        achado=achado, recomendacao_sugerida_id=recomendacao_sugerida_id, origem=origem,
        regra_id=regra_id, decisao=decisao, recomendacao_final_id=recomendacao_final_id,
        justificativa=justificativa, usuario=usuario,
        evidencia={
            "contagem": alvo["contagem"], "total": alvo["total"], "frequencia": alvo["frequencia"],
            "criticidade_atual": atuais.get("criticidade_atual"), "regra_validacao": (alvo["regra"] or {}).get("validacao"),
        },
    )


def aderencia(queryset=None):
    """Taxa de aderência por origem, usando a ÚLTIMA decisão de cada (achado, sugestão, origem)."""
    qs = queryset if queryset is not None else AceitacaoSugestao.objects.all()
    ultimas = {}
    for registro in qs.order_by("criado_em", "pk"):
        ultimas[(registro.achado_id, registro.recomendacao_sugerida_id, registro.origem)] = registro
    resumo = {origem: {"total": 0, "aceitas": 0, "editadas": 0, "rejeitadas": 0, "taxa_aderencia": None}
              for origem in OrigemSugestao.values}
    for registro in ultimas.values():
        bloco = resumo[registro.origem]
        bloco["total"] += 1
        chave = {DecisaoSugestao.ACEITA: "aceitas", DecisaoSugestao.EDITADA: "editadas",
                 DecisaoSugestao.REJEITADA: "rejeitadas"}[registro.decisao]
        bloco[chave] += 1
    for bloco in resumo.values():
        if bloco["total"]:
            bloco["taxa_aderencia"] = round((bloco["aceitas"] + bloco["editadas"]) / bloco["total"], 2)
    return resumo
