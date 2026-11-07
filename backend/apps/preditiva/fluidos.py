"""Tendência e projeção de um parâmetro de fluido — Anexo I 2.4.1.3 (complemento).

Série: campanhas anteriores do MESMO equipamento, ensaio e parâmetro, com o mesmo
contexto comparável já registrado no resultado (`comparacao_fluido`), mesma unidade
e mesmo método. Campanha sem contexto registrado não entra: sem contexto, a tendência
é inconclusiva (o cálculo histórico da ficha já funciona assim).

Limite: referência vigente do escopo da coleta (`ResolvedorReferencias`), apenas dos
tipos MÁXIMO (limite acima é pior) e MÍNIMO (abaixo é pior) com valor numérico.
Variação percentual, código ISO, qualitativo e outros tipos não têm limite fixo
para projetar: ficam sem critério.
"""
from datetime import datetime, time, timezone as dt_timezone

from apps.coletas.analise_preditiva import numero_finito
from apps.ensaios.models import ResultadoEnsaio, SituacaoResultado, TipoReferencia, ValorParametro
from apps.ensaios.relatorio_fluidos import ResolvedorReferencias

from .tendencia import PARAMETROS_PADRAO, configuracao_vigente, projetar_serie

VERSAO_FLUIDOS = "tendencia_fluido_v1"
TIPOS_COM_LIMITE = {TipoReferencia.MAXIMO: "SUPERIOR", TipoReferencia.MINIMO: "INFERIOR"}


def _instante(data):
    return datetime.combine(data, time(), tzinfo=dt_timezone.utc)


def _contexto_da_campanha(resultado):
    return (resultado.contexto_tecnico or {}).get("comparacao_fluido")


def analisar_valor_fluido(resultado: ResultadoEnsaio, codigo: str):
    """Tendência do parâmetro `codigo` na campanha `resultado`. Não grava nada."""
    from apps.ensaios.models import ParametroEnsaio

    parametro = ParametroEnsaio.objects.filter(ensaio_id=resultado.ensaio_id, codigo=codigo).first()
    atual = ValorParametro.objects.filter(resultado=resultado, parametro=parametro).first() if parametro else None
    cfg = configuracao_vigente(resultado.item.carregamento.cliente_id, resultado.item.carregamento.data_coleta)
    base = {"versao": VERSAO_FLUIDOS, "parametro": codigo, "resultado_id": resultado.pk,
            "configuracao": cfg, "limite": {"validado": False, "motivo": "", "valores": [], "referencia_id": None}}
    if parametro is None or atual is None or atual.estado != "MEDIDO" or numero_finito(atual.valor) is None:
        base["serie"] = {"versao": "projecao_fluido", "status": "INSUFICIENTE", "motivo": "leitura_atual_ausente_ou_invalida",
                         "n": 0, "pontos": [], "projecoes": [], "estatisticas": {}, "modelo": None,
                         "comparacao_modelos": None}
        return base

    contexto = _contexto_da_campanha(resultado)
    unidade, metodo = parametro.unidade, atual.metodo or parametro.norma
    data_atual = resultado.item.carregamento.data_coleta
    pontos = [(data_atual, float(atual.valor), resultado.pk)]
    if contexto:
        candidatos = (ValorParametro.objects.filter(
            parametro_id=parametro.pk, resultado__ensaio_id=resultado.ensaio_id,
            resultado__situacao=SituacaoResultado.REALIZADO, resultado__ativo=True,
            resultado__item__equipamento_id=resultado.item.equipamento_id,
            resultado__item__carregamento__data_coleta__lt=data_atual,
        ).exclude(resultado_id=resultado.pk).select_related(
            "resultado__item__carregamento", "parametro",
        ).order_by("-resultado__item__carregamento__data_coleta", "-pk")[:200])
        for v in candidatos:
            if len(pontos) >= cfg["janela"]:
                break
            r = v.resultado
            if _contexto_da_campanha(r) != contexto or v.estado != "MEDIDO":
                continue
            valor = numero_finito(v.valor)
            if valor is None or v.parametro.unidade != unidade or (v.metodo or v.parametro.norma) != metodo:
                continue
            pontos.append((r.item.carregamento.data_coleta, float(valor), r.pk))
    pontos.sort(key=lambda p: (p[0], p[2]))
    if not contexto:
        base["serie"] = {"versao": "projecao_fluido", "status": "INSUFICIENTE",
                         "motivo": "contexto_historico_nao_registrado", "n": len(pontos), "pontos": [],
                         "projecoes": [], "estatisticas": {}, "modelo": None, "comparacao_modelos": None}
        return base

    coleta = getattr(resultado.item, "coleta_fluido", None)
    escopo = {"cliente_id": resultado.item.carregamento.cliente_id,
              "equipamento_id": resultado.item.equipamento_id,
              "produto_id": coleta.produto_id if coleta else None,
              "aplicacao": coleta.aplicacao if coleta else "",
              "tipo_equipamento_id": resultado.item.equipamento.tipo_equipamento_id,
              "data": data_atual}
    referencia = ResolvedorReferencias([parametro.pk]).para(parametro.pk, **escopo)
    limites = []
    if referencia is not None and referencia.tipo in TIPOS_COM_LIMITE:
        if referencia.limite_alerta is not None:
            limites.append({"nivel": "ALERTA", "valor": referencia.limite_alerta,
                            "sentido": TIPOS_COM_LIMITE[referencia.tipo]})
        if referencia.limite_critico is not None:
            limites.append({"nivel": "CRITICO", "valor": referencia.limite_critico,
                            "sentido": TIPOS_COM_LIMITE[referencia.tipo]})
        base["limite"].update(validado=bool(limites), referencia_id=referencia.pk,
                              valores=[{"nivel": x["nivel"], "valor": str(x["valor"]), "sentido": x["sentido"]}
                                       for x in limites])
    if not limites:
        base["limite"]["motivo"] = "sem_limite_fixo_para_projetar"

    serie = projetar_serie([_instante(p[0]) for p in pontos], [p[1] for p in pontos], limites,
                           {**PARAMETROS_PADRAO, **{k: cfg[k] for k in PARAMETROS_PADRAO}})
    for ponto, pk in zip(serie["pontos"], [p[2] for p in pontos]):
        ponto["resultado_id"] = pk
    base["serie"] = serie
    return base
