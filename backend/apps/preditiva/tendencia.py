"""Tendência e projeção até o limite de alarme — Anexo I 2.4.1.3.

Duas camadas:
- `projetar_serie` é pura: recebe instantes, valores e limites, e devolve o
  status estatístico, a comparação de modelos, as projeções com intervalo de
  confiança e o texto que a tela e o laudo devem mostrar.
- `analisar_medicao` lê o banco: monta a série comparável (mesmo contexto exato
  do motor de histórico em `coletas/analise_preditiva.py`), resolve o limite
  vigente e chama a camada pura.

Regras de honestidade (ver docs/23):
- Não há estimativa sem limite cadastrado e validado. Vibração usa o critério
  vigente de `apps.cadastros.criterios`; termografia e demais técnicas usam
  `LimiteAlarmeSerie`. Sem isso, o resultado é SEM_CRITERIO e nenhuma data é dada.
- Inclinação sem significância estatística (95%) ou ajuste abaixo do R² ajustado
  mínimo não gera projeção: o status é SEM_TENDENCIA, nunca “normal”.
- A data estimada é da RETA da medição. Não é probabilidade de falha, vida útil
  remanescente nem diagnóstico. Todo resultado traz esse texto.
"""
import math
from datetime import timedelta

from .estatistica import (
    atipicos,
    banda_confianca,
    escolher_modelo,
    inclinacao_significativa,
    inverter_para,
    primeiro_x_que_atinge,
    t_critico,
    valor_em,
)

VERSAO = "tendencia_v1"

TEXTO_LIMITE = (
    "Estimativa estatística da medição, não probabilidade de falha, vida útil remanescente "
    "ou diagnóstico. Depende de série comparável e do limite cadastrado."
)

#: Parâmetros estatísticos da plataforma enquanto o cliente não confirma os seus.
#: Não são limites de alarme. Origem registrada no resultado.
PARAMETROS_PADRAO = {
    "pontos_minimos": 4,
    "janela": 8,
    "r2_minimo": 0.5,
    "horizonte_dias": 365,
    "margem_modelo": 0.05,
    "origem": "padrao_provisorio",
}


def _iso(instante):
    return instante.isoformat() if instante is not None else None


def _data_em(origem, dias: float):
    return origem + timedelta(seconds=dias * 86400)


