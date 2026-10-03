import type { ReactNode } from "react";
import type { Dist, DossieFluido, GrauSigla } from "../../tipos";
import { PaginaInterna } from "../../shell/folhas";
import { CATEGORICAS_KPI, CINZA_KPI, comCoresCategoricas, GraficoDistribuicao, STATUS_KPI } from "../../shell/kpis";

/* ============================================================================
   Gráficos gerenciais da análise de fluidos (Seção B, como no relatório-modelo
   do laboratório): status das condições, dos componentes e das anomalias, graus
   de risco ao longo do tempo, equipamentos × anomalias e controle das O.S.P.

   Skill dataviz: um eixo por gráfico; a cor de cada grau de risco acompanha o
   rótulo em tinta (legenda + tabela logo abaixo), então a identidade nunca é só
   a cor — o amarelo do GR-3 tem contraste baixo (1,79:1) e o alívio é esse rótulo
   e a tabela. Colunas finas, 2px de respiro entre os segmentos, grade discreta.
   ========================================================================== */

const COR_GRAU: Record<string, string> = {
  "GR-1": STATUS_KPI.critical,
  "GR-2": STATUS_KPI.serious,
  "GR-3": STATUS_KPI.warning,
  "GR-4": CATEGORICAS_KPI[0],
  "GR-0": STATUS_KPI.good,
  OK: STATUS_KPI.good,
};
const ROTULO_GRAU: Record<GrauSigla, string> = { "GR-0": "OK", "GR-1": "GR-1", "GR-2": "GR-2", "GR-3": "GR-3", "GR-4": "GR-4" };
const GRADE = "#e4e2dc";
const BASE = "#b9b7b0";
const TXT = { primaria: "#0b0b0b", secundaria: "#52514e", suave: "#898781" };
const FONTE = '"Segoe UI", system-ui, -apple-system, Roboto, Arial, sans-serif';

type Serie = { rotulo: string; cor: string; valores: number[] };

function Titulo({ children }: { children: ReactNode }) {
  return <h3 className="mb-2 text-sm font-bold text-slate-800">{children}</h3>;
}

function Legenda({ series }: { series: { rotulo: string; cor: string }[] }) {
  return (
    <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1">
      {series.map((s) => (
        <div key={s.rotulo} className="flex items-center gap-1.5 text-[10px]">
          <span className="h-2 w-2 shrink-0 rounded-sm" style={{ background: s.cor }} />
          <span className="font-medium text-slate-700">{s.rotulo}</span>
        </div>
      ))}
    </div>
  );
}

