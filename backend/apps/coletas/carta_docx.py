"""
Carta ao Cliente (Seção A) em .docx — documento independente do relatório,
fiel ao modelo VB_Carta_Foroni. Gerado com python-docx (MIT, sem lock-in —
Cláusula 12.4). Preenchido com os dados do próprio relatório.

Layout: A4, margens 35/15/10/25mm, Segoe UI 12pt justificado, cabeçalho timbrado
(logo + dados do prestador em cinza) repetido em toda página, itens numerados
1–8, tabela de severidade ISO-10816-1 colorida, glossário 6.1–6.9, Definição da
Técnica (texto + imagem de pontos de medição) e assinatura.
"""
from __future__ import annotations

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Mm, Pt, RGBColor

FONTE = "Segoe UI"
PRETO = RGBColor(0x00, 0x00, 0x00)
CINZA = RGBColor(0x80, 0x80, 0x80)
CINZA2 = RGBColor(0x9A, 0x9A, 0x9A)
AZUL = RGBColor(0xC3, 0xDD, 0xF0)
VERMELHO = RGBColor(0xCC, 0x00, 0x00)

# ----------------------------- Conteúdo fixo (modelo Word) -------------------
CONTEUDO = [
    "Seção A – Carta ao Cliente",
    "Seção B – KPI’s Dashboard",
    "Seção C – Relação de Equipamentos Contemplados",
    "Seção D – Ordens de Serviços Preditivos [corretiva orientada pela preditiva]",
]

GLOSSARIO = [
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
]

CONSIDERACOES = [
    "Os critérios considerados nas análises das anomalias detectadas são técnicos, associados com a vasta experiência do analista que dará diagnóstico preciso referente à condição dinâmica na qual o objeto avaliado está submetido, porém vale lembrar que cada equipamento tem seu nível de criticidade para a planta onde está instalado, e deverá ser levado em consideração pelo controle e planejamento da manutenção durante a elaboração do plano de manutenções corretivas baseadas pela manutenção preditiva.",
    "As OSP´s emergenciais (GR-1) foram apresentadas, discutidas e tratadas com o planejamento e controle de manutenção ao término das medições.",
    "Toda anomalia detectada deverá ser corrigida o mais rápido possível, pois o prazo sugerido serve apenas como referência, haja vista que a avaliação contratada não é executada em periodicidade mensal (caso sua planta realize avaliação mensal, desconsiderar este parágrafo).",
]

# Tabela ISO-10816-1: velocidades e zonas por classe.
ISO_VEL = [
    (0.28, 0.02), (0.45, 0.03), (0.71, 0.04), (1.12, 0.06), (1.80, 0.10), (2.80, 0.16),
    (4.50, 0.25), (7.10, 0.40), (11.20, 0.62), (18.00, 1.00), (28.00, 1.56), (45.00, 2.51),
]
ISO_ZONAS = {"I": (0.71, 1.80, 4.50), "II": (1.12, 2.80, 7.10),
             "III": (1.80, 4.50, 11.20), "IV": (2.80, 7.10, 18.00)}
_SEV = [("Bom", "22C55E", RGBColor(0xFF, 0xFF, 0xFF)),
        ("Satisfatório", "A3E635", PRETO),
        ("Alerta", "F59E0B", PRETO),
        ("Perigo", "EF4444", RGBColor(0xFF, 0xFF, 0xFF))]


def _sev(v, cls):
    z = ISO_ZONAS[cls]
    if v <= z[0]:
        return _SEV[0]
    if v <= z[1]:
        return _SEV[1]
    if v <= z[2]:
        return _SEV[2]
    return _SEV[3]


# ------------------------------ Helpers de baixo nível -----------------------
def _dt(d):
    return d.strftime("%d/%m/%Y") if d else "—"


def _shade(cell, fill_hex):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), fill_hex)
    tcPr.append(shd)


def _shade_par(paragraph, fill_hex):
    """Sombreamento de fundo do parágrafo (barra de margem a margem)."""
    pPr = paragraph._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill_hex)
    pPr.append(shd)


def _cant_split(row):
    """Impede que a LINHA da tabela seja quebrada entre páginas."""
    row._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))


