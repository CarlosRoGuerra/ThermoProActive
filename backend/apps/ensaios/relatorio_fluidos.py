"""
Módulo do relatório de fluidos lubrificantes e hidráulicos (`FLUIDO_LUBRIFICANTE`).

Mesmo shell das outras tecnologias (capa, carta, KPIs, relação de equipamentos,
paginação e PDF). Por equipamento da rota (item):

    Registro da coleta da amostra → FQ → EF → CP

Cada ficha é uma tabela "parâmetro × coleta": as colunas são as últimas coletas
do mesmo equipamento (até 6, a atual por último) — o histórico é o que dá sentido
a um resultado de óleo. Cada parâmetro mostra a referência cadastrada que vale
para aquele equipamento/fluido/cliente na data da coleta (com origem e vigência),
o estado (Rotina/Alerta/Crítica) e a tendência. Sem referência, o valor sai sem
classificação; a criticidade do laudo continua sendo decisão do analista.

CP: contagens por mL (> 4, > 6, > 14 µm(c) e as opcionais) e o código ISO 4406 de
cada coleta, comparado com a meta de limpeza quando há meta cadastrada.
"""
from collections import Counter, defaultdict
from datetime import date

from apps.cadastros.models import Equipamento, ModuloTecnico

from . import calculos_fluidos as cf
from . import grau_risco_fluidos as gr
from .carta import CONSIDERACOES_FLUIDO, CONTEUDO_FLUIDO, GLOSSARIO_FLUIDO
from .models import (
    AplicacaoFluido,
    ColetaFluido,
    Ensaio,
    ReferenciaParametro,
    ResultadoEnsaio,
    SituacaoResultado,
    TipoReferencia,
)
from .relatorio import (
    HISTORICO_MAXIMO,
    STATUS_ROTULO,
    ModuloEnsaiosLaboratoriais,
    _Campanha,
    _distribuicao,
    _instrumento,
    _lista,
    rotulo_condicao,
)

REALIZADO = SituacaoResultado.REALIZADO
SIGLA_CP = "CP"
CODIGO_ISO4406 = "ISO4406"
SITUACOES_FINAIS = (REALIZADO, SituacaoResultado.NAO_COLETADO, SituacaoResultado.NAO_REALIZADO)

STATUS_FLUIDO_ROTULO = {
    cf.ROTINA: "Dentro das referências",
    cf.ALERTA: "Alerta",
    cf.CRITICA: "Crítica",
    "SEM_CRITERIO": "Sem referência cadastrada",
    SituacaoResultado.NAO_COLETADO: STATUS_ROTULO[SituacaoResultado.NAO_COLETADO],
    SituacaoResultado.NAO_REALIZADO: STATUS_ROTULO[SituacaoResultado.NAO_REALIZADO],
    SituacaoResultado.SEM_RESULTADO: STATUS_ROTULO[SituacaoResultado.SEM_RESULTADO],
}

ESCOPO_ROTULO = (("equipamento_id", "Equipamento"), ("produto_id", "Fluido"), ("cliente_id", "Cliente"),
                 ("aplicacao", "Aplicação"))


# ------------------------------- Referências ---------------------------------
class ResolvedorReferencias:
    """
    Escolhe a referência de cada parâmetro: entre as ativas, em vigor na data da
    coleta e com o escopo compatível (campo vazio = qualquer), a mais específica —
    equipamento (8) > fluido (4) > cliente (2) > aplicação (1); empate, a de
    vigência mais recente. Carrega tudo de uma vez.
    """

    def __init__(self, parametros_ids):
        self.por_parametro = defaultdict(list)
        for r in ReferenciaParametro.objects.ativos().filter(parametro_id__in=list(parametros_ids)):
            self.por_parametro[r.parametro_id].append(r)

    def para(self, parametro_id, *, data=None, cliente_id=None, equipamento_id=None, produto_id=None,
             aplicacao=""):
        candidatos = []
        for r in self.por_parametro.get(parametro_id, ()):
            if data and ((r.vigencia_inicio and r.vigencia_inicio > data) or (r.vigencia_fim and r.vigencia_fim < data)):
                continue
            if (r.cliente_id and r.cliente_id != cliente_id) or (r.equipamento_id and r.equipamento_id != equipamento_id):
                continue
            if (r.produto_id and r.produto_id != produto_id) or (r.aplicacao and r.aplicacao != aplicacao):
                continue
            peso = 8 * bool(r.equipamento_id) + 4 * bool(r.produto_id) + 2 * bool(r.cliente_id) + bool(r.aplicacao)
            candidatos.append((peso, r.vigencia_inicio or date.min, r.id, r))
        return max(candidatos, key=lambda c: c[:3])[3] if candidatos else None


