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
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Mm, Pt, RGBColor

FONTE = "Segoe UI"
PRETO = RGBColor(0x00, 0x00, 0x00)
CINZA = RGBColor(0x80, 0x80, 0x80)
CINZA2 = RGBColor(0x9A, 0x9A, 0x9A)
AZUL = RGBColor(0x1D, 0x4E, 0xD8)
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

# Legenda genérica (segura) usada antes da imagem quando a tecnologia não define uma.
DEFINICAO_LEGENDA = "Abaixo observaremos a disposição dos pontos de medição:"

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


def _bottom_border(paragraph, color_hex="1D4ED8", size="4"):
    """Linha fina embaixo do parágrafo (usada como régua do timbrado)."""
    p = paragraph._p
    pPr = p.get_or_add_pPr()
    pbdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), size)
    bottom.set(qn("w:space"), "1")
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
       left=None, hanging=None, space_after=2, space_before=0, color=PRETO):
    p = container.add_paragraph()
    pf = p.paragraph_format
    if align is not None:
        p.alignment = align
    if left is not None:
        pf.left_indent = Mm(left)
    if hanging is not None:
        pf.first_line_indent = Mm(-hanging)
    pf.space_after = Pt(space_after)
    pf.space_before = Pt(space_before)
    pf.line_spacing = 1.15
    if text:
        _fmt_run(p.add_run(text), bold=bold, italic=italic, size=size, color=color)
    return p


def _titulo(container, texto):
    """Título de item numerado (1.–8.) com mais respiro acima."""
    return _p(container, texto, bold=True, left=10, hanging=10, space_before=10, space_after=2)


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
    # Limpa o parágrafo padrão do header.
    for p in list(header.paragraphs):
        p._element.getparent().remove(p._element)

    tab = header.add_table(rows=1, cols=2, width=Mm(170))
    tab.autofit = False
    tab.columns[0].width = Mm(62)
    tab.columns[1].width = Mm(108)
    esq, dir_ = tab.rows[0].cells
    esq.width = Mm(62)
    dir_.width = Mm(108)

    # Logo à esquerda.
    pl = esq.paragraphs[0]
    pl.alignment = WD_ALIGN_PARAGRAPH.LEFT
    try:
        if prestador.logomarca:
            pl.add_run().add_picture(prestador.logomarca.path, width=Mm(50))
    except Exception:
        pass

    # Dados do prestador à direita (cinza).
    l1, l2 = _montar_endereco(prestador)
    ie = f" | IE {prestador.inscricao_estadual}" if getattr(prestador, "inscricao_estadual", "") else ""
    linhas = [
        (prestador.nome, dict(bold=True, size=12, color=CINZA)),
        (f"CNPJ {prestador.cnpj}{ie}", dict(size=9, color=CINZA2)),
        (l1, dict(size=8, color=CINZA2)),
        (l2, dict(size=8, color=CINZA2)),
        (prestador.telefone, dict(size=8, color=CINZA2)),
        (prestador.email, dict(size=8, color=CINZA2)),
    ]
    primeiro = dir_.paragraphs[0]
    for i, (txt, fmt) in enumerate([(t, f) for t, f in linhas if t]):
        p = primeiro if i == 0 else dir_.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.line_spacing = 1.1
        _fmt_run(p.add_run(txt), **fmt)


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
    """Escopo do relatório (dados do banco) para o parágrafo gerado do item 7."""
    from apps.coletas.models import Achado, ItemInspecao

    equip, setores = set(), set()
    for it in ItemInspecao.objects.filter(carregamento__relatorio=rel).select_related("equipamento__setor"):
        eq = it.equipamento
        equip.add(eq.id)
        if eq.setor_id:
            setores.add(eq.setor_id)
    n_anom = 0
    for a in Achado.objects.filter(item__carregamento__relatorio=rel):
        if a.tipo_anomalia_id or (a.anomalia_texto or "").strip() or a.tipo_componente_id or (a.componente_texto or "").strip():
            n_anom += 1
    return len(equip), len(setores), n_anom