/** Tabela dos valores (a mesma da planilha do modelo): linhas = séries, colunas = categorias. */
function TabelaValores({ categorias, series }: { categorias: string[]; series: Serie[] }) {
  const th = "px-2 py-1 text-[10px] font-semibold text-slate-500 text-right";
  const td = "px-2 py-1 text-right tabular-nums text-xs text-slate-800";
  return (
    <table className="mt-2 w-full border-collapse">
      <thead>
        <tr className="border-b border-slate-300">
          <th className={`${th} text-left`} />
          {categorias.map((c) => <th key={c} className={th}>{c}</th>)}
        </tr>
      </thead>
      <tbody>
        {series.map((s) => (
          <tr key={s.rotulo} className="border-b border-slate-100">
            <td className="px-2 py-1 text-xs font-medium text-slate-800">{s.rotulo}</td>
            {s.valores.map((v, i) => <td key={i} className={td}>{v || "—"}</td>)}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

const passoEixo = (max: number) => (max <= 5 ? 1 : max <= 10 ? 2 : max <= 25 ? 5 : max <= 50 ? 10 : 20);

/** Colunas (empilhadas ou agrupadas) sobre um único eixo de contagem inteira. */
function Colunas({
  categorias, series, empilhada, altura = 46,
}: { categorias: string[]; series: Serie[]; empilhada: boolean; altura?: number }) {
  const W = 190;
  const x0 = 9;
  const yTopo = 4;
  const yBase = altura - 8;
  const totais = categorias.map((_, i) =>
    empilhada ? series.reduce((s, x) => s + x.valores[i], 0) : Math.max(...series.map((x) => x.valores[i])));
  const passo = passoEixo(Math.max(1, ...totais));
  const max = Math.max(passo, Math.ceil(Math.max(1, ...totais) / passo) * passo);
  const y = (v: number) => yBase - (v / max) * (yBase - yTopo);
  const larguraCat = (W - x0 - 2) / categorias.length;
  const largura = Math.min(empilhada ? 16 : 11, larguraCat * 0.6);
  const ticks = Array.from({ length: max / passo + 1 }, (_, i) => i * passo);
  const fonte = 2.6;
  return (
    <svg viewBox={`0 0 ${W} ${altura}`} width="100%" style={{ display: "block", fontFamily: FONTE }} role="img">
      {ticks.map((t) => (
        <g key={t}>
          <line x1={x0} x2={W - 2} y1={y(t)} y2={y(t)} stroke={t === 0 ? BASE : GRADE} strokeWidth={t === 0 ? 0.3 : 0.2} />
          <text x={x0 - 1.5} y={y(t) + fonte * 0.35} fontSize={fonte} textAnchor="end" fill={TXT.suave}>{t}</text>
        </g>
      ))}
      {categorias.map((c, i) => {
        const centro = x0 + larguraCat * (i + 0.5);
        const barras: ReactNode[] = [];
        if (empilhada) {
          let acumulado = 0;
          series.forEach((s) => {
            const v = s.valores[i];
            if (!v) return;
            const alto = y(acumulado) - y(acumulado + v);
            barras.push(
              <g key={s.rotulo}>
                <rect x={centro - largura / 2} y={y(acumulado + v)} width={largura} height={Math.max(0.4, alto - 0.5)} fill={s.cor} />
                {alto >= 4 && (
                  <text x={centro} y={y(acumulado + v) + alto / 2 + fonte * 0.35} fontSize={fonte} textAnchor="middle" fill="#0b0b0b">{v}</text>
                )}
              </g>,
            );
            acumulado += v;
          });
        } else {
          const n = series.length;
          series.forEach((s, k) => {
            const v = s.valores[i];
            const xk = centro - (largura * n) / 2 + k * largura + 0.5;
            barras.push(
              <g key={s.rotulo}>
                <rect x={xk} y={y(v)} width={largura - 1} height={Math.max(0.4, yBase - y(v))} fill={s.cor} />
                <text x={xk + (largura - 1) / 2} y={y(v) - 1} fontSize={fonte} textAnchor="middle" fill={TXT.primaria}>{v}</text>
              </g>,
            );
          });
        }
        return (
          <g key={c}>
            {barras}
            <text x={centro} y={yBase + 4.6} fontSize={fonte} textAnchor="middle" fill={TXT.secundaria}>{c}</text>
          </g>
        );
      })}
    </svg>
  );
}

const comCorDoGrau = (itens: Dist[]) =>
  itens.map((s) => ({ ...s, cor: COR_GRAU[s.rotulo] ?? CINZA_KPI }));

/** Pré-requisito: GR em ordem de gravidade — a pilha cresce do mais grave para o menos grave. */
const ORDEM_GRAU: GrauSigla[] = ["GR-1", "GR-2", "GR-3", "GR-4", "GR-0"];

function Painel({ children }: { children: ReactNode }) {
  return <section className="mb-6 break-inside-avoid">{children}</section>;
}

export function KpisGerenciaisFluidos({ d }: { d: DossieFluido }) {
  const g = d.graficos;
  const cab = d.cabecalho;
  const temEvolucao = g.graus_tempo.meses.length > 0;
  const grausSeries: Serie[] = ORDEM_GRAU.map((gr) => {
    const s = g.graus_tempo.series.find((x) => x.gr === gr);
    return { rotulo: ROTULO_GRAU[gr], cor: COR_GRAU[gr], valores: s?.valores ?? g.graus_tempo.meses.map(() => 0) };
  }).filter((s) => s.valores.some((v) => v > 0));
  const ea = g.equipamentos_anomalias;
  const eaSeries: Serie[] = [
    { rotulo: "Equipamentos monitorados", cor: CATEGORICAS_KPI[0], valores: ea.monitorados },
    { rotulo: "Anomalias diagnosticadas", cor: STATUS_KPI.critical, valores: ea.anomalias },
  ];
  const ospSeries: Serie[] = ORDEM_GRAU.filter((gr) => gr !== "GR-0")
    .map((gr) => ({ rotulo: gr, cor: COR_GRAU[gr], valores: g.osp.linhas.find((l) => l.gr === gr)?.valores ?? [] }))
    .filter((s) => s.valores.some((v) => v > 0));
  const temOsp = ospSeries.length > 0;

  return (
    <>
      <PaginaInterna cab={cab}>
        <div className="space-y-6 text-slate-800">
          <Painel>
            <GraficoDistribuicao titulo="Status das Condições (Grau de Risco)" segmentos={comCorDoGrau(g.condicoes)} />
            <p className="mt-2 text-[10px] leading-snug text-slate-500">
              O grau de risco de cada equipamento sai do número de ensaios (FQ, EF e CP) com parâmetro fora das
              referências cadastradas: 1 ensaio = GR-4, 2 = GR-3, mais de 2 = GR-2. O GR-1 é o das anomalias vistas
              a olho nu, marcado como condição na folha de campo. Ensaio sem referência não conta.
            </p>
          </Painel>
          <Painel>
            <GraficoDistribuicao titulo="Status dos Componentes" segmentos={comCoresCategoricas(g.componentes)} />
          </Painel>
          <Painel>
            <GraficoDistribuicao
              titulo="Status das Anomalias (parâmetros fora da referência)"
              segmentos={g.anomalias.length ? comCoresCategoricas(g.anomalias) : []}
            />
            {!g.anomalias.length && <p className="text-xs text-slate-400">Nenhum parâmetro fora das referências neste ciclo.</p>}
          </Painel>
          {temEvolucao && (
            <Painel>
              <Titulo>Equipamentos Inspecionados × Anomalias Diagnosticadas</Titulo>
              <Colunas categorias={ea.meses} series={eaSeries} empilhada={false} />
              <Legenda series={eaSeries} />
              <TabelaValores categorias={ea.meses} series={eaSeries} />
            </Painel>
          )}
        </div>
      </PaginaInterna>

      <PaginaInterna cab={cab}>
        <div className="space-y-6 text-slate-800">
          {temEvolucao && grausSeries.length > 0 && (
            <Painel>
              <Titulo>Status dos Graus de Risco</Titulo>
              <Colunas categorias={g.graus_tempo.meses} series={grausSeries} empilhada />
              <Legenda series={grausSeries} />
              <TabelaValores categorias={g.graus_tempo.meses} series={grausSeries} />
            </Painel>
          )}
          <Painel>
            <Titulo>Controle das O.S.P.&apos;s</Titulo>
            {temOsp ? (
              <>
                <Colunas categorias={g.osp.colunas} series={ospSeries} empilhada />
                <Legenda series={ospSeries} />
                <TabelaValores categorias={g.osp.colunas} series={ospSeries} />
                <p className="mt-2 text-[10px] leading-snug text-slate-500">
                  Comparação com a coleta anterior do mesmo equipamento. <b>Aberta</b>: anomalia nova;{" "}
                  <b>Corrigida</b>: tinha anomalia e voltou ao normal; <b>Reincidente</b>: a anomalia continua;{" "}
                  <b>Não reavaliada</b>: tinha anomalia e não foi avaliada neste ciclo.
                </p>
              </>
            ) : (
              <p className="text-xs text-slate-400">Nenhuma O.S.P. neste ciclo.</p>
            )}
          </Painel>
        </div>
      </PaginaInterna>
    </>
  );
}