def _num(v, casas):
    if v is None:
        return ""
    texto = f"{v:,.{casas}f}"
    return texto.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def texto_referencia(r, casas=2, unidade="") -> str:
    """Referência como a ficha imprime ("Alerta > 50,0 · Crítico > 100,0 ppm")."""
    if r is None:
        return ""
    u = f" {unidade}" if unidade else ""
    partes = []
    if r.tipo == TipoReferencia.MAXIMO:
        if r.limite_alerta is not None:
            partes.append(f"Alerta > {_num(r.limite_alerta, casas)}")
        if r.limite_critico is not None:
            partes.append(f"Crítico > {_num(r.limite_critico, casas)}")
        return " · ".join(partes) + (u if partes else "")
    if r.tipo == TipoReferencia.MINIMO:
        if r.limite_alerta is not None:
            partes.append(f"Alerta < {_num(r.limite_alerta, casas)}")
        if r.limite_critico is not None:
            partes.append(f"Crítico < {_num(r.limite_critico, casas)}")
        return " · ".join(partes) + (u if partes else "")
    if r.tipo == TipoReferencia.VARIACAO:
        partes.append(f"Base {_num(r.valor_base, casas)}{u}")
        if r.limite_alerta is not None:
            partes.append(f"Alerta ±{_num(r.limite_alerta, 0)}%")
        if r.limite_critico is not None:
            partes.append(f"Crítico ±{_num(r.limite_critico, 0)}%")
        return " · ".join(partes)
    if r.tipo == TipoReferencia.CODIGO_ISO:
        texto = f"Meta {r.referencia_texto}"
        if r.limite_critico is not None:
            texto += f" · Crítico a partir de +{_num(r.limite_critico, 0)}"
        return texto
    return r.referencia_texto


def resumo_referencia(r, casas=2, unidade=""):
    if r is None:
        return None
    escopo = next((rotulo for campo, rotulo in ESCOPO_ROTULO if getattr(r, campo)), "Geral")
    return {
        "id": r.id, "tipo": r.tipo, "tipo_display": r.get_tipo_display(),
        "valor_base": r.valor_base, "limite_alerta": r.limite_alerta, "limite_critico": r.limite_critico,
        "referencia_texto": r.referencia_texto, "texto": texto_referencia(r, casas, unidade),
        "origem": r.origem, "origem_display": r.get_origem_display(), "fonte": r.fonte,
        "vigencia_inicio": r.vigencia_inicio, "vigencia_fim": r.vigencia_fim, "escopo": escopo,
    }


# --------------------------------- Fichas ------------------------------------
def _celula(v):
    if v is None:
        return {"valor": None, "texto": "", "estado": "", "metodo": ""}
    return {"valor": v.valor, "texto": v.valor_texto, "estado": v.estado, "metodo": v.metodo}


def _contexto_referencia(campanha, equipamento):
    """Escopo da referência: data, cliente, equipamento e o fluido/aplicação da coleta da campanha."""
    coleta = campanha.coleta_fluido if campanha else None
    cliente_id = equipamento.setor.area.cliente_id if equipamento.setor_id else None
    return {
        "data": campanha.data if campanha else None, "cliente_id": cliente_id, "equipamento_id": equipamento.id,
        "produto_id": coleta.produto_id if coleta else None, "aplicacao": coleta.aplicacao if coleta else "",
    }


def _status_ficha(resultado, statuses):
    if resultado is None:
        return SituacaoResultado.SEM_RESULTADO
    if resultado.situacao != REALIZADO:
        return resultado.situacao
    return cf.pior(statuses) or "SEM_CRITERIO"


