import type { ReactNode } from "react";

/* ---------------------- Primitivas dos KPIs (Seção B) ----------------------
   Comuns a qualquer tecnologia: o módulo decide QUAIS indicadores mostrar; o
   desenho de cada um sai daqui. Skill dataviz — paleta validada (script
   validate_palette.js), não "a olho". Só para os gráficos da Seção B: a folha
   da OSP (badge de GR) está TRAVADA dimensionalmente por pedido do cliente. */
export const STATUS_KPI = { critical: "#d03b3b", serious: "#ec835a", warning: "#fab219", good: "#0ca30c" };
export const CINZA_KPI = "#898781";
export const CATEGORICAS_KPI = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"];

export type ItemDistribuicao = { rotulo: string; total: number; percentual: number };
export type Segmento = ItemDistribuicao & { cor: string };

/** Séries categóricas (identidade, não severidade): até 6 cores fixas da paleta;
 * o resto dobra em "Outros" cinza — nunca gera uma 9ª cor (teto da escada de séries). */
export function comCoresCategoricas(itens: ItemDistribuicao[], max = 6): Segmento[] {
  const principais = itens.slice(0, max).map((it, i) => ({ ...it, cor: CATEGORICAS_KPI[i % CATEGORICAS_KPI.length] }));
  const resto = itens.slice(max);
  if (!resto.length) return principais;
  const total = resto.reduce((s, r) => s + r.total, 0);
  const percentual = Math.round(resto.reduce((s, r) => s + r.percentual, 0) * 10) / 10;
  return [...principais, { rotulo: "Outros", total, percentual, cor: CINZA_KPI }];
}

/** Barra empilhada horizontal (parte-do-todo) — marca ≤24px, gap de 2px entre
 * segmentos (a cor da página faz a separação, nunca uma borda), rótulo interno
 * só quando cabe (≥8%); o resto fica só na legenda, nunca cortado. */
function BarraEmpilhada({ segmentos }: { segmentos: Segmento[] }) {
  const visiveis = segmentos.filter((s) => s.percentual > 0);
  if (!visiveis.length) return <p className="text-xs text-slate-400">Sem dados.</p>;
  return (
    <div className="flex h-6 w-full gap-0.5 overflow-hidden rounded-md">
      {visiveis.map((s, i) => (
        <div
          key={i}
          title={`${s.rotulo}: ${s.total} (${s.percentual}%)`}
          style={{ width: `${s.percentual}%`, background: s.cor }}
          className="flex min-w-[2px] items-center justify-center"
        >
          {s.percentual >= 8 && <span className="truncate px-1 text-[9px] font-semibold text-white">{s.percentual}%</span>}
        </div>
      ))}
    </div>
  );
}

/** Legenda — sempre presente p/ 2+ séries; identidade nunca só na cor (texto usa
 * tokens de tinta, nunca a cor da série). */
function LegendaKPI({ segmentos }: { segmentos: Segmento[] }) {
  return (
    <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1">
      {segmentos.map((s, i) => (
        <div key={i} className="flex items-center gap-1.5 text-[10px]">
          <span className="h-2 w-2 shrink-0 rounded-sm" style={{ background: s.cor }} />
          <span className="font-medium text-slate-700">{s.rotulo}</span>
          <span className="text-slate-400">{s.total} · {s.percentual}%</span>
        </div>
      ))}
    </div>
  );
}

export function GraficoDistribuicao({ titulo, segmentos }: { titulo: string; segmentos: Segmento[] }) {
  return (
    <div>
      <h3 className="mb-2 text-sm font-bold text-slate-800">{titulo}</h3>
      <BarraEmpilhada segmentos={segmentos} />
      <LegendaKPI segmentos={segmentos} />
    </div>
  );
}

/** Cartão de indicador único — valor em destaque (figuras proporcionais, não
 * tabulares — reservadas a colunas), rótulo em caixa normal sem dois-pontos. */
export function StatTile({ valor, rotulo, cor = "#0b0b0b" }: { valor: ReactNode; rotulo: string; cor?: string }) {
  return (
    <div className="min-w-[34mm] flex-1 rounded-lg border border-slate-200 bg-white px-4 py-3">
      <p className="text-2xl font-semibold leading-tight" style={{ color: cor }}>{valor}</p>
      <p className="mt-0.5 text-[10px] text-slate-500">{rotulo}</p>
    </div>
  );
}

/** Medidor (valor único vs. limite) — trilho é um degrau mais claro da MESMA
 * rampa do preenchimento (azul sequencial), nunca uma pizza de 2 fatias. */
export function Medidor({ valor, meta }: { valor: number; meta?: number }) {
  const pct = Math.min(100, Math.max(0, valor));
  return (
    <div className="relative h-3 w-full overflow-hidden rounded-full" style={{ background: "#cde2fb" }}>
      <div className="h-full rounded-full transition-[width]" style={{ width: `${pct}%`, background: "#2a78d6" }} />
      {meta != null && (
        <div className="absolute top-[-2px] bottom-[-2px] w-[2px]" style={{ left: `${Math.min(100, meta)}%`, background: "#52514e" }} />
      )}
    </div>
  );
}