def _bottom_border(paragraph, color_hex="C3DDF0", size="6", space="0"):
    """Borda inferior do próprio parágrafo; usada para a linha azul do timbrado."""
    p = paragraph._p
    pPr = p.get_or_add_pPr()
    pbdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), size)
    bottom.set(qn("w:space"), str(space))
    bottom.set(qn("w:color"), color_hex)
    pbdr.append(bottom)
    pPr.append(pbdr)


def _fmt_run(run, *, bold=False, italic=False, size=12, color=PRETO):
    run.bold = bold
    run.italic = italic
    run.font.name = FONTE
    run.font.size = Pt(size)
    run.font.color.rgb = color
    # Garante a fonte também para o conjunto "hAnsi"/eastAsia.
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    for attr in ("w:ascii", "w:hAnsi", "w:cs"):
        rfonts.set(qn(attr), FONTE)


def _p(container, text="", *, bold=False, italic=False, size=12, align=None,
       left=None, hanging=None, space_after=0, space_before=0, color=PRETO,
       style=None, line_spacing=None):
    """Cria parágrafo; None em before/after mantém o valor herdado do estilo."""
    p = container.add_paragraph(style=style) if style else container.add_paragraph()
    pf = p.paragraph_format
    if align is not None:
        p.alignment = align
    if left is not None:
        pf.left_indent = Mm(left)
    if hanging is not None:
        pf.first_line_indent = Mm(-hanging)
    if space_after is not None:
        pf.space_after = Pt(space_after)
    if space_before is not None:
        pf.space_before = Pt(space_before)
    if line_spacing is not None:
        pf.line_spacing = line_spacing
    if text:
        _fmt_run(p.add_run(text), bold=bold, italic=italic, size=size, color=color)
    return p


def _blank(container, *, style=None):
    """
    Linha em branco manual do modelo.

    No Normal ela HERDA os 10 pt de espaço depois; no SemEspaamento
    herda 0 pt. Isso é importante para reproduzir a altura visual do modelo.
    """
    return _p(container, style=style, space_before=0, space_after=None)


def _blank_tight(container, *, style=None):
    """Linha em branco sem espaço adicional depois (usada no bloco do destinatário)."""
    return _p(container, style=style, space_before=0, space_after=0)


def _titulo(container, texto, *, style=None, space_after=None, line_spacing=None):
    """
    Título numerado 1.–8. reproduzindo o XML do modelo:
      w:ind w:left="567" w:hanging="567"
      tab stop em w:pos="567"

    A gravação é feita diretamente em twips para não depender de arredondamento
    ou interpretação do python-docx/Word. Assim, o número começa na margem do
    texto e o título começa exatamente 10 mm à direita, alinhado ao corpo.
    """
    p = container.add_paragraph(style=style) if style else container.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    pf = p.paragraph_format
    pf.space_before = Pt(0)
    if space_after is not None:
        pf.space_after = Pt(space_after)
    if line_spacing is not None:
        pf.line_spacing = line_spacing

    pPr = p._p.get_or_add_pPr()

    # Recuo EXATO do modelo: 567 twips = 10 mm.
    ind = pPr.find(qn("w:ind"))
    if ind is None:
        ind = OxmlElement("w:ind")
        pPr.append(ind)
    ind.set(qn("w:left"), "567")
    ind.set(qn("w:hanging"), "567")
    # Remove propriedades conflitantes, caso venham do estilo.
    ind.attrib.pop(qn("w:firstLine"), None)
    ind.attrib.pop(qn("w:start"), None)
    ind.attrib.pop(qn("w:end"), None)

    # Tab stop EXATO em 567 twips. Remove tabs diretos anteriores do parágrafo.
    old_tabs = pPr.find(qn("w:tabs"))
    if old_tabs is not None:
        pPr.remove(old_tabs)
    tabs = OxmlElement("w:tabs")
    tab = OxmlElement("w:tab")
    tab.set(qn("w:val"), "left")
    tab.set(qn("w:pos"), "567")
    tabs.append(tab)
    pPr.append(tabs)

    if " " in texto:
        numero, titulo = texto.split(" ", 1)
        _fmt_run(p.add_run(numero), bold=True)

        # TAB real (<w:tab/>), em vez de espaço comum.
        rtab = p.add_run()
        rtab._r.append(OxmlElement("w:tab"))

        _fmt_run(p.add_run(titulo), bold=True)
    else:
        _fmt_run(p.add_run(texto), bold=True)
    return p