def projetar_serie(instantes, valores, limites, cfg=None):
    """Análise estatística pura de uma série com limites de alarme.

    instantes: datetimes em ordem crescente (o último é a medição analisada).
    valores: floats finitos, mesma ordem.
    limites: lista de {"nivel": str, "valor": float, "sentido": "SUPERIOR"|"INFERIOR"}.
    cfg: parâmetros (ver PARAMETROS_PADRAO).
    """
    cfg = {**PARAMETROS_PADRAO, **(cfg or {})}
    n = len(valores)
    marcados = set(atipicos(valores))
    resultado = {
        "versao": VERSAO, "status": "INSUFICIENTE", "motivo": "", "n": n,
        "parametros": {k: cfg[k] for k in PARAMETROS_PADRAO},
        "pontos": [{"indice": i, "data_hora": _iso(t), "valor": str(v), "atipico": i in marcados}
                   for i, (t, v) in enumerate(zip(instantes, valores))],
        "modelo": None, "comparacao_modelos": None, "estatisticas": {},
        "projecoes": [], "texto": TEXTO_LIMITE,
    }
    if n < cfg["pontos_minimos"]:
        resultado["motivo"] = "pontos_insuficientes"
        return resultado
    origem = instantes[0]
    xs = [(t - origem).total_seconds() / 86400 for t in instantes]
    if len(set(valores)) == 1:
        resultado.update(status="SERIE_CONSTANTE", motivo="valores_iguais_sem_variacao")
        return resultado
    ajuste, comparacao = escolher_modelo(xs, valores, cfg["margem_modelo"])
    resultado["comparacao_modelos"] = comparacao
    if ajuste is None:
        resultado["motivo"] = "sem_variacao_temporal"
        return resultado

    t_stat, significativa = inclinacao_significativa(ajuste)
    t = t_critico(ajuste["gl"])
    resultado["modelo"] = ajuste["modelo"]
    resultado["estatisticas"] = {
        "r2": _arred(ajuste["r2"]), "r2_ajustado": _arred(ajuste["r2_ajustado"]),
        "estatistica_t_inclinacao": _arred(t_stat) if t_stat != float("inf") else "infinita",
        "t_critico_95": t, "graus_liberdade": ajuste["gl"],
        "inclinacao_por_dia": _arred(ajuste["b"]) if ajuste["modelo"] == "linear" else None,
        "fator_crescimento_por_dia": _arred(math.exp(ajuste["b"])) if ajuste["modelo"] == "exponencial" else None,
        "unidade_inclinacao": "unidade do valor por dia" if ajuste["modelo"] == "linear" else "fator por dia",
    }

    if not significativa:
        resultado.update(status="SEM_TENDENCIA", motivo="inclinacao_nao_significativa_95")
        return resultado
    if ajuste["r2_ajustado"] is None or ajuste["r2_ajustado"] < cfg["r2_minimo"]:
        resultado.update(status="SEM_TENDENCIA", motivo="ajuste_abaixo_do_r2_minimo")
        return resultado

    sobe = ajuste["b"] > 0
    resultado.update(status="TENDENCIA", motivo="inclinacao_significativa_95",
                     sentido="SOBE" if sobe else "DESCE")
    if not limites:
        resultado["motivo"] = "tendencia_sem_limite_cadastrado"
        return resultado
    resultado["projecoes"] = [
        _projetar_limite(ajuste, xs, valores, origem, limite, cfg, t) for limite in limites
    ]
    return resultado


def _projetar_limite(ajuste, xs, valores, origem, limite, cfg, t):
    """Estado da série frente a UM limite. Só estima data com inclinação na direção dele."""
    alvo = float(limite["valor"])
    superior = limite.get("sentido", "SUPERIOR") == "SUPERIOR"
    base = {"nivel": limite["nivel"], "limite": str(limite["valor"]), "sentido": "SUPERIOR" if superior else "INFERIOR"}
    if (valores[-1] >= alvo) if superior else (valores[-1] <= alvo):
        return {**base, "estado": "ATINGIDO", "data_observada": _iso(_data_em(origem, xs[-1])),
                "data_estimada": None, "intervalo_confianca": None, "dias_ate_limite": 0.0,
                "motivo": "ultima_medicao_ja_atingiu_o_limite"}
    if (ajuste["b"] > 0) != superior:
        return {**base, "estado": "NAO_CONVERGE", "data_estimada": None, "intervalo_confianca": None,
                "dias_ate_limite": None, "motivo": "tendencia_se_afasta_do_limite"}
    x_alvo = inverter_para(ajuste, alvo)
    if x_alvo is None:
        return {**base, "estado": "NAO_CONVERGE", "data_estimada": None, "intervalo_confianca": None,
                "dias_ate_limite": None, "motivo": "limite_nao_representavel_no_modelo"}
    x_ultimo = xs[-1]
    if x_alvo <= x_ultimo:
        return {**base, "estado": "ATINGIDO", "data_estimada": None, "intervalo_confianca": None,
                "dias_ate_limite": 0.0, "motivo": "tendencia_ja_ultrapassa_o_limite"}
    horizonte = float(cfg["horizonte_dias"])
    if x_alvo - x_ultimo > horizonte:
        return {**base, "estado": "FORA_DO_HORIZONTE", "data_estimada": None, "intervalo_confianca": None,
                "dias_ate_limite": round(x_alvo - x_ultimo, 1),
                "motivo": f"estimativa_alem_do_horizonte_de_{int(horizonte)}_dias"}

    # Intervalo de confiança do cruzamento: o mais cedo usa a borda da banda que
    # se aproxima do limite primeiro; o mais tarde, a borda oposta. Bisseção
    # dentro do horizonte. Índice 0 = inferior, 1 = superior da banda.
    borda_cedo = 1 if superior else 0
    borda_tarde = 0 if superior else 1
    x_limite = x_ultimo + horizonte
    cedo = primeiro_x_que_atinge(
        lambda x: banda_confianca(ajuste, x, t)[borda_cedo], alvo, x_ultimo, x_limite, superior,
    )
    tarde = primeiro_x_que_atinge(
        lambda x: banda_confianca(ajuste, x, t)[borda_tarde], alvo, x_ultimo, x_limite, superior,
    )
    return {
        **base, "estado": "ESTIMADO",
        "data_estimada": _iso(_data_em(origem, x_alvo)),
        "intervalo_confianca": [_iso(_data_em(origem, cedo)) if cedo is not None else None,
                                _iso(_data_em(origem, tarde)) if tarde is not None else None],
        "dias_ate_limite": round(x_alvo - x_ultimo, 1),
        "motivo": "reta_de_tendencia_cruza_o_limite",
    }


