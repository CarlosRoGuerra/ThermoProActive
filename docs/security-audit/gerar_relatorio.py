# -*- coding: utf-8 -*-
"""
Gerador do Relatório de Auditoria de Segurança — ThermoProActive / Pred Ativos.

Lê os dados de `achados.py` e o texto das issues de `issues.py` e produz
`relatorio-auditoria-seguranca.pdf` (A4, margens de 2 cm, cabeçalho e rodapé
com nome do relatório e numeração "Página X de Y").

Uso (ambiente isolado, nada é instalado globalmente):

    python -m venv .venv
    .venv/Scripts/python -m pip install reportlab matplotlib     # Windows
    .venv/bin/python     -m pip install reportlab matplotlib     # Linux/macOS
    .venv/Scripts/python docs/security-audit/gerar_relatorio.py

O script pode ser executado de qualquer diretório: os caminhos são resolvidos
em relação ao próprio arquivo.
"""
import os
import sys
import textwrap
from datetime import datetime

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.platypus import (
    BaseDocTemplate, Frame, Image, KeepTogether, NextPageTemplate, PageBreak,
    PageTemplate, Paragraph, Spacer, Table, TableStyle,
)

import achados as D
from issues import montar_issues

# ---------------------------------------------------------------------------
# Paleta (definida no pedido da auditoria)
# ---------------------------------------------------------------------------
COR = {
    "critica": colors.HexColor("#B91C1C"),
    "alta": colors.HexColor("#EA580C"),
    "media": colors.HexColor("#D97706"),
    "baixa": colors.HexColor("#2563EB"),
    "forte": colors.HexColor("#059669"),
}
HEX = {k: v.hexval().replace("0x", "#") for k, v in COR.items()}

TINTA = colors.HexColor("#0F172A")       # texto principal
TINTA_FRACA = colors.HexColor("#475569")  # texto secundário
LINHA = colors.HexColor("#CBD5E1")
FUNDO_SUAVE = colors.HexColor("#F1F5F9")
FUNDO_CODIGO = colors.HexColor("#0F172A")
CODIGO_TXT = colors.HexColor("#E2E8F0")

ROTULO = {"critica": "CRÍTICA", "alta": "ALTA", "media": "MÉDIA", "baixa": "BAIXA"}
ORDEM = ["critica", "alta", "media", "baixa"]

TITULO_RELATORIO = f"Relatório de Auditoria de Segurança — {D.PROJETO}"

SAIDA_PDF = os.path.join(AQUI, "relatorio-auditoria-seguranca.pdf")
SAIDA_MD = os.path.join(AQUI, "issues-github.md")
DIR_GRAF = os.path.join(AQUI, "_graficos")