def _texto_valor(linha, celula):
    if celula["estado"] and celula["estado"] != "MEDIDO":
        return celula["texto"] or celula["estado"]
    return _num(celula["valor"], linha["casas"]) if celula["valor"] is not None else celula["texto"]


def observacoes_geradas(linhas, corpo) -> list:
    """
    Observações analíticas montadas SÓ com o que as referências cadastradas apontaram
    (o analista continua escrevendo a conclusão). Um item por parâmetro fora da referência.
    """
    obs = []
    for linha in linhas:
        if linha["status"] not in (cf.ALERTA, cf.CRITICA) or not linha["valores"]:
            continue
        valor = _texto_valor(linha, linha["valores"][-1])
        unidade = f" {linha['unidade']}" if linha["unidade"] else ""
        rotulo = "em alerta" if linha["status"] == cf.ALERTA else "crítico"
        texto = f"{linha['nome']}: {valor}{unidade}, {rotulo}"
        if linha["referencia"]:
            texto += f" (referência: {linha['referencia']['texto']})"
        var, tend = linha["variacao_pct"], linha["tendencia"]
        if var is not None:
            texto += f"; {'+' if var > 0 else ''}{_num(var, 1)}% em relação ao valor de base"
        elif tend and tend["pct_anterior"] is not None:
            texto += f"; {'+' if tend['pct_anterior'] > 0 else ''}{_num(tend['pct_anterior'], 1)}% em relação à coleta anterior"
        obs.append(texto + ".")
    if corpo.get("tipo") == "CP" and corpo.get("situacao_meta") == "FORA":
        atual = next((c for c in corpo["codigos"] if c["atual"]), None)
        obs.append(f"Código de limpeza ISO 4406 {atual['codigo'] if atual else ''} acima da meta "
                   f"{corpo['meta']['referencia_texto']} em {corpo['excesso_meta']} "
                   f"{'grau' if corpo['excesso_meta'] == 1 else 'graus'}.")
    return obs


