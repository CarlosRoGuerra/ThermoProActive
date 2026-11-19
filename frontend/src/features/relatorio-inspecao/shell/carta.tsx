"use client";

import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";
import type { DossieShell, Prestador } from "../tipos";
import type { ConteudoCarta } from "../modulos/contrato";
import { FONTE_RELATORIO } from "./folhas";
import { ddmmaaaa } from "./formato";

/* ============================================================================
   CARTA AO CLIENTE — fiel ao modelo Word (VB_Carta_Foroni). Folha A4 física,
   margens 35/15/10/25mm, Segoe UI 12pt justificado, itens numerados 1–8 e
   assinatura. O shell desenha os itens; o conteúdo técnico vem do módulo da
   tecnologia: os textos (seções, glossário, considerações) pelo backend em
   `d.carta` — a mesma fonte da carta .docx — e a tabela normativa e os
   parágrafos sobre o que foi apurado pelo módulo do front (`ConteudoCarta`).
   ========================================================================== */

/* ------------------------------- Blocos base ------------------------------ */
/* Cabeçalho institucional (papel timbrado) do Word: logo à esquerda + dados do
   prestador em cinza à direita, largura útil 170mm (margens esq. 25 / dir. 15).
   Posicionado DENTRO da margem superior reservada (não em fluxo) — mesma
   geometria do .docx: `header_distance = 5mm`, corpo começa em 35mm fixos,
   independente da altura que o timbrado ocupar. */