# ---------------------------------------------------------------------------
# Fontes — DejaVu (vem com o matplotlib) para cobertura Unicode completa
# ---------------------------------------------------------------------------
F_REG, F_BOLD, F_MONO, F_MONOB = "Helvetica", "Helvetica-Bold", "Courier", "Courier-Bold"
try:
    ttf = os.path.join(matplotlib.get_data_path(), "fonts", "ttf")
    pdfmetrics.registerFont(TTFont("DejaVu", os.path.join(ttf, "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVu-Bold", os.path.join(ttf, "DejaVuSans-Bold.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVuMono", os.path.join(ttf, "DejaVuSansMono.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVuMono-Bold", os.path.join(ttf, "DejaVuSansMono-Bold.ttf")))
    F_REG, F_BOLD, F_MONO, F_MONOB = "DejaVu", "DejaVu-Bold", "DejaVuMono", "DejaVuMono-Bold"
except Exception as exc:  # pragma: no cover
    print(f"[aviso] fontes DejaVu indisponíveis ({exc}); usando as padrão do reportlab")

MONO_LARG = pdfmetrics.stringWidth("0", F_MONO, 1000) / 1000.0  # largura relativa do caractere

# ---------------------------------------------------------------------------
# Estilos
# ---------------------------------------------------------------------------
_base = getSampleStyleSheet()


def _st(nome, **kw):
    kw.setdefault("fontName", F_REG)
    kw.setdefault("textColor", TINTA)
    return ParagraphStyle(nome, parent=_base["Normal"], **kw)


S = {
    "capa_titulo": _st("capa_titulo", fontName=F_BOLD, fontSize=25, leading=31,
                       textColor=colors.white),
    "capa_sub": _st("capa_sub", fontSize=12.5, leading=18, textColor=colors.HexColor("#CBD5E1")),
    "capa_meta": _st("capa_meta", fontSize=10, leading=16, textColor=colors.HexColor("#94A3B8")),
    "h1": _st("h1", fontName=F_BOLD, fontSize=16.5, leading=21, spaceBefore=4, spaceAfter=9),
    "h2": _st("h2", fontName=F_BOLD, fontSize=12, leading=16, spaceBefore=12, spaceAfter=5),
    "h3": _st("h3", fontName=F_BOLD, fontSize=9.6, leading=13, spaceBefore=8, spaceAfter=3,
              textColor=TINTA_FRACA),
    "p": _st("p", fontSize=9.3, leading=14.2, alignment=TA_JUSTIFY, spaceAfter=6),
    "p_peq": _st("p_peq", fontSize=8.4, leading=12.6, alignment=TA_JUSTIFY, spaceAfter=4),
    # lista de arquivos: alinhada à esquerda — justificar abriria vãos enormes
    # entre os caminhos, que são "palavras" muito longas.
    "p_arq": _st("p_arq", fontSize=8.0, leading=12.4, spaceAfter=4),
    "li": _st("li", fontSize=9.0, leading=13.4, leftIndent=11, bulletIndent=2, spaceAfter=2.5),
    "cel": _st("cel", fontSize=8.3, leading=11.8),
    "cel_mono": _st("cel_mono", fontName=F_MONO, fontSize=6.9, leading=10.2),
    "cel_cab": _st("cel_cab", fontName=F_BOLD, fontSize=8.3, leading=11.6,
                   textColor=colors.white),
    "chip": _st("chip", fontName=F_BOLD, fontSize=7.4, leading=10, alignment=TA_CENTER,
                textColor=colors.white),
    "legenda": _st("legenda", fontSize=7.8, leading=11, textColor=TINTA_FRACA,
                   alignment=TA_CENTER, spaceBefore=3),
    "kpi_n": _st("kpi_n", fontName=F_BOLD, fontSize=21, leading=24, alignment=TA_CENTER,
                 textColor=colors.white),
    "kpi_r": _st("kpi_r", fontName=F_BOLD, fontSize=7.2, leading=10, alignment=TA_CENTER,
                 textColor=colors.white),
}

LARG = A4[0] - 4 * cm  # largura útil com margens de 2 cm


def esc(t):
    """Escapa o mini-HTML do Paragraph."""
    return (str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _data_vigente():
    """A data que o documento carrega: a da revisão, se houver."""
    return getattr(D, "DATA_REVISAO", None) or D.DATA_AUDITORIA


# ---------------------------------------------------------------------------
# Blocos reutilizáveis
# ---------------------------------------------------------------------------
def chip(sev):
    """Chip colorido de severidade, pronto para ir numa célula de tabela."""
    t = Table([[Paragraph(ROTULO[sev], S["chip"])]], colWidths=[1.85 * cm], rowHeights=[0.46 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), COR[sev]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("ROUNDEDCORNERS", [3, 3, 3, 3]),
    ]))
    return t


def _quebrar(texto, largura, tam):
    """Quebra o código em linhas que cabem na largura útil do bloco."""
    limite = int((largura - 16) / (MONO_LARG * tam))
    linhas = []
    for bruta in texto.split("\n"):
        if not bruta.strip():
            linhas.append("")
            continue
        partes = textwrap.wrap(bruta, width=limite, subsequent_indent="      ",
                               drop_whitespace=False, replace_whitespace=False) or [""]
        linhas.extend(partes)
    return linhas


def bloco_codigo_paginado(texto, largura=LARG, tam=6.4, por_fatia=8):
    """
    Versão do bloco de código para textos longos (as issues).

    Uma Table de 1 célula não se divide entre páginas. O texto é então fatiado
    em pedaços curtos, sem recheio vertical e com o mesmo fundo, de modo que
    fatias consecutivas se encostam e formam um bloco contínuo — e o reportlab
    quebra a página entre duas fatias, desperdiçando no máximo a altura de uma
    (~8 linhas) em vez de uma página inteira.
    """
    linhas = _quebrar(texto, largura, tam)
    linhas = [""] + linhas + [""]  # respiro no topo e no rodapé do bloco inteiro
    fatias = [linhas[i:i + por_fatia] for i in range(0, len(linhas), por_fatia)]
    return [_bloco_de_linhas(f, largura, tam, None, recheio_v=0) for f in fatias]


def bloco_codigo(texto, largura=LARG, tam=6.9, cabecalho=None):
    """Trecho de código sobre fundo escuro, com quebra de linha controlada."""
    return _bloco_de_linhas(_quebrar(texto, largura, tam), largura, tam, cabecalho)


def _bloco_de_linhas(linhas, largura, tam, cabecalho, recheio_v=6):
    corpo = "<br/>".join(esc(x) if x else "&nbsp;" for x in linhas)
    st = ParagraphStyle("cod", fontName=F_MONO, fontSize=tam, leading=tam * 1.5,
                        textColor=CODIGO_TXT)
    dados = []
    if cabecalho:
        dados.append([Paragraph(esc(cabecalho),
                                ParagraphStyle("codcab", fontName=F_MONOB, fontSize=tam,
                                               leading=tam * 1.6,
                                               textColor=colors.HexColor("#7DD3FC")))])
    dados.append([Paragraph(corpo, st)])
    t = Table(dados, colWidths=[largura])
    estilo = [
        ("BACKGROUND", (0, 0), (-1, -1), FUNDO_CODIGO),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), recheio_v),
        ("BOTTOMPADDING", (0, 0), (-1, -1), recheio_v),
    ]
    if recheio_v:
        estilo.append(("ROUNDEDCORNERS", [4, 4, 4, 4]))
    if cabecalho:
        estilo += [("BOTTOMPADDING", (0, 0), (0, 0), 1), ("TOPPADDING", (0, 1), (0, 1), 1)]
    t.setStyle(TableStyle(estilo))
    return t


