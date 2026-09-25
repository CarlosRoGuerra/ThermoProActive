"""
Módulos do relatório técnico de transformador: óleo isolante e ensaios elétricos.

Mesmo shell das outras tecnologias (capa, carta, KPIs, relação de equipamentos,
paginação e PDF). Daqui saem os KPIs e as fichas, uma sequência por transformador
(item da rota):

    óleo      → Registro da coleta (+ inspeção visual) → FQ → CR → PCB → 2-FAL
    elétricos → Registro dos ensaios → R×T → R×I → R×O

A ficha de um ensaio sai quando ele foi solicitado ou tem resultado registrado — um
2-FAL "amostra não coletada" com recomendação continua saindo, como no relatório de
referência. Cálculos em `calculos.py`; valor ausente nunca vira zero.
"""
from collections import Counter, defaultdict
from decimal import Decimal

from django.core.exceptions import ObjectDoesNotExist

from apps.cadastros.models import Equipamento, ModuloTecnico

from . import calculos
from .carta import (
    CONSIDERACOES_ELETRICO,
    CONSIDERACOES_OLEO,
    CONTEUDO_ELETRICO,
    CONTEUDO_OLEO,
    GLOSSARIO_ELETRICO,
    GLOSSARIO_OLEO,
)
from .models import (
    ColetaOleo,
    Ensaio,
    EstadoChecklist,
    RegistroEnsaioEletrico,
    ResultadoEnsaio,
    SituacaoResultado,
    TipoLimite,
)

REALIZADO = SituacaoResultado.REALIZADO
HISTORICO_MAXIMO = 6  # linhas por ficha, como no relatório de referência

STATUS_ROTULO = {
    "CONFORME": "Conforme",
    "NAO_CONFORME": "Não conforme",
    "SEM_CRITERIO": "Sem critério definido",
    SituacaoResultado.NAO_COLETADO: "Amostra não coletada",
    SituacaoResultado.NAO_REALIZADO: "Não realizado",
    SituacaoResultado.SEM_RESULTADO: "Aguardando resultado",
}
ROTULO_CURTO = {"PCB": "Teor PCB", "2FAL": "2-FAL", "RXT": "R×T", "RXI": "R×I", "RXO": "R×O"}
TIPO_FICHA = {"RXT": "RXT", "RXI": "RXI", "RXO": "RXO"}  # os demais são tabela de parâmetros


def rotulo_condicao(cond) -> str:
    # Mesma regra do shell (relatorio_tecnico.shell) — local para não importar o pacote
    # do relatório, que por sua vez registra este módulo.
    return (cond.sigla or cond.nome) if cond else "—"


def _um(obj, atributo):
    try:
        return getattr(obj, atributo)
    except ObjectDoesNotExist:
        return None


def _lista(itens):
    itens = list(itens)
    return itens[0] if len(itens) == 1 else f"{', '.join(itens[:-1])} e {itens[-1]}" if itens else ""


def _distribuicao(contagem: Counter):
    total = sum(contagem.values()) or 1
    return [
        {"rotulo": k, "total": v, "percentual": round(v * 100 / total, 1)}
        for k, v in sorted(contagem.items(), key=lambda x: -x[1])
    ]


def _instrumento(ins):
    if not ins:
        return ""
    partes = [("Marca", ins.marca), ("Modelo", ins.modelo), ("Serial", ins.numero_serie)]
    return " / ".join(f"{k}: {v}" for k, v in partes if v) or ins.tipo


def _parametro(p):
    return {
        "codigo": p.codigo, "nome": p.nome, "unidade": p.unidade, "norma": p.norma,
        "tipo_limite": p.tipo_limite, "limite": p.limite, "limite_superior": p.limite_superior,
        "referencia_texto": p.referencia_texto, "casas": p.casas_decimais, "no_grafico": p.no_grafico,
    }


def _avaliar(p, valor, texto="", estado="MEDIDO"):
    return calculos.avaliar(
        valor=valor, texto=texto, estado=estado, tipo_limite=p.tipo_limite, limite=p.limite,
        limite_superior=p.limite_superior, referencia_texto=p.referencia_texto,
    )


def _status(resultado, conformes):
    if resultado is None:
        return SituacaoResultado.SEM_RESULTADO
    if resultado.situacao != REALIZADO:
        return resultado.situacao
    avaliados = [c for c in conformes if c is not None]
    if not avaliados:
        return "SEM_CRITERIO"
    return "CONFORME" if all(avaliados) else "NAO_CONFORME"