def _arred(valor, casas=6):
    return None if valor is None else round(valor, casas)


# =============================================================================
# Leitura do banco: série comparável, limite vigente e análise de uma medição.
# =============================================================================

def modalidade_de(medicao) -> str:
    return {"MedicaoVibracao": "vibracao", "MedicaoTermografia": "termografia"}.get(type(medicao).__name__, "tecnica")


def campo_nome(medicao) -> str:
    nome = type(medicao).__name__
    if nome == "MedicaoVibracao":
        return "velocidade_rms"
    if nome == "MedicaoTermografia":
        return "delta_t"
    return medicao.grandeza


def chave_grupo(medicao) -> str:
    """Agrupamento de séries do mesmo ponto; cada grupo recebe a leitura mais recente."""
    partes = [modalidade_de(medicao), medicao.equipamento_id, medicao.componente_id, medicao.ponto_medicao,
              medicao.instrumento_id]
    nome = type(medicao).__name__
    if nome == "MedicaoVibracao":
        partes += [medicao.subtipo, medicao.direcao, medicao.parametro, medicao.numero_mancal]
    elif nome == "MedicaoTermografia":
        partes += [medicao.sistema]
    else:
        partes += [medicao.tipo, medicao.subtipo, medicao.grandeza]
    return "|".join(str(p) for p in partes)


def configuracao_vigente(cliente_id, data=None):
    """Parâmetros estatísticos vigentes: os do cliente antes dos globais; sem cadastro, o padrão provisório."""
    from django.db.models import Q
    from django.utils import timezone

    from .models import ConfiguracaoTendencia

    data = data or timezone.localdate()
    qs = ConfiguracaoTendencia.objects.filter(ativo=True).filter(
        Q(vigencia_inicio__isnull=True) | Q(vigencia_inicio__lte=data),
        Q(vigencia_fim__isnull=True) | Q(vigencia_fim__gte=data),
    )
    qs = qs.filter(Q(cliente__isnull=True) | Q(cliente_id=cliente_id)) if cliente_id \
        else qs.filter(cliente__isnull=True)
    candidatos = sorted(qs, key=lambda c: (
        0 if c.cliente_id else 1, -(c.vigencia_inicio.toordinal() if c.vigencia_inicio else 0), -c.pk,
    ))
    if not candidatos:
        return {**PARAMETROS_PADRAO, "validacao": "PROVISORIA", "fonte": ""}
    c = candidatos[0]
    return {
        "pontos_minimos": c.pontos_minimos, "janela": c.janela, "r2_minimo": float(c.r2_minimo),
        "horizonte_dias": c.horizonte_dias, "margem_modelo": float(c.margem_modelo),
        "origem": f"cadastro_{c.pk}", "validacao": c.validacao, "fonte": c.fonte,
    }