def montar_ficha_fluido(ensaio, params, resultado, atual, campanhas, equipamento, resolvedor, solicitado) -> dict:
    """Ficha de um ensaio (FQ, EF ou CP) de uma amostra, com o histórico das coletas."""
    escopo = _contexto_referencia(atual, equipamento)
    digitados = [p for p in params if not p.calculado]
    # CP: as contagens são avaliadas juntas, pelo código ISO 4406 contra a meta —
    # contagem sem referência própria não é "parâmetro sem referência".
    avaliado_pelo_codigo = {c for c in cf.TAMANHOS_CODIGO + ("P21", "P38", "P70")} if ensaio.sigla == SIGLA_CP else set()
    calculados = {p.codigo: p for p in params if p.calculado}
    linhas, statuses = [], []
    for p in digitados:
        valores = [_celula(c.primeiro(p.codigo)) for c in campanhas]
        ref = resolvedor.para(p.id, **escopo)
        cel = valores[-1] if atual is not None and valores else None
        avaliacao = {"status": None, "variacao_pct": None, "excesso": None}
        if ref is not None and cel is not None and resultado is not None and resultado.situacao == REALIZADO:
            avaliacao = cf.classificar(
                tipo=ref.tipo, valor=cel["valor"], texto=cel["texto"], estado=cel["estado"] or "MEDIDO",
                valor_base=ref.valor_base, limite_alerta=ref.limite_alerta, limite_critico=ref.limite_critico,
                referencia_texto=ref.referencia_texto,
            )
        tem_valor = cel is not None and (cel["valor"] is not None or cel["texto"])
        statuses.append(avaliacao["status"])
        linhas.append({
            "codigo": p.codigo, "nome": p.nome, "simbolo": p.simbolo, "grupo": p.grupo, "unidade": p.unidade,
            "norma": p.norma, "metodo": (cel or {}).get("metodo", ""), "casas": p.casas_decimais,
            "no_grafico": p.no_grafico, "qualitativo": p.tipo_limite == "QUALITATIVO",
            "valores": valores, "referencia": resumo_referencia(ref, p.casas_decimais, p.unidade),
            "status": avaliacao["status"], "variacao_pct": avaliacao["variacao_pct"],
            "sem_referencia": bool(tem_valor and ref is None and p.codigo not in avaliado_pelo_codigo),
            "tendencia": cf.tendencia([v["valor"] for v in valores]),
        })

    corpo = {"tipo": "PARAMETROS"}
    if ensaio.sigla == SIGLA_CP:
        codigos = []
        for c in campanhas:
            vals = {cod: (c.primeiro(cod).valor if c.primeiro(cod) else None) for cod in cf.TAMANHOS_CODIGO}
            texto, escalas = cf.codigo_iso4406(*(vals[cod] for cod in cf.TAMANHOS_CODIGO))
            codigos.append({"data": c.data, "atual": c is atual, "codigo": texto, "escalas": escalas})
        p_iso = calculados.get(CODIGO_ISO4406)
        meta = resolvedor.para(p_iso.id, **escopo) if p_iso else None
        atual_codigo = codigos[-1] if atual is not None and codigos else None
        situacao_meta, excesso = None, None
        if atual_codigo and atual_codigo["codigo"] and resultado is not None and resultado.situacao == REALIZADO:
            if meta is None or meta.tipo != TipoReferencia.CODIGO_ISO:
                situacao_meta = "SEM_META"
            else:
                aval = cf.classificar(tipo=meta.tipo, escalas=atual_codigo["escalas"],
                                      referencia_texto=meta.referencia_texto,
                                      limite_alerta=meta.limite_alerta, limite_critico=meta.limite_critico)
                excesso = aval["excesso"]
                situacao_meta = None if excesso is None else ("DENTRO" if excesso <= 0 else "FORA")
                statuses.append(aval["status"])
        corpo = {
            "tipo": "CP", "codigos": codigos, "meta": resumo_referencia(meta, 0) if meta else None,
            "situacao_meta": situacao_meta, "excesso_meta": excesso,
        }

    grupos = list(dict.fromkeys(linha["grupo"] for linha in linhas))
    status = _status_ficha(resultado, statuses)
    r = resultado
    return {
        "observacoes_geradas": observacoes_geradas(linhas, corpo) if status in (cf.ALERTA, cf.CRITICA) else [],
        "sigla": ensaio.sigla, "nome": ensaio.nome, "rotulo": ensaio.sigla, "titulo": ensaio.titulo_ficha,
        "solicitado": solicitado,
        "situacao": r.situacao if r else SituacaoResultado.SEM_RESULTADO,
        "status": status, "status_rotulo": STATUS_FLUIDO_ROTULO[status],
        "avaliados": sum(1 for s in statuses if s is not None),
        "alertas": sum(1 for s in statuses if s == cf.ALERTA),
        "criticas": sum(1 for s in statuses if s == cf.CRITICA),
        "fora": sum(1 for s in statuses if s in (cf.ALERTA, cf.CRITICA)),
        "sem_referencia": sum(1 for linha in linhas if linha["sem_referencia"]),
        "numero_laudo": r.numero_laudo if r else "",
        "criticidade": r.get_criticidade_display() if r and r.criticidade else "",
        "criticidade_codigo": r.criticidade if r else "",
        "data_analise": r.data_analise if r else None, "data_proxima": r.data_proxima if r else None,
        "conclusao": r.conclusao if r else "", "recomendacao": r.recomendacao if r else "",
        "informacoes_adicionais": r.informacoes_adicionais if r else "",
        "instrumento": _instrumento(r.instrumento) if r else "", "laboratorio": r.laboratorio if r else "",
        "rotulos": {"conclusao": ensaio.rotulo_conclusao, "informacoes": ensaio.rotulo_informacoes,
                    "proxima": ensaio.rotulo_proxima},
        "notas": [linha.strip() for linha in ensaio.nota_tecnica.splitlines() if linha.strip()],
        "campanhas": [{"data": c.data, "atual": c is atual} for c in campanhas],
        "linhas": linhas, "grupos": grupos,
        **corpo,
    }