def _configurar_doc_defaults(doc):
    """Replica no XML os defaults do modelo: Segoe UI 12 pt e entrelinha 1,15."""
    styles = doc.styles.element
    doc_defaults = styles.find(qn("w:docDefaults"))
    if doc_defaults is None:
        doc_defaults = OxmlElement("w:docDefaults")
        styles.insert(0, doc_defaults)

    rpr_default = doc_defaults.find(qn("w:rPrDefault"))
    if rpr_default is None:
        rpr_default = OxmlElement("w:rPrDefault")
        doc_defaults.append(rpr_default)
    rpr = rpr_default.find(qn("w:rPr"))
    if rpr is None:
        rpr = OxmlElement("w:rPr")
        rpr_default.append(rpr)

    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.insert(0, rfonts)
    for attr in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        rfonts.set(qn(attr), FONTE)
    for theme_attr in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
        rfonts.attrib.pop(qn(theme_attr), None)

    for tag in ("w:sz", "w:szCs"):
        el = rpr.find(qn(tag))
        if el is None:
            el = OxmlElement(tag)
            rpr.append(el)
        el.set(qn("w:val"), "24")

    ppr_default = doc_defaults.find(qn("w:pPrDefault"))
    if ppr_default is None:
        ppr_default = OxmlElement("w:pPrDefault")
        doc_defaults.append(ppr_default)
    ppr = ppr_default.find(qn("w:pPr"))
    if ppr is None:
        ppr = OxmlElement("w:pPr")
        ppr_default.append(ppr)
    spacing = ppr.find(qn("w:spacing"))
    if spacing is None:
        spacing = OxmlElement("w:spacing")
        ppr.append(spacing)
    spacing.set(qn("w:after"), "0")
    spacing.set(qn("w:line"), "276")
    spacing.set(qn("w:lineRule"), "auto")


# --------------------------------- Cabeçalho ---------------------------------
def _montar_endereco(o):
    """(linha1, linha2) no padrão do timbrado: logradouro/nº – bairro | CEP – cidade/UF."""
    l1 = " – ".join(x for x in [
        ", ".join(y for y in [getattr(o, "logradouro", ""), getattr(o, "numero", "")] if y),
        getattr(o, "bairro", ""),
    ] if x)
    l2 = " – ".join(x for x in [getattr(o, "cep", ""), getattr(o, "cidade_uf", "")] if x)
    return l1, l2


def _timbrado(section, prestador):
    if not prestador:
        return

    header = section.header
    header.is_linked_to_previous = False

    # Limpa o parágrafo padrão do cabeçalho.
    for p in list(header.paragraphs):
        p._element.getparent().remove(p._element)

    # A largura útil é exatamente 170 mm: 210 - 25 - 15.
    tab = header.add_table(rows=1, cols=2, width=Mm(170))
    tab.autofit = False
    tab.columns[0].width = Mm(62)
    tab.columns[1].width = Mm(108)
    esq, dir_ = tab.rows[0].cells
    esq.width = Mm(62)
    dir_.width = Mm(108)

    # Zera margens internas para o bloco da direita terminar exatamente
    # na largura da coluna e para a borda do CNPJ não ficar recuada.
    def _cell_margins_zero(cell):
        tcPr = cell._tc.get_or_add_tcPr()
        tcMar = tcPr.find(qn("w:tcMar"))
        if tcMar is None:
            tcMar = OxmlElement("w:tcMar")
            tcPr.append(tcMar)
        for side in ("top", "left", "bottom", "right"):
            el = tcMar.find(qn(f"w:{side}"))
            if el is None:
                el = OxmlElement(f"w:{side}")
                tcMar.append(el)
            el.set(qn("w:w"), "0")
            el.set(qn("w:type"), "dxa")

    _cell_margins_zero(esq)
    _cell_margins_zero(dir_)

    # Logo à esquerda. Ela NÃO controla mais a posição da linha azul:
    # a linha pertence ao parágrafo do CNPJ, na coluna direita.
    pl = esq.paragraphs[0]
    pl.alignment = WD_ALIGN_PARAGRAPH.LEFT
    pl.paragraph_format.space_before = Pt(0)
    pl.paragraph_format.space_after = Pt(0)
    pl.paragraph_format.line_spacing = 1.0
    try:
        if prestador.logomarca:
            pl.add_run().add_picture(prestador.logomarca.path, height=Mm(11))
    except Exception:
        pass

    l1, l2 = _montar_endereco(prestador)
    ie = f" | IE {prestador.inscricao_estadual}" if getattr(prestador, "inscricao_estadual", "") else ""

    def _linha_cinza(container, txt, fmt, primeiro=None, *, line_spacing=1.0):
        p = primeiro if primeiro is not None else container.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.line_spacing = line_spacing
        _fmt_run(p.add_run(txt), **fmt)
        return p

    # Razão social.
    _linha_cinza(
        dir_, prestador.nome,
        dict(bold=True, size=12, color=CINZA),
        primeiro=dir_.paragraphs[0],
        line_spacing=1.0,
    )

    # CNPJ + IE. A linha azul é a BORDA INFERIOR DESTE MESMO PARÁGRAFO.
    # Portanto não existe parágrafo vazio, espaço_before ou espaço_after
    # capaz de deslocá-la para baixo.
    p_cnpj = _linha_cinza(
        dir_, f"CNPJ {prestador.cnpj}{ie}",
        dict(size=9, color=CINZA2),
        line_spacing=1.0,
    )
    _bottom_border(p_cnpj, color_hex="C3DDF0", size="6", space="0")

    # ABAIXO da linha azul: endereço / telefone / e-mail, todos à direita.
    # O primeiro parágrafo começa imediatamente depois da borda do CNPJ.
    for txt, fmt in [
        (l1, dict(size=8, color=CINZA2)),
        (l2, dict(size=8, color=CINZA2)),
        (prestador.telefone, dict(size=8, color=CINZA2)),
        (prestador.email, dict(size=8, color=CINZA2)),
    ]:
        if txt:
            _linha_cinza(header, txt, fmt, line_spacing=1.0)


