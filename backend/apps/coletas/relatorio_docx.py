"""
Relatório Final em .docx — o MESMO conteúdo do dossiê em PDF (Capa + Seções
A a D), num único arquivo. Reaproveita o papel timbrado e os estilos já
aprovados da Carta (`carta_docx.py`) e acrescenta B/C/D nesta segunda etapa.

Diferente da Carta (fiel, mm a mm, ao modelo Word do cliente), Seções B/C/D
ainda não têm um gabarito Word aprovado — o gabarito existente (dimensões
"travadas") é o da versão HTML/PDF (`dossie()` em views.py e `dossie.tsx`).
Este módulo repete os MESMOS DADOS e a MESMA lógica de apuração dessa versão,
em layout de tabelas nativo do Word (sem gráficos: Word não tem biblioteca de
gráficos embutida sem depender de imagem rasterizada).
"""
from __future__ import annotations

from decimal import Decimal

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Mm, Pt, RGBColor

from .carta_docx import (
    PRETO,
    _cant_split,
    _dt,
    _fmt_run,
    _p,
    _shade,
    _shade_par,
    criar_documento_base,
    preencher_secao_a,
)


def _titulo_secao(doc, texto):
    """Título de Seção B/C/D — diferente de `_titulo` (formato numerado "1.
    Objetivo" da Carta, com tab stop fixo em 10mm); aqui é só um cabeçalho."""
    return _p(doc, texto, bold=True, size=13, color=PRETO, space_before=6, space_after=8)

CINZA_CLARO = "F1F5F9"
ZEBRA = "F8FAFC"

#: Mesmas cores da Seção B/D no dossiê (dossie.tsx `CORES`/`corCondicao`).
CORES_GR = {
    "GR0": ("16A34A", RGBColor(0xFF, 0xFF, 0xFF)),
    "GR1": ("DC2626", RGBColor(0xFF, 0xFF, 0xFF)),
    "GR2": ("B91C1C", RGBColor(0xFF, 0xFF, 0xFF)),
    "GR3": ("EA580C", RGBColor(0xFF, 0xFF, 0xFF)),
    "GR4": ("FACC15", PRETO),
    "OK": ("16A34A", RGBColor(0xFF, 0xFF, 0xFF)),
}
_COR_PADRAO = ("94A3B8", RGBColor(0xFF, 0xFF, 0xFF))

NIVEL_ALARME = {
    "GR1": "Nível 3 — Crítico", "GR2": "Nível 2 — Alerta",
    "GR3": "Nível 1 — Aviso", "GR4": "Nível 1 — Aviso",
}


def _norm_sigla(cond) -> str:
    if not cond:
        return ""
    return (cond.sigla or cond.nome or "").strip().upper().replace("-", "").replace(" ", "")


def _cor_gr(sigla_norm: str):
    return CORES_GR.get(sigla_norm, _COR_PADRAO)


def _quebra_pagina(doc):
    p = doc.add_paragraph()
    p.paragraph_format.page_break_before = True
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(0)
    return p


def _moeda(v) -> str:
    if v is None:
        return "—"
    return f'R$ {v:,.2f}'.replace(",", "X").replace(".", ",").replace("X", ".")


def _cell(cell, text, *, bold=False, size=9, color=PRETO, fill=None,
          align=WD_ALIGN_PARAGRAPH.LEFT):
    cell.paragraphs[0].alignment = align
    cell.paragraphs[0].paragraph_format.space_after = Pt(0)
    _fmt_run(cell.paragraphs[0].add_run(str(text)), bold=bold, size=size, color=color)
    if fill:
        _shade(cell, fill)