CAMPOS_AVALIACAO = ("observacoes_geradas", "tipo", "status", "status_rotulo", "avaliados", "fora", "alertas", "criticas",
                    "sem_referencia", "campanhas", "linhas", "grupos", "codigos", "meta", "situacao_meta",
                    "excesso_meta")


def _status_campanha(ensaio, params, campanha, equipamento, resolvedor):
    """Pior estado de um ensaio numa coleta (referências da época). None sem referência para avaliar."""
    escopo = _contexto_referencia(campanha, equipamento)
    statuses = []
    for p in (p for p in params if not p.calculado):
        v = campanha.primeiro(p.codigo)
        ref = resolvedor.para(p.id, **escopo) if v is not None else None
        if ref is None:
            continue
        statuses.append(cf.classificar(
            tipo=ref.tipo, valor=v.valor, texto=v.valor_texto, estado=v.estado or "MEDIDO",
            valor_base=ref.valor_base, limite_alerta=ref.limite_alerta, limite_critico=ref.limite_critico,
            referencia_texto=ref.referencia_texto,
        )["status"])
    if ensaio.sigla == SIGLA_CP:
        p_iso = next((p for p in params if p.codigo == CODIGO_ISO4406), None)
        meta = resolvedor.para(p_iso.id, **escopo) if p_iso else None
        contagens = [campanha.primeiro(cod) for cod in cf.TAMANHOS_CODIGO]
        _, escalas = cf.codigo_iso4406(*(c.valor if c else None for c in contagens))
        if meta is not None and meta.tipo == TipoReferencia.CODIGO_ISO:
            statuses.append(cf.classificar(
                tipo=meta.tipo, escalas=escalas, referencia_texto=meta.referencia_texto,
                limite_alerta=meta.limite_alerta, limite_critico=meta.limite_critico)["status"])
    return cf.pior(statuses)


def _historico(equipamento_id, ensaio_id, excluir_item_ids):
    qs = (ResultadoEnsaio.objects.ativos()
          .filter(item__equipamento_id=equipamento_id, ensaio_id=ensaio_id, situacao=REALIZADO)
          .exclude(item_id__in=list(excluir_item_ids))
          .select_related("item__carregamento", "item__coleta_oleo", "item__registro_eletrico",
                          "item__coleta_fluido")
          .prefetch_related("valores__parametro"))
    return [_Campanha(r) for r in qs]


def _campanhas_historico(campanhas, limite):
    """As últimas `limite` coletas, em ordem cronológica (a mais recente vira a "atual")."""
    return sorted(campanhas, key=lambda c: (c.data, c.resultado.id))[-limite:]


def _campanhas(atual, anteriores):
    antes = sorted((c for c in anteriores if atual is None or c.data < atual.data), key=lambda c: c.data)
    return antes[-(HISTORICO_MAXIMO - 1):] + ([atual] if atual else [])


def avaliar_resultado_fluido(resultado) -> dict:
    """
    A parte calculada da ficha para o editor: referência, estado e tendência de cada
    parâmetro, o código ISO 4406 e a meta — com o histórico do equipamento, como no
    relatório.
    """
    params = [p for p in resultado.ensaio.parametros.all() if p.ativo]
    atual = _Campanha(resultado)
    eq = resultado.item.equipamento
    campanhas = _campanhas(atual, _historico(eq.id, resultado.ensaio_id, {resultado.item_id}))
    resolvedor = ResolvedorReferencias(p.id for p in params)
    ficha = montar_ficha_fluido(resultado.ensaio, params, resultado, atual, campanhas, eq, resolvedor, False)
    return {k: ficha[k] for k in CAMPOS_AVALIACAO if k in ficha}


