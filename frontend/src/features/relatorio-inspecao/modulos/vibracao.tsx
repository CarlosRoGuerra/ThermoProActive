import type { DossieShell, LinhaSeveridade, OspD } from "../tipos";
import { LINHA_MEDICAO, criarModuloInspecao, type QuadroImagem } from "./inspecao/modulo";

/* Vibração: amplitudes globais na OSP, quadros Tendência/Espectro e a tabela de
   severidade no item 5 da carta. As zonas de cada classe vêm do critério vigente
   na data do relatório (perfil normativo, no payload `carta.tabela_severidade`);
   limite que não é o da norma — o B/C de 4,49 mm/s da Classe II — sai com nota. */

export function AmplitudesVibracao({ o }: { o: OspD }) {
  return (
    <>
      <div style={{ ...LINHA_MEDICAO, fontWeight: 700 }}>Amplitudes [valor global]</div>
      <div style={LINHA_MEDICAO}><span style={{ fontWeight: 700 }}>Aceleração [g&rsquo;s]:</span> {o.amplitude_aceleracao ?? "—"}</div>
      <div style={LINHA_MEDICAO}><span style={{ fontWeight: 700 }}>Velocidade [mm/s]:</span> {o.amplitude_velocidade ?? "—"}</div>
      {o.amplitude_deslocamento != null && (
        <div style={LINHA_MEDICAO}><span style={{ fontWeight: 700 }}>Deslocamento [µm]:</span> {o.amplitude_deslocamento}</div>
      )}
    </>
  );
}

export const QUADROS_VIBRACAO: QuadroImagem[] = [
  { tipo: "Linha de tendência", rotulo: "Tendência" },
  { tipo: "Espectro", rotulo: "Espectro" },
];

/* ---------------- Tabela de severidade (ISO 10816-1 / ISO 20816-3) ----------------
   Desde 07/10/2026: Classe I (até 15 kW), Grupo 2 (15 a 300 kW) e Grupo 1 (acima de
   300 kW). As classes II–IV aparecem só nos relatórios até 06/10/2026. */
const ISO_VEL: [number, number][] = [
  [0.28, 0.02], [0.45, 0.03], [0.71, 0.04], [1.12, 0.06], [1.80, 0.10], [2.80, 0.16],
  [4.50, 0.25], [7.10, 0.40], [11.20, 0.62], [18.00, 1.00], [28.00, 1.56], [45.00, 2.51],
];
const CABECALHO: Record<string, [string, string]> = {
  I: ["Classe I", "< 15 kW"], G2: ["Grupo 2", "15 a 300 kW"], G1: ["Grupo 1", "> 300 kW"],
  II: ["Classe II", "15 a 75 kW"], III: ["Classe III", "Rígida · > 75 kW"], IV: ["Classe IV", "Flexível · > 75 kW"],
};
const ORDEM_CLASSES = ["I", "G2", "G1", "II", "III", "IV"];
const BASE: Record<string, string> = { RIGIDO: "Base rígida", FLEXIVEL: "Base flexível" };
const ORDEM_SUPORTE: Record<string, number> = { "": 0, RIGIDO: 1, FLEXIVEL: 2 };

type Coluna = { chave: string; titulo: string; sub: string; c: LinhaSeveridade };
/** Uma coluna por grupo e, nos grupos da ISO 20816-3, por tipo de base (rígida/flexível). */
function colunasSeveridade(linhas: LinhaSeveridade[]): Coluna[] {
  return [...linhas]
    .sort((a, b) => ORDEM_CLASSES.indexOf(a.classe) - ORDEM_CLASSES.indexOf(b.classe)
      || (ORDEM_SUPORTE[a.suporte ?? ""] ?? 9) - (ORDEM_SUPORTE[b.suporte ?? ""] ?? 9))
    .map((c) => {
      const [titulo, sub] = CABECALHO[c.classe] ?? [c.rotulo, ""];
      return { chave: `${c.classe}|${c.suporte ?? ""}`, titulo, sub: c.suporte ? `${BASE[c.suporte]} · ${sub}` : sub, c };
    });
}
const faixaDesloc = (d: { ab: string; bc: string; cd: string }, z: number) => {
  const l = [d.ab, d.bc, d.cd].map((v) => Number(v).toLocaleString("pt-BR"));
  return z === 0 ? `< ${l[0]}` : z === 3 ? `> ${l[2]}` : `${l[z - 1]} – ${l[z]}`;
};
const ZONAS_DESLOC: { nome: string; bg: string; fg: string }[] = [
  { nome: "A — Bom", bg: "#22c55e", fg: "#fff" }, { nome: "B — Satisfatório", bg: "#a3e635", fg: "#1f2937" },
  { nome: "C — Alerta", bg: "#f59e0b", fg: "#1f2937" }, { nome: "D — Perigo", bg: "#ef4444", fg: "#fff" },
];

/** Escala fixa da ISO + os limites dos grupos da ISO 20816-3 que não estão nela (senão uma zona some). */
function gradeSeveridade(linhas: LinhaSeveridade[]): [number, number][] {
  const fixos = new Set(ISO_VEL.map(([mm]) => mm));
  const extras = new Set<number>();
  for (const c of linhas) {
    if (c.classe !== "G1" && c.classe !== "G2") continue;
    for (const v of [c.limites.ab, c.limites.bc, c.limites.cd]) if (!fixos.has(Number(v))) extras.add(Number(v));
  }
  return [...ISO_VEL, ...[...extras].map((mm) => [mm, Math.round((mm * Math.SQRT2 / 25.4) * 100) / 100] as [number, number])]
    .sort((a, b) => a[0] - b[0]);
}