function Timbrado({ p }: { p: Prestador | null }) {
  if (!p) return null;
  return (
    <div style={{ position: "absolute", left: "25mm", top: "5mm", width: "170mm", fontFamily: FONTE_RELATORIO }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end" }}>
        {p.logomarca && (
          <div style={{ width: "62mm", height: "13mm", display: "flex", alignItems: "center", overflow: "hidden" }}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={p.logomarca} alt="Thermoproactive" style={{ width: "55mm", height: "auto", maxHeight: "12mm", objectFit: "contain", objectPosition: "left center" }} />
          </div>
        )}
        <div style={{ textAlign: "right", color: "#9a9a9a", lineHeight: 1.2 }}>
          <div style={{ fontSize: "12pt", fontWeight: 700, color: "#808080" }}>{p.nome}</div>
          {p.cnpj && <div style={{ fontSize: "9pt" }}>CNPJ {p.cnpj}{p.inscricao_estadual ? ` | IE ${p.inscricao_estadual}` : ""}</div>}
        </div>
      </div>
      <div style={{ borderTop: "0.15mm solid #1d4ed8", marginTop: "2mm" }} />
      <div style={{ textAlign: "right", color: "#9a9a9a", fontSize: "8pt", lineHeight: 1.25, marginTop: "1mm" }}>
        {p.endereco_linha1 && <div>{p.endereco_linha1}</div>}
        {p.endereco_linha2 && <div>{p.endereco_linha2}</div>}
        {p.telefone && <div>{p.telefone}</div>}
        {p.email && <div>{p.email}</div>}
      </div>
    </div>
  );
}

/* Texto da carta: Segoe UI 12pt, entrelinha 1,15. A folha e o medidor das folhas
   em fluxo usam o mesmo estilo — a medida só vale se o texto for igual. */
const TEXTO_CARTA: CSSProperties = {
  fontFamily: FONTE_RELATORIO, fontSize: "12pt", color: "#000", lineHeight: 1.15,
  WebkitFontSmoothing: "antialiased", MozOsxFontSmoothing: "grayscale",
};

/* Folha A4 física da carta (210×297mm) — MESMAS margens do gerador .docx
   (carta_docx.py): topo 35 / direita 15 / baixo 10 / esquerda 25mm. Própria da
   carta — as páginas do relatório usam PaginaInterna/Timbrado de `folhas.tsx`. */
function Folha({ p, children }: { p: Prestador | null; children: ReactNode }) {
  return (
    <section
      className="pagina pagina-carta"
      style={{
        position: "relative", width: "210mm", minHeight: "297mm", padding: "35mm 15mm 10mm 25mm", boxSizing: "border-box",
        background: "#fff", ...TEXTO_CARTA,
      }}
    >
      <Timbrado p={p} />
      <div style={{ width: "170mm" }}>{children}</div>
    </section>
  );
}

/* Título de item numerado (1.–8.), negrito, recuo pendente de 10mm. Sem
 * espaço ACIMA (no .docx `_titulo` sempre usa space_before=0 — o respiro
 * antes do título vem do conteúdo anterior, nunca do título em si).
 * `gap` = espaço ATÉ o primeiro parágrafo — valor calibrado visualmente
 * contra o .docx (o cálculo em pt/twips ficava sistematicamente menor do
 * que o modelo real renderiza), igual nos itens 1–5 e 6–8. */
function CItem({ n, children, gap = "6mm" }: { n: string; children: ReactNode; gap?: string }) {
  return <p style={{ fontWeight: 700, marginTop: 0, marginBottom: gap, marginLeft: "10mm", textIndent: "-10mm" }}>{n} {children}</p>;
}
/* Parágrafo do corpo (justificado, recuo padrão 10mm). Por padrão TIGHT
 * (margin 0 — no .docx, `_p()` sem override usa space_after=0: parágrafos de
 * um mesmo item ficam colados, só a entrelinha 1,15 separa). `solto` é para
 * os itens 6–8 (glossário/definição da técnica/considerações), onde o .docx
 * intercala uma linha em branco (estilo SemEspaçamento) entre CADA
 * parágrafo — bem mais espaçado que 1–5. */
function CP({ children, ml = "10mm", solto = false }: { children: ReactNode; ml?: string; solto?: boolean }) {
  return <p style={{ margin: 0, marginBottom: solto ? "7mm" : 0, marginLeft: ml, textAlign: "justify" }}>{children}</p>;
}
/* Linha em branco entre itens (só onde 2+ itens dividem a mesma Folha —
 * hoje só a Folha 1, itens 1–4): no .docx é um `_blank()` explícito entre
 * cada item. */
function CBlank() {
  return <div aria-hidden style={{ height: "12mm" }} />;
}

/* Item 4 no formato do RT.TE (termografia elétrica): "4.1. <instrumento>" com Marca |
   Modelo na mesma linha, calibração em mês/ano e os softwares num subitem próprio.
   Mesma regra da carta .docx (carta_docx.py). */
function InstrumentacaoNumerada({ instrumentos }: { instrumentos: DossieShell["cabecalho"]["instrumentos"] }) {
  const mesAno = (d: string) => { const [a, m] = d.split("-"); return `${m}/${a}`; };
  const softwares = Array.from(new Set(instrumentos.map((i) => (i.software_analise || "").trim()).filter(Boolean)));
  return (
    <>
      {instrumentos.map((i, k) => (
        <div key={k} style={{ marginBottom: "1mm" }}>
          <p style={{ margin: 0, marginLeft: "10mm" }}>4.{k + 1}. {i.tipo || "Instrumento"}</p>
          <div style={{ marginLeft: "22.5mm" }}>
            {(i.marca || i.modelo) && (
              <p style={{ margin: 0 }}>{[i.marca && `Marca: ${i.marca}`, i.modelo && `Modelo: ${i.modelo}`].filter(Boolean).join(" | ")}</p>
            )}
            {i.numero_serie && <p style={{ margin: 0 }}>Serial #: {i.numero_serie}</p>}
            {i.data_ultima_calibracao && <p style={{ margin: 0 }}>Data da última calibração: {mesAno(i.data_ultima_calibracao)}</p>}
            {i.periodicidade && i.data_ultima_calibracao && <p style={{ margin: 0 }}>Validade: {i.periodicidade}</p>}
            {i.entidade_calibracao && <p style={{ margin: 0 }}>Entidade Calibração: {i.entidade_calibracao}</p>}
          </div>
        </div>
      ))}
      {softwares.length > 0 && (
        <div>
          <p style={{ margin: 0, marginLeft: "10mm" }}>4.{instrumentos.length + 1}. Softwares de Análises:</p>
          <p style={{ margin: 0, marginLeft: "22.5mm" }}>{softwares.join(" | ")}</p>
        </div>
      )}
    </>
  );
}

/* ---------------------------- Folhas em fluxo ----------------------------- */
/* Itens 5 e 6 correm como no Word (carta .docx e RT.TE): a Normatização e o
   Glossário seguem um atrás do outro e só passam de folha quando a folha enche.
   Quebra fixa por termo deixava meia folha em branco, porque a altura do texto
   depende da fonte de quem imprime. Aqui a altura de cada bloco é medida no
   próprio navegador e a divisão em folhas sai dessa medida. Um bloco nunca se
   divide: a tabela normativa que não cabe no resto da folha passa inteira para a
   seguinte (na carta .docx a quebra antes dela existe só porque o Word partiria a
   tabela). Enquanto mede, o medidor fica marcado com `data-paginando` e a
   impressão (paged.js) espera. */
export type Bloco = {
  chave: string;
  conteudo: ReactNode;
  /** Não fica sozinho no pé da folha: desce junto com o bloco seguinte (títulos). */
  comOProximo?: boolean;
  /** Espaço entre itens: some quando cairia no topo de uma folha. */
  espaco?: boolean;
};

/* Área útil da Folha (297 − 35 de topo − 10 de pé), com 2 mm de folga para o
   arredondamento entre a medida e a impressão. */
const ALTURA_UTIL_MM = 297 - 35 - 10 - 2;

/** Índices dos blocos de cada folha. `altos` = altura de cada bloco com as margens
 *  (o paged.js conta a margem de baixo do último bloco); `limite` na mesma unidade. */
export function distribuirBlocos(blocos: Bloco[], altos: number[], limite: number): number[][] {
  const folhas: number[][] = [[]];
  let usado = 0;
  const atual = () => folhas[folhas.length - 1];
  const temConteudo = () => atual().some((k) => !blocos[k].espaco);
  const virar = () => {
    while (atual().length && blocos[atual()[atual().length - 1]].espaco) atual().pop();
    folhas.push([]);
    usado = 0;
  };
  let i = 0;
  while (i < blocos.length) {
    // Bloco que não desenha nada (ex.: tabela normativa sem linhas) não conta.
    if (altos[i] < 0.5) { i++; continue; }
    if (blocos[i].espaco && !temConteudo()) { i++; continue; }
    // Grupo = o bloco e os seguintes que ele segura (título + primeiro termo).
    let j = i;
    while (j + 1 < blocos.length && blocos[j].comOProximo) j++;
    let alto = 0;
    for (let k = i; k <= j; k++) alto += altos[k];
    if (usado + alto > limite && temConteudo()) { virar(); continue; }
    for (let k = i; k <= j; k++) { atual().push(k); usado += altos[k]; }
    i = j + 1;
  }
  return folhas.filter((f) => f.length);
}

/* Cada bloco numa caixa que contém as próprias margens: a altura medida é a
   mesma que o bloco ocupa na folha. */
const CAIXA_BLOCO: CSSProperties = { display: "flow-root" };

function FolhasEmFluxo({ p, blocos }: { p: Prestador | null; blocos: Bloco[] }) {
  const assinatura = blocos.map((b) => b.chave).join("\u0001");
  const [estado, setEstado] = useState<{ assinatura: string; folhas: number[][] } | null>(null);
  const medindo = estado?.assinatura !== assinatura;
  const regua = useRef<HTMLDivElement>(null);
  const medidor = useRef<HTMLDivElement>(null);
  const blocosRef = useRef(blocos);
  blocosRef.current = blocos;

  useEffect(() => {
    if (!medindo) return;
    const caixa = medidor.current;
    const mm = regua.current;
    if (!caixa || !mm) return;
    let vivo = true;
    const medir = () => {
      if (!vivo) return;
      // Sem layout (ex.: dentro de display:none) não há medida: o observer tenta de novo.
      const pxPorMm = mm.getBoundingClientRect().height / 100;
      if (!pxPorMm || !caixa.getBoundingClientRect().width) return;
      // A régua põe o limite na mesma escala das medidas (vale também com zoom/transform na tela).
      const altos = Array.from(caixa.children).map((el) => el.getBoundingClientRect().height);
      setEstado({ assinatura, folhas: distribuirBlocos(blocosRef.current, altos, ALTURA_UTIL_MM * pxPorMm) });
    };
    // A fonte muda a altura do texto: mede depois que as fontes carregarem.
    const observador = new ResizeObserver(() => { void document.fonts.ready.then(medir); });
    observador.observe(caixa);
    return () => { vivo = false; observador.disconnect(); };
  }, [assinatura, medindo]);

  return (
    <>
      {medindo && (
        <div
          aria-hidden
          data-paginando=""
          style={{ position: "absolute", left: 0, top: 0, visibility: "hidden", pointerEvents: "none", ...TEXTO_CARTA }}
        >
          <div ref={regua} style={{ position: "absolute", width: "1px", height: "100mm" }} />
          <div ref={medidor} style={{ width: "170mm" }}>
            {blocos.map((b) => <div key={b.chave} style={CAIXA_BLOCO}>{b.conteudo}</div>)}
          </div>
        </div>
      )}
      {!medindo && estado.folhas.map((indices, f) => (
        <Folha key={`fluxo${f}`} p={p}>
          {indices.map((k) => <div key={blocos[k].chave} style={CAIXA_BLOCO}>{blocos[k].conteudo}</div>)}
        </Folha>
      ))}
    </>
  );
}

/* ------------------------------ Documento --------------------------------- */
export function CartaCorpo({ d, carta }: { d: DossieShell; carta: ConteudoCarta }) {
  const cab = d.cabecalho;
  const p = cab.prestador;
  const textos = d.carta;
  const rangeMedicao =
    cab.data_inicio && cab.data_termino && cab.data_inicio !== cab.data_termino
      ? `${ddmmaaaa(cab.data_inicio)} a ${ddmmaaaa(cab.data_termino)}`
      : ddmmaaaa(cab.data_termino || cab.data_inicio);
  // Definição da Técnica — parágrafos GERADOS dos dados do relatório + texto da técnica.
  const linhasDef = (s?: string) => (s || "").split("\n").map((l) => l.trim()).filter(Boolean);
  const introDef = linhasDef(cab.definicao_tecnica);
  const fluxoDef = linhasDef(cab.definicao_fluxo_trabalho);
  const nEquip = d.secao_c.equip_monitorados;
  const nSetores = new Set(d.secao_c.grupos.map((g) => `${g.area}|${g.setor}`)).size;
  const nAreas = new Set(d.secao_c.grupos.map((g) => g.area)).size;
  const eqTxt = nEquip === 1 ? "1 equipamento" : `${nEquip} equipamentos`;
  const stTxt = nSetores === 1 ? "1 setor" : `${nSetores} setores`;
  const arTxt = nAreas === 1 ? "1 área" : `${nAreas} áreas`;
  // Alcance do relatório (comum) + o que o módulo apurou (texto do backend e/ou do front).
  const paragrafosGerados = [
    `Neste relatório aplicou-se a técnica de ${cab.tecnologia}, contemplando ${eqTxt} monitorado(s) em ${stTxt} (${arTxt}), com o auxílio da instrumentação descrita no item 4.`,
    ...textos.paragrafos,
    ...carta.paragrafosDefinicao,
  ];
  // A termografia elétrica segue o RT.TE: sem a Definição da Técnica (Considerações = item 7).
  const comDefinicao = textos.definicao_tecnica !== false;
  // Itens 5 (Normatização, com a tabela normativa do módulo) e 6 (Glossário) em fluxo.
  const blocosFluxo: Bloco[] = [
    { chave: "item5", conteudo: <CItem n="5.">Normatização</CItem>, comOProximo: true },
    {
      chave: `normas|${cab.normas.map((n) => `${n.codigo}|${n.nome}`).join("|")}`,
      conteudo: cab.normas.length
        ? cab.normas.map((n, k) => <CP key={k}>{[n.codigo, n.nome].filter(Boolean).join(" - ")}</CP>)
        : <CP>Não informada.</CP>,
    },
    ...(carta.normatizacao ? [
      { chave: "espaco-tabela", conteudo: <div aria-hidden style={{ height: "6mm" }} />, espaco: true },
      { chave: "tabela-normativa", conteudo: carta.normatizacao },
    ] : []),
    { chave: "espaco6", conteudo: <CBlank />, espaco: true },
    { chave: "item6", conteudo: <CItem n="6." gap="7mm">Glossário Técnico</CItem>, comOProximo: true },
    ...textos.glossario.map((g) => ({
      chave: `${g.n}|${g.sigla}|${g.texto}`,
      // Sem texto = título de grupo (ex.: "6.1. Temperaturas"), sem travessão: desce com o termo seguinte.
      // Sem sigla = passo numerado (ex.: "6.11.1. Contratada realiza…").
      conteudo: (
        <CP solto>
          {g.sigla ? <><b>{g.n}. {g.sigla}</b>{g.texto ? <> – {g.texto}</> : null}</> : <><b>{g.n}.</b> {g.texto}</>}
        </CP>
      ),
      comOProximo: !g.texto,
    })),
  ];

  return (
    <div className="carta-doc">
      {/* ---- Folha 1: destinatário + nº + itens 1 a 4 ---- */}
      <Folha p={p}>
        <div style={{ marginBottom: "2mm" }}>
          <p style={{ fontWeight: 700, margin: 0 }}>{cab.empresa}{cab.nome_fantasia ? `   ${cab.nome_fantasia}` : ""}</p>
          {cab.endereco_linha1 && <p style={{ margin: 0 }}>{cab.endereco_linha1}</p>}
          {cab.endereco_linha2 && <p style={{ margin: 0 }}>{cab.endereco_linha2}</p>}
          {cab.contato && <p style={{ fontWeight: 700, margin: "4mm 0 0 0" }}>A/C.: Sr(a). {cab.contato}</p>}
          {cab.departamento && <p style={{ fontWeight: 700, margin: 0 }}>{cab.departamento}</p>}
        </div>
        <div style={{ width: "170mm", background: "#d9d9d9", textAlign: "center", fontWeight: 700, padding: "1.5mm 0", margin: "5mm 0" }}>{cab.numero}</div>

        <CItem n="1.">Objetivo do Relatório</CItem>
        <CP>Este relatório técnico tem como objetivo apresentar os resultados das análises técnicas de:</CP>
        <CP>{cab.tecnologia}</CP>
        <CBlank />

        <CItem n="2.">Data(s) da(s) Execução(ões) da(s) Atividade(s)</CItem>
        <CP>Medições em Campo – {rangeMedicao}</CP>
        {textos.data_upload_osps && <CP>Upload das OSP´s – {ddmmaaaa(textos.data_upload_osps)}</CP>}
        <CP>Upload Relatório Completo – {ddmmaaaa(cab.data_finalizacao)}</CP>
        <CBlank />

        <CItem n="3.">Conteúdo do Relatório</CItem>
        {textos.conteudo.map((t) => <CP key={t}>{t}</CP>)}
        <CBlank />

        <CItem n="4.">Instrumentação Utilizada</CItem>
        {cab.instrumentos.length && textos.instrumentacao_numerada ? (
          <InstrumentacaoNumerada instrumentos={cab.instrumentos} />
        ) : cab.instrumentos.length ? cab.instrumentos.map((i, k) => (
          <div key={k} style={{ marginLeft: "22.5mm", marginBottom: "2mm" }}>
            {i.tipo && <p style={{ margin: 0 }}>{i.tipo}</p>}
            {i.marca && <p style={{ margin: 0 }}>Marca: {i.marca}</p>}
            {i.modelo && <p style={{ margin: 0 }}>Modelo: {i.modelo}</p>}
            {i.numero_serie && <p style={{ margin: 0 }}>Serial #: {i.numero_serie}</p>}
            {i.data_ultima_calibracao && <p style={{ margin: 0 }}>Data da última calibração: {ddmmaaaa(i.data_ultima_calibracao)}</p>}
            {i.periodicidade && i.data_ultima_calibracao && <p style={{ margin: 0 }}>Validade: {i.periodicidade}</p>}
            {i.entidade_calibracao && <p style={{ margin: 0 }}>Entidade Calibração: {i.entidade_calibracao}</p>}
            {i.software_analise && <><p style={{ margin: "2mm 0 0 0" }}>Softwares de Análises</p><p style={{ margin: 0 }}>{i.software_analise}</p></>}
          </div>
        )) : <CP ml="22.5mm">Não informada.</CP>}
      </Folha>

      {/* ---- Itens 5 (Normatização) e 6 (Glossário): folhas em fluxo ---- */}
      <FolhasEmFluxo p={p} blocos={blocosFluxo} />

      {/* ---- Folha 4: item 7 (Definição da Técnica) — só nos módulos que a têm ---- */}
      {comDefinicao && (
        <Folha p={p}>
          <CItem n="7." gap="7mm">Definição da Técnica</CItem>
          {/* Parágrafos gerados a partir dos dados do relatório (banco) */}
          {paragrafosGerados.map((t, k) => <CP key={`g${k}`} solto>{t}</CP>)}
          {/* Descrição fixa da técnica (cadastro da tecnologia), quando houver */}
          {introDef.map((t, k) => <CP key={`i${k}`} solto>{t}</CP>)}
          {fluxoDef.map((t, k) => <CP key={`f${k}`} solto>{t}</CP>)}
        </Folha>
      )}

      {/* ---- Folha 5: Considerações (item 8; item 7 sem a Definição da Técnica) + assinatura ---- */}
      <Folha p={p}>
        <CItem n={comDefinicao ? "8." : "7."} gap="7mm">Considerações Importantes</CItem>
        {textos.consideracoes.map((t, k) => <CP key={k} solto>{t}</CP>)}
        {cab.consideracoes_finais.trim() && <CP solto><span style={{ whiteSpace: "pre-line" }}>{cab.consideracoes_finais}</span></CP>}
        <p style={{ margin: "10mm 0 0 10mm" }}>Atenciosamente,</p>
        <div style={{ marginTop: "18mm", display: "flex", justifyContent: "flex-end", gap: "16mm", flexWrap: "wrap" }}>
          {(cab.analistas.length ? cab.analistas : [{ nome: "Analista", assinatura: null }]).map((a) => (
            <div key={a.nome} style={{ textAlign: "center", minWidth: "70mm", paddingTop: "1mm" }}>
              {a.assinatura ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={a.assinatura} alt={`Assinatura de ${a.nome}`} style={{ height: "12mm", objectFit: "contain", margin: "0 auto" }} />
              ) : (
                <div style={{ height: "12mm" }} />
              )}
              <p style={{ fontWeight: 700, margin: 0, borderTop: "0.2mm solid #64748b", paddingTop: "1mm" }}>{a.nome}</p>
              <p style={{ fontSize: "8pt", margin: 0 }}>Analista em Manutenção Preditiva</p>
            </div>
          ))}
        </div>
      </Folha>
    </div>
  );
}
