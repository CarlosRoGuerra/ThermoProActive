"""
Módulos do relatório técnico de ensaios elétricos de subestação: TC, TP, DJ, CS e RP.

Mesmo shell das outras tecnologias (capa, carta, KPIs, relação de equipamentos,
paginação e PDF). Daqui saem os KPIs e as fichas, uma sequência por equipamento (item
da rota): registro dos ensaios → uma ficha por ensaio solicitado ou com resultado.

Duas formas de ficha (`ensaio.forma`), ambas por série (fase, polo, núcleo, função):

    MEDICAO → uma linha por série, uma coluna por parâmetro; as colunas calculadas
              (erro de relação, erro de pickup e de tempo) saem da avaliação;
    CURVA   → pontos (tensão × corrente) por núcleo, com a tensão de joelho.

Os cálculos estão em `calculos_subestacao.py` (cada um com a fonte) e os critérios vêm
da classe da placa (TC/TP) ou da tolerância lançada (relé). Sem critério, o valor sai
"sem critério definido" — nunca "conforme". Valor ausente nunca vira zero.

As fichas mostram a campanha atual (sem histórico de campanhas, diferente do
transformador): ver docs/25, seção 3.
"""
from collections import Counter, defaultdict
from apps.cadastros.models import Equipamento, ModuloTecnico

from . import calculos_subestacao as cs
from .carta_subestacao import (
    CONSIDERACOES_SUBESTACAO,
    CONTEUDO_CS,
    CONTEUDO_DJ,
    CONTEUDO_RP,
    CONTEUDO_TC,
    CONTEUDO_TP,
    GLOSSARIO_CS,
    GLOSSARIO_DJ,
    GLOSSARIO_RP,
    GLOSSARIO_TC,
    GLOSSARIO_TP,
)
from .contexto import parametros_registrados, restaurar
from .models import DadosPlacaSubestacao, Ensaio, FormaEnsaio, RegistroEnsaioSubestacao, ResultadoEnsaio, SituacaoResultado
from .relatorio import (
    REALIZADO,
    STATUS_ROTULO,
    ModuloEnsaiosLaboratoriais,
    _Campanha,
    _distribuicao,
    _instrumento,
    _lista,
    _status,
    _um,
    rotulo_condicao,
)

FONTE_CLASSE = {"ENSAIO_ELETRICO_TC": "TC", "ENSAIO_ELETRICO_TP": "TP"}
FONTE_NORMA_RELACAO = {"TC": "IEC 61869-2", "TP": "IEC 61869-3"}
ROTULOS_LAUDO = {"conclusao": "Observações", "informacoes": "Instrumentação Utilizada", "proxima": "Data da Próxima Análise"}


def _celula(v=None):
    if v is None:
        return {"valor": None, "texto": "", "conforme": None}
    return {"valor": v.valor, "texto": v.valor_texto, "conforme": None}


# ----------------------------- Avaliação da linha -----------------------------
def _avaliar_linha(modulo, sigla, celulas, placa):
    """
    Preenche as colunas calculadas de uma linha (série) com o critério de cada uma.
    Só o que a norma (classe da placa) ou o próprio lançamento (tolerância) define vira
    "conforme/fora". Sem isso, a célula fica sem critério.
    """
    if modulo in FONTE_CLASSE and sigla == "RELA":
        nominal = placa.relacao_transformacao if placa else None
        erro = cs.erro_relacao(celulas["RELACAO_MEDIDA"]["valor"], nominal)
        admissivel = _criterio_erro_relacao(placa, modulo)
        conforme = None
        if erro is not None and admissivel is not None:
            conforme = abs(erro) <= admissivel
        celulas["ERRO_RELACAO"] = {"valor": erro, "texto": "", "conforme": conforme}
        if "POLARIDADE" in celulas and placa and placa.polaridade and celulas["POLARIDADE"]["texto"].strip():
            celulas["POLARIDADE"]["conforme"] = (
                celulas["POLARIDADE"]["texto"].strip().casefold() == placa.polaridade.strip().casefold()
            )
    if modulo == ModuloTecnico.ENSAIO_ELETRICO_RP.value and "ESPERADO" in celulas:
        # Pickup e tempo de relé: o erro é frente ao valor esperado; o critério é a tolerância da linha.
        erro = cs.erro_percentual(celulas["MEDIDO"]["valor"], celulas["ESPERADO"]["valor"])
        tolerancia = celulas["TOLERANCIA"]["valor"]
        celulas["ERRO"] = {"valor": erro, "texto": "", "conforme": cs.dentro_da_tolerancia(erro, tolerancia)}