def serie_comparavel(medicao, janela):
    """(instantes, valores, ids, motivo) em ordem crescente, terminando na medição analisada.

    Usa o mesmo contexto exato do histórico (`contexto_medicao`): instrumento, ponto,
    regime e parâmetros iguais. Campanhas posteriores ou de data posterior à inspeção
    ficam de fora. Valor ausente ou inválido não vira zero.
    """
    from apps.coletas.analise_preditiva import campo_valor, contexto_medicao, numero_finito

    campo = campo_valor(medicao)
    atual = numero_finito(getattr(medicao, campo))
    if atual is None or (campo == "velocidade_rms" and atual < 0):
        return [], [], [], "leitura_ausente_ou_invalida"
    if medicao.instrumento_id is None:
        return [], [], [], "instrumento_nao_informado"
    contexto = contexto_medicao(medicao)
    filtros = {k: v for k, v in contexto.items() if medicao._meta.get_field(k).get_internal_type() != "JSONField"}
    candidatos = type(medicao).objects.filter(
        **filtros, data_hora__lt=medicao.data_hora, inspecao__data__lte=medicao.inspecao.data,
    ).exclude(pk=medicao.pk).select_related("inspecao").order_by("-data_hora", "-pk")
    pontos = [(medicao.data_hora, float(atual), medicao.pk)]
    for anterior in candidatos.iterator():
        if len(pontos) >= janela:
            break
        valor = numero_finito(getattr(anterior, campo))
        if valor is None or (campo == "velocidade_rms" and valor < 0):
            continue
        if contexto_medicao(anterior) != contexto:
            continue
        pontos.append((anterior.data_hora, float(valor), anterior.pk))
    pontos.reverse()
    motivo = "" if len(pontos) > 1 else "sem_historico_comparavel"
    return [p[0] for p in pontos], [p[1] for p in pontos], [p[2] for p in pontos], motivo