def _tabela_distribuicao(doc, titulo, itens, *, cor_fn=None):
    """Tabela genérica Rótulo | Qtde | % — usada pelos KPIs de distribuição."""
    _p(doc, titulo, bold=True, size=11, space_before=8, space_after=4)
    if not itens:
        _p(doc, "Sem dados neste relatório.", italic=True, size=9, space_after=8)
        return
    tab = doc.add_table(rows=1, cols=3)
    tab.style = "Table Grid"
    hdr = tab.rows[0].cells
    _cell(hdr[0], "Rótulo", bold=True, fill=CINZA_CLARO)
    _cell(hdr[1], "Qtde.", bold=True, fill=CINZA_CLARO, align=WD_ALIGN_PARAGRAPH.CENTER)
    _cell(hdr[2], "%", bold=True, fill=CINZA_CLARO, align=WD_ALIGN_PARAGRAPH.CENTER)
    for it in itens:
        row = tab.add_row().cells
        fill = cor_fn(it["rotulo"])[0] if cor_fn else None
        cor_fg = cor_fn(it["rotulo"])[1] if cor_fn else PRETO
        _cell(row[0], it["rotulo"], bold=bool(fill), color=cor_fg, fill=fill)
        _cell(row[1], it["total"], align=WD_ALIGN_PARAGRAPH.CENTER)
        _cell(row[2], f'{it["percentual"]}%', align=WD_ALIGN_PARAGRAPH.CENTER)
    for row in tab.rows:
        _cant_split(row)
    _p(doc, "", space_after=8)


def _tabela_indicadores(doc, pares):
    """Tabela chave/valor — indicadores numéricos únicos (não-distribuição)."""
    tab = doc.add_table(rows=0, cols=2)
    tab.style = "Table Grid"
    for rotulo, valor in pares:
        row = tab.add_row().cells
        _cell(row[0], rotulo, bold=True, fill=CINZA_CLARO)
        _cell(row[1], valor, align=WD_ALIGN_PARAGRAPH.CENTER)
    for row in tab.rows:
        _cant_split(row)
    _p(doc, "", space_after=8)


