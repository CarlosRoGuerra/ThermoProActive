"""
Família "inspeção por rota" do relatório técnico.

Tecnologias em que o analista percorre uma rota, classifica cada equipamento
(Condição) e registra análises (Achado) que viram Ordens de Serviço Preditivas.
Vibração e termografia são desta família: o que muda entre elas são as grandezas
medidas e a norma da carta — declaradas em `ModuloInspecaoRota` (ver `modulos.py`).

Monta a parte técnica do payload do dossiê — `secao_b` (KPIs) e `secao_d` (folhas
de OSP) — e o conteúdo técnico da Carta ao Cliente (itens 3, 5, 6, 7 e 8).
"""
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal

from ..models import Achado, ItemInspecao
from .shell import ContextoRelatorio, rotulo_condicao


@dataclass(frozen=True)
class MediaDiagnostico:
    """KPI "Média dos Valores de Diagnóstico": média de um campo medido do Achado."""

    chave: str  # nome em `secao_b.diagnostico_medio`
    campo: str  # campo do Achado
    casas: int


MEDIA_VELOCIDADE = MediaDiagnostico("velocidade", "velocidade_global", 2)
MEDIA_ACELERACAO = MediaDiagnostico("aceleracao", "aceleracao_global", 2)
MEDIA_TEMPERATURA = MediaDiagnostico("temperatura", "temperatura_medida", 1)
# Chaves sempre presentes no payload (nulas quando o módulo não mede a grandeza).
MEDIAS_DO_PAYLOAD = (MEDIA_VELOCIDADE, MEDIA_ACELERACAO, MEDIA_TEMPERATURA)


# ------------------------- Carta ao Cliente (modelo Word) ---------------------
# Textos do modelo VB_Carta_Foroni aprovado pelo cliente — padrão da família
# (falam de OSP e Grau de Risco); um módulo pode trocar o glossário e as
# considerações (ver termografia.py). Fonte única: o .docx lê daqui e a carta em
# PDF recebe os mesmos textos no payload (`carta`, via `textos_carta()`).
CARTA_CONTEUDO = (
    "Seção A – Carta ao Cliente",
    "Seção B – KPI’s Dashboard",
    "Seção C – Relação de Equipamentos Contemplados",
    "Seção D – Ordens de Serviços Preditivos [corretiva orientada pela preditiva]",
)

CARTA_GLOSSARIO = (
    ("6.1", "O.S.P.", "Ordem de Serviço Preditivo gerada para correção de cada anomalia detectada."),
    ("6.2", "G.R.", "Grau de Risco: Determinam o prazo de correção das anomalias detectadas."),
    ("6.2.1", "GR-1", "Grau de Risco N°.01: Risco eminente – Recomenda-se intervenção imediata pela equipe de manutenção em prazo máximo de 03 dias. Em casos extremos o inspetor poderá solicitar o reparo em caráter de urgência."),
    ("6.2.2", "GR-2", "Grau de Risco N°.02: Risco elevado – Recomenda-se intervenção pela equipe de manutenção em prazo máximo de 10 dias."),
    ("6.2.3", "GR-3", "Grau de Risco N°.03: Risco moderado – Recomenda-se intervenção pela equipe de manutenção em prazo máximo de 20 dias."),
    ("6.2.4", "GR-4", "Grau de Risco N°.04: Risco baixo – Recomenda-se intervenção pela equipe de manutenção em parada programada prazo máximo de 30 dias."),
    ("6.3", "MP", "Monitoramento Prejudicado: Ocorre em casos em que há existência de obstrução parcial aos equipamentos a serem monitorados. É interessante avaliar o nível de obstrução juntamente com o departamento de segurança do trabalho, sendo possível programar a desobstrução temporária."),
    ("6.4", "NM", "Não Monitorado: Ocorre em casos em que há existência de obstrução total aos equipamentos a serem monitorados; e/ou que coloque em risco a integridade física dos trabalhadores. É interessante avaliar a possibilidade de desobstrução do equipamento juntamente com o departamento de segurança do trabalho e/ou criar condição segura aos trabalhadores."),
    ("6.5", "OK", "Normalidade Operacional: Carga ≥ 70,0%. Os circuitos carregados não apresentam anomalias térmicas."),
    ("6.6", "PDM", "Parado Devido Manutenção: Equipamento encontra-se parado devido algum tipo de intervenção da equipe de manutenção;"),
    ("6.7", "PDP", "Parado Devido Processo: Equipamento encontra-se parado devido anormalidades do processo produtivo;"),
    ("6.8", "LA", "Lado Acoplado;"),
    ("6.9", "LOA", "Lado Oposto ao Acoplamento."),
)