def caminho(p, max_chars=36):
    """
    Quebra um `arquivo:linha` longo depois de uma barra, em vez de deixar o
    reportlab cortar no meio de um identificador ("...models.p / y:108-110").
    """
    p = esc(p)
    if len(p) <= max_chars:
        return p
    # só depois de "/": o nome do arquivo e o intervalo de linhas ficam juntos
    partes = p.split("/")
    pedacos = [seg + "/" for seg in partes[:-1]] + [partes[-1]]
    linha, saida = "", []
    for pedaco in pedacos:
        if linha and len(linha) + len(pedaco) > max_chars:
            saida.append(linha)
            linha = pedaco
        else:
            linha += pedaco
    saida.append(linha)
    return "<br/>".join(x for x in saida if x)


def bullets(itens, estilo="li"):
    return [Paragraph(esc(i), S[estilo], bulletText="•") for i in itens]


def barra_secao(numero, titulo):
    """Título de seção com barra lateral colorida."""
    t = Table([[Paragraph(f"{esc(numero)}  {esc(titulo)}", S["h1"])]], colWidths=[LARG])
    t.setStyle(TableStyle([
        ("LINEBEFORE", (0, 0), (0, 0), 3, TINTA),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    return t


# ---------------------------------------------------------------------------
# Gráficos (matplotlib -> PNG -> Image)
# ---------------------------------------------------------------------------
def _contagens():
    por_sev = {s: 0 for s in ORDEM}
    for a in D.ACHADOS:
        por_sev[a["severidade"]] += 1
    por_cat = {}
    for a in D.ACHADOS:
        por_cat[a["categoria"]] = por_cat.get(a["categoria"], 0) + 1
    # categorias auditadas sem achado aparecem com zero — é informação, não ausência
    for c in ("5. Inputs sem tratamento (XSS)",):
        por_cat.setdefault(c, 0)
    return por_sev, por_cat


def grafico_rosca(por_sev, caminho):
    rotulos, valores, cores = [], [], []
    for s in ORDEM:
        if por_sev[s]:
            rotulos.append(f"{ROTULO[s]}\n{por_sev[s]}")
            valores.append(por_sev[s])
            cores.append(HEX[s])
    fig, ax = plt.subplots(figsize=(3.5, 2.9), dpi=220)
    wedges, textos = ax.pie(
        valores, colors=cores, startangle=90, counterclock=False,
        wedgeprops=dict(width=0.40, edgecolor="white", linewidth=2.2),
        labels=rotulos, labeldistance=1.16,
        textprops=dict(fontsize=7.4, color="#0F172A", fontweight="bold", ha="center"),
    )
    ax.text(0, 0.10, str(sum(valores)), ha="center", va="center",
            fontsize=21, fontweight="bold", color="#0F172A")
    ax.text(0, -0.24, "achados", ha="center", va="center", fontsize=7.6, color="#475569")
    ax.set(aspect="equal")
    fig.tight_layout(pad=0.2)
    fig.savefig(caminho, transparent=True)
    plt.close(fig)


def grafico_barras(por_cat, caminho):
    itens = sorted(por_cat.items(), key=lambda kv: kv[0])
    nomes = [textwrap.fill(k, 26) for k, _ in itens]
    vals = [v for _, v in itens]
    # cor da barra = severidade máxima presente naquela categoria
    cores = []
    for cat, _ in itens:
        sevs = [a["severidade"] for a in D.ACHADOS if a["categoria"] == cat]
        cores.append(HEX[min(sevs, key=ORDEM.index)] if sevs else HEX["forte"])
    fig, ax = plt.subplots(figsize=(4.5, 2.9), dpi=220)
    y = range(len(nomes))
    ax.barh(list(y), vals, color=cores, height=0.52, zorder=3)
    for i, v in enumerate(vals):
        ax.text(v + 0.09, i, "nenhum" if v == 0 else str(v), va="center",
                fontsize=7.4, fontweight="bold",
                color="#059669" if v == 0 else "#0F172A")
    ax.set_yticks(list(y))
    ax.set_yticklabels(nomes, fontsize=7.2, color="#0F172A")
    ax.invert_yaxis()
    ax.set_xlim(0, max(vals) + 1.05)
    ax.set_xticks(range(0, max(vals) + 2))
    ax.tick_params(axis="x", labelsize=7, colors="#475569")
    ax.grid(axis="x", color="#E2E8F0", zorder=0)
    for lado in ("top", "right", "left"):
        ax.spines[lado].set_visible(False)
    ax.spines["bottom"].set_color("#CBD5E1")
    fig.tight_layout(pad=0.2)
    fig.savefig(caminho, transparent=True)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Canvas com "Página X de Y" + cabeçalho/rodapé
# ---------------------------------------------------------------------------
class Numerado(pdfcanvas.Canvas):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._paginas = []

    def showPage(self):
        self._paginas.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._paginas)
        for estado in self._paginas:
            self.__dict__.update(estado)
            if getattr(self, "_e_capa", False):
                super().showPage()
                continue
            self._cabecalho_rodape(total)
            super().showPage()
        super().save()

    def _cabecalho_rodape(self, total):
        larg, alt = A4
        self.saveState()
        self.setFont(F_REG, 7.6)
        self.setFillColor(TINTA_FRACA)
        self.drawString(2 * cm, alt - 1.28 * cm, TITULO_RELATORIO)
        self.setStrokeColor(LINHA)
        self.setLineWidth(0.5)
        self.line(2 * cm, alt - 1.45 * cm, larg - 2 * cm, alt - 1.45 * cm)
        self.line(2 * cm, 1.42 * cm, larg - 2 * cm, 1.42 * cm)
        self.setFont(F_REG, 7.4)
        # O rodapé tem uma linha só: mantenha-o curto ou ele encosta no número
        # da página. A data completa de emissão/revisão fica na capa.
        self.drawString(2 * cm, 1.02 * cm,
                        f"{D.PROJETO} · rev. {D.REVISAO} · {_data_vigente()}")
        self.drawRightString(larg - 2 * cm, 1.02 * cm, f"Página {self._pageNumber} de {total}")
        self.restoreState()


def _marcar_capa(canvas, doc):
    canvas._e_capa = True


def _fundo_capa(canvas, doc):
    canvas._e_capa = True
    larg, alt = A4
    canvas.saveState()
    canvas.setFillColor(colors.HexColor("#0B1220"))
    canvas.rect(0, 0, larg, alt, stroke=0, fill=1)
    # faixa de severidades no topo
    x = 0
    for s in ORDEM:
        canvas.setFillColor(COR[s])
        canvas.rect(x, alt - 0.55 * cm, larg / 4.0, 0.55 * cm, stroke=0, fill=1)
        x += larg / 4.0
    canvas.setFillColor(colors.HexColor("#1E293B"))
    canvas.rect(0, 0, larg, 1.1 * cm, stroke=0, fill=1)
    canvas.setFillColor(colors.HexColor("#94A3B8"))
    canvas.setFont(F_REG, 7.6)
    canvas.drawString(2 * cm, 0.42 * cm, "Documento interno · uso restrito à equipe do projeto")
    canvas.restoreState()


def _conteudo(canvas, doc):
    canvas._e_capa = False


# ---------------------------------------------------------------------------
# Seções
# ---------------------------------------------------------------------------
def secao_capa(por_sev):
    el = [Spacer(1, 3.6 * cm)]
    el.append(Paragraph("AUDITORIA DE SEGURANÇA", S["capa_meta"]))
    el.append(Spacer(1, 5 * mm))
    el.append(Paragraph(f"Relatório de Auditoria<br/>de Segurança<br/>"
                        f"<font size=15 color='#94A3B8'>{esc(D.PROJETO)}</font>",
                        S["capa_titulo"]))
    el.append(Spacer(1, 8 * mm))
    emissao = f"Emitido em {esc(D.DATA_AUDITORIA)}"
    if getattr(D, "DATA_REVISAO", None):
        emissao += f" &nbsp;·&nbsp; revisado em {esc(D.DATA_REVISAO)}"
    el.append(Paragraph(
        f"{emissao}<br/>revisão auditada: {esc(D.REVISAO)}", S["capa_sub"]))
    el.append(Spacer(1, 1.1 * cm))

    # tira de KPIs — 4 cartões, alinhados exatamente à coluna de texto
    vao = 8.0                      # respiro entre cartões
    passo = LARG / 4.0
    cartao = passo - vao
    celulas = []
    for i, s in enumerate(ORDEM):
        celulas.append(Table(
            [[Paragraph(str(por_sev[s]), S["kpi_n"])], [Paragraph(ROTULO[s], S["kpi_r"])]],
            colWidths=[passo if i == 3 else cartao], rowHeights=[0.95 * cm, 0.5 * cm],
            style=TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), COR[s]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("ROUNDEDCORNERS", [5, 5, 5, 5]),
            ])))
    tira = Table([celulas], colWidths=[passo] * 4)
    tira.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), vao),
        ("RIGHTPADDING", (3, 0), (3, 0), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    el.append(tira)
    el.append(Spacer(1, 1.1 * cm))

    st_t = _st("capa_h", fontName=F_BOLD, fontSize=9.6, leading=13,
               textColor=colors.HexColor("#7DD3FC"), spaceAfter=4)
    st_c = _st("capa_c", fontSize=8.5, leading=12.8, alignment=TA_JUSTIFY,
               textColor=colors.HexColor("#CBD5E1"), spaceAfter=3)

    el.append(Paragraph("ESCOPO AUDITADO", st_t))
    for x in D.ESCOPO:
        el.append(Paragraph("•&nbsp; " + esc(x), st_c))
    el.append(Spacer(1, 6 * mm))
    el.append(Paragraph("NOTA METODOLÓGICA", st_t))
    el.append(Paragraph(
        "As cinco categorias do pedido foram mapeadas para os equivalentes da stack detectada. "
        "O mapeamento completo está na seção 1; o resumo é: "
        "não há RLS neste projeto, o isolamento de inquilino é filtro manual no ORM; a matriz de papéis "
        "do frontend foi cruzada uma a uma com as permission_classes do DRF; todos os handlers de rota "
        "foram percorridos, não amostras; e as categorias sem equivalente na stack estão declaradas como "
        "não aplicáveis em vez de preenchidas à força.", st_c))
    return el


def secao_metodologia():
    el = [barra_secao("1.", "Escopo e nota metodológica"), Spacer(1, 3 * mm)]
    linhas = [[Paragraph("Categoria / item", S["cel_cab"]),
               Paragraph("Como foi mapeada para esta stack", S["cel_cab"])]]
    for titulo, texto in D.METODOLOGIA:
        linhas.append([Paragraph(f"<b>{esc(titulo)}</b>", S["cel"]),
                       Paragraph(esc(texto), S["cel"])])
    t = Table(linhas, colWidths=[4.3 * cm, LARG - 4.3 * cm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), TINTA),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.4, LINHA),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, FUNDO_SUAVE]),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    el.append(t)

    el.append(Paragraph("Categorias não aplicáveis a esta stack", S["h2"]))
    linhas = [[Paragraph("Item", S["cel_cab"]), Paragraph("Situação", S["cel_cab"])]]
    for titulo, texto in D.NAO_APLICAVEL:
        linhas.append([Paragraph(f"<b>{esc(titulo)}</b>", S["cel"]), Paragraph(esc(texto), S["cel"])])
    t = Table(linhas, colWidths=[4.3 * cm, LARG - 4.3 * cm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), COR["forte"]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.4, LINHA),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#ECFDF5")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    el.append(t)
    return el