# ------------------------------ Coleta dos dados -----------------------------
def _coletar_dados(rel):
    """
    Reproduz a MESMA apuração de `RelatorioInspecaoViewSet.dossie` (views.py) —
    condições/componentes/anomalias/alarmes, KPIs numéricos, Seção C e Seção D —
    mas devolvendo estruturas Python simples (sem Response/URLs absolutas: o
    .docx referencia as imagens pelo caminho local do arquivo).
    """
    from apps.cadastros.models import CriticidadeEquip, Equipamento
    from apps.osp.models import OrdemServico as OSP
    from apps.osp.models import ResultadoConfirmacao

    from .models import Achado, ItemInspecao

    cliente = rel.cliente

    def rotulo(cond):
        return (cond.sigla or cond.nome) if cond else "—"

    def concat(categoria, texto):
        return " ".join(p for p in [(categoria or "").strip(), (texto or "").strip()] if p)

    itens = (
        ItemInspecao.objects.filter(carregamento__relatorio=rel)
        .select_related("equipamento__setor__area", "condicao")
        .prefetch_related("achados__condicao")
        .order_by("equipamento__setor__area__nome", "equipamento__setor__nome",
                  "equipamento__tag", "ordem")
    )
    grupos, cond_tally, equipamentos_ids = {}, {}, set()
    for item in itens:
        eq = item.equipamento
        equipamentos_ids.add(eq.id)
        setor = eq.setor
        area = setor.area if setor else None
        chave = (area.nome if area else "—", setor.nome if setor else "—")
        linhas = grupos.setdefault(chave, [])
        achados = list(item.achados.all())
        linhas.append({"tag": eq.tag, "equipamento": eq.nome, "condicao": rotulo(item.condicao)})
        if achados:
            for a in achados:
                r = rotulo(a.condicao)
                cond_tally[r] = cond_tally.get(r, 0) + 1
        else:
            cond_tally[rotulo(item.condicao)] = cond_tally.get(rotulo(item.condicao), 0) + 1

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
    soma_vel = soma_acel = soma_temp = Decimal("0")
    n_vel = n_acel = n_temp = 0
    custo_evitado = Decimal("0")
    diagnosticos_avaliados = diagnosticos_confirmados = 0
    secao_d = []
    for a in achados_qs:
        tem_componente = bool(a.tipo_componente_id or (a.componente_texto or "").strip())
        tem_anomalia = bool(a.tipo_anomalia_id or (a.anomalia_texto or "").strip())
        if not tem_componente and not tem_anomalia:
            continue
        comp_cat = a.tipo_componente.nome if a.tipo_componente_id else (a.componente_texto or "Outros")
        anom_cat = a.tipo_anomalia.nome if a.tipo_anomalia_id else (a.anomalia_texto or "Outros")
        comp_tally[comp_cat] = comp_tally.get(comp_cat, 0) + 1
        anom_tally[anom_cat] = anom_tally.get(anom_cat, 0) + 1
        if a.velocidade_global is not None:
            soma_vel += a.velocidade_global
            n_vel += 1
        if a.aceleracao_global is not None:
            soma_acel += a.aceleracao_global
            n_acel += 1
        if a.temperatura_medida is not None:
            soma_temp += a.temperatura_medida
            n_temp += 1
        sigla_norm = _norm_sigla(a.condicao)
        nivel = NIVEL_ALARME.get(sigla_norm)
        if nivel:
            alarme_tally[nivel] = alarme_tally.get(nivel, 0) + 1

        eq = a.item.equipamento
        setor = eq.setor
        area = setor.area if setor else None
        osp = getattr(a, "osp", None)
        if osp is not None:
            custo_evitado += osp.retorno_investimento
            if osp.resultado_confirmacao != ResultadoConfirmacao.PENDENTE:
                diagnosticos_avaliados += 1
                if osp.resultado_confirmacao == ResultadoConfirmacao.CONFIRMADO:
                    diagnosticos_confirmados += 1
        osp_num = (
            f"{osp.sequencial_cliente}/{osp.sequencial_global}"
            if osp and osp.sequencial_cliente and osp.sequencial_global
            else (a.numero_osp or "—")
        )
        secao_d.append({
            "osp": osp_num, "area": area.nome if area else "—", "setor": setor.nome if setor else "—",
            "tag": eq.tag, "equipamento": eq.nome,
            "componente": concat(a.tipo_componente.nome if a.tipo_componente_id else "", a.componente_texto),
            "anomalia": concat(a.tipo_anomalia.nome if a.tipo_anomalia_id else "", a.anomalia_texto),
            "recomendacao": concat(a.recomendacao.nome if a.recomendacao_id else "", a.recomendacao_texto),
            "observacao": a.observacoes,
            "grau_risco": rotulo(a.condicao), "sigla_norm": sigla_norm,
            "amplitude_velocidade": a.velocidade_global, "amplitude_aceleracao": a.aceleracao_global,
            "temperatura_medida": a.temperatura_medida, "temperatura_referencia": a.temperatura_referencia,
            "delta_t": a.delta_t, "carga_percentual": a.carga_percentual,
            "analista": a.item.carregamento.analista.nome if a.item.carregamento.analista_id else "",
            "imagens": [img for img in a.imagens.all() if img.arquivo],
            "osp_obj": osp,
        })

    def distribuicao(tally):
        total = sum(tally.values()) or 1
        return [
            {"rotulo": k, "total": v, "percentual": round(v * 100 / total, 1)}
            for k, v in sorted(tally.items(), key=lambda x: -x[1])
        ]

    from collections import defaultdict
    datas_por_equip: dict[int, list] = defaultdict(list)
    for eq_id, criado in OSP.objects.filter(cliente=cliente).values_list("equipamento_id", "criado_em"):
        datas_por_equip[eq_id].append(criado)
    intervalos_dias = []
    for datas in datas_por_equip.values():
        datas.sort()
        intervalos_dias.extend((b - a).total_seconds() / 86400 for a, b in zip(datas, datas[1:]))
    mtbf_dias = round(sum(intervalos_dias) / len(intervalos_dias), 1) if intervalos_dias else None

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

    secao_b = {
        "condicoes": distribuicao(cond_tally), "componentes": distribuicao(comp_tally),
        "anomalias": distribuicao(anom_tally), "alarmes": distribuicao(alarme_tally),
        "equip_monitorados": len(equipamentos_ids), "anomalias_diagnosticadas": len(secao_d),
        "media_anomalias_por_equipamento": (
            round(len(secao_d) / len(equipamentos_ids), 2) if equipamentos_ids else 0
        ),
        "velocidade_media": round(soma_vel / n_vel, 2) if n_vel else None,
        "aceleracao_media": round(soma_acel / n_acel, 2) if n_acel else None,
        "temperatura_media": round(soma_temp / n_temp, 1) if n_temp else None,
        "custo_evitado": custo_evitado,
        "taxa_acerto_diagnostico": (
            round(diagnosticos_confirmados * 100 / diagnosticos_avaliados, 1)
            if diagnosticos_avaliados else None
        ),
        "diagnosticos_avaliados": diagnosticos_avaliados,
        "mtbf_dias": mtbf_dias, "cobertura_ativos_criticos": cobertura_ativos,
    }
    secao_c = {"total": len(equipamentos_ids), "grupos": grupos}
    return secao_b, secao_c, secao_d