def _paragrafo_gerado(rel, n_equip, n_setores, n_anom):
    """Texto do item 7 montado a partir dos dados do relatório (banco)."""
    tec = rel.tecnologia.nome
    eq = "1 equipamento distribuído" if n_equip == 1 else f"{n_equip} equipamentos distribuídos"
    st = "1 setor" if n_setores == 1 else f"{n_setores} setores"
    if n_anom == 0:
        fecho = "não foram diagnosticadas anomalias que ensejassem Ordens de Serviço Preditivas."
    elif n_anom == 1:
        fecho = ("foi diagnosticada 1 anomalia, classificada conforme os Graus de Risco descritos no "
                 "item 6 e convertida na Ordem de Serviço Preditiva apresentada na Seção D.")
    else:
        fecho = (f"foram diagnosticadas {n_anom} anomalias, classificadas conforme os Graus de Risco "
                 "descritos no item 6 e convertidas nas Ordens de Serviço Preditivas apresentadas na Seção D.")
    return (
        f"Neste relatório aplicou-se a técnica de {tec}, contemplando {eq} em {st}, com o auxílio da "
        f"instrumentação descrita no item 4. A partir das medições realizadas, {fecho}"
    )


# --------------------------------- Documento ---------------------------------
def construir_carta_docx(rel, prestador) -> Document:
    doc = Document()

    # Fonte padrão.
    normal = doc.styles["Normal"]
    normal.font.name = FONTE
    normal.font.size = Pt(12)
    normal.font.color.rgb = PRETO
    # Entrelinhas 1.15 em toda a carta (pedido do cliente).
    normal.paragraph_format.line_spacing = 1.15

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
        _p(doc, cl1, left=0, space_after=0)
    if cl2:
        _p(doc, cl2, left=0, space_after=0)
    if cli.contato_gestor:
        _p(doc, f"A/C.: Sr(a). {cli.contato_gestor}", bold=True, left=0, space_before=4, space_after=0)
    if cli.departamento:
        _p(doc, cli.departamento, bold=True, left=0, space_after=0)

    # ---- Número (centralizado, barra cinza de margem a margem) ----
    pnum = _p(doc, rel.numero, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=8, space_after=8)
    _shade_par(pnum, "CCCCCC")

    # ---- 1. Objetivo ----
    _titulo(doc, "1. Objetivo do Relatório")
    _p(doc, "Este relatório técnico tem como objetivo apresentar os resultados das análises técnicas de:",
       align=WD_ALIGN_PARAGRAPH.JUSTIFY, left=10, space_after=0)
    _p(doc, tec.nome, align=WD_ALIGN_PARAGRAPH.JUSTIFY, left=10)

    # ---- 2. Datas (apenas duas: fim das medições e fim das análises) ----
    _titulo(doc, "2. Data(s) da(s) Execução(ões) da(s) Atividade(s)")
    _p(doc, f"Finalização das medições em campo – {_dt(rel.data_termino)}", left=10, space_after=0)
    _p(doc, f"Finalização das análises – {_dt(rel.data_finalizacao)}", left=10)

    # ---- 3. Conteúdo ----
    _titulo(doc, "3. Conteúdo do Relatório")
    for t in CONTEUDO:
        _p(doc, t, left=10, space_after=0)

    # ---- 4. Instrumentação (sub-itens alinhados a 10mm) ----
    _titulo(doc, "4. Instrumentação Utilizada")
    if instrumentos:
        for ins in instrumentos:
            if ins.tipo:
                _p(doc, ins.tipo, left=10, space_after=0)
            if ins.marca:
                _p(doc, f"Marca: {ins.marca}", left=10, space_after=0)
            if ins.modelo:
                _p(doc, f"Modelo: {ins.modelo}", left=10, space_after=0)
            if ins.numero_serie:
                _p(doc, f"Serial #: {ins.numero_serie}", left=10, space_after=0)
            if ins.data_ultima_calibracao:
                _p(doc, f"Data da última calibração: {_dt(ins.data_ultima_calibracao)}", left=10, space_after=0)
            periodicidade = ins.get_periodicidade_calibracao_display() if ins.periodicidade_calibracao else ""
            if periodicidade:
                _p(doc, f"Validade: {periodicidade}", left=10, space_after=0)
            if ins.entidade_calibracao:
                _p(doc, f"Entidade Calibração: {ins.entidade_calibracao}", left=10, space_after=0)
            if ins.software_analise:
                _p(doc, "Softwares de Análises", left=10, space_before=2, space_after=0)
                _p(doc, ins.software_analise, left=10, space_after=2)
    else:
        _p(doc, "Não informada.", left=10)

    # ---- 5. Normatização + tabela ISO ----
    _titulo(doc, "5. Normatização")
    if normas:
        for n in normas:
            texto = " - ".join(x for x in [n.codigo, n.nome] if x)
            _p(doc, texto, align=WD_ALIGN_PARAGRAPH.JUSTIFY, left=10, space_after=0)
    else:
        _p(doc, "Não informada.", left=10)
    _tabela_iso(doc)

    # ---- 6. Glossário ----
    _titulo(doc, "6. Glossário Técnico")
    for n, sigla, texto in GLOSSARIO:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.left_indent = Mm(10)
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.line_spacing = 1.15
        _fmt_run(p.add_run(f"{n}. {sigla}"), bold=True)
        _fmt_run(p.add_run(f" – {texto}"))

    # ---- 7. Definição da Técnica (parágrafo GERADO dos dados + texto da técnica) ----
    _titulo(doc, "7. Definição da Técnica")
    # 7.0 Parágrafo montado a partir dos dados do relatório (banco).
    n_equip, n_setores, n_anom = _escopo(rel)
    _p(doc, _paragrafo_gerado(rel, n_equip, n_setores, n_anom), align=WD_ALIGN_PARAGRAPH.JUSTIFY, left=10)
    # A seguir, a descrição fixa da técnica cadastrada na tecnologia.
    intro = (tec.definicao_tecnica or "").strip()
    fluxo = (getattr(tec, "definicao_fluxo_trabalho", "") or "").strip()
    legenda = (getattr(tec, "definicao_legenda_imagem", "") or "").strip()
    tem_imagem = bool(getattr(tec, "imagem_pontos_medicao", None))
    # 7.1 Texto introdutório
    for par in intro.splitlines():
        if par.strip():
            _p(doc, par.strip(), align=WD_ALIGN_PARAGRAPH.JUSTIFY, left=10)
    # 7.2 Etapas do fluxo de trabalho
    for par in fluxo.splitlines():
        if par.strip():
            _p(doc, par.strip(), align=WD_ALIGN_PARAGRAPH.JUSTIFY, left=10)
    # 7.3 Legenda + imagem dos pontos de medição
    if tem_imagem:
        _p(doc, legenda or DEFINICAO_LEGENDA, align=WD_ALIGN_PARAGRAPH.JUSTIFY, left=10)
        try:
            pimg = doc.add_paragraph()
            pimg.alignment = WD_ALIGN_PARAGRAPH.CENTER
            pimg.add_run().add_picture(tec.imagem_pontos_medicao.path, width=Mm(150))
        except Exception:
            pass
    elif legenda:
        _p(doc, legenda, align=WD_ALIGN_PARAGRAPH.JUSTIFY, left=10)

    # ---- 8. Considerações + assinatura ----
    _titulo(doc, "8. Considerações Importantes")
    for par in CONSIDERACOES:
        _p(doc, par, align=WD_ALIGN_PARAGRAPH.JUSTIFY, left=10)
    if (rel.consideracoes_finais or "").strip():
        for par in rel.consideracoes_finais.splitlines():
            if par.strip():
                _p(doc, par.strip(), align=WD_ALIGN_PARAGRAPH.JUSTIFY, left=10)

    _p(doc, "Atenciosamente,", left=10, space_before=8)
    for a in (analistas or ["Analista"]):
        _p(doc, "", space_before=10)
        _p(doc, a, bold=True, align=WD_ALIGN_PARAGRAPH.RIGHT, space_after=0)
        _p(doc, "Analista em Manutenção Preditiva", size=8, align=WD_ALIGN_PARAGRAPH.RIGHT)

    return doc