def secao_resumo(por_sev, por_cat, png_rosca, png_barras):
    el = [barra_secao("2.", "Resumo executivo"), Spacer(1, 2 * mm)]
    n = len(D.ACHADOS)
    poc = sum(1 for a in D.ACHADOS if a.get("poc"))

    def _contagem(qtd, sing, plur):
        return f"{qtd} {sing if qtd == 1 else plur}"

    placar = ", ".join([
        _contagem(por_sev["critica"], "crítico", "críticos"),
        _contagem(por_sev["alta"], "alto", "altos"),
        _contagem(por_sev["media"], "médio", "médios"),
        _contagem(por_sev["baixa"], "baixo", "baixos"),
    ])
    altos = [a for a in D.ACHADOS if a["severidade"] == "alta"]
    lista_altos = "; ".join(f"<b>{esc(a['id'])}</b> — {esc(a['titulo'])}" for a in altos)

    el.append(Paragraph(
        f"A auditoria produziu <b>{n} achados verificados no código real</b> — {placar} — e "
        f"<b>{poc} deles foram reproduzidos com prova de conceito executável</b> contra a própria API "
        "(teste Django + APIClient), não apenas inferidos da leitura. O achado crítico é um par de "
        "endpoints JWT legados que continua publicado ao lado do fluxo de autenticação endurecido e "
        "anula MFA, bloqueio de conta e revogação de sessão. Em contrapartida, o núcleo do isolamento "
        "multi-tenant e a superfície de XSS estão sólidos — a seção 3 detalha o que foi verificado e "
        "está correto.", S["p"]))
    if altos:
        el.append(Paragraph(
            f"Achados de severidade alta: {lista_altos}.", S["p"]))
    if getattr(D, "DATA_REVISAO", None):
        el.append(Paragraph(
            f"<b>Revisão de {esc(D.DATA_REVISAO)}.</b> O Portal do Cliente passou a ser somente "
            "consulta, com uma única escrita recortada (o retorno de informação da Ordem de Serviço). "
            "Isso fechou o vetor de A-02, que era ALTA e passou a BAIXA — a lacuna estrutural que o "
            "originou continua no código e está descrita no achado. Os demais achados não foram "
            "afetados.", S["p"]))
    el.append(Spacer(1, 3 * mm))

    g1 = Image(png_rosca); g1._restrictSize(7.4 * cm, 6.0 * cm)
    g2 = Image(png_barras); g2._restrictSize(9.6 * cm, 6.0 * cm)
    graf = Table([[g1, g2],
                  [Paragraph("Distribuição por severidade", S["legenda"]),
                   Paragraph("Achados por categoria auditada", S["legenda"])]],
                 colWidths=[LARG * 0.42, LARG * 0.58])
    graf.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, 0), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, 0), 2),
    ]))
    el.append(graf)
    el.append(Spacer(1, 4 * mm))

    linhas = [[Paragraph("Severidade", S["cel_cab"]), Paragraph("Qtde.", S["cel_cab"]),
               Paragraph("Achados", S["cel_cab"]),
               Paragraph("Leitura", S["cel_cab"])]]
    leitura = {
        "critica": "Corrigir antes do próximo deploy.",
        "alta": "Corrigir nesta sprint; há vazamento de dado ou de segredo.",
        "media": "Corrigir na sequência; depende de um estado de configuração alcançável.",
        "baixa": "Dívida técnica de segurança; sem exploração conhecida hoje.",
    }
    for s in ORDEM:
        ids = ", ".join(a["id"] for a in D.ACHADOS if a["severidade"] == s) or "—"
        linhas.append([chip(s), Paragraph(f"<b>{por_sev[s]}</b>", S["cel"]),
                       Paragraph(esc(ids), S["cel"]), Paragraph(esc(leitura[s]), S["cel"])])
    t = Table(linhas, colWidths=[2.4 * cm, 1.5 * cm, 2.6 * cm, LARG - 6.5 * cm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), TINTA),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.4, LINHA),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, FUNDO_SUAVE]),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    el.append(t)
    return el


