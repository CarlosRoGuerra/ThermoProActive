import type { OspD } from "../tipos";
import { LINHA_MEDICAO, criarModuloInspecao, type QuadroImagem } from "./inspecao/modulo";

/* Vibração: amplitudes globais na OSP, quadros Tendência/Espectro e a tabela de
   severidade ISO‑10816 no item 5 da carta. */

export function AmplitudesVibracao({ o }: { o: OspD }) {
  return (
    <>
      <div style={{ ...LINHA_MEDICAO, fontWeight: 700 }}>Amplitudes [valor global]</div>
      <div style={LINHA_MEDICAO}><span style={{ fontWeight: 700 }}>Aceleração [g&rsquo;s]:</span> {o.amplitude_aceleracao ?? "—"}</div>
      <div style={LINHA_MEDICAO}><span style={{ fontWeight: 700 }}>Velocidade [mm/s]:</span> {o.amplitude_velocidade ?? "—"}</div>
    </>
  );
}

export const QUADROS_VIBRACAO: QuadroImagem[] = [
  { tipo: "Linha de tendência", rotulo: "Tendência" },
  { tipo: "Espectro", rotulo: "Espectro" },
];

/* ------------------------- Tabela ISO-10816-1 ----------------------------- */
const ISO_VEL: [number, number][] = [
  [0.28, 0.02], [0.45, 0.03], [0.71, 0.04], [1.12, 0.06], [1.80, 0.10], [2.80, 0.16],
  [4.50, 0.25], [7.10, 0.40], [11.20, 0.62], [18.00, 1.00], [28.00, 1.56], [45.00, 2.51],
];
/* Limites Bom|Satisfatório|Alerta por classe. Classe II = 4,49 mm/s (confirmado
   com o cliente — commit 2ab0ce0), o mesmo do cálculo e da carta .docx. */
const ISO_ZONAS: Record<string, [number, number, number]> = {
  I: [0.71, 1.80, 4.50], II: [1.12, 4.49, 7.10], III: [1.80, 4.50, 11.20], IV: [2.80, 7.10, 18.00],
};
function sevISO(v: number, cls: string) {
  const z = ISO_ZONAS[cls];
  if (v <= z[0]) return { txt: "Bom", bg: "#22c55e", fg: "#fff" };
  if (v <= z[1]) return { txt: "Satisfatório", bg: "#a3e635", fg: "#1f2937" };
  if (v <= z[2]) return { txt: "Alerta", bg: "#f59e0b", fg: "#1f2937" };
  return { txt: "Perigo", bg: "#ef4444", fg: "#fff" };
}

export function TabelaISO10816() {
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

export const MODULO_VIBRACAO = criarModuloInspecao({
  chave: "VIBRACAO",
  Medicoes: AmplitudesVibracao,
  quadros: QUADROS_VIBRACAO,
  Normatizacao: TabelaISO10816,
});