class _Campanha:
    """Um resultado com a data da campanha e a ficha de coleta/registro do seu item."""

    def __init__(self, resultado):
        self.resultado = resultado
        item = resultado.item
        self.coleta = _um(item, "coleta_oleo")
        self.registro = _um(item, "registro_eletrico")
        base = self.coleta.data_coleta if self.coleta else self.registro.data_ensaio if self.registro else None
        self.data = base or item.carregamento.data_coleta

    def valores(self, codigo=None):
        return [v for v in self.resultado.valores.all() if codigo is None or v.parametro.codigo == codigo]

    def primeiro(self, codigo):
        encontrados = self.valores(codigo)
        return encontrados[0] if encontrados else None


# --------------------------- Fichas por tipo de ensaio --------------------------
def _celula(p, v):
    if v is None:
        return {"valor": None, "texto": "", "estado": "", "conforme": None, "calculado": False}
    return {
        "valor": v.valor, "texto": v.valor_texto, "estado": v.estado,
        "conforme": _avaliar(p, v.valor, v.valor_texto, v.estado), "calculado": False,
    }


def _ficha_tabela(ensaio, params, campanhas, atual):
    """FQ, CR, PCB e 2-FAL: uma coluna por parâmetro, uma linha por campanha."""
    tabela = [p for p in params if not p.calculado]
    linhas = []
    for c in campanhas:
        valores = {p.codigo: _celula(p, c.primeiro(p.codigo)) for p in tabela}
        # 2-FAL: sem GP do laboratório, estima pelo 2-Furfural (De Pablo, nota 3 da ficha).
        gp, fal = valores.get("GP"), valores.get("2FAL")
        if gp is not None and gp["valor"] is None and fal and fal["valor"] is not None:
            p_gp = next(p for p in tabela if p.codigo == "GP")
            estimado = calculos.grau_polimerizacao_de_pablo(fal["valor"])
            valores["GP"] = {"valor": estimado, "texto": "", "estado": "MEDIDO",
                             "conforme": _avaliar(p_gp, estimado), "calculado": True}
        linhas.append({"data": c.data, "atual": c is atual, "valores": valores})

    corrente = linhas[-1]["valores"] if atual is not None and linhas else {}
    grafico = [
        {"codigo": p.codigo, "nome": p.nome, "tipo_limite": p.tipo_limite,
         "percentual": calculos.percentual_do_limite((corrente.get(p.codigo) or {}).get("valor"), p.limite)}
        for p in tabela if p.no_grafico and p.tipo_limite in (TipoLimite.MAXIMO, TipoLimite.MINIMO)
    ]
    conformes = [cel["conforme"] for cel in corrente.values()]
    indicadores = {}
    if ensaio.sigla == "CR" and atual is not None and atual.resultado.situacao == REALIZADO:
        gases = {cod: cel["valor"] for cod, cel in corrente.items()}
        indicadores = {
            "TG": calculos.soma_gases(gases, calculos.GASES_TODOS),
            "TGC": calculos.soma_gases(gases, calculos.GASES_COMBUSTIVEIS),
        }
    return {
        "tipo": "TABELA", "parametros": [_parametro(p) for p in tabela], "campanhas": linhas,
        "grafico": grafico, "indicadores": indicadores, "conformes": conformes,
        "gp_estimado": bool(corrente.get("GP", {}).get("calculado")),
    }


def _ficha_rxt(params, campanhas, atual, trafo):
    p = {x.codigo: x for x in params}
    linhas, conformes = [], []
    for c in campanhas:
        entrado = c.primeiro("NOMINAL")
        nominal = entrado.valor if entrado and entrado.valor is not None else None
        calculada = nominal is None
        if calculada and c.registro and trafo:
            nominal = calculos.relacao_nominal(
                c.registro.tensao_tap_v, trafo.tensao_secundaria_v, trafo.tensao_secundaria_fase_v, trafo.grupo_ligacao,
            )
        fases = []
        for v in sorted(c.valores("MEDIDA"), key=lambda v: v.serie):
            erro = calculos.erro_relacao_pct(v.valor, nominal)
            conforme = _avaliar(p["ERRO"], erro)
            fases.append({"serie": v.serie, "medido": v.valor, "erro": erro, "conforme": conforme})
            if c is atual:
                conformes.append(conforme)
        linhas.append({"data": c.data, "atual": c is atual, "nominal": nominal,
                       "nominal_calculada": calculada and nominal is not None, "fases": fases})
    erro = p["ERRO"]
    return {
        "tipo": "RXT", "campanhas": linhas, "conformes": conformes,
        "limite": {"inferior": erro.limite, "superior": erro.limite_superior, "norma": erro.norma},
    }


