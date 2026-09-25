import type { DossieInspecao } from "../../tipos";

/* Item 7 da Carta ao Cliente na inspeção por rota. Os textos fixos da carta
   (seções, glossário, considerações) vêm do backend no payload (`d.carta`). */

const lista = (arr: string[]) =>
  arr.length <= 1 ? (arr[0] ?? "") : `${arr.slice(0, -1).join(", ")} e ${arr[arr.length - 1]}`;

/** Item 7: anomalias diagnosticadas neste relatório, por tipo e por Grau de Risco. */
export function paragrafoAnomalias(d: DossieInspecao): string {
  const nAnom = d.secao_b.anomalias_diagnosticadas;
  if (nAnom === 0) {
    return "A partir das medições realizadas, não foram diagnosticadas anomalias que ensejassem Ordens de Serviço Preditivas neste ciclo.";
  }
  const base = nAnom === 1 ? "foi diagnosticada 1 anomalia" : `foram diagnosticadas ${nAnom} anomalias`;
  const tipos = lista(d.secao_b.anomalias.map((a) => a.rotulo));
  const trechoTipos = tipos ? `, do(s) tipo(s): ${tipos}` : "";
  const dist = d.secao_b.condicoes.map((c) => `${c.rotulo}: ${c.total}`).join("; ");
  const trechoGr = dist ? ` A distribuição por Grau de Risco foi — ${dist}.` : "";
  return `A partir das medições realizadas, ${base}${trechoTipos}. Cada anomalia foi classificada conforme os Graus de Risco descritos no item 6 e convertida em Ordem de Serviço Preditiva na Seção D.${trechoGr}`;
}
