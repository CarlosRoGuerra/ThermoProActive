import type { Cabecalho, SecaoC } from "../tipos";
import { PaginaInterna } from "./folhas";

/* Relação de Equipamentos Monitorados (Seção C) — por Área → Setor, 1 linha por
   item da rota com a condição do equipamento. Igual para qualquer tecnologia. */
export function SecaoEquipamentos({ cab, c }: { cab: Cabecalho; c: SecaoC }) {
  return (
    <PaginaInterna cab={cab} conteudoTopMm={34.9}>
      <p style={{ fontSize: "9pt" }}><span style={{ fontWeight: 700 }}>Empresa:</span> {cab.empresa}</p>
      {c.grupos.length === 0 ? (
        <p style={{ fontSize: "9pt", textAlign: "center", padding: "12mm 0", color: "#64748b" }}>Nenhum equipamento inspecionado.</p>
      ) : (
        c.grupos.map((g, gi) => (
          <div key={gi} style={{ marginTop: "4mm", fontSize: "9pt" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
              <div>
                <p><span style={{ fontWeight: 700 }}>Área:</span> {g.area}</p>
                <p><span style={{ fontWeight: 700 }}>Setor:</span> {g.setor}</p>
              </div>
              {gi === 0 && <p><span style={{ fontWeight: 700 }}>Total de equipamentos:</span> {c.equip_monitorados}</p>}
            </div>
            <table style={{ width: "190mm", borderCollapse: "collapse", marginTop: "2mm", fontSize: "9pt", tableLayout: "fixed" }}>
              <thead>
                <tr style={{ borderBottom: "0.3mm solid #94a3b8", textAlign: "left" }}>
                  <th style={{ width: "30mm", fontWeight: 700, paddingBottom: "1mm" }}>TAG</th>
                  <th style={{ fontWeight: 700, paddingBottom: "1mm" }}>Equipamento</th>
                  <th style={{ width: "22mm", fontWeight: 700, textAlign: "right", paddingBottom: "1mm" }}>Condição</th>
                </tr>
              </thead>
              <tbody>
                {g.linhas.map((l, li) => {
                  return (
                    <tr key={li} style={{ background: li % 2 === 0 ? "#eff6ff" : "#fff" }}>
                      <td style={{ fontFamily: "monospace", padding: "0.6mm 0" }}>{l.tag || "—"}</td>
                      <td style={{ padding: "0.6mm 0" }}>{l.equipamento}</td>
                      <td style={{ textAlign: "right", padding: "0.6mm 0", fontWeight: 400 }}>{l.condicao}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ))
      )}
    </PaginaInterna>
  );
}