def limites_medicao(medicao):
    """Limites de alarme aplicáveis à série e o critério que os sustenta.

    Vibração: critério normativo vigente (ALERTA acima de B/C, CRITICO acima de C/D), com
    as mesmas condições de aplicabilidade da classificação. Demais modalidades: só
    `LimiteAlarmeSerie` com situação VALIDADA. Sem isso, `limites` fica vazio.
    """
    from apps.cadastros.criterios import criterio_vigente, faixas_vigentes, resumo_criterio, suporte_do_equipamento
    from apps.cadastros.models import OrigemCriterio

    if type(medicao).__name__ == "MedicaoVibracao":
        eq = medicao.equipamento
        suporte = suporte_do_equipamento(eq)
        cliente_id = eq.setor.area.cliente_id
        criterio = criterio_vigente(eq.classe_iso, data=medicao.inspecao.data, cliente_id=cliente_id,
                                    suporte=suporte) if eq.classe_iso else None
        aplicavel = criterio is not None and criterio.origem != OrigemCriterio.LEGADO \
            and not (eq.classe_iso in ("G1", "G2") and not suporte)
        if not aplicavel:
            return {"limites": [], "criterio": None, "fonte": "", "validado": False,
                    "motivo": "criterio_ou_base_nao_confirmados"}
        faixas = faixas_vigentes(eq.classe_iso, data=medicao.inspecao.data, cliente_id=cliente_id, suporte=suporte)
        return {
            "limites": [
                {"nivel": "ALERTA", "valor": faixas["B"], "sentido": "SUPERIOR"},
                {"nivel": "CRITICO", "valor": faixas["C"], "sentido": "SUPERIOR"},
            ],
            "criterio": resumo_criterio(criterio), "fonte": criterio.fonte, "validado": True, "motivo": "",
        }

    from django.db.models import Q

    from .models import LimiteAlarmeSerie, Validacao

    modalidade = modalidade_de(medicao)
    # Modalidade do cadastro = tipo da própria medição (TipoAnalise). Termografia tem tipo fixo.
    tipo = "TERMOGRAFIA" if modalidade == "termografia" else medicao.tipo
    grandeza = "delta_t" if modalidade == "termografia" else medicao.grandeza
    unidade = "°C" if modalidade == "termografia" else medicao.unidade
    eq = medicao.equipamento
    cliente_id = medicao.inspecao.cliente_id
    data = medicao.inspecao.data
    sistema = getattr(medicao, "sistema", "") or ""
    qs = LimiteAlarmeSerie.objects.filter(ativo=True, modalidade=tipo, grandeza=grandeza, unidade=unidade).filter(
        Q(cliente__isnull=True) | Q(cliente_id=cliente_id),
        Q(tipo_equipamento__isnull=True) | Q(tipo_equipamento_id=eq.tipo_equipamento_id),
        Q(equipamento__isnull=True) | Q(equipamento_id=eq.pk),
        Q(sistema="") | Q(sistema=sistema),
        Q(vigencia_inicio__isnull=True) | Q(vigencia_inicio__lte=data),
        Q(vigencia_fim__isnull=True) | Q(vigencia_fim__gte=data),
    )
    # Mais específico primeiro: equipamento, tipo de equipamento, sistema, cliente, vigência.
    escolhidos = sorted(qs, key=lambda c: (
        0 if c.equipamento_id else 1, 0 if c.tipo_equipamento_id else 1, 0 if c.sistema else 1,
        0 if c.cliente_id else 1, -(c.vigencia_inicio.toordinal() if c.vigencia_inicio else 0), -c.pk,
    ))
    if not escolhidos:
        return {"limites": [], "criterio": None, "fonte": "", "validado": False, "motivo": "sem_limite_cadastrado"}
    limite = escolhidos[0]
    lista = []
    if limite.valor_alerta is not None:
        lista.append({"nivel": "ALERTA", "valor": limite.valor_alerta, "sentido": limite.sentido})
    if limite.valor_critico is not None:
        lista.append({"nivel": "CRITICO", "valor": limite.valor_critico, "sentido": limite.sentido})
    validado = limite.validacao == Validacao.VALIDADA
    return {
        "limites": lista if validado else [],
        "criterio": {"id": limite.pk, "origem": limite.origem, "origem_display": limite.get_origem_display(),
                     "validacao": limite.validacao, "sentido": limite.sentido},
        "fonte": limite.fonte, "validado": validado,
        "motivo": "" if validado else "limite_nao_validado",
    }


def analisar_medicao(medicao):
    """Tendência de UMA medição: série comparável, limites e projeção. Não grava nada."""
    cfg = configuracao_vigente(medicao.inspecao.cliente_id, medicao.inspecao.data)
    instantes, valores, ids, motivo = serie_comparavel(medicao, cfg["janela"])
    limite = limites_medicao(medicao)
    if motivo:
        serie = {"versao": VERSAO, "status": "INSUFICIENTE", "motivo": motivo, "n": len(valores),
                 "parametros": {k: cfg[k] for k in PARAMETROS_PADRAO}, "pontos": [], "modelo": None,
                 "comparacao_modelos": None, "estatisticas": {}, "projecoes": [], "texto": TEXTO_LIMITE}
    else:
        serie = projetar_serie(instantes, valores, limite["limites"], cfg)
        for ponto, pk in zip(serie["pontos"], ids):
            ponto["medicao_id"] = pk
    return {
        "modalidade": modalidade_de(medicao), "medicao_id": medicao.pk,
        "chave_grupo": chave_grupo(medicao), "grandeza": campo_nome(medicao),
        "ponto_medicao": medicao.ponto_medicao, "equipamento_id": medicao.equipamento_id,
        "criticidade": medicao.criticidade or "", "classificacao_status": medicao.classificacao_status,
        "configuracao": cfg,
        "limite": {"validado": limite["validado"], "motivo": limite["motivo"], "fonte": limite["fonte"],
                   "criterio": limite["criterio"],
                   "valores": [{"nivel": x["nivel"], "valor": str(x["valor"]), "sentido": x["sentido"]}
                               for x in limite["limites"]]},
        "serie": serie,
    }