def secao_fortes_fracos():
    el = [barra_secao("3.", "Pontos fortes e pontos fracos")]
    el.append(Paragraph(
        "Os pontos fortes abaixo não são elogios genéricos: cada um cita o arquivo e a linha que "
        "sustentam a afirmação, e juntos delimitam a cobertura desta auditoria — o que foi olhado e "
        "encontrado correto.", S["p"]))

    el.append(Paragraph("3.1 · O que está protegido (com evidência)", S["h2"]))
    linhas = [[Paragraph("Controle verificado", S["cel_cab"]), Paragraph("Evidência no código", S["cel_cab"])]]
    for titulo, texto in D.PONTOS_FORTES:
        linhas.append([Paragraph(f"<b>{esc(titulo)}</b>", S["cel"]), Paragraph(esc(texto), S["cel"])])
    t = Table(linhas, colWidths=[5.4 * cm, LARG - 5.4 * cm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), COR["forte"]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.4, LINHA),
        ("LINEBEFORE", (0, 1), (0, -1), 2.2, COR["forte"]),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F0FDF4")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    el.append(t)

    el.append(Paragraph("3.2 · Riscos centrais", S["h2"]))
    linhas = [[Paragraph("Risco", S["cel_cab"]), Paragraph("Por quê", S["cel_cab"])]]
    for titulo, texto in D.PONTOS_FRACOS:
        linhas.append([Paragraph(f"<b>{esc(titulo)}</b>", S["cel"]), Paragraph(esc(texto), S["cel"])])
    t = Table(linhas, colWidths=[5.4 * cm, LARG - 5.4 * cm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), COR["critica"]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.4, LINHA),
        ("LINEBEFORE", (0, 1), (0, -1), 2.2, COR["critica"]),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FEF2F2")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    el.append(t)

    el.append(Paragraph("3.3 · Categoria 5 (XSS): o que foi verificado e está correto", S["h2"]))
    el.append(Paragraph(
        "A categoria não gerou achados. A tabela registra cada ponto inspecionado, para que a ausência "
        "de achados seja auditável em vez de uma afirmação sem lastro.", S["p_peq"]))
    linhas = [[Paragraph("Arquivo:linha", S["cel_cab"]), Paragraph("Vetor checado", S["cel_cab"]),
               Paragraph("Resultado", S["cel_cab"])]]
    for arq, vetor, res in D.VERIFICADO_XSS:
        linhas.append([Paragraph(caminho(arq, 34), S["cel_mono"]), Paragraph(esc(vetor), S["cel"]),
                       Paragraph(esc(res), S["cel"])])
    t = Table(linhas, colWidths=[5.6 * cm, 3.5 * cm, LARG - 9.1 * cm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), COR["forte"]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.4, LINHA),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F0FDF4")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5),
    ]))
    el.append(t)
    return el