CARTA_CONSIDERACOES = (
    "Os critérios considerados nas análises das anomalias detectadas são técnicos, associados com a vasta experiência do analista que dará diagnóstico preciso referente à condição dinâmica na qual o objeto avaliado está submetido, porém vale lembrar que cada equipamento tem seu nível de criticidade para a planta onde está instalado, e deverá ser levado em consideração pelo controle e planejamento da manutenção durante a elaboração do plano de manutenções corretivas baseadas pela manutenção preditiva.",
    "As OSP´s emergenciais (GR-1) foram apresentadas, discutidas e tratadas com o planejamento e controle de manutenção ao término das medições.",
    "Toda anomalia detectada deverá ser corrigida o mais rápido possível, pois o prazo sugerido serve apenas como referência, haja vista que a avaliação contratada não é executada em periodicidade mensal (caso sua planta realize avaliação mensal, desconsiderar este parágrafo).",
)


# ------------------------------ Normalizações --------------------------------
def _concat(categoria, texto) -> str:
    """[valor do dropdown] + " " + [texto livre] (regra do cliente)."""
    return " ".join(p for p in [(categoria or "").strip(), (texto or "").strip()] if p)


def _tem_conteudo_tecnico(a) -> bool:
    """Achado sem componente E sem anomalia não vira anomalia/OSP nem entra nos KPIs."""
    tem_componente = bool(a.tipo_componente_id or (a.componente_texto or "").strip())
    tem_anomalia = bool(a.tipo_anomalia_id or (a.anomalia_texto or "").strip())
    return tem_componente or tem_anomalia


def _distribuicao(tally: dict) -> list:
    total = sum(tally.values()) or 1
    return [
        {"rotulo": k, "total": v, "percentual": round(v * 100 / total, 1)}
        for k, v in sorted(tally.items(), key=lambda x: -x[1])
    ]


def _avaliacao_osp(o):
    """Avaliação de Resultados (tabela verde da OSP): preditiva × emergencial e o ROI."""
    if o is None:
        return None
    return {
        "linhas": [
            {"rotulo": "Mão de Obra [h]", "pred_q": o.pred_mao_obra_h, "pred_v": o.pred_mao_obra_valor,
             "emerg_q": o.emerg_mao_obra_h, "emerg_v": o.emerg_mao_obra_valor},
            {"rotulo": "M.O. Terceirizada [h]", "pred_q": o.pred_terceirizado_h, "pred_v": o.pred_terceirizado_valor,
             "emerg_q": o.emerg_terceirizado_h, "emerg_v": o.emerg_terceirizado_valor},
            {"rotulo": "Material Reparo [$]", "pred_q": None, "pred_v": o.pred_material_valor,
             "emerg_q": None, "emerg_v": o.emerg_material_valor},
            {"rotulo": "Produção [h|Ton.]", "pred_q": o.pred_producao_h, "pred_v": o.pred_producao_valor,
             "emerg_q": o.emerg_producao_h, "emerg_v": o.emerg_producao_valor},
            {"rotulo": "Outros [$]", "pred_q": None, "pred_v": o.pred_outros_valor,
             "emerg_q": None, "emerg_v": o.emerg_outros_valor},
        ],
        "total_preditiva": o.total_preditiva,
        "total_emergencial": o.total_emergencial,
        "retorno": o.retorno_investimento,
    }