def _ficha_rxi(params, atual):
    p = {x.codigo: x for x in params}
    series, conformes = [], []
    if atual is not None:
        tensoes = {v.serie: v.valor for v in atual.valores("TENSAO")}
        pontos = defaultdict(list)
        for v in atual.valores("RESISTENCIA"):
            pontos[v.serie].append({"tempo": v.posicao, "valor": v.valor, "estado": v.estado})
        for nome in sorted(pontos):
            pts = sorted(pontos[nome], key=lambda x: x["tempo"] if x["tempo"] is not None else Decimal("0"))
            r = {x["tempo"]: x["valor"] for x in pts if x["tempo"] is not None}
            ip = calculos.indice_polarizacao(r.get(Decimal("600")), r.get(Decimal("60")))
            ia = calculos.indice_absorcao(r.get(Decimal("60")), r.get(Decimal("30")))
            conforme = _avaliar(p["IP"], ip)
            conformes.append(conforme)
            series.append({"nome": nome, "tensao": tensoes.get(nome), "pontos": pts, "ip": ip, "ia": ia,
                           "ip_conforme": conforme})
    tempos = sorted({x["tempo"] for s in series for x in s["pontos"] if x["tempo"] is not None})
    return {
        "tipo": "RXI", "series": series, "tempos": tempos, "conformes": conformes,
        "criterio_ip": {"limite": p["IP"].limite, "norma": p["IP"].norma},
    }


def _ficha_rxo(params, campanhas, atual, trafo):
    grupo = (trafo.grupo_ligacao if trafo else "") or ""
    at_triangulo, bt_triangulo = grupo[:1] in ("D", "d"), grupo[1:2] in ("D", "d")
    unidades = {p.codigo: p.unidade for p in params}
    linhas = []
    for c in campanhas:
        temperatura = c.registro.temperatura_oleo_c if c.registro else None
        medidos = {v.parametro.codigo: v.valor for v in c.valores() if v.valor is not None}
        calculados, corrigidos = {}, {}
        for codigo, valor in medidos.items():
            triangulo = at_triangulo if codigo.startswith("H") else bt_triangulo
            fase = calculos.resistencia_fase(valor, triangulo, com_neutro="0" in codigo)
            if fase != valor:
                calculados[codigo] = fase
            corrigidos[codigo] = calculos.corrigir_temperatura(fase, temperatura)
        linhas.append({
            "data": c.data, "atual": c is atual, "tap": c.registro.tap if c.registro else "",
            "temperatura_oleo_c": temperatura,
            "linhas": [
                {"tipo": "Corrigido", "valores": corrigidos},
                {"tipo": "Calculado", "valores": calculados},
                {"tipo": "Medido", "valores": medidos},
            ],
        })
    return {
        "tipo": "RXO", "campanhas": linhas, "conformes": [],
        "pares": [{"codigo": p.codigo, "nome": p.nome, "unidade": unidades[p.codigo], "casas": p.casas_decimais}
                  for p in params],
        "correcao": {"temperatura_referencia_c": calculos.TEMPERATURA_REFERENCIA_C, "constante": calculos.TK_COBRE},
    }