# --------------------------------- Seção B ------------------------------------
def preencher_secao_b(doc: Document, secao_b: dict) -> None:
    _quebra_pagina(doc)
    _titulo_secao(doc, "Seção B – KPI's Dashboard")
    _p(doc, "", space_after=4)

    _tabela_indicadores(doc, [
        ("Equipamentos monitorados", secao_b["equip_monitorados"]),
        ("Anomalias diagnosticadas", secao_b["anomalias_diagnosticadas"]),
        ("Média de anomalias / equipamento", secao_b["media_anomalias_por_equipamento"]),
        ("Custo evitado", _moeda(secao_b["custo_evitado"])),
        (
            "Taxa de acerto do diagnóstico",
            f'{secao_b["taxa_acerto_diagnostico"]}%' if secao_b["taxa_acerto_diagnostico"] is not None
            else "— (nenhum diagnóstico confirmado ainda)",
        ),
        ("MTBF estimado (dias)", secao_b["mtbf_dias"] if secao_b["mtbf_dias"] is not None else "—"),
        (
            "Cobertura de ativos críticos",
            f'{secao_b["cobertura_ativos_criticos"]}%' if secao_b["cobertura_ativos_criticos"] is not None
            else "— (nenhum equipamento criticidade A cadastrado)",
        ),
    ])

    _tabela_distribuicao(doc, "Status das Condições", secao_b["condicoes"],
                          cor_fn=lambda r: _cor_gr(r.replace("-", "").replace(" ", "").upper()))
    _tabela_distribuicao(doc, "Status dos Tipos de Componentes", secao_b["componentes"])
    _tabela_distribuicao(doc, "Status dos Tipos de Anomalias", secao_b["anomalias"])
    if secao_b["alarmes"]:
        _tabela_distribuicao(doc, "Status dos Tipos de Alarmes", secao_b["alarmes"])

    if secao_b["velocidade_media"] is not None or secao_b["aceleracao_media"] is not None \
            or secao_b["temperatura_media"] is not None:
        pares = []
        if secao_b["velocidade_media"] is not None:
            pares.append(("Velocidade RMS média (mm/s)", secao_b["velocidade_media"]))
        if secao_b["aceleracao_media"] is not None:
            pares.append(("Aceleração RMS média (g)", secao_b["aceleracao_media"]))
        if secao_b["temperatura_media"] is not None:
            pares.append(("Temperatura média (°C)", secao_b["temperatura_media"]))
        _p(doc, "Média dos Valores de Diagnóstico", bold=True, size=11, space_before=8, space_after=4)
        _tabela_indicadores(doc, pares)


# --------------------------------- Seção C ------------------------------------
def preencher_secao_c(doc: Document, secao_c: dict) -> None:
    _quebra_pagina(doc)
    _titulo_secao(doc, "Seção C – Relação de Equipamentos Contemplados")
    _p(doc, f'Total de equipamentos: {secao_c["total"]}', bold=True, space_before=4, space_after=8)

    for (area, setor), linhas in secao_c["grupos"].items():
        _p(doc, f"Área: {area}  ·  Setor: {setor}", bold=True, size=10, space_before=6, space_after=2)
        tab = doc.add_table(rows=1, cols=3)
        tab.style = "Table Grid"
        hdr = tab.rows[0].cells
        _cell(hdr[0], "TAG", bold=True, fill=CINZA_CLARO)
        _cell(hdr[1], "Equipamento", bold=True, fill=CINZA_CLARO)
        _cell(hdr[2], "Condição", bold=True, fill=CINZA_CLARO, align=WD_ALIGN_PARAGRAPH.CENTER)
        for i, linha in enumerate(linhas):
            row = tab.add_row().cells
            zebra = ZEBRA if i % 2 else None
            _cell(row[0], linha["tag"], fill=zebra)
            _cell(row[1], linha["equipamento"], fill=zebra)
            sigla_norm = linha["condicao"].replace("-", "").replace(" ", "").upper()
            fill, cor_fg = _cor_gr(sigla_norm) if sigla_norm in CORES_GR else (zebra, PRETO)
            _cell(row[2], linha["condicao"], bold=fill is not None and sigla_norm in CORES_GR,
                  color=cor_fg, fill=fill, align=WD_ALIGN_PARAGRAPH.CENTER)
        for row in tab.rows:
            _cant_split(row)


