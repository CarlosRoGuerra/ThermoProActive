import type { Cabecalho, GrupoC, LinhaC, SecaoC } from "../tipos";
import { PaginaInterna } from "./folhas";

/* Relação de Equipamentos Monitorados (Seção C) — por Área → Setor, 1 linha por
   item da rota com a condição do equipamento. Igual para qualquer tecnologia.

   A lista é repartida em folhas A4 AQUI, e não pelo navegador: uma rota de
   termografia elétrica passa de 300 painéis e a folha que transbordava continuava
   nas páginas seguintes sem o papel timbrado. Como cada linha tem altura fixa, dá
   para saber quantas cabem; o setor que não cabe inteiro continua na folha seguinte,
   repetindo Área, Setor e o cabeçalho da tabela. */

/* Alturas em mm — as mesmas usadas no desenho abaixo. */
const TOPO_MM = 34.9;                 // onde o conteúdo começa (PaginaInterna)
const UTIL_MM = 297 - TOPO_MM - 10 - 3; // folha − topo − margem inferior − folga
const EMPRESA_MM = 5;
const GRUPO_MM = 4 + 5 + 5 + 2 + 6.5; // respiro + Área + Setor + respiro + cabeçalho da tabela
const LINHA_MM = 5;
/* Nome que passa disto quebra em duas linhas na coluna de 138 mm a 9 pt. */
const CARACTERES_POR_LINHA = 78;

const alturaLinha = (l: LinhaC) => LINHA_MM * Math.max(1, Math.ceil((l.equipamento || "").length / CARACTERES_POR_LINHA));

type Trecho = { grupo: GrupoC; linhas: LinhaC[]; continuacao: boolean; zebraInicial: number };

/** Reparte os grupos em folhas; um grupo só começa numa folha se couberem ao menos 2 linhas dele. */
export function paginarEquipamentos(grupos: GrupoC[]): Trecho[][] {
  const folhas: Trecho[][] = [[]];
  let livre = UTIL_MM - EMPRESA_MM;
  const novaFolha = () => { folhas.push([]); livre = UTIL_MM; };
  for (const grupo of grupos) {
    let inicio = 0;
    let continuacao = false;
    do {
      const minimo = GRUPO_MM + grupo.linhas.slice(inicio, inicio + 2).reduce((s, l) => s + alturaLinha(l), 0);
      if (livre < minimo && folhas[folhas.length - 1].length > 0) novaFolha();
      livre -= GRUPO_MM;
      let fim = inicio;
      while (fim < grupo.linhas.length && alturaLinha(grupo.linhas[fim]) <= livre) {
        livre -= alturaLinha(grupo.linhas[fim]);
        fim += 1;
      }
      if (fim === inicio && inicio < grupo.linhas.length) fim = inicio + 1; // linha mais alta que a folha: vai assim mesmo
      folhas[folhas.length - 1].push({ grupo, linhas: grupo.linhas.slice(inicio, fim), continuacao, zebraInicial: inicio });
      inicio = fim;
      continuacao = true;
      if (inicio < grupo.linhas.length) novaFolha();
    } while (inicio < grupo.linhas.length);
  }
  return folhas;
}

function TabelaGrupo({ t, mostraTotal, total }: { t: Trecho; mostraTotal: boolean; total: number }) {
  const g = t.grupo;
  return (
    <div style={{ marginTop: "4mm", fontSize: "9pt" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <p style={{ height: "5mm", lineHeight: "5mm" }}><span style={{ fontWeight: 700 }}>Área:</span> {g.area}</p>
          <p style={{ height: "5mm", lineHeight: "5mm" }}>
            <span style={{ fontWeight: 700 }}>Setor:</span> {g.setor}{t.continuacao ? " (continuação)" : ""}
          </p>
        </div>
        {mostraTotal && <p style={{ lineHeight: "5mm" }}><span style={{ fontWeight: 700 }}>Total de equipamentos:</span> {total}</p>}
      </div>
      <table style={{ width: "190mm", borderCollapse: "collapse", marginTop: "2mm", fontSize: "9pt", tableLayout: "fixed" }}>
        <thead>
          <tr style={{ borderBottom: "0.3mm solid #94a3b8", textAlign: "left", height: "6.2mm" }}>
            <th style={{ width: "30mm", fontWeight: 700, paddingBottom: "1mm" }}>TAG</th>
            <th style={{ fontWeight: 700, paddingBottom: "1mm" }}>Equipamento</th>
            <th style={{ width: "22mm", fontWeight: 700, textAlign: "right", paddingBottom: "1mm" }}>Condição</th>
          </tr>
        </thead>
        <tbody>
          {t.linhas.map((l, li) => (
            <tr key={li} style={{ background: (t.zebraInicial + li) % 2 === 0 ? "#eff6ff" : "#fff", lineHeight: `${LINHA_MM}mm` }}>
              <td style={{ fontFamily: "monospace", padding: 0, whiteSpace: "nowrap", overflow: "hidden" }}>{l.tag || "—"}</td>
              <td style={{ padding: 0 }}>{l.equipamento}</td>
              <td style={{ textAlign: "right", padding: 0, fontWeight: 400, whiteSpace: "nowrap" }}>{l.condicao}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function SecaoEquipamentos({ cab, c }: { cab: Cabecalho; c: SecaoC }) {
  if (c.grupos.length === 0) {
    return (
      <PaginaInterna cab={cab} conteudoTopMm={TOPO_MM}>
        <p style={{ fontSize: "9pt" }}><span style={{ fontWeight: 700 }}>Empresa:</span> {cab.empresa}</p>
        <p style={{ fontSize: "9pt", textAlign: "center", padding: "12mm 0", color: "#64748b" }}>Nenhum equipamento inspecionado.</p>
      </PaginaInterna>
    );
  }
  return (
    <>
      {paginarEquipamentos(c.grupos).map((trechos, f) => (
        <PaginaInterna key={f} cab={cab} conteudoTopMm={TOPO_MM} evitarQuebra>
          {f === 0 && (
            <p style={{ fontSize: "9pt", height: `${EMPRESA_MM}mm`, lineHeight: `${EMPRESA_MM}mm` }}>
              <span style={{ fontWeight: 700 }}>Empresa:</span> {cab.empresa}
            </p>
          )}
          {trechos.map((t, ti) => (
            <TabelaGrupo key={ti} t={t} mostraTotal={f === 0 && ti === 0} total={c.equip_monitorados} />
          ))}
        </PaginaInterna>
      ))}
    </>
  );
}