# ---------------------------------- Módulo ----------------------------------
class ModuloTransformador:
    """Base dos relatórios de transformador (um módulo por família de ensaios)."""

    chave = ""
    oleo = False
    tabelas_normativas = ()
    carta_conteudo = carta_glossario = carta_consideracoes = carta_quebras_glossario = ()
    # Sujeito do parágrafo do item 7 da carta: (singular, plural com {n}).
    sujeito = ("foi analisada 1 amostra de óleo isolante", "foram analisadas {n} amostras de óleo isolante")

    # --- Carta ---
    def textos_carta(self, tecnico=None) -> dict:
        return {
            "conteudo": list(self.carta_conteudo),
            "glossario": [{"n": n, "sigla": s, "texto": t} for n, s, t in self.carta_glossario],
            "quebras_glossario": list(self.carta_quebras_glossario),
            "consideracoes": list(self.carta_consideracoes),
            "paragrafos": [tecnico["resumo"]] if tecnico and tecnico.get("resumo") else [],
        }

    def paragrafos_carta(self, rel) -> list:
        from apps.coletas.relatorio_tecnico.shell import carregar_contexto

        resumo = self.montar(carregar_contexto(rel, None)).get("resumo")
        return [resumo] if resumo else []

    def instrumentos_adicionais(self, ctx) -> list:
        vistos, lista = set(), []
        for r in (ResultadoEnsaio.objects.filter(item__in=ctx.itens, ensaio__modulo=self.chave)
                  .select_related("instrumento").order_by("ensaio__ordem")):
            if r.instrumento_id and r.instrumento_id not in vistos:
                vistos.add(r.instrumento_id)
                lista.append(r.instrumento)
        return lista

    # --- Payload ---
    def montar(self, ctx) -> dict:
        ensaios = list(Ensaio.objects.ativos().filter(modulo=self.chave).prefetch_related("parametros"))
        params = {e.id: [p for p in e.parametros.all() if p.ativo] for e in ensaios}
        itens = ctx.itens
        equipamentos = {
            e.id: e for e in Equipamento.objects.filter(id__in={i.equipamento_id for i in itens})
            .select_related("tipo_equipamento", "setor__area", "dados_transformador")
        }
        resultados = defaultdict(dict)
        for r in (ResultadoEnsaio.objects.ativos().filter(item__in=itens, ensaio__modulo=self.chave)
                  .select_related("ensaio", "instrumento", "item__carregamento", "item__coleta_oleo",
                                  "item__registro_eletrico")
                  .prefetch_related("valores__parametro")):
            resultados[r.item_id][r.ensaio_id] = r
        historico = defaultdict(list)
        for r in (ResultadoEnsaio.objects.ativos()
                  .filter(item__equipamento_id__in=list(equipamentos), ensaio__modulo=self.chave, situacao=REALIZADO)
                  .exclude(item__in=itens)
                  .select_related("item__carregamento", "item__coleta_oleo", "item__registro_eletrico")
                  .prefetch_related("valores__parametro")):
            historico[(r.item.equipamento_id, r.ensaio_id)].append(_Campanha(r))

        extras = self._fichas_de_coleta(itens)
        transformadores = []
        for item in itens:
            eq = equipamentos[item.equipamento_id]
            trafo = _um(eq, "dados_transformador")
            registro_base = extras.get(item.id)
            solicitados = {e.id for e in registro_base.ensaios.all()} if registro_base else set()
            fichas = []
            for ensaio in ensaios:
                resultado = resultados[item.id].get(ensaio.id)
                if ensaio.id not in solicitados and resultado is None:
                    continue
                atual = _Campanha(resultado) if resultado else None
                anteriores = sorted(
                    (c for c in historico[(eq.id, ensaio.id)] if atual is None or c.data < atual.data),
                    key=lambda c: c.data,
                )
                campanhas = anteriores[-(HISTORICO_MAXIMO - 1):] + ([atual] if atual else [])
                fichas.append(self._ficha(ensaio, params[ensaio.id], resultado, atual, campanhas, trafo,
                                          ensaio.id in solicitados))
            transformadores.append({
                "item_id": item.id, "tag": eq.tag, "equipamento": eq.nome,
                "area": eq.setor.area.nome if eq.setor_id else "—", "setor": eq.setor.nome if eq.setor_id else "—",
                "condicao": rotulo_condicao(item.condicao),
                "cadastro": self._cadastro(eq, trafo),
                "tipos_ensaio": [{"sigla": e.sigla, "nome": ROTULO_CURTO.get(e.sigla, e.sigla),
                                  "solicitado": e.id in solicitados} for e in ensaios],
                **self._registro(registro_base, ctx.request),
                "ensaios": fichas,
            })
        kpis = self._kpis(transformadores)
        cliente = ctx.rel.cliente
        return {
            "transformadores": transformadores, "kpis": kpis, "resumo": self._resumo(transformadores),
            # A ficha de registro traz o contato do cliente completo (o cabeçalho do shell não tem fone/e-mail).
            "contato_cliente": {"telefone": cliente.telefone, "email": cliente.email},
        }

    # --- Partes ---
    def _fichas_de_coleta(self, itens):
        modelo = ColetaOleo if self.oleo else RegistroEnsaioEletrico
        qs = modelo.objects.ativos().filter(item__in=itens).prefetch_related("ensaios")
        if self.oleo:
            qs = qs.select_related("ponto_coleta", "tipo_fluido").prefetch_related("inspecao_visual__item_checklist")
        return {r.item_id: r for r in qs}

    def _registro(self, r, request) -> dict:
        raise NotImplementedError

    @staticmethod
    def _cadastro(eq, trafo) -> dict:
        t = trafo
        return {
            "local": eq.setor.nome if eq.setor_id else "",
            "identificacao": " - ".join(x for x in [eq.tag, eq.nome] if x),
            "numero_serie": eq.numero_serie, "numero_patrimonio": eq.numero_patrimonio,
            "fabricante": eq.fabricante, "ano_fabricacao": eq.ano_fabricacao,
            "tipo_equipamento": eq.tipo_equipamento.nome if eq.tipo_equipamento_id else eq.tipo,
            "modelo": eq.modelo,
            "potencia_kva": t.potencia_kva if t else None,
            "tensao_primaria_v": t.tensao_primaria_v if t else None,
            "tensao_secundaria_v": t.tensao_secundaria_v if t else None,
            "tensao_secundaria_fase_v": t.tensao_secundaria_fase_v if t else None,
            "impedancia_pct": t.impedancia_pct if t else None,
            "grupo_ligacao": t.grupo_ligacao if t else "",
            "volume_oleo_l": t.volume_oleo_l if t else None,
            "possui_tanque_expansao": t.possui_tanque_expansao if t else None,
        }

    def _ficha(self, ensaio, params, resultado, atual, campanhas, trafo, solicitado) -> dict:
        tipo = TIPO_FICHA.get(ensaio.sigla)
        if tipo == "RXT":
            corpo = _ficha_rxt(params, campanhas, atual, trafo)
        elif tipo == "RXI":
            corpo = _ficha_rxi(params, atual if resultado and resultado.situacao == REALIZADO else None)
        elif tipo == "RXO":
            corpo = _ficha_rxo(params, campanhas, atual, trafo)
        else:
            corpo = _ficha_tabela(ensaio, params, campanhas, atual)
        conformes = corpo.pop("conformes")
        status = _status(resultado, conformes)
        r = resultado
        return {
            "sigla": ensaio.sigla, "nome": ensaio.nome, "rotulo": ROTULO_CURTO.get(ensaio.sigla, ensaio.sigla),
            "titulo": ensaio.titulo_ficha, "solicitado": solicitado,
            "situacao": r.situacao if r else SituacaoResultado.SEM_RESULTADO,
            "status": status, "status_rotulo": STATUS_ROTULO[status],
            "avaliados": sum(1 for c in conformes if c is not None),
            "fora": sum(1 for c in conformes if c is False),
            "numero_laudo": r.numero_laudo if r else "",
            "criticidade": r.get_criticidade_display() if r and r.criticidade else "",
            "data_analise": r.data_analise if r else None, "data_proxima": r.data_proxima if r else None,
            "conclusao": r.conclusao if r else "", "recomendacao": r.recomendacao if r else "",
            "informacoes_adicionais": r.informacoes_adicionais if r else "",
            "instrumento": _instrumento(r.instrumento) if r else "",
            "rotulos": {"conclusao": ensaio.rotulo_conclusao, "informacoes": ensaio.rotulo_informacoes,
                        "proxima": ensaio.rotulo_proxima},
            "notas": [linha.strip() for linha in ensaio.nota_tecnica.splitlines() if linha.strip()],
            **corpo,
        }

    def _kpis(self, transformadores) -> dict:
        fichas = [f for t in transformadores for f in t["ensaios"]]
        proximas = [f["data_proxima"] for f in fichas if f["data_proxima"]]
        return {
            "transformadores": len(transformadores),
            "ensaios_solicitados": sum(1 for f in fichas if f["solicitado"]),
            "ensaios_realizados": sum(1 for f in fichas if f["situacao"] == REALIZADO),
            "parametros_avaliados": sum(f["avaliados"] for f in fichas),
            "parametros_fora": sum(f["fora"] for f in fichas),
            "status_ensaios": _distribuicao(Counter(f["status_rotulo"] for f in fichas)),
            "status_por_ensaio": [
                {"rotulo": f["rotulo"], "status": f["status"], "status_rotulo": f["status_rotulo"]}
                for f in fichas
            ],
            "proxima_data": min(proximas) if proximas else None,
        }

    def _resumo(self, transformadores) -> str:
        fichas = [f for t in transformadores for f in t["ensaios"]]
        if not transformadores:
            return ""
        n = len(transformadores)
        feitos = list(dict.fromkeys(f["rotulo"] for f in fichas if f["situacao"] == REALIZADO))
        conformes = sum(1 for f in fichas if f["status"] == "CONFORME")
        fora = [f["rotulo"] for f in fichas if f["status"] == "NAO_CONFORME"]
        sem_criterio = [f["rotulo"] for f in fichas if f["status"] == "SEM_CRITERIO"]
        pendentes = [f"{f['rotulo']} ({f['status_rotulo'].lower()})" for f in fichas if f["situacao"] != REALIZADO]
        sujeito = self.sujeito[0] if n == 1 else self.sujeito[1].format(n=n)
        partes = [f"Neste ciclo {sujeito}" + (f", com os ensaios {_lista(feitos)}." if feitos else ".")]
        if feitos:
            txt = f"{conformes} {'ensaio ficou' if conformes == 1 else 'ensaios ficaram'} dentro das referências"
            txt += f" e {len(fora)} fora delas ({_lista(fora)})" if fora else " e nenhum fora delas"
            if sem_criterio:
                txt += f"; {_lista(sem_criterio)} sem critério de aceitação definido"
            partes.append(txt + ".")
        if pendentes:
            partes.append(f"{'Ensaio sem resultado' if len(pendentes) == 1 else 'Ensaios sem resultado'}: "
                          f"{_lista(pendentes)}.")
        return " ".join(partes)