# Nível de alarme (KPI "Status dos Tipos de Alarmes"): reagrupa o GR já existente
# em 3 níveis gerenciais — não é um catálogo novo, só uma leitura diferente da
# mesma severidade (mesma normalização de sigla de OrdemServico.gerar_de_achado,
# "GR-4" → "GR4").
NIVEL_ALARME = {
    "GR1": "Nível 3 — Crítico", "GR2": "Nível 2 — Alerta",
    "GR3": "Nível 1 — Aviso", "GR4": "Nível 1 — Aviso",
}


@dataclass(frozen=True)
class ModuloInspecaoRota:
    """
    Módulo de uma tecnologia da família "inspeção por rota".

    `medias`: grandezas que entram no KPI "Média dos Valores de Diagnóstico".
    `tabelas_normativas`: tabelas que a carta desenha no item 5 (chaves conhecidas
    pelo gerador da carta, ex.: "ISO_10816").
    """

    chave: str
    medias: tuple = ()
    tabelas_normativas: tuple = ()
    carta_conteudo: tuple = field(default=CARTA_CONTEUDO)
    carta_glossario: tuple = field(default=CARTA_GLOSSARIO)
    carta_consideracoes: tuple = field(default=CARTA_CONSIDERACOES)
    # Termos do glossário que abrem uma folha nova na carta em PDF (cada folha é uma
    # A4 fixa); o .docx ignora — o Word pagina sozinho.
    carta_quebras_glossario: tuple = ()

    def montar(self, ctx: ContextoRelatorio) -> dict:
        """Parte técnica do payload: `secao_b` (KPIs) e `secao_d` (folhas de OSP)."""
        return _montar_inspecao(ctx, self)

    def textos_carta(self, tecnico=None) -> dict:
        """
        Textos técnicos da carta (itens 3, 6 e 8) — os mesmos do .docx, para a carta em
        PDF. O parágrafo do item 7 desta família é montado no front a partir da Seção B.
        """
        return {
            "conteudo": list(self.carta_conteudo),
            "glossario": [{"n": n, "sigla": sigla, "texto": texto} for n, sigla, texto in self.carta_glossario],
            "quebras_glossario": list(self.carta_quebras_glossario),
            "consideracoes": list(self.carta_consideracoes),
            "paragrafos": [],
        }

    def instrumentos_adicionais(self, ctx) -> list:
        """Instrumentação além da dos carregamentos — nenhuma nesta família."""
        return []

    def paragrafos_carta(self, rel) -> list:
        """Parágrafo do item 7 da carta sobre as anomalias e as OSPs deste relatório."""
        return [_paragrafo_anomalias(rel)]