def secao_tabela_achados():
    el = [barra_secao("4.", "Achados detalhados por categoria")]
    el.append(Paragraph(
        "Visão tabular exigida pelo escopo: severidade, arquivo:linha e descrição, agrupadas por "
        "categoria. O detalhamento técnico de cada achado — trecho de código, prova de conceito, "
        "condições de explorabilidade e correção — vem na seção 5.", S["p"]))

    ordenados = sorted(D.ACHADOS, key=lambda a: (a["categoria"], ORDEM.index(a["severidade"])))
    linhas = [[Paragraph("Severidade", S["cel_cab"]), Paragraph("Arquivo:linha", S["cel_cab"]),
               Paragraph("Descrição", S["cel_cab"])]]
    estilo = [
        ("BACKGROUND", (0, 0), (-1, 0), TINTA),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.4, LINHA),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    cat_atual = None
    i = 0
    for a in ordenados:
        if a["categoria"] != cat_atual:
            cat_atual = a["categoria"]
            i += 1
            linhas.append([Paragraph(f"<b>{esc(cat_atual)}</b>", S["cel"]), "", ""])
            estilo += [("SPAN", (0, i), (-1, i)),
                       ("BACKGROUND", (0, i), (-1, i), colors.HexColor("#E2E8F0"))]
        i += 1
        arqs = "<br/>".join(caminho(x) for x in a["arquivos"])
        desc = (f"<b>{esc(a['id'])} — {esc(a['titulo'])}</b><br/>{esc(a['impacto'])}")
        if a.get("poc"):
            desc += "<br/><font color='#B91C1C'><b>Reproduzido com prova de conceito.</b></font>"
        if a.get("condicoes"):
            desc += f"<br/><i>Condição: {esc(a['condicoes'])}</i>"
        linhas.append([chip(a["severidade"]), Paragraph(arqs, S["cel_mono"]),
                       Paragraph(desc, S["cel"])])
        estilo.append(("BACKGROUND", (0, i), (0, i), colors.white))

    t = Table(linhas, colWidths=[2.4 * cm, 5.9 * cm, LARG - 8.3 * cm], repeatRows=1)
    t.setStyle(TableStyle(estilo))
    el.append(t)
    return el