# --------------------------------- Tabela ISO --------------------------------
def _tabela_iso(doc):
    classes = ["I", "II", "III", "IV"]
    cab = {"I": ("Classe I", "< 15 kW"), "II": ("Classe II", "15 a 75 kW"),
           "III": ("Classe III", "Rígida · > 75 kW"), "IV": ("Classe IV", "Flexível · > 75 kW")}
    # A tabela começa em página nova: garante que ela caiba INTEIRA numa folha
    # (o Word ignora keepNext em linhas de tabela; a quebra-antes é o método seguro).
    quebra = doc.add_paragraph()
    quebra.paragraph_format.page_break_before = True
    quebra.paragraph_format.space_after = Pt(0)
    quebra.paragraph_format.space_before = Pt(0)
    tab = doc.add_table(rows=2, cols=6)
    tab.style = "Table Grid"
    tab.alignment = WD_ALIGN_PARAGRAPH.CENTER

    def _cell(cell, text, *, bold=True, size=8.5, color=PRETO, fill=None, align=WD_ALIGN_PARAGRAPH.CENTER):
        cell.paragraphs[0].alignment = align
        cell.paragraphs[0].paragraph_format.space_after = Pt(0)
        _fmt_run(cell.paragraphs[0].add_run(text), bold=bold, size=size, color=color)
        if fill:
            _shade(cell, fill)

    # Título (linha mesclada) + subcabeçalho.
    top = tab.rows[0].cells
    top[0].merge(top[5])
    _cell(top[0], "Norma ISO-20816-3 — Severidade · Faixas de Velocidade e Classes de Máquina",
          bold=True, size=10, color=VERMELHO)
    hdr = tab.rows[1].cells
    _cell(hdr[0], "V [mm/s] RMS", fill="F1F5F9")
    _cell(hdr[1], "V [in/s] Pico", fill="F1F5F9")
    for i, cl in enumerate(classes):
        _cell(hdr[2 + i], f"{cab[cl][0]}\n{cab[cl][1]}", fill="F1F5F9")

    for mm, pol in ISO_VEL:
        row = tab.add_row().cells
        _cell(row[0], f"{mm:.2f}", bold=True)
        _cell(row[1], f"{pol:.2f}", bold=True)
        for i, cl in enumerate(classes):
            txt, fill, fg = _sev(mm, cl)
            _cell(row[2 + i], txt, bold=True, color=fg, fill=fill)

    # Reforço: nenhuma LINHA da tabela pode ser dividida entre páginas.
    for row in tab.rows:
        _cant_split(row)