class ModuloOleoIsolante(ModuloTransformador):
    chave = ModuloTecnico.OLEO_ISOLANTE.value
    oleo = True
    carta_conteudo = CONTEUDO_OLEO
    carta_glossario = GLOSSARIO_OLEO
    carta_consideracoes = CONSIDERACOES_OLEO
    carta_quebras_glossario = ("6.3",)

    def _registro(self, c, request) -> dict:
        if c is None:
            return {"coleta": None, "inspecao_visual": []}
        foto = lambda f: (request.build_absolute_uri(f.url) if request else f.url) if f else None  # noqa: E731
        return {
            "coleta": {
                "data": c.data_coleta, "amostrador": c.amostrador,
                "temperatura_amostra_c": c.temperatura_amostra_c, "temperatura_ambiente_c": c.temperatura_ambiente_c,
                "umidade_relativa_pct": c.umidade_relativa_pct,
                "ponto_coleta": c.ponto_coleta.nome if c.ponto_coleta_id else "",
                "tipo_fluido": c.tipo_fluido.nome if c.tipo_fluido_id else "",
            },
            "inspecao_visual": [
                {"grupo": i.item_checklist.grupo, "item": i.item_checklist.nome, "estado": i.estado,
                 "observacao": i.observacao, "foto": foto(i.foto)}
                for i in c.inspecao_visual.all()
            ],
        }

    def _kpis(self, transformadores) -> dict:
        kpis = super()._kpis(transformadores)
        estados = Counter(
            EstadoChecklist(i["estado"]).label for t in transformadores for i in t.get("inspecao_visual", [])
        )
        kpis["inspecao_visual"] = _distribuicao(estados)
        return kpis