# --------------------------------- Seção D ------------------------------------
def preencher_secao_d(doc: Document, secao_d: list) -> None:
    for o in secao_d:
        _quebra_pagina(doc)
        _titulo_secao(doc, f'OSP {o["osp"]} — {o["tag"]} · {o["equipamento"]}')
        _p(doc, f'{o["area"]} / {o["setor"]}', size=9, italic=True, space_after=4)

        fill, cor_fg = _cor_gr(o["sigla_norm"])
        p_gr = _p(doc, f'Condição: {o["grau_risco"]}', bold=True, size=12, color=cor_fg, space_after=6)
        _shade_par(p_gr, fill)

        _tabela_indicadores(doc, [
            (r, v) for r, v in [
                ("Componente", o["componente"]), ("Anomalia", o["anomalia"]),
                ("Recomendação", o["recomendacao"]), ("Observação", o["observacao"]),
                ("Analista", o["analista"]),
            ] if v
        ])

        medicoes = []
        if o["amplitude_velocidade"] is not None:
            medicoes.append(("Amplitude velocidade (mm/s)", o["amplitude_velocidade"]))
        if o["amplitude_aceleracao"] is not None:
            medicoes.append(("Amplitude aceleração (g)", o["amplitude_aceleracao"]))
        if o["temperatura_medida"] is not None:
            medicoes.append(("Temperatura medida (°C)", o["temperatura_medida"]))
        if o["temperatura_referencia"] is not None:
            medicoes.append(("Temperatura de referência (°C)", o["temperatura_referencia"]))
        if o["delta_t"] is not None:
            medicoes.append(("ΔT (°C)", o["delta_t"]))
        if o["carga_percentual"] is not None:
            medicoes.append(("Carga (%)", o["carga_percentual"]))
        if medicoes:
            _tabela_indicadores(doc, medicoes)

        osp_obj = o["osp_obj"]
        if osp_obj is not None and osp_obj.retorno_investimento:
            _tabela_indicadores(doc, [
                ("Total preditiva", _moeda(osp_obj.total_preditiva)),
                ("Total emergencial", _moeda(osp_obj.total_emergencial)),
                ("Retorno do investimento", _moeda(osp_obj.retorno_investimento)),
            ])

        for img in o["imagens"]:
            try:
                _p(doc, img.get_tipo_display(), size=8, bold=True, space_after=2)
                doc.add_picture(img.arquivo.path, width=Mm(80))
            except Exception:
                continue


# --------------------------------- Documento completo -------------------------
def construir_relatorio_final_docx(rel, prestador) -> Document:
    """
    Relatório Final = Capa (título) + Seção A (carta) + Seção B (KPIs) +
    Seção C (equipamentos) + Seção D (OSPs), num único .docx.
    """
    doc = criar_documento_base(prestador)

    cli = rel.cliente
    _p(doc, "RELATÓRIO TÉCNICO", bold=True, size=22, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=40)
    _p(doc, "Manutenção Preditiva", size=13, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=20)
    p_num = _p(doc, rel.numero, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=12, space_after=12)
    _shade_par(p_num, "D9D9D9")
    _p(doc, cli.nome, bold=True, size=14, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=16)
    if cli.nome_fantasia:
        _p(doc, cli.nome_fantasia, italic=True, align=WD_ALIGN_PARAGRAPH.CENTER)
    _p(doc, rel.tecnologia.nome, italic=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=8)
    if rel.data_termino:
        _p(doc, f"Emitido em {_dt(rel.data_termino)}", size=9, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=20)

    _quebra_pagina(doc)
    preencher_secao_a(doc, rel)

    secao_b, secao_c, secao_d = _coletar_dados(rel)
    preencher_secao_b(doc, secao_b)
    preencher_secao_c(doc, secao_c)
    preencher_secao_d(doc, secao_d)

    return doc