def _criterio_erro_relacao(placa, modulo):
    """Erro admissível da classe da placa (IEC 61869-2 ou -3). Sem classe na tabela = None."""
    if not placa or modulo not in FONTE_CLASSE:
        return None
    return cs.erro_admissivel_relacao(placa.classe_exatidao, FONTE_CLASSE[modulo])


# ------------------------------- Fichas -------------------------------
def _ficha_medicao(ensaio, params, atual, placa):
    colunas = [
        {"codigo": p.codigo, "nome": p.nome, "unidade": p.unidade, "casas": p.casas_decimais,
         "calculado": p.calculado, "tipo_limite": p.tipo_limite, "norma": p.norma}
        for p in params
    ]
    conformes, linhas = [], []
    if atual is not None:
        por_serie = {}
        for v in atual.valores():
            por_serie.setdefault(v.serie, {})[v.parametro.codigo] = v
        for nome, valores in por_serie.items():
            celulas = {p.codigo: _celula(valores.get(p.codigo)) for p in params if not p.calculado}
            for p in params:
                if p.calculado:
                    celulas[p.codigo] = _celula()
            _avaliar_linha(ensaio.modulo, ensaio.sigla, celulas, placa)
            linhas.append({"serie": nome, "celulas": celulas})
            conformes.extend(c["conforme"] for c in celulas.values() if c["conforme"] is not None)
    indicadores = {}
    if ensaio.sigla == "TEMP" and linhas:
        indicadores = {
            "simultaneidade_abertura_ms": cs.simultaneidade([l["celulas"]["TEMPO_ABERTURA"]["valor"]
                                                             for l in linhas if "TEMPO_ABERTURA" in l["celulas"]]),
            "simultaneidade_fechamento_ms": cs.simultaneidade([l["celulas"]["TEMPO_FECHAMENTO"]["valor"]
                                                               for l in linhas if "TEMPO_FECHAMENTO" in l["celulas"]]),
        }
    criterio = None
    if ensaio.sigla == "RELA" and ensaio.modulo in FONTE_CLASSE:
        tipo = FONTE_CLASSE[ensaio.modulo]
        criterio = {
            "norma": f"{tipo} — {FONTE_NORMA_RELACAO[tipo]}",
            "classe": placa.classe_exatidao if placa else "",
            "relacao_nominal": placa.relacao_transformacao if placa else None,
            "admissivel": _criterio_erro_relacao(placa, ensaio.modulo),
        }
    return {"tipo": "MEDICAO", "colunas": colunas, "linhas": linhas, "indicadores": indicadores,
            "criterio": criterio, "conformes": conformes}


def _ficha_curva(ensaio, params, atual):
    pontos, series = [], []
    if atual is not None:
        for v in atual.valores():
            if v.valor is None or v.posicao is None:
                continue
            pontos.append({"serie": v.serie, "tensao": v.posicao, "corrente": v.valor})
            if v.serie not in series:
                series.append(v.serie)
    tensoes = sorted({p["tensao"] for p in pontos})
    tabela = []
    for t in tensoes:
        correntes = {s: next((p["corrente"] for p in pontos if p["serie"] == s and p["tensao"] == t), None)
                     for s in series}
        tabela.append({"tensao": t, "correntes": correntes})
    joelhos = {s: cs.joelho_excitacao([(p["tensao"], p["corrente"]) for p in pontos if p["serie"] == s])
               for s in series}
    return {
        "tipo": "CURVA", "series": series, "tabela": tabela, "joelhos": joelhos,
        "criterio": None, "conformes": [],
        "grafico": [{"nome": s, "pontos": sorted([{"tensao": p["tensao"], "corrente": p["corrente"]}
                                                  for p in pontos if p["serie"] == s], key=lambda x: x["tensao"])}
                    for s in series],
        "colunas": [{"codigo": p.codigo, "nome": p.nome, "unidade": p.unidade, "casas": p.casas_decimais}
                    for p in params],
    }