# ------------------------------ Coleta dos dados -----------------------------
def _dados(rel):
    from apps.cadastros.models import Norma

    carregs = list(rel.carregamentos.select_related("instrumento", "analista"))
    analistas = sorted({c.analista.nome for c in carregs if c.analista_id})
    instrumentos, vistos = [], set()
    for c in carregs:
        ins = c.instrumento
        if ins and ins.id not in vistos:
            vistos.add(ins.id)
            instrumentos.append(ins)
    normas = list(Norma.objects.ativos().filter(tecnologias=rel.tecnologia).order_by("codigo"))
    return analistas, instrumentos, normas


def _escopo(rel):
    """Escopo do relatório (dados do banco) para os parágrafos gerados do item 7."""
    from apps.coletas.models import Achado, ItemInspecao

    equip, setores, areas = set(), set(), set()
    for it in ItemInspecao.objects.filter(carregamento__relatorio=rel).select_related("equipamento__setor__area"):
        eq = it.equipamento
        equip.add(eq.id)
        if eq.setor_id:
            setores.add(eq.setor_id)
            if eq.setor.area_id:
                areas.add(eq.setor.area_id)
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
    return {
        "n_equip": len(equip), "n_setores": len(setores), "n_areas": len(areas),
        "n_anom": n_anom, "gr_tally": gr_tally, "tipos_anom": tipos_anom,
    }


def _lista(itens):
    itens = list(itens)
    if len(itens) <= 1:
        return itens[0] if itens else ""
    return ", ".join(itens[:-1]) + " e " + itens[-1]


def _paragrafos_gerados(rel, e):
    """Parágrafos do item 7 montados a partir dos dados do relatório (banco)."""
    tec = rel.tecnologia.nome
    eq = "1 equipamento" if e["n_equip"] == 1 else f"{e['n_equip']} equipamentos"
    st = "1 setor" if e["n_setores"] == 1 else f"{e['n_setores']} setores"
    ar = "1 área" if e["n_areas"] == 1 else f"{e['n_areas']} áreas"
    p1 = (
        f"Neste relatório aplicou-se a técnica de {tec}, contemplando {eq} monitorado(s) em {st} "
        f"({ar}), com o auxílio da instrumentação descrita no item 4."
    )
    if e["n_anom"] == 0:
        p2 = ("A partir das medições realizadas, não foram diagnosticadas anomalias que ensejassem "
               "Ordens de Serviço Preditivas neste ciclo.")
    else:
        n = e["n_anom"]
        base = ("foi diagnosticada 1 anomalia" if n == 1 else f"foram diagnosticadas {n} anomalias")
        tipos = _lista(e["tipos_anom"])
        trecho_tipos = f", do(s) tipo(s): {tipos}" if tipos else ""
        gr = e["gr_tally"]
        if gr:
            dist = "; ".join(f"{k}: {v}" for k, v in sorted(gr.items()))
            trecho_gr = f" A distribuição por Grau de Risco foi — {dist}."
        else:
            trecho_gr = ""
        p2 = (
            f"A partir das medições realizadas, {base}{trecho_tipos}. Cada anomalia foi classificada "
            f"conforme os Graus de Risco descritos no item 6 e convertida em Ordem de Serviço Preditiva "
            f"na Seção D.{trecho_gr}"
        )
    return [p1, p2]


