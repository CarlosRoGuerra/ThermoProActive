import type { ReactNode } from "react";
import type { Dossie } from "@/app/(app)/relatorios-inspecao/[id]/dossie";

/* ============================================================================
   CARTA AO CLIENTE — documento independente do relatório, fiel ao modelo Word
   (VB_Carta_Foroni). Folha A4 física, margens 35/15/10/25mm, Segoe UI 12pt
   justificado, itens numerados 1–8, tabela de severidade ISO-10816-1,
   glossário 6.1–6.9, Definição da Técnica e assinatura.
   ========================================================================== */

const FONTE = '"Segoe UI", system-ui, -apple-system, Roboto, Arial, sans-serif';
const ddmmaaaa = (iso: string | null) => (iso ? iso.split("-").reverse().join("/") : "—");

type Cab = Dossie["cabecalho"];
type Prestador = NonNullable<Cab["prestador"]>;

/* ------------------------------- Conteúdo fixo ---------------------------- */
const CONTEUDO_CARTA = [
  "Seção A – Carta ao Cliente",
  "Seção B – KPI’s Dashboard",
  "Seção C – Relação de Equipamentos Contemplados",
  "Seção D – Ordens de Serviços Preditivos [corretiva orientada pela preditiva]",
];

const GLOSSARIO_CARTA: { n: string; sigla: string; texto: string }[] = [
  { n: "6.1", sigla: "O.S.P.", texto: "Ordem de Serviço Preditivo gerada para correção de cada anomalia detectada." },
  { n: "6.2", sigla: "G.R.", texto: "Grau de Risco: Determinam o prazo de correção das anomalias detectadas." },
  { n: "6.2.1", sigla: "GR-1", texto: "Grau de Risco N°.01: Risco eminente – Recomenda-se intervenção imediata pela equipe de manutenção em prazo máximo de 03 dias. Em casos extremos o inspetor poderá solicitar o reparo em caráter de urgência." },
  { n: "6.2.2", sigla: "GR-2", texto: "Grau de Risco N°.02: Risco elevado – Recomenda-se intervenção pela equipe de manutenção em prazo máximo de 10 dias." },
  { n: "6.2.3", sigla: "GR-3", texto: "Grau de Risco N°.03: Risco moderado – Recomenda-se intervenção pela equipe de manutenção em prazo máximo de 20 dias." },
  { n: "6.2.4", sigla: "GR-4", texto: "Grau de Risco N°.04: Risco baixo – Recomenda-se intervenção pela equipe de manutenção em parada programada prazo máximo de 30 dias." },
  { n: "6.3", sigla: "MP", texto: "Monitoramento Prejudicado: Ocorre em casos em que há existência de obstrução parcial aos equipamentos a serem monitorados. É interessante avaliar o nível de obstrução juntamente com o departamento de segurança do trabalho, sendo possível programar a desobstrução temporária." },
  { n: "6.4", sigla: "NM", texto: "Não Monitorado: Ocorre em casos em que há existência de obstrução total aos equipamentos a serem monitorados; e/ou que coloque em risco a integridade física dos trabalhadores. É interessante avaliar a possibilidade de desobstrução do equipamento juntamente com o departamento de segurança do trabalho e/ou criar condição segura aos trabalhadores." },
  { n: "6.5", sigla: "OK", texto: "Normalidade Operacional: Carga ≥ 70,0%. Os circuitos carregados não apresentam anomalias térmicas." },
  { n: "6.6", sigla: "PDM", texto: "Parado Devido Manutenção: Equipamento encontra-se parado devido algum tipo de intervenção da equipe de manutenção;" },
  { n: "6.7", sigla: "PDP", texto: "Parado Devido Processo: Equipamento encontra-se parado devido anormalidades do processo produtivo;" },
  { n: "6.8", sigla: "LA", texto: "Lado Acoplado;" },
  { n: "6.9", sigla: "LOA", texto: "Lado Oposto ao Acoplamento." },
];

const CONSIDERACOES_CARTA = [
  "Os critérios considerados nas análises das anomalias detectadas são técnicos, associados com a vasta experiência do analista que dará diagnóstico preciso referente à condição dinâmica na qual o objeto avaliado está submetido, porém vale lembrar que cada equipamento tem seu nível de criticidade para a planta onde está instalado, e deverá ser levado em consideração pelo controle e planejamento da manutenção durante a elaboração do plano de manutenções corretivas baseadas pela manutenção preditiva.",
  "As OSP´s emergenciais (GR-1) foram apresentadas, discutidas e tratadas com o planejamento e controle de manutenção ao término das medições.",
  "Toda anomalia detectada deverá ser corrigida o mais rápido possível, pois o prazo sugerido serve apenas como referência, haja vista que a avaliação contratada não é executada em periodicidade mensal (caso sua planta realize avaliação mensal, desconsiderar este parágrafo).",
];