def montar_ficha_subestacao(ensaio, params, resultado, atual, placa, solicitado) -> dict:
    """Ficha de um ensaio de subestação: textos do laudo, avaliação e o corpo (medição ou curva)."""
    if resultado is not None:
        params = parametros_registrados(resultado, params)
        contexto = resultado.contexto_tecnico or {}
        if "dados_placa" in contexto:
            # Laudo emitido guarda a placa do momento do lançamento, não a atual.
            placa = restaurar(DadosPlacaSubestacao, contexto["dados_placa"]) if contexto["dados_placa"] else None
    if ensaio.forma == FormaEnsaio.CURVA:
        corpo = _ficha_curva(ensaio, params, atual)
    else:
        corpo = _ficha_medicao(ensaio, params, atual, placa)
    conformes = corpo.pop("conformes")
    status = _status(resultado, conformes)
    r = resultado
    return {
        "sigla": ensaio.sigla, "nome": ensaio.nome, "rotulo": ensaio.sigla,
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


# O que o editor de lançamento mostra depois de salvar: a parte calculada da ficha.
CAMPOS_AVALIACAO_SUBESTACAO = ("tipo", "status", "status_rotulo", "avaliados", "fora", "colunas", "linhas",
                               "indicadores", "criterio", "series", "tabela", "joelhos", "grafico")


def avaliar_resultado_subestacao(resultado) -> dict:
    """Os cálculos da ficha só com este resultado (sem histórico), com as mesmas regras do relatório."""
    params = [p for p in resultado.ensaio.parametros.all() if p.ativo]
    atual = _Campanha(resultado)
    placa = _um(resultado.item.equipamento, "dados_placa_subestacao")
    ficha = montar_ficha_subestacao(resultado.ensaio, params, resultado, atual, placa, solicitado=False)
    return {k: ficha[k] for k in CAMPOS_AVALIACAO_SUBESTACAO if k in ficha}


# ---------------------------------- Módulo ----------------------------------
class ModuloEnsaioSubestacao(ModuloEnsaiosLaboratoriais):
    """Base dos cinco relatórios de subestação: um módulo por tipo de equipamento."""

    chave = ""
    equipamento = ""  # rótulo no singular, para o resumo ("foi ensaiado 1 transformador de corrente")
    equipamento_plural = ""
    carta_conteudo = carta_glossario = carta_consideracoes = ()
    tabelas_normativas = ()

    def textos_carta(self, tecnico=None, ctx=None) -> dict:
        textos = super().textos_carta(tecnico, ctx)
        textos["consideracoes"] = list(CONSIDERACOES_SUBESTACAO) + list(textos["consideracoes"])
        return textos

    def montar(self, ctx) -> dict:
        ensaios = list(Ensaio.objects.ativos().filter(modulo=self.chave).prefetch_related("parametros"))
        params = {e.id: [p for p in e.parametros.all() if p.ativo] for e in ensaios}
        itens = ctx.itens
        equipamentos = {
            e.id: e for e in Equipamento.objects.filter(id__in={i.equipamento_id for i in itens})
            .select_related("tipo_equipamento", "setor__area", "dados_placa_subestacao")
        }
        resultados = defaultdict(dict)
        for r in (ResultadoEnsaio.objects.ativos().filter(item__in=itens, ensaio__modulo=self.chave)
                  .select_related("ensaio", "instrumento", "item__carregamento", "item__coleta_oleo",
                                  "item__registro_eletrico", "item__coleta_fluido", "item__registro_subestacao")
                  .prefetch_related("valores__parametro")):
            resultados[r.item_id][r.ensaio_id] = r
        registros = {r.item_id: r for r in RegistroEnsaioSubestacao.objects.ativos().filter(item__in=itens)
                     .prefetch_related("ensaios")}

        saida = []
        for item in itens:
            eq = equipamentos[item.equipamento_id]
            placa = _um(eq, "dados_placa_subestacao")
            registro = registros.get(item.id)
            solicitados = {e.id for e in registro.ensaios.all()} if registro else set()
            fichas = []
            for ensaio in ensaios:
                resultado = resultados[item.id].get(ensaio.id)
                if ensaio.id not in solicitados and resultado is None:
                    continue
                atual = _Campanha(resultado) if resultado else None
                fichas.append(montar_ficha_subestacao(ensaio, params[ensaio.id], resultado, atual, placa,
                                                      ensaio.id in solicitados))
            saida.append({
                "item_id": item.id, "tag": eq.tag, "equipamento": eq.nome,
                "area": eq.setor.area.nome if eq.setor_id else "—", "setor": eq.setor.nome if eq.setor_id else "—",
                "condicao": rotulo_condicao(item.condicao),
                "cadastro": self._cadastro(eq, placa),
                "tipos_ensaio": [{"sigla": e.sigla, "nome": e.nome, "solicitado": e.id in solicitados}
                                 for e in ensaios],
                "registro": self._registro(registro),
                "ensaios": fichas,
            })
        cliente = ctx.rel.cliente
        return {
            "equipamentos": saida, "kpis": self._kpis(saida), "resumo": self._resumo(saida),
            "contato_cliente": {"telefone": cliente.telefone, "email": cliente.email},
        }

    # --- Partes ---
    @staticmethod
    def _registro(r):
        if r is None:
            return None
        return {"data": r.data_ensaio, "analista": r.analista,
                "temperatura_equipamento_c": r.temperatura_equipamento_c,
                "temperatura_ambiente_c": r.temperatura_ambiente_c, "umidade_relativa_pct": r.umidade_relativa_pct}

    @staticmethod
    def _cadastro(eq, p) -> dict:
        return {
            "local": eq.setor.nome if eq.setor_id else "",
            "identificacao": " - ".join(x for x in [eq.tag, eq.nome] if x),
            "numero_serie": eq.numero_serie, "numero_patrimonio": eq.numero_patrimonio,
            "fabricante": eq.fabricante, "ano_fabricacao": eq.ano_fabricacao,
            "tipo_equipamento": eq.tipo_equipamento.nome if eq.tipo_equipamento_id else eq.tipo,
            "modelo": eq.modelo,
            "tensao_nominal_kv": p.tensao_nominal_kv if p else None,
            "corrente_nominal_a": p.corrente_nominal_a if p else None,
            "relacao_texto": p.relacao_texto if p else "",
            "relacao_transformacao": p.relacao_transformacao if p else None,
            "classe_exatidao": p.classe_exatidao if p else "",
            "carga_nominal_va": p.carga_nominal_va if p else None,
            "numero_nucleos": p.numero_nucleos if p else None,
            "polaridade": p.polaridade if p else "",
            "numero_polos": p.numero_polos if p else None,
            "capacidade_interrupcao_ka": p.capacidade_interrupcao_ka if p else None,
            "mecanismo": p.mecanismo if p else "",
            "funcoes_protecao": [linha.strip() for linha in (p.funcoes_protecao if p else "").splitlines()
                                 if linha.strip()],
        }

    def _kpis(self, equipamentos) -> dict:
        fichas = [f for e in equipamentos for f in e["ensaios"]]
        proximas = [f["data_proxima"] for f in fichas if f["data_proxima"]]
        return {
            "equipamentos": len(equipamentos),
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
            "destaques": self._destaques(equipamentos),
        }

    def _destaques(self, equipamentos) -> list:
        """Maior erro por ensaio (erro de relação, de pickup ou de tempo) e maior simultaneidade do DJ."""
        destaques, vistos = [], set()
        for ficha in (f for e in equipamentos for f in e["ensaios"] if f["tipo"] == "MEDICAO"):
            if ficha["sigla"] in vistos:
                continue
            vistos.add(ficha["sigla"])
            colunas = [c for c in ("ERRO_RELACAO", "ERRO") if any(c in linha["celulas"] for linha in ficha["linhas"])]
            erros = [abs(linha["celulas"][c]["valor"]) for e in equipamentos for f in e["ensaios"]
                     if f["sigla"] == ficha["sigla"] for linha in f["linhas"] for c in colunas
                     if linha["celulas"][c]["valor"] is not None]
            if erros:
                destaques.append({"rotulo": f"Maior erro — {ficha['sigla']}", "valor": max(erros), "unidade": "%",
                                  "casas": 2, "detalhe": self._detalhe_erro(ficha)})
            simultaneidades = [f["indicadores"][k] for e in equipamentos for f in e["ensaios"]
                               if f["sigla"] == ficha["sigla"] for k in f.get("indicadores", {})
                               if f["indicadores"][k] is not None]
            if simultaneidades:
                destaques.append({"rotulo": f"Maior simultaneidade entre polos — {ficha['sigla']}",
                                  "valor": max(simultaneidades), "unidade": "ms", "casas": 1,
                                  "detalhe": "critério do fabricante"})
        return destaques

    @staticmethod
    def _detalhe_erro(ficha) -> str:
        criterio = ficha.get("criterio")
        if criterio and criterio.get("admissivel") is not None:
            return f"admitido ± {criterio['admissivel']} % (classe {criterio['classe']}, {criterio['norma'].split(' — ')[-1]})"
        if criterio:
            return "sem critério definido para a classe da placa"
        return "tolerância informada no lançamento"

    def _resumo(self, equipamentos) -> str:
        fichas = [f for e in equipamentos for f in e["ensaios"]]
        if not equipamentos:
            return ""
        n = len(equipamentos)
        feitos = list(dict.fromkeys(f["rotulo"] for f in fichas if f["situacao"] == REALIZADO))
        conformes = sum(1 for f in fichas if f["status"] == "CONFORME")
        fora = [f["rotulo"] for f in fichas if f["status"] == "NAO_CONFORME"]
        sem_criterio = [f["rotulo"] for f in fichas if f["status"] == "SEM_CRITERIO"]
        pendentes = [f"{f['rotulo']} ({f['status_rotulo'].lower()})" for f in fichas if f["situacao"] != REALIZADO]
        sujeito = (f"foi ensaiado 1 {self.equipamento}" if n == 1
                   else f"foram ensaiados {n} {self.equipamento_plural}")
        partes = [f"Neste ciclo {sujeito}" + (f", com os ensaios {_lista(feitos)}." if feitos else ".")]
        if feitos:
            if conformes or fora:
                txt = f"{conformes} {'ensaio ficou' if conformes == 1 else 'ensaios ficaram'} dentro das referências"
                txt += f" e {len(fora)} fora delas ({_lista(fora)})" if fora else " e nenhum fora delas"
                if sem_criterio:
                    txt += f"; {_lista(sem_criterio)} sem critério de aceitação definido"
            else:
                # Nenhum critério neste ciclo: resultados informativos, sem "0 dentro".
                txt = f"{_lista(feitos)} sem critério de aceitação definido (resultados informativos)"
            partes.append(txt + ".")
        if pendentes:
            partes.append(f"{'Ensaio sem resultado' if len(pendentes) == 1 else 'Ensaios sem resultado'}: "
                          f"{_lista(pendentes)}.")
        return " ".join(partes)


class ModuloTC(ModuloEnsaioSubestacao):
    chave = ModuloTecnico.ENSAIO_ELETRICO_TC.value
    equipamento, equipamento_plural = "transformador de corrente", "transformadores de corrente"
    carta_conteudo = CONTEUDO_TC
    carta_glossario = GLOSSARIO_TC


class ModuloTP(ModuloEnsaioSubestacao):
    chave = ModuloTecnico.ENSAIO_ELETRICO_TP.value
    equipamento, equipamento_plural = "transformador de potencial", "transformadores de potencial"
    carta_conteudo = CONTEUDO_TP
    carta_glossario = GLOSSARIO_TP


class ModuloDJ(ModuloEnsaioSubestacao):
    chave = ModuloTecnico.ENSAIO_ELETRICO_DJ.value
    equipamento, equipamento_plural = "disjuntor", "disjuntores"
    carta_conteudo = CONTEUDO_DJ
    carta_glossario = GLOSSARIO_DJ


class ModuloCS(ModuloEnsaioSubestacao):
    chave = ModuloTecnico.ENSAIO_ELETRICO_CS.value
    equipamento, equipamento_plural = "chave seccionadora", "chaves seccionadoras"
    carta_conteudo = CONTEUDO_CS
    carta_glossario = GLOSSARIO_CS


class ModuloRP(ModuloEnsaioSubestacao):
    chave = ModuloTecnico.ENSAIO_ELETRICO_RP.value
    equipamento, equipamento_plural = "relé de proteção", "relés de proteção"
    carta_conteudo = CONTEUDO_RP
    carta_glossario = GLOSSARIO_RP


MODULO_TC, MODULO_TP, MODULO_DJ, MODULO_CS, MODULO_RP = ModuloTC(), ModuloTP(), ModuloDJ(), ModuloCS(), ModuloRP()