function sevISO(v: number, z: [number, number, number]) {
  if (v <= z[0]) return { txt: "Bom", bg: "#22c55e", fg: "#fff" };
  if (v <= z[1]) return { txt: "Satisfatório", bg: "#a3e635", fg: "#1f2937" };
  if (v <= z[2]) return { txt: "Alerta", bg: "#f59e0b", fg: "#1f2937" };
  return { txt: "Perigo", bg: "#ef4444", fg: "#fff" };
}

export function TabelaISO10816({ d }: { d: DossieShell }) {
  const linhas: LinhaSeveridade[] = d.carta.tabela_severidade ?? [];
  if (!linhas.length) return null;
  const colunas = colunasSeveridade(linhas);
  const zona = (c: LinhaSeveridade) => [Number(c.limites.ab), Number(c.limites.bc), Number(c.limites.cd)] as [number, number, number];
  const classes = colunas.map((col) => col.c.classe);
  const comDesloc = colunas.filter((col) => col.c.deslocamento);
  const norma = [...new Set(linhas.map((c) => c.norma.replace(/ /g, "-")))].join(" / ") || "ISO-10816-1";
  const termo = classes.some((cl) => cl.startsWith("G")) ? "Grupos" : "Classes";
  const th = { border: "0.2mm solid #94a3b8", padding: "1mm", textAlign: "center" as const, fontWeight: 700, background: "#f1f5f9" };
  const td = { border: "0.2mm solid #94a3b8", padding: "0.8mm", textAlign: "center" as const };
  return (
    <>
      <table style={{ width: "170mm", margin: "3mm auto", borderCollapse: "collapse", fontSize: "8.5pt", tableLayout: "fixed", breakInside: "avoid" }}>
        <thead>
          <tr><th colSpan={2 + colunas.length} style={{ ...th, color: "#c00", fontSize: "11pt", background: "#fff" }}>Norma {norma} — Severidade · Faixas de Velocidade e {termo} de Máquina</th></tr>
          <tr>
            <th style={th}>V [mm/s]<br />RMS</th>
            <th style={th}>V [in/s]<br />Pico</th>
            {colunas.map((col) => (
              <th key={col.chave} style={th}>{col.titulo}<br /><span style={{ fontWeight: 400 }}>{col.sub}</span></th>
            ))}
          </tr>
        </thead>
        <tbody>
          {gradeSeveridade(linhas).map(([mm, pol]) => (
            <tr key={mm}>
              <td style={{ ...td, fontWeight: 700 }}>{mm.toFixed(2)}</td>
              <td style={{ ...td, fontWeight: 700 }}>{pol.toFixed(2)}</td>
              {colunas.map((col) => {
                const s = sevISO(mm, zona(col.c));
                return <td key={col.chave} style={{ ...td, background: s.bg, color: s.fg }}>{s.txt}</td>;
              })}
            </tr>
          ))}
        </tbody>
      </table>
      {comDesloc.length > 0 && (
        <table style={{ width: "170mm", margin: "3mm auto", borderCollapse: "collapse", fontSize: "8.5pt", tableLayout: "fixed", breakInside: "avoid" }}>
          <thead>
            <tr><th colSpan={1 + comDesloc.length} style={{ ...th, color: "#c00", fontSize: "11pt", background: "#fff" }}>Deslocamento [µm] RMS — Limites de Zona</th></tr>
            <tr>
              <th style={th}>Zona</th>
              {comDesloc.map((col) => (
                <th key={col.chave} style={th}>{col.titulo}<br /><span style={{ fontWeight: 400 }}>{col.sub}</span></th>
              ))}
            </tr>
          </thead>
          <tbody>
            {ZONAS_DESLOC.map((z, i) => (
              <tr key={z.nome}>
                <td style={{ ...td, fontWeight: 700, background: z.bg, color: z.fg }}>{z.nome}</td>
                {comDesloc.map((col) => <td key={col.chave} style={{ ...td, fontWeight: 700 }}>{faixaDesloc(col.c.deslocamento!, i)}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {(d.carta.notas_severidade ?? []).map((nota) => (
        <p key={nota} style={{ width: "170mm", margin: "1mm auto 0", fontSize: "7.5pt", fontStyle: "italic", textAlign: "justify" }}>
          {nota}
        </p>
      ))}
    </>
  );
}

export const MODULO_VIBRACAO = criarModuloInspecao({
  chave: "VIBRACAO",
  Medicoes: AmplitudesVibracao,
  quadros: QUADROS_VIBRACAO,
  Normatizacao: TabelaISO10816,
});

/* Balanceamento: o veredito de cada ponto é a zona de severidade de vibração, por
   isso a carta mantém a tabela; a folha da OSP é a corretiva do balanceamento.
   Mesmo layout de antes, agora declarado (antes era o "padrão"). */
export const MODULO_BALANCEAMENTO = criarModuloInspecao({
  chave: "BALANCEAMENTO",
  Medicoes: AmplitudesVibracao,
  quadros: QUADROS_VIBRACAO,
  Normatizacao: TabelaISO10816,
});