/* ------------------------- Tabela ISO-10816-1 ----------------------------- */
const ISO_VEL: [number, number][] = [
  [0.28, 0.02], [0.45, 0.03], [0.71, 0.04], [1.12, 0.06], [1.80, 0.10], [2.80, 0.16],
  [4.50, 0.25], [7.10, 0.40], [11.20, 0.62], [18.00, 1.00], [28.00, 1.56], [45.00, 2.51],
];
const ISO_ZONAS: Record<string, [number, number, number]> = {
  I: [0.71, 1.80, 4.50], II: [1.12, 2.80, 7.10], III: [1.80, 4.50, 11.20], IV: [2.80, 7.10, 18.00],
};
function sevISO(v: number, cls: string) {
  const z = ISO_ZONAS[cls];
  if (v <= z[0]) return { txt: "Bom", bg: "#22c55e", fg: "#fff" };
  if (v <= z[1]) return { txt: "Satisfatório", bg: "#a3e635", fg: "#1f2937" };
  if (v <= z[2]) return { txt: "Alerta", bg: "#f59e0b", fg: "#1f2937" };
  return { txt: "Perigo", bg: "#ef4444", fg: "#fff" };
}

function TabelaISO10816() {
  const classes = ["I", "II", "III", "IV"];
  const cab: Record<string, [string, string]> = {
    I: ["Classe I", "< 15 kW"], II: ["Classe II", "15 a 75 kW"],
    III: ["Classe III", "Rígida · > 75 kW"], IV: ["Classe IV", "Flexível · > 75 kW"],
  };
  const th = { border: "0.2mm solid #94a3b8", padding: "1mm", textAlign: "center" as const, fontWeight: 700, background: "#f1f5f9" };
  const td = { border: "0.2mm solid #94a3b8", padding: "0.8mm", textAlign: "center" as const };
  return (
    <table style={{ width: "170mm", margin: "3mm auto", borderCollapse: "collapse", fontSize: "8.5pt", tableLayout: "fixed", breakInside: "avoid" }}>
      <thead>
        <tr><th colSpan={6} style={{ ...th, color: "#c00", fontSize: "11pt", background: "#fff" }}>Norma ISO-10816-1 — Severidade · Faixas de Velocidade e Classes de Máquina</th></tr>
        <tr>
          <th style={th}>V [mm/s]<br />RMS</th>
          <th style={th}>V [in/s]<br />Pico</th>
          {classes.map((cl) => (
            <th key={cl} style={th}>{cab[cl][0]}<br /><span style={{ fontWeight: 400 }}>{cab[cl][1]}</span></th>
          ))}
        </tr>
      </thead>
      <tbody>
        {ISO_VEL.map(([mm, pol]) => (
          <tr key={mm}>
            <td style={{ ...td, fontWeight: 700 }}>{mm.toFixed(2)}</td>
            <td style={{ ...td, fontWeight: 700 }}>{pol.toFixed(2)}</td>
            {classes.map((cl) => {
              const s = sevISO(mm, cl);
              return <td key={cl} style={{ ...td, background: s.bg, color: s.fg }}>{s.txt}</td>;
            })}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/* ------------------------------- Blocos base ------------------------------ */
/* Cabeçalho institucional (papel timbrado) do Word: logo à esquerda + dados do
   prestador em cinza à direita, largura útil 170mm (margens esq. 25 / dir. 15).
   Posicionado DENTRO da margem superior reservada (não em fluxo) — mesma
   geometria do .docx: `header_distance = 5mm`, corpo começa em 35mm fixos,
   independente da altura que o timbrado ocupar. */
function Timbrado({ p }: { p: Prestador | null }) {
  if (!p) return null;
  return (
    <div style={{ position: "absolute", left: "25mm", top: "5mm", width: "170mm", fontFamily: FONTE }}>
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

/* Folha A4 física da carta (210×297mm) — MESMAS margens do gerador .docx
   (`criar_documento_base` em carta_docx.py): topo 35 / direita 15 / baixo 10 /
   esquerda 25mm. Componente isolado (só usado por CartaCorpo) — não afeta o
   Relatório Final, que usa PaginaInterna/Timbrado próprios em dossie.tsx. */
function Folha({ p, children }: { p: Prestador | null; children: ReactNode }) {
  return (
    <section
      className="pagina"
      style={{
        position: "relative", width: "210mm", minHeight: "297mm", padding: "35mm 15mm 10mm 25mm", boxSizing: "border-box",
        background: "#fff", fontFamily: FONTE, fontSize: "12pt", color: "#000", lineHeight: 1.15,
        WebkitFontSmoothing: "antialiased", MozOsxFontSmoothing: "grayscale",
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
 * `gap` = espaço ATÉ o primeiro parágrafo: 3,5mm nos itens 1–5 (Normal,
 * herda 10pt-depois); 4,2mm nos itens 6–8 (estilo SemEspaçamento, after=12pt
 * explícito no .docx). */
function CItem({ n, children, gap = "3.5mm" }: { n: string; children: ReactNode; gap?: string }) {
  return <p style={{ fontWeight: 700, marginTop: 0, marginBottom: gap, marginLeft: "10mm", textIndent: "-10mm" }}>{n} {children}</p>;
}
/* Parágrafo do corpo (justificado, recuo padrão 10mm). Por padrão TIGHT
 * (margin 0 — no .docx, `_p()` sem override usa space_after=0: parágrafos de
 * um mesmo item ficam colados, só a entrelinha 1,15 separa). `solto` é para
 * os itens 6–8 (glossário/definição da técnica/considerações), onde o .docx
 * intercala uma linha em branco (estilo SemEspaçamento, ~4,2mm) entre CADA
 * parágrafo — bem mais espaçado que 1–5. */
function CP({ children, ml = "10mm", solto = false }: { children: ReactNode; ml?: string; solto?: boolean }) {
  return <p style={{ margin: 0, marginBottom: solto ? "4.2mm" : 0, marginLeft: ml, textAlign: "justify" }}>{children}</p>;
}
/* Linha em branco entre itens (só onde 2+ itens dividem a mesma Folha —
 * hoje só a Folha 1, itens 1–4): no .docx é um `_blank()` explícito entre
 * cada item, ~8,5mm (10pt de space-after herdado + a própria entrelinha). */
function CBlank() {
  return <div aria-hidden style={{ height: "8.5mm" }} />;
}

/* ------------------------------ Documento --------------------------------- */
export function CartaCorpo({ d }: { d: Dossie }) {
  const cab = d.cabecalho;
  const p = cab.prestador;
  const rangeMedicao =
    cab.data_inicio && cab.data_termino && cab.data_inicio !== cab.data_termino
      ? `${ddmmaaaa(cab.data_inicio)} a ${ddmmaaaa(cab.data_termino)}`
      : ddmmaaaa(cab.data_termino || cab.data_inicio);
  // Definição da Técnica — parágrafos GERADOS dos dados do relatório + texto da técnica.
  const linhasDef = (s?: string) => (s || "").split("\n").map((l) => l.trim()).filter(Boolean);
  const introDef = linhasDef(cab.definicao_tecnica);
  const fluxoDef = linhasDef(cab.definicao_fluxo_trabalho);
  const lista = (arr: string[]) =>
    arr.length <= 1 ? (arr[0] ?? "") : `${arr.slice(0, -1).join(", ")} e ${arr[arr.length - 1]}`;
  const nEquip = d.secao_b.equip_monitorados;
  const nAnom = d.secao_b.anomalias_diagnosticadas;
  const nSetores = new Set(d.secao_c.grupos.map((g) => `${g.area}|${g.setor}`)).size;
  const nAreas = new Set(d.secao_c.grupos.map((g) => g.area)).size;
  const eqTxt = nEquip === 1 ? "1 equipamento" : `${nEquip} equipamentos`;
  const stTxt = nSetores === 1 ? "1 setor" : `${nSetores} setores`;
  const arTxt = nAreas === 1 ? "1 área" : `${nAreas} áreas`;
  const par7a = `Neste relatório aplicou-se a técnica de ${cab.tecnologia}, contemplando ${eqTxt} monitorado(s) em ${stTxt} (${arTxt}), com o auxílio da instrumentação descrita no item 4.`;
  let par7b: string;
  if (nAnom === 0) {
    par7b = "A partir das medições realizadas, não foram diagnosticadas anomalias que ensejassem Ordens de Serviço Preditivas neste ciclo.";
  } else {
    const base = nAnom === 1 ? "foi diagnosticada 1 anomalia" : `foram diagnosticadas ${nAnom} anomalias`;
    const tipos = lista(d.secao_b.anomalias.map((a) => a.rotulo));
    const trechoTipos = tipos ? `, do(s) tipo(s): ${tipos}` : "";
    const dist = d.secao_b.condicoes.map((c) => `${c.rotulo}: ${c.total}`).join("; ");
    const trechoGr = dist ? ` A distribuição por Grau de Risco foi — ${dist}.` : "";
    par7b = `A partir das medições realizadas, ${base}${trechoTipos}. Cada anomalia foi classificada conforme os Graus de Risco descritos no item 6 e convertida em Ordem de Serviço Preditiva na Seção D.${trechoGr}`;
  }
  const paragrafosGerados = [par7a, par7b];

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
        <p style={{ textAlign: "center", fontWeight: 700, margin: "5mm 0" }}>{cab.numero}</p>

        <CItem n="1.">Objetivo do Relatório</CItem>
        <CP>Este relatório técnico tem como objetivo apresentar os resultados das análises técnicas de:</CP>
        <CP>{cab.tecnologia}</CP>
        <CBlank />

        <CItem n="2.">Data(s) da(s) Execução(ões) da(s) Atividade(s)</CItem>
        <CP>Medições em Campo – {rangeMedicao}</CP>
        <CP>Upload das OSP’s – {ddmmaaaa(cab.data_termino)}</CP>
        <CP>Upload Relatório Completo – {ddmmaaaa(cab.data_finalizacao)}</CP>
        <CBlank />

        <CItem n="3.">Conteúdo do Relatório</CItem>
        {CONTEUDO_CARTA.map((t) => <CP key={t}>{t}</CP>)}
        <CBlank />

        <CItem n="4.">Instrumentação Utilizada</CItem>
        {cab.instrumentos.length ? cab.instrumentos.map((i, k) => (
          <div key={k} style={{ marginLeft: "22.5mm", marginBottom: "2mm" }}>
            {i.tipo && <p style={{ margin: 0 }}>{i.tipo}</p>}
            {i.marca && <p style={{ margin: 0 }}>Marca: {i.marca}</p>}
            {i.modelo && <p style={{ margin: 0 }}>Modelo: {i.modelo}</p>}
            {i.numero_serie && <p style={{ margin: 0 }}>Serial #: {i.numero_serie}</p>}
            {i.data_ultima_calibracao && <p style={{ margin: 0 }}>Data da última calibração: {ddmmaaaa(i.data_ultima_calibracao)}</p>}
            {i.periodicidade && <p style={{ margin: 0 }}>Validade: {i.periodicidade}</p>}
            {i.entidade_calibracao && <p style={{ margin: 0 }}>Entidade Calibração: {i.entidade_calibracao}</p>}
            {i.software_analise && <><p style={{ margin: "2mm 0 0 0" }}>Softwares de Análises</p><p style={{ margin: 0 }}>{i.software_analise}</p></>}
          </div>
        )) : <CP ml="22.5mm">Não informada.</CP>}
      </Folha>

      {/* ---- Folha 2: item 5 (Normatização + tabela ISO) ---- */}
      <Folha p={p}>
        <CItem n="5.">Normatização</CItem>
        {cab.normas.length ? cab.normas.map((n, k) => (
          <CP key={k}>{[n.codigo, n.nome].filter(Boolean).join(" - ")}</CP>
        )) : <CP>Não informada.</CP>}
        <TabelaISO10816 />
      </Folha>

      {/* ---- Folha 3: item 6 (Glossário) ---- */}
      <Folha p={p}>
        <CItem n="6." gap="4.2mm">Glossário Técnico</CItem>
        {GLOSSARIO_CARTA.map((g) => (
          <CP key={g.n} solto><b>{g.n}. {g.sigla}</b> – {g.texto}</CP>
        ))}
      </Folha>

      {/* ---- Folha 4: item 7 (Definição da Técnica) ---- */}
      <Folha p={p}>
        <CItem n="7." gap="4.2mm">Definição da Técnica</CItem>
        {/* Parágrafos gerados a partir dos dados do relatório (banco) */}
        {paragrafosGerados.map((t, k) => <CP key={`g${k}`} solto>{t}</CP>)}
        {/* Descrição fixa da técnica (cadastro da tecnologia), quando houver */}
        {introDef.map((t, k) => <CP key={`i${k}`} solto>{t}</CP>)}
        {fluxoDef.map((t, k) => <CP key={`f${k}`} solto>{t}</CP>)}
      </Folha>

      {/* ---- Folha 5: item 8 (Considerações) + assinatura ---- */}
      <Folha p={p}>
        <CItem n="8." gap="4.2mm">Considerações Importantes</CItem>
        {CONSIDERACOES_CARTA.map((t, k) => <CP key={k} solto>{t}</CP>)}
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