# --------------------------------- Documento ---------------------------------
def construir_carta_docx(rel, prestador) -> Document:
    doc = Document()

    # Defaults do modelo Word: Segoe UI 12 pt e entrelinha 1,15 (w:line=276).
    _configurar_doc_defaults(doc)
    normal = doc.styles["Normal"]
    normal.font.name = FONTE
    normal.font.size = Pt(12)
    normal.font.color.rgb = PRETO
    normal.paragraph_format.space_before = Pt(0)
    # No modelo, o Normal mantém 10 pt depois. Os parágrafos de corpo
    # zeram esse valor diretamente; títulos 1–5 e linhas em branco o herdam.
    normal.paragraph_format.space_after = Pt(10)
    # A entrelinha do Normal herda 1,15 do docDefaults.
    normal.paragraph_format.line_spacing = None

    # Estilo usado pelo modelo nos itens 6, 7 e 8: entrelinha simples, sem espaço extra.
    try:
        sem_espacamento = doc.styles["SemEspaamento"]
    except KeyError:
        sem_espacamento = doc.styles.add_style("SemEspaamento", WD_STYLE_TYPE.PARAGRAPH)
    sem_espacamento.base_style = normal
    sem_espacamento.font.name = FONTE
    sem_espacamento.font.size = Pt(12)
    sem_espacamento.font.color.rgb = PRETO
    sem_espacamento.paragraph_format.space_before = Pt(0)
    sem_espacamento.paragraph_format.space_after = Pt(0)
    sem_espacamento.paragraph_format.line_spacing = 1.0

    # Página A4 + margens do modelo (topo 35 reserva o cabeçalho).
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Mm(210), Mm(297)
    sec.top_margin, sec.bottom_margin = Mm(35), Mm(10)
    sec.left_margin, sec.right_margin = Mm(25), Mm(15)
    sec.header_distance, sec.footer_distance = Mm(5), Mm(5)

    _timbrado(sec, prestador)

    cli = rel.cliente
    analistas, instrumentos, normas = _dados(rel)
    tec = rel.tecnologia

    # ---- Destinatário (rente à margem esquerda, como no modelo Word) ----
    razao = cli.nome + (f"   {cli.nome_fantasia}" if cli.nome_fantasia else "")
    _p(doc, razao, bold=True, left=0, space_after=0)
    cl1, cl2 = _montar_endereco(cli)
    if cl1:
        _p(doc, cl1, italic=True, left=0, space_after=0)
    if cl2:
        _p(doc, cl2, italic=True, left=0, space_after=0)
    if cli.contato_gestor:
        # O modelo deixa uma linha visual entre o endereço e o A/C.
        _blank_tight(doc)
        _p(doc, f"A/C.: Sr(a). {cli.contato_gestor}", bold=True, left=0, space_before=0, space_after=0)
    if cli.departamento:
        _p(doc, cli.departamento, bold=True, left=0, space_after=0)

    # ---- Número (centralizado, barra cinza de margem a margem) ----
    pnum = _p(doc, rel.numero, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=12, space_after=12)
    # O número do relatório herda a entrelinha 1,15 do docDefaults, como no modelo.
    _shade_par(pnum, "D9D9D9")

    # ---- 1. Objetivo ----
    _titulo(doc, "1. Objetivo do Relatório")
    _p(doc, "Este relatório técnico tem como objetivo apresentar os resultados das análises técnicas de:",
       align=WD_ALIGN_PARAGRAPH.JUSTIFY, left=10)
    _p(doc, tec.nome, italic=True, align=WD_ALIGN_PARAGRAPH.JUSTIFY, left=10)
    _blank(doc)

    # ---- 2. Datas (apenas duas: fim das medições e fim das análises) ----
    _titulo(doc, "2. Data(s) da(s) Execução(ões) da(s) Atividade(s)")
    _p(doc, f"Finalização das medições em campo – {_dt(rel.data_termino)}",
       align=WD_ALIGN_PARAGRAPH.JUSTIFY, left=10)
    _p(doc, f"Finalização das análises – {_dt(rel.data_finalizacao)}",
       align=WD_ALIGN_PARAGRAPH.JUSTIFY, left=10)
    _blank(doc)

    # ---- 3. Conteúdo ----
    _titulo(doc, "3. Conteúdo do Relatório")
    for t in CONTEUDO:
        _p(doc, t, align=WD_ALIGN_PARAGRAPH.JUSTIFY, left=10)
    _blank(doc)

    # ---- 4. Instrumentação (sub-itens a 22,51 mm, conforme XML do modelo) ----
    _titulo(doc, "4. Instrumentação Utilizada")
    if instrumentos:
        for ins in instrumentos:
            if ins.tipo:
                _p(doc, ins.tipo, align=WD_ALIGN_PARAGRAPH.JUSTIFY, left=22.51)
            if ins.marca:
                _p(doc, f"Marca: {ins.marca}", align=WD_ALIGN_PARAGRAPH.JUSTIFY, left=22.51)
            if ins.modelo:
                _p(doc, f"Modelo: {ins.modelo}", align=WD_ALIGN_PARAGRAPH.JUSTIFY, left=22.51)
            if ins.numero_serie:
                _p(doc, f"Serial #: {ins.numero_serie}", align=WD_ALIGN_PARAGRAPH.JUSTIFY, left=22.51)
            if ins.data_ultima_calibracao:
                _p(doc, f"Data da última calibração: {_dt(ins.data_ultima_calibracao)}",
                   align=WD_ALIGN_PARAGRAPH.JUSTIFY, left=22.51)
            periodicidade = ins.get_periodicidade_calibracao_display() if ins.periodicidade_calibracao else ""
            if periodicidade:
                _p(doc, f"Validade: {periodicidade}", align=WD_ALIGN_PARAGRAPH.JUSTIFY, left=22.51)
            if ins.entidade_calibracao:
                _p(doc, f"Entidade Calibração: {ins.entidade_calibracao}",
                   align=WD_ALIGN_PARAGRAPH.JUSTIFY, left=22.51)
            if ins.software_analise:
                _p(doc, "Softwares de Análises", align=WD_ALIGN_PARAGRAPH.JUSTIFY, left=22.51)
                _p(doc, ins.software_analise, align=WD_ALIGN_PARAGRAPH.JUSTIFY, left=22.51)
    else:
        _p(doc, "Não informada.", align=WD_ALIGN_PARAGRAPH.JUSTIFY, left=22.51)
    _blank(doc)

    # ---- 5. Normatização + tabela ISO ----
    _titulo(doc, "5. Normatização")
    if normas:
        for n in normas:
            texto = " - ".join(x for x in [n.codigo, n.nome] if x)
            _p(doc, texto, align=WD_ALIGN_PARAGRAPH.JUSTIFY, left=10)
    else:
        _p(doc, "Não informada.", align=WD_ALIGN_PARAGRAPH.JUSTIFY, left=10)
    _tabela_iso(doc)
    _blank(doc)

    # ---- 6. Glossário ----
    # No modelo, o título usa SemEspaamento com override 1,15 e after=12 pt.
    _titulo(doc, "6. Glossário Técnico", style="SemEspaamento", space_after=12, line_spacing=1.15)
    for i, (n, sigla, texto) in enumerate(GLOSSARIO):
        p = doc.add_paragraph(style="SemEspaamento")
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.left_indent = Mm(10)
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(0)
        # Sem override de line_spacing: herda 1,0 do estilo SemEspaamento.
        _fmt_run(p.add_run(f"{n}. {sigla}"), bold=True)
        _fmt_run(p.add_run(f" – {texto}"))
        if i < len(GLOSSARIO) - 1:
            _blank(doc, style="SemEspaamento")
    _blank(doc, style="SemEspaamento")

    # ---- 7. Definição da Técnica (GERADO dos dados do relatório + texto da técnica) ----
    # Mesmo padrão do item 6: título 1,15 + after=12 pt; corpo simples (1,0).
    _titulo(doc, "7. Definição da Técnica", style="SemEspaamento", space_after=12, line_spacing=1.15)

    definicao_paragrafos = list(_paragrafos_gerados(rel, _escopo(rel)))
    for campo in ((tec.definicao_tecnica or ""), (getattr(tec, "definicao_fluxo_trabalho", "") or "")):
        for par in campo.strip().splitlines():
            if par.strip():
                definicao_paragrafos.append(par.strip())

    for i, par in enumerate(definicao_paragrafos):
        _p(doc, par, align=WD_ALIGN_PARAGRAPH.JUSTIFY, left=10,
           style="SemEspaamento", line_spacing=None)
        if i < len(definicao_paragrafos) - 1:
            _blank(doc, style="SemEspaamento")
    _blank(doc, style="SemEspaamento")

    # ---- 8. Considerações + assinatura ----
    # O título 8 força 1,15, mas NÃO tem after=12; o modelo usa uma linha em branco após o título.
    _titulo(doc, "8. Considerações Importantes", style="SemEspaamento", line_spacing=1.15)
    _blank(doc, style="SemEspaamento")

    consideracoes = list(CONSIDERACOES)
    if (rel.consideracoes_finais or "").strip():
        consideracoes.extend(par.strip() for par in rel.consideracoes_finais.splitlines() if par.strip())

    for i, par in enumerate(consideracoes):
        _p(doc, par, align=WD_ALIGN_PARAGRAPH.JUSTIFY, left=10,
           style="SemEspaamento", line_spacing=None)
        if i < len(consideracoes) - 1:
            _blank(doc, style="SemEspaamento")

    _p(doc, "Atenciosamente,", left=10, space_before=8)
    for a in (analistas or ["Analista"]):
        _p(doc, "", space_before=10)
        _p(doc, a, bold=True, align=WD_ALIGN_PARAGRAPH.RIGHT, space_after=0)
        _p(doc, "Analista em Manutenção Preditiva", size=8, align=WD_ALIGN_PARAGRAPH.RIGHT)

    return doc