def secao_detalhe():
    el = [barra_secao("5.", "Detalhamento técnico dos achados")]
    el.append(Paragraph(
        "Um bloco por achado, na ordem de severidade. Os blocos escuros reproduzem o código exatamente "
        "como está no repositório, com o número de linha original.", S["p"]))

    for a in sorted(D.ACHADOS, key=lambda x: ORDEM.index(x["severidade"])):
        bloco = []
        cab = Table([[chip(a["severidade"]),
                      Paragraph(f"<b>{esc(a['id'])}</b> &nbsp; {esc(a['titulo'])}",
                                _st("ach_t", fontName=F_BOLD, fontSize=10.4, leading=14))]],
                    colWidths=[2.2 * cm, LARG - 2.2 * cm])
        cab.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (0, 0), 0), ("LEFTPADDING", (1, 0), (1, 0), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LINEBELOW", (0, 0), (-1, -1), 1.4, COR[a["severidade"]]),
        ]))
        bloco.append(cab)
        bloco.append(Spacer(1, 2.5 * mm))
        bloco.append(Paragraph(f"Categoria: {esc(a['categoria'])}", S["h3"]))
        bloco.append(Paragraph(
            "Arquivos: " + "&nbsp;&nbsp;".join(f"<font face='{F_MONO}' size=7.4>{esc(x)}</font>"
                                               for x in a["arquivos"]),
            S["p_arq"]))
        bloco.append(bloco_codigo(a["trecho"]))
        bloco.append(Spacer(1, 3 * mm))
        el.append(KeepTogether(bloco))

        el.append(Paragraph("Por que é explorável", S["h3"]))
        el.append(Paragraph(esc(a["porque"]), S["p"]))
        if a.get("bypassa"):
            el.append(Paragraph("Proteções contornadas, uma a uma:", S["p_peq"]))
            el.extend(bullets(a["bypassa"]))
            el.append(Spacer(1, 2 * mm))
        if a.get("poc") and a.get("poc_texto"):
            el.append(Paragraph("Prova de conceito executada", S["h3"]))
            el.append(bloco_codigo(a["poc_texto"], tam=6.9,
                                   cabecalho="$ python manage.py test  (saída real)"))
            el.append(Spacer(1, 3 * mm))
        if a.get("condicoes"):
            el.append(Paragraph("Condições de explorabilidade", S["h3"]))
            el.append(Paragraph(esc(a["condicoes"]), S["p"]))
        el.append(Paragraph("Impacto", S["h3"]))
        el.append(Paragraph(esc(a["impacto"]), S["p"]))
        el.append(Paragraph("Correção sugerida", S["h3"]))
        el.append(Paragraph(esc(a["correcao"]), S["p"]))
        el.append(Spacer(1, 6 * mm))
    return el


def secao_recomendacoes():
    el = [barra_secao("6.", "Recomendações priorizadas")]
    el.append(Paragraph(
        "P1 = antes do próximo deploy. P2 = nesta sprint. P3 = backlog de higiene, sem exploração "
        "conhecida hoje. ✓ = já corrigido depois da primeira emissão deste relatório.", S["p"]))
    cor_p = {"P1": COR["critica"], "P2": COR["media"], "P3": COR["baixa"], "✓": COR["forte"]}
    linhas = [[Paragraph("Prio.", S["cel_cab"]), Paragraph("Ação", S["cel_cab"]),
               Paragraph("Achado", S["cel_cab"]), Paragraph("Como", S["cel_cab"])]]
    estilo = [
        ("BACKGROUND", (0, 0), (-1, 0), TINTA),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.4, LINHA),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, FUNDO_SUAVE]),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("ALIGN", (0, 1), (0, -1), "CENTER"),
    ]
    # Uma tabela chamada "priorizada" precisa sair na ordem da prioridade,
    # não na ordem em que os itens foram escritos; o concluído (✓) vai ao fim.
    ordem_prio = {"P1": 0, "P2": 1, "P3": 2, "✓": 3}
    ordenadas = sorted(D.RECOMENDACOES, key=lambda r: ordem_prio.get(r[0], 9))
    for i, (prio, acao, ref, como) in enumerate(ordenadas, start=1):
        linhas.append([
            Paragraph(f"<b>{prio}</b>", _st("prio", fontName=F_BOLD, fontSize=9,
                                            alignment=TA_CENTER, textColor=colors.white)),
            Paragraph(f"<b>{esc(acao)}</b>", S["cel"]),
            Paragraph(esc(ref), S["cel_mono"]),
            Paragraph(esc(como), S["cel"]),
        ])
        estilo.append(("BACKGROUND", (0, i), (0, i), cor_p[prio]))
        estilo.append(("VALIGN", (0, i), (0, i), "MIDDLE"))
    t = Table(linhas, colWidths=[1.3 * cm, 5.4 * cm, 1.9 * cm, LARG - 8.6 * cm], repeatRows=1)
    t.setStyle(TableStyle(estilo))
    el.append(t)
    return el