class ModuloEnsaioEletrico(ModuloTransformador):
    chave = ModuloTecnico.ENSAIO_ELETRICO.value
    carta_conteudo = CONTEUDO_ELETRICO
    carta_glossario = GLOSSARIO_ELETRICO
    carta_consideracoes = CONSIDERACOES_ELETRICO
    carta_quebras_glossario = ("6.2",)
    sujeito = ("foi ensaiado 1 transformador", "foram ensaiados {n} transformadores")

    def _registro(self, r, request) -> dict:
        if r is None:
            return {"registro": None}
        return {"registro": {
            "data": r.data_ensaio, "analista": r.analista, "tap": r.tap, "tensao_tap_v": r.tensao_tap_v,
            "temperatura_oleo_c": r.temperatura_oleo_c, "temperatura_ambiente_c": r.temperatura_ambiente_c,
            "umidade_relativa_pct": r.umidade_relativa_pct,
        }}

    def _kpis(self, transformadores) -> dict:
        kpis = super()._kpis(transformadores)
        erros = [abs(fase["erro"]) for t in transformadores for f in t["ensaios"] if f["sigla"] == "RXT"
                 for c in f["campanhas"] if c["atual"] for fase in c["fases"] if fase["erro"] is not None]
        ips = [s["ip"] for t in transformadores for f in t["ensaios"] if f["sigla"] == "RXI"
               for s in f["series"] if s["ip"] is not None]
        limite = next((f["limite"]["superior"] for t in transformadores for f in t["ensaios"] if f["sigla"] == "RXT"),
                      None)
        kpis.update({
            "maior_erro_relacao": max(erros) if erros else None, "limite_erro_relacao": limite,
            "menor_ip": min(ips) if ips else None,
        })
        return kpis