def _montar_inspecao(ctx: ContextoRelatorio, modulo: ModuloInspecaoRota) -> dict:
    from apps.cadastros.models import CriticidadeEquip, Equipamento
    from apps.osp.models import OrdemServico, ResultadoConfirmacao

    # Manutenção corretiva: o ServicoCampo de cada análise técnica, carregado de uma
    # vez (a folha precisa de planos, pontos, economia e equipamento); buscar
    # serviço por serviço dentro do laço seria N+1 num relatório com dezenas de folhas.
    from apps.servicos.models import ServicoCampo
    from apps.servicos.osp_corretiva import numero_da_osp, osp_da_intervencao
    from apps.servicos.relatorio_corretivo import payload_corretivo_do_dossie

    rel, request = ctx.rel, ctx.request
    cliente = rel.cliente

    # Distribuição das condições (KPI): por análise (achado); equipamento sem
    # análise entra com a condição do item.
    cond_tally: dict = {}
    for item in ctx.itens:
        achados = list(item.achados.all())
        if achados:
            for a in achados:
                r = rotulo_condicao(a.condicao)
                cond_tally[r] = cond_tally.get(r, 0) + 1
        else:
            r = rotulo_condicao(item.condicao)
            cond_tally[r] = cond_tally.get(r, 0) + 1

    servicos_corretivos = {
        s.analise_tecnica_id: s
        for s in (
            ServicoCampo.objects.ativos()
            .filter(analise_tecnica__item__carregamento__relatorio=rel)
            .select_related(
                "cliente", "equipamento", "analista", "instrumento", "economia",
                "osp", "item",
            )
            .prefetch_related("planos", "pontos")
        )
    }

    # Apuração (Seção B) E folhas (Seção D) saem da MESMA lista de achados — a
    # contagem de anomalias bate sempre com o número de folhas.
    achados_qs = (
        Achado.objects.filter(item__carregamento__relatorio=rel)
        .select_related(
            "tipo_componente", "tipo_anomalia", "recomendacao", "condicao",
            "item__equipamento__setor__area", "item__carregamento__analista", "osp",
        )
        .prefetch_related("imagens")
        .order_by("item__equipamento__setor__area__nome", "item__equipamento__setor__nome",
                  "item__equipamento__tag", "id")
    )
    comp_tally, anom_tally, alarme_tally = {}, {}, {}
    somas = {m.chave: Decimal("0") for m in modulo.medias}
    contagens = {m.chave: 0 for m in modulo.medias}
    custo_evitado = Decimal("0")
    diagnosticos_avaliados = diagnosticos_confirmados = 0
    secao_d = []
    for a in achados_qs:
        if not _tem_conteudo_tecnico(a):
            continue
        comp_cat = a.tipo_componente.nome if a.tipo_componente_id else (a.componente_texto or "Outros")
        anom_cat = a.tipo_anomalia.nome if a.tipo_anomalia_id else (a.anomalia_texto or "Outros")
        comp_tally[comp_cat] = comp_tally.get(comp_cat, 0) + 1
        anom_tally[anom_cat] = anom_tally.get(anom_cat, 0) + 1
        for m in modulo.medias:
            valor = getattr(a, m.campo)
            if valor is not None:
                somas[m.chave] += valor
                contagens[m.chave] += 1
        if a.condicao_id:
            sigla_norm = (a.condicao.sigla or "").strip().upper().replace("-", "").replace(" ", "")
            nivel = NIVEL_ALARME.get(sigla_norm)
            if nivel:
                alarme_tally[nivel] = alarme_tally.get(nivel, 0) + 1

        eq = a.item.equipamento
        setor = eq.setor
        area = setor.area if setor else None
        servico_corretivo = servicos_corretivos.get(a.id)
        corretiva = (
            payload_corretivo_do_dossie(servico_corretivo)
            if servico_corretivo is not None else None
        )
        # OSP ligada diretamente a ESTE achado — alimenta os KPIs da Seção B
        # (custo evitado, taxa de acerto), que são sobre a OSP que ESTA análise
        # gerou, não sobre uma OSP de origem herdada de outra análise/relatório.
        osp = getattr(a, "osp", None)
        if osp is not None:
            custo_evitado += osp.retorno_investimento
            if osp.resultado_confirmacao != ResultadoConfirmacao.PENDENTE:
                diagnosticos_avaliados += 1
                if osp.resultado_confirmacao == ResultadoConfirmacao.CONFIRMADO:
                    diagnosticos_confirmados += 1
        # A OSP EXIBIDA na folha pode ser outra: numa intervenção que herdou uma
        # OSP de origem, `a.osp` fica vazio de propósito (a origem não é
        # sequestrada para esta análise) — usa o ServicoCampo já carregado em
        # lote, sem consulta extra (mesma regra da tela de Análise final).
        osp_num = numero_da_osp(
            osp_da_intervencao(a, servico=servico_corretivo), fallback=(a.numero_osp or "—")
        )
        imagens = [
            {"tipo": img.get_tipo_display(), "arquivo": request.build_absolute_uri(img.arquivo.url),
             "legenda": img.legenda}
            for img in a.imagens.all()
        ]
        secao_d.append({
            "osp": osp_num,
            "area": area.nome if area else "—",
            "setor": setor.nome if setor else "—",
            "tag": eq.tag,
            "equipamento": eq.nome,
            "componente": _concat(a.tipo_componente.nome if a.tipo_componente_id else "", a.componente_texto),
            "anomalia": _concat(a.tipo_anomalia.nome if a.tipo_anomalia_id else "", a.anomalia_texto),
            "recomendacao": _concat(a.recomendacao.nome if a.recomendacao_id else "", a.recomendacao_texto),
            "observacao": a.observacoes,
            "grau_risco": rotulo_condicao(a.condicao),
            "grau_risco_descricao": a.condicao.nome if a.condicao_id else "",
            # Medições do Achado. Cada módulo do front mostra só as suas.
            "amplitude_velocidade": a.velocidade_global,
            "amplitude_aceleracao": a.aceleracao_global,
            "temperatura_medida": a.temperatura_medida,
            "temperatura_referencia": a.temperatura_referencia,
            "delta_t": a.delta_t,
            "carga_percentual": a.carga_percentual,
            # Correção pela corrente (C.T.M.): nulas até a fórmula ser definida com o cliente.
            "temperatura_medida_corrigida": a.temperatura_medida_corrigida,
            "delta_t_corrigido": a.delta_t_corrigido,
            "corrente": [a.corrente_nominal, a.corrente_a, a.corrente_b, a.corrente_c],
            "tensao": [a.tensao_nominal, a.tensao_a, a.tensao_b, a.tensao_c],
            "analista": a.item.carregamento.analista.nome if a.item.carregamento.analista_id else "",
            "imagens": imagens,
            "avaliacao": _avaliacao_osp(osp),
            # Manutenção corretiva: o layout da folha muda por tipo (hoje só o
            # balanceamento tem apresentação definida). Vazio nos achados
            # preditivos, que seguem com o layout de sempre.
            "tipo_corretiva": a.item.carregamento.tipo_corretiva,
            "tipo_corretiva_display": a.item.carregamento.get_tipo_corretiva_display(),
            "corretiva": corretiva,
        })

    # --- MTBF (proxy) — tempo médio, em dias, entre OSPs consecutivas do mesmo
    # equipamento, olhando TODO o histórico do cliente (não só este relatório: 1
    # OSP isolada não tem "intervalo"). Sem um cadastro de parada/falha real, é a
    # melhor aproximação com os dados existentes.
    datas_por_equip: dict = defaultdict(list)
    for eq_id, criado in OrdemServico.objects.filter(cliente=cliente).values_list("equipamento_id", "criado_em"):
        datas_por_equip[eq_id].append(criado)
    intervalos_dias = []
    for datas in datas_por_equip.values():
        datas.sort()
        intervalos_dias.extend((b - a).total_seconds() / 86400 for a, b in zip(datas, datas[1:]))
    mtbf_dias = round(sum(intervalos_dias) / len(intervalos_dias), 1) if intervalos_dias else None

    # --- Cobertura de Ativos Preditivos — % dos equipamentos criticidade "A"
    # (crítico ao processo) do cliente que já entraram em alguma rota/coleta,
    # em qualquer tecnologia, não só a deste relatório.
    equipamentos_criticos_ids = set(
        Equipamento.objects.filter(setor__area__cliente=cliente, criticidade=CriticidadeEquip.A)
        .values_list("id", flat=True)
    )
    if equipamentos_criticos_ids:
        ja_monitorados = set(
            ItemInspecao.objects.filter(
                carregamento__cliente=cliente, equipamento_id__in=equipamentos_criticos_ids
            ).values_list("equipamento_id", flat=True).distinct()
        )
        cobertura_ativos = round(len(ja_monitorados) * 100 / len(equipamentos_criticos_ids), 1)
    else:
        cobertura_ativos = None

    # Média dos valores de diagnóstico — só as grandezas que ESTA tecnologia mede.
    diagnostico_medio = {m.chave: None for m in MEDIAS_DO_PAYLOAD}
    for m in modulo.medias:
        if contagens[m.chave]:
            diagnostico_medio[m.chave] = round(somas[m.chave] / contagens[m.chave], m.casas)

    n_equip = len(ctx.equipamentos_ids)
    return {
        "secao_b": {
            "condicoes": _distribuicao(cond_tally),
            "componentes": _distribuicao(comp_tally),
            "anomalias": _distribuicao(anom_tally),
            "equip_monitorados": n_equip,
            # Bate exatamente com o nº de folhas da Seção D.
            "anomalias_diagnosticadas": len(secao_d),
            # Média de anomalias por equipamento monitorado (KPI "aderência").
            "media_anomalias_por_equipamento": round(len(secao_d) / n_equip, 2) if n_equip else 0,
            "diagnostico_medio": diagnostico_medio,
            # Status dos tipos de alarme (GR reagrupado em 3 níveis gerenciais).
            "alarmes": _distribuicao(alarme_tally),
            # Custo evitado (R$): soma do ROI (emergencial − preditivo) das OSPs
            # deste relatório que já têm avaliação de resultados lançada.
            "custo_evitado": custo_evitado,
            # Taxa de acerto do diagnóstico — só entre as OSPs já confirmadas
            # (ou não) pela manutenção; null enquanto nenhuma foi avaliada.
            "taxa_acerto_diagnostico": (
                round(diagnosticos_confirmados * 100 / diagnosticos_avaliados, 1)
                if diagnosticos_avaliados else None
            ),
            "diagnosticos_avaliados": diagnosticos_avaliados,
            # MTBF em dias (proxy — ver nota acima) e cobertura de ativos críticos
            # (%) calculados sobre TODO o histórico do cliente, não só este relatório.
            "mtbf_dias": mtbf_dias,
            "cobertura_ativos_criticos": cobertura_ativos,
        },
        "secao_d": secao_d,
    }