def secao_issues():
    el = [barra_secao("7.", "Issues para o GitHub")]
    el.append(Paragraph(
        "Texto completo em Markdown, pronto para copiar e colar. Cada issue está delimitada entre "
        "<font face='%s'>--- ISSUE n ---</font> e <font face='%s'>--- FIM ISSUE n ---</font>. "
        "Achados triviais do mesmo tema foram agrupados numa issue só, para não gerar spam no "
        "repositório." % (F_MONO, F_MONO), S["p"]))
    el.append(Spacer(1, 2 * mm))

    st_delim = _st("delim", fontName=F_MONOB, fontSize=8.2, leading=12,
                   textColor=colors.HexColor("#B91C1C"), spaceBefore=6, spaceAfter=3)
    for n, titulo, texto in montar_issues():
        el.append(Paragraph(f"--- ISSUE {n} ---", st_delim))
        el.extend(bloco_codigo_paginado(texto, tam=6.4))
        el.append(Paragraph(f"--- FIM ISSUE {n} ---", st_delim))
        el.append(Spacer(1, 3 * mm))
    return el


# ---------------------------------------------------------------------------
def main():
    os.makedirs(DIR_GRAF, exist_ok=True)
    por_sev, por_cat = _contagens()
    png_rosca = os.path.join(DIR_GRAF, "severidade.png")
    png_barras = os.path.join(DIR_GRAF, "categorias.png")
    grafico_rosca(por_sev, png_rosca)
    grafico_barras(por_cat, png_barras)

    doc = BaseDocTemplate(
        SAIDA_PDF, pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm,
        title=TITULO_RELATORIO, author="Auditoria de segurança", subject=D.PROJETO,
    )
    quadro_capa = Frame(2 * cm, 2 * cm, LARG, A4[1] - 4 * cm, id="capa",
                        leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    quadro = Frame(2 * cm, 1.75 * cm, LARG, A4[1] - 3.9 * cm, id="corpo",
                   leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([
        PageTemplate(id="capa", frames=[quadro_capa], onPage=_fundo_capa),
        PageTemplate(id="conteudo", frames=[quadro], onPage=_conteudo),
    ])

    hist = []
    hist += secao_capa(por_sev)
    hist.append(NextPageTemplate("conteudo"))
    hist.append(PageBreak())
    hist += secao_metodologia()
    hist.append(PageBreak())
    hist += secao_resumo(por_sev, por_cat, png_rosca, png_barras)
    hist.append(PageBreak())
    hist += secao_fortes_fracos()
    hist.append(PageBreak())
    hist += secao_tabela_achados()
    hist.append(PageBreak())
    hist += secao_detalhe()
    hist.append(PageBreak())
    hist += secao_recomendacoes()
    hist.append(PageBreak())
    hist += secao_issues()

    doc.build(hist, canvasmaker=Numerado)

    # Mesmo conteúdo da seção 7, em arquivo .md — copiar e colar de um PDF
    # costuma trazer sujeira, então o texto sai também em formato nativo.
    with open(SAIDA_MD, "w", encoding="utf-8") as fh:
        fh.write(f"# Issues de segurança — {D.PROJETO}\n\n")
        fh.write(f"Geradas a partir da auditoria de {D.DATA_AUDITORIA} "
                 f"(revisão {D.REVISAO}). Uma issue por bloco.\n\n")
        for n, titulo, texto in montar_issues():
            fh.write(f"--- ISSUE {n} ---\n\n{texto}\n\n--- FIM ISSUE {n} ---\n\n")
    print(f"Issues geradas: {SAIDA_MD}")

    print(f"PDF gerado: {SAIDA_PDF}")
    print(f"Achados: {len(D.ACHADOS)}  |  "
          + "  ".join(f"{ROTULO[s]}={por_sev[s]}" for s in ORDEM))
    print(f"Gerado em {datetime.now():%d/%m/%Y %H:%M}")


if __name__ == "__main__":
    main()