# --------------------------------- Módulo ------------------------------------
class ModuloFluidoLubrificante(ModuloEnsaiosLaboratoriais):
    chave = ModuloTecnico.FLUIDO_LUBRIFICANTE.value
    carta_conteudo = CONTEUDO_FLUIDO
    carta_glossario = GLOSSARIO_FLUIDO
    carta_consideracoes = CONSIDERACOES_FLUIDO
    carta_quebras_glossario = ("6.5", "6.9", "6.12")

    def instrumentos_adicionais(self, ctx) -> list:
        """Os do laudo e, no que faltar, a instrumentação padrão cadastrada para a tecnologia do relatório."""
        lista = super().instrumentos_adicionais(ctx)
        vistos = {i.id for i in lista}
        padrao = ctx.rel.tecnologia.instrumentos.filter(ativo=True).order_by("id")
        return lista + [i for i in padrao if i.id not in vistos]

    def montar(self, ctx) -> dict:
        ensaios = list(Ensaio.objects.ativos().filter(modulo=self.chave).prefetch_related("parametros"))
        params = {e.id: [p for p in e.parametros.all() if p.ativo] for e in ensaios}
        resolvedor = ResolvedorReferencias(p.id for lista in params.values() for p in lista)
        itens = ctx.itens
        equipamentos = {
            e.id: e for e in Equipamento.objects.filter(id__in={i.equipamento_id for i in itens})
            .select_related("tipo_equipamento", "setor__area")
        }
        coletas = {
            c.item_id: c for c in ColetaFluido.objects.ativos().filter(item__in=itens)
            .select_related("ponto_coleta", "produto").prefetch_related("ensaios")
        }
        resultados = defaultdict(dict)
        for r in (ResultadoEnsaio.objects.ativos().filter(item__in=itens, ensaio__modulo=self.chave)
                  .select_related("ensaio", "instrumento", "item__carregamento", "item__coleta_oleo",
                                  "item__registro_eletrico", "item__coleta_fluido")
                  .prefetch_related("valores__parametro")):
            resultados[r.item_id][r.ensaio_id] = r
        historico = defaultdict(list)
        for r in (ResultadoEnsaio.objects.ativos()
                  .filter(item__equipamento_id__in=list(equipamentos), ensaio__modulo=self.chave, situacao=REALIZADO)
                  .exclude(item__in=itens)
                  .select_related("item__carregamento", "item__coleta_oleo", "item__registro_eletrico",
                                  "item__coleta_fluido")
                  .prefetch_related("valores__parametro")):
            historico[(r.item.equipamento_id, r.ensaio_id)].append(_Campanha(r))

        amostras, graus_passados = [], {}
        for item in itens:
            eq = equipamentos[item.equipamento_id]
            coleta = coletas.get(item.id)
            solicitados = {e.id for e in coleta.ensaios.all()} if coleta else set()
            fichas = []
            for ensaio in ensaios:
                resultado = resultados[item.id].get(ensaio.id)
                if ensaio.id not in solicitados and resultado is None:
                    continue
                atual = _Campanha(resultado) if resultado else None
                campanhas = _campanhas(atual, historico[(eq.id, ensaio.id)])
                fichas.append(montar_ficha_fluido(ensaio, params[ensaio.id], resultado, atual, campanhas, eq,
                                                  resolvedor, ensaio.id in solicitados))
            statuses = {f["sigla"]: f["status"] for f in fichas if f["situacao"] == REALIZADO}
            condicao = item.condicao.sigla if item.condicao_id else ""
            data_atual = coleta.data_coleta if coleta else item.carregamento.data_coleta
            graus_passados[eq.id] = self._graus_passados(eq, ensaios, params, historico, resolvedor, data_atual)
            amostras.append({
                "equipamento_id": eq.id, "data": data_atual,
                "grau_risco": gr.grau_de_risco(statuses, condicao),
                "item_id": item.id, "tag": eq.tag, "equipamento": eq.nome,
                "area": eq.setor.area.nome if eq.setor_id else "—", "setor": eq.setor.nome if eq.setor_id else "—",
                "condicao": rotulo_condicao(item.condicao),
                "cadastro": {
                    "local": eq.setor.nome if eq.setor_id else "",
                    "identificacao": " - ".join(x for x in [eq.tag, eq.nome] if x),
                    "numero_serie": eq.numero_serie, "numero_patrimonio": eq.numero_patrimonio,
                    "fabricante": eq.fabricante, "modelo": eq.modelo, "ano_fabricacao": eq.ano_fabricacao,
                    "tipo_equipamento": eq.tipo_equipamento.nome if eq.tipo_equipamento_id else eq.tipo,
                },
                "coleta": self._coleta(coleta),
                "tipos_ensaio": [{"sigla": e.sigla, "nome": e.nome, "solicitado": e.id in solicitados} for e in ensaios],
                "ensaios": fichas,
            })
        cliente = ctx.rel.cliente
        return {
            "amostras": amostras, "kpis": self._kpis(amostras), "resumo": self._resumo(amostras),
            "graficos": gr.montar_graficos(
                [{
                    "equipamento_id": a["equipamento_id"], "data": a["data"], "grau": a["grau_risco"],
                    "tipo": a["cadastro"]["tipo_equipamento"],
                    "anomalias": self._parametros_fora(a),
                } for a in amostras],
                graus_passados,
            ),
            "contato_cliente": {"telefone": cliente.telefone, "email": cliente.email},
        }

    @staticmethod
    def _parametros_fora(amostra) -> list:
        """Rótulos dos parâmetros fora da referência na coleta atual (o CP entra pelo código ISO 4406)."""
        fora = []
        for f in amostra["ensaios"]:
            fora += [linha["nome"] for linha in f["linhas"] if linha["status"] in (cf.ALERTA, cf.CRITICA)]
            if f.get("situacao_meta") == "FORA":
                fora.append("Código ISO 4406")
        return fora

    @staticmethod
    def _graus_passados(eq, ensaios, params, historico, resolvedor, data_atual) -> dict:
        """{data: "GR-x"} das coletas anteriores ao relatório, avaliadas pelas referências da época."""
        por_data = defaultdict(dict)
        for ensaio in ensaios:
            for c in historico[(eq.id, ensaio.id)]:
                if data_atual is None or c.data < data_atual:
                    por_data[c.data][ensaio.sigla] = _status_campanha(ensaio, params[ensaio.id], c, eq, resolvedor)
        graus = {d: gr.grau_de_risco(statuses) for d, statuses in por_data.items()}
        return {d: g["sigla"] for d, g in graus.items() if g}

    @staticmethod
    def _coleta(c):
        if c is None:
            return None
        return {
            "data": c.data_coleta, "identificacao_amostra": c.identificacao_amostra, "amostrador": c.amostrador,
            "aplicacao": c.aplicacao, "aplicacao_display": c.get_aplicacao_display(),
            "fluido": c.nome_fluido, "fabricante_fluido": c.produto.fabricante if c.produto_id else "",
            "grau_viscosidade": c.grau_viscosidade or (c.produto.grau_viscosidade if c.produto_id else ""),
            "ponto_coleta": c.ponto_coleta.nome if c.ponto_coleta_id else "",
            "temperatura_fluido_c": c.temperatura_fluido_c, "temperatura_ambiente_c": c.temperatura_ambiente_c,
            "condicao_operacional": c.get_condicao_operacional_display() if c.condicao_operacional else "",
            "horas_equipamento": c.horas_equipamento, "horas_fluido": c.horas_fluido,
            "volume_reservatorio_l": c.volume_reservatorio_l,
            "data_ultima_troca": c.data_ultima_troca, "complemento_recente": c.complemento_recente,
            "volume_complemento_l": c.volume_complemento_l, "troca_filtro_recente": c.troca_filtro_recente,
            "intervencao_recente": c.intervencao_recente, "observacoes": c.observacoes,
        }

    @staticmethod
    def _kpis(amostras) -> dict:
        fichas = [f for a in amostras for f in a["ensaios"]]
        realizadas = [f for f in fichas if f["situacao"] == REALIZADO]
        cps = [f for f in realizadas if f["tipo"] == "CP"]
        proximas = [f["data_proxima"] for f in fichas if f["data_proxima"]]
        criticidade = Counter(f["criticidade"] or "Não classificado" for f in realizadas)
        return {
            "amostras": sum(1 for a in amostras if a["coleta"]),
            "equipamentos": len(amostras),
            "ensaios_solicitados": sum(1 for f in fichas if f["solicitado"]),
            "ensaios_realizados": len(realizadas),
            "ensaios_pendentes": sum(1 for f in fichas if f["solicitado"] and f["situacao"] not in SITUACOES_FINAIS),
            "parametros_avaliados": sum(f["avaliados"] for f in fichas),
            "parametros_alerta": sum(f["alertas"] for f in fichas),
            "parametros_criticos": sum(f["criticas"] for f in fichas),
            "parametros_sem_referencia": sum(f["sem_referencia"] for f in fichas),
            "laudos_por_criticidade": _distribuicao(criticidade),
            "avaliacao_ensaios": _distribuicao(Counter(f["status_rotulo"] for f in fichas)),
            "limpeza": {
                "dentro": sum(1 for f in cps if f["situacao_meta"] == "DENTRO"),
                "fora": sum(1 for f in cps if f["situacao_meta"] == "FORA"),
                "sem_meta": sum(1 for f in cps if f["situacao_meta"] == "SEM_META"),
            },
            "status_por_ensaio": [{"rotulo": f["rotulo"], "status": f["status"], "status_rotulo": f["status_rotulo"]}
                                  for f in fichas],
            "proxima_data": min(proximas) if proximas else None,
        }

    @staticmethod
    def _resumo(amostras) -> str:
        if not amostras:
            return ""
        fichas = [f for a in amostras for f in a["ensaios"]]
        n_amostras = sum(1 for a in amostras if a["coleta"])
        feitos = list(dict.fromkeys(f["rotulo"] for f in fichas if f["situacao"] == REALIZADO))
        sujeito = ("foi analisada 1 amostra" if n_amostras == 1 else f"foram analisadas {n_amostras} amostras")
        n_eq = len(amostras)
        partes = [f"Neste ciclo {sujeito} de fluido lubrificante/hidráulico de "
                  f"{'1 equipamento' if n_eq == 1 else f'{n_eq} equipamentos'}"
                  + (f", com os ensaios {_lista(feitos)}." if feitos else ".")]
        dentro = sum(1 for f in fichas if f["status"] == cf.ROTINA)
        alerta = [f"{f['rotulo']} ({a['tag']})" for a in amostras for f in a["ensaios"] if f["status"] == cf.ALERTA]
        critica = [f"{f['rotulo']} ({a['tag']})" for a in amostras for f in a["ensaios"] if f["status"] == cf.CRITICA]
        if feitos:
            txt = f"Pelas referências cadastradas, {dentro} {'ensaio ficou' if dentro == 1 else 'ensaios ficaram'} dentro"
            txt += f", {len(alerta)} em alerta ({_lista(alerta)})" if alerta else ", nenhum em alerta"
            txt += f" e {len(critica)} crítico(s) ({_lista(critica)})" if critica else " e nenhum crítico"
            partes.append(txt + ".")
        sem_ref = sum(f["sem_referencia"] for f in fichas)
        if sem_ref:
            partes.append(f"{sem_ref} {'parâmetro sem referência cadastrada foi informado' if sem_ref == 1 else 'parâmetros sem referência cadastrada foram informados'} sem classificação.")
        fora_meta = [a["tag"] for a in amostras for f in a["ensaios"] if f.get("situacao_meta") == "FORA"]
        if fora_meta:
            partes.append(f"Código de limpeza ISO 4406 acima da meta em {_lista(fora_meta)}.")
        pendentes = [f"{f['rotulo']} ({a['tag']})" for a in amostras for f in a["ensaios"] if f["situacao"] != REALIZADO]
        if pendentes:
            partes.append(f"{'Ensaio sem resultado' if len(pendentes) == 1 else 'Ensaios sem resultado'}: {_lista(pendentes)}.")
        return " ".join(partes)


def ensaios_padrao(aplicacao):
    """Ensaios marcados por padrão na coleta para a aplicação (regra acordada, editável no admin)."""
    from .models import SolicitacaoPadraoEnsaio

    if aplicacao not in AplicacaoFluido.values:
        return []
    return list(
        Ensaio.objects.ativos().filter(
            modulo=ModuloTecnico.FLUIDO_LUBRIFICANTE,
            solicitacoes_padrao__aplicacao=aplicacao, solicitacoes_padrao__ativo=True,
        ).order_by("ordem")
    )