def _lista(itens) -> str:
    itens = list(itens)
    if len(itens) <= 1:
        return itens[0] if itens else ""
    return ", ".join(itens[:-1]) + " e " + itens[-1]


def _paragrafo_anomalias(rel) -> str:
    """Item 7 da carta .docx: anomalias diagnosticadas, por tipo e por Grau de Risco."""
    gr_tally, tipos_anom, n_anom = {}, [], 0
    for a in Achado.objects.filter(item__carregamento__relatorio=rel).select_related("condicao", "tipo_anomalia"):
        if not (a.tipo_anomalia_id or (a.anomalia_texto or "").strip() or a.tipo_componente_id or (a.componente_texto or "").strip()):
            continue
        n_anom += 1
        if a.condicao_id:
            sig = (a.condicao.sigla or a.condicao.nome or "").strip()
            if sig:
                gr_tally[sig] = gr_tally.get(sig, 0) + 1
        nome = (a.tipo_anomalia.nome if a.tipo_anomalia_id else (a.anomalia_texto or "")).strip()
        if nome and nome not in tipos_anom:
            tipos_anom.append(nome)

    if n_anom == 0:
        return ("A partir das medições realizadas, não foram diagnosticadas anomalias que ensejassem "
                "Ordens de Serviço Preditivas neste ciclo.")
    base = "foi diagnosticada 1 anomalia" if n_anom == 1 else f"foram diagnosticadas {n_anom} anomalias"
    tipos = _lista(tipos_anom)
    trecho_tipos = f", do(s) tipo(s): {tipos}" if tipos else ""
    if gr_tally:
        dist = "; ".join(f"{k}: {v}" for k, v in sorted(gr_tally.items()))
        trecho_gr = f" A distribuição por Grau de Risco foi — {dist}."
    else:
        trecho_gr = ""
    return (
        f"A partir das medições realizadas, {base}{trecho_tipos}. Cada anomalia foi classificada "
        f"conforme os Graus de Risco descritos no item 6 e convertida em Ordem de Serviço Preditiva "
        f"na Seção D.{trecho_gr}"
    )
