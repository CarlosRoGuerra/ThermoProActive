"use client";

/**
 * Gráficos interativos dos painéis (Anexo I 2.8.1.3.1). SVG próprio e leve, sem lib nova.
 *
 * Em todos eles:
 * - ao passar o mouse ou focar com o teclado, aparece o tooltip com valor e percentual;
 * - a legenda liga e desliga cada série (ao menos uma fica visível);
 * - clicar (ou Enter/Espaço, com o foco no item) chama `onSelecionar` ou navega para `destino`.
 *
 * Os números NÃO são calculados aqui: quem chama passa os valores que vêm de
 * `relatorios/indicadores.py`. A única conta do componente é o percentual da própria
 * exibição (valor ÷ total visível), para leitura.
 */

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { cn } from "@/components/ds";

export type Serie = { chave: string; rotulo: string; cor: string };
export type Categoria = { chave: string; rotulo: string; valores: Record<string, number> };
export type Fatia = { chave: string; rotulo: string; valor: number; cor: string; destino?: string };

const fmtPadrao = (v: number) => v.toLocaleString("pt-BR");
const pct = (parte: number, total: number) =>
  total > 0 ? `${Math.round((parte / total) * 100)}%` : "—";

function Legenda({
  itens,
  ocultas,
  alternar,
}: {
  itens: { chave: string; rotulo: string; cor: string }[];
  ocultas: Set<string>;
  alternar: (chave: string) => void;
}) {
  const visiveis = itens.length - ocultas.size;
  return (
    <ul className="mb-3 flex flex-wrap gap-2 text-xs" aria-label="Legenda do gráfico">
      {itens.map((i) => {
        const oculta = ocultas.has(i.chave);
        const unica = !oculta && visiveis <= 1;
        return (
          <li key={i.chave}>
            <button
              type="button"
              aria-pressed={!oculta}
              disabled={unica}
              title={unica ? "Ao menos uma série precisa ficar visível" : undefined}
              onClick={() => alternar(i.chave)}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full border border-border px-2.5 py-1 text-fg transition-opacity focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:cursor-not-allowed",
                oculta && "opacity-45 line-through"
              )}
            >
              <span className="h-2.5 w-2.5 rounded-sm" style={{ background: i.cor }} aria-hidden="true" />
              {i.rotulo}
            </button>
          </li>
        );
      })}
    </ul>
  );
}

/* ================================ Barras agrupadas ================================ */

export function GraficoBarras({
  categorias,
  series,
  descricao,
  formatarValor = fmtPadrao,
  onSelecionar,
  altura = 176,
}: {
  categorias: Categoria[];
  series: Serie[];
  /** Texto do gráfico para leitor de tela (o que ele mostra e como ler). */
  descricao: string;
  formatarValor?: (v: number) => string;
  onSelecionar?: (categoria: Categoria, serie: Serie) => void;
  altura?: number;
}) {
  const [ocultas, setOcultas] = useState<Set<string>>(new Set());
  const [ativo, setAtivo] = useState<{ cat: Categoria; serie: Serie } | null>(null);
  const visiveis = useMemo(() => series.filter((s) => !ocultas.has(s.chave)), [series, ocultas]);

  const yMax = Math.max(1, ...categorias.flatMap((c) => visiveis.map((s) => c.valores[s.chave] ?? 0)));
  const W = 600;
  const H = altura;
  const topo = 8;
  const base = H - 24;
  const plotH = base - topo;
  const larguraGrupo = W / Math.max(1, categorias.length);
  const larguraBarra = Math.min(28, (larguraGrupo * 0.7) / Math.max(1, visiveis.length));

  function alternar(chave: string) {
    setOcultas((atual) => {
      const nova = new Set(atual);
      if (nova.has(chave)) nova.delete(chave);
      else if (series.length - nova.size > 1) nova.add(chave);
      return nova;
    });
  }

  return (
    <div>
      <Legenda itens={series} ocultas={ocultas} alternar={alternar} />
      <div className="relative">
        <svg viewBox={`0 0 ${W} ${H}`} className="h-44 w-full" role="group" aria-label={descricao}>
          <line x1={0} x2={W} y1={base} y2={base} stroke="var(--border)" />
          {categorias.map((cat, i) => {
            const x0 = i * larguraGrupo + (larguraGrupo - larguraBarra * visiveis.length) / 2;
            return (
              <g key={cat.chave}>
                {visiveis.map((s, j) => {
                  const valor = cat.valores[s.chave] ?? 0;
                  const altBarra = (valor / yMax) * plotH;
                  const x = x0 + j * larguraBarra;
                  const clicavel = !!onSelecionar;
                  const foco = ativo?.cat.chave === cat.chave && ativo?.serie.chave === s.chave;
                  return (
                    <g
                      key={s.chave}
                      role={clicavel ? "button" : "img"}
                      tabIndex={clicavel ? 0 : -1}
                      aria-label={`${cat.rotulo}, ${s.rotulo}: ${formatarValor(valor)}`}
                      className={cn("focus:outline-none", clicavel && "cursor-pointer")}
                      onMouseEnter={() => setAtivo({ cat, serie: s })}
                      onMouseLeave={() => setAtivo(null)}
                      onFocus={() => setAtivo({ cat, serie: s })}
                      onBlur={() => setAtivo(null)}
                      onClick={() => onSelecionar?.(cat, s)}
                      onKeyDown={(e) => {
                        if (clicavel && (e.key === "Enter" || e.key === " ")) {
                          e.preventDefault();
                          onSelecionar?.(cat, s);
                        }
                      }}
                    >
                      <rect
                        x={x}
                        y={base - altBarra}
                        width={larguraBarra - 3}
                        height={Math.max(altBarra, valor > 0 ? 1 : 0)}
                        rx={3}
                        fill={s.cor}
                        opacity={foco ? 1 : 0.85}
                        stroke={foco ? "var(--fg)" : undefined}
                        strokeWidth={foco ? 1.5 : 0}
                      />
                    </g>
                  );
                })}
                <text x={i * larguraGrupo + larguraGrupo / 2} y={H - 6} textAnchor="middle" fontSize={11} fill="var(--fg-subtle)">
                  {cat.rotulo}
                </text>
              </g>
            );
          })}
        </svg>
        {ativo && (
          <Tooltip
            titulo={`${ativo.cat.rotulo} · ${ativo.serie.rotulo}`}
            linhas={[
              `${formatarValor(ativo.cat.valores[ativo.serie.chave] ?? 0)}`,
              `${pct(
                ativo.cat.valores[ativo.serie.chave] ?? 0,
                visiveis.reduce((t, s) => t + (ativo.cat.valores[s.chave] ?? 0), 0)
              )} do total visível deste mês`,
            ]}
            posicaoX={((categorias.findIndex((c) => c.chave === ativo.cat.chave) + 0.5) / Math.max(1, categorias.length)) * 100}
          />
        )}
      </div>
      <TabelaTextual
        linhas={categorias.map((c) => ({
          rotulo: c.rotulo,
          valores: visiveis.map((s) => `${s.rotulo} ${formatarValor(c.valores[s.chave] ?? 0)}`).join(" · "),
        }))}
      />
    </div>
  );
}

/* ================================== Rosca ================================== */

export function GraficoRosca({
  fatias,
  descricao,
  centro,
  formatarValor = fmtPadrao,
  onSelecionar,
}: {
  fatias: Fatia[];
  descricao: string;
  centro?: { valor: string; rotulo: string };
  formatarValor?: (v: number) => string;
  onSelecionar?: (fatia: Fatia) => void;
}) {
  const [ocultas, setOcultas] = useState<Set<string>>(new Set());
  const [ativa, setAtiva] = useState<string | null>(null);
  const router = useRouter();
  const visiveis = fatias.filter((f) => !ocultas.has(f.chave) && f.valor > 0);
  const total = visiveis.reduce((t, f) => t + f.valor, 0);
  const legenda = fatias.map((f) => ({ chave: f.chave, rotulo: f.rotulo, cor: f.cor }));

  function alternar(chave: string) {
    setOcultas((atual) => {
      const nova = new Set(atual);
      if (nova.has(chave)) nova.delete(chave);
      else if (fatias.length - nova.size > 1) nova.add(chave);
      return nova;
    });
  }

  const R = 70;
  const r = 44;
  let angulo = -Math.PI / 2;
  const arcos = visiveis.map((f) => {
    const sweep = (f.valor / total) * Math.PI * 2;
    const inicio = angulo;
    angulo += sweep;
    return { fatia: f, inicio, fim: angulo, sweep };
  });

  function caminho(inicio: number, fim: number, sweep: number) {
    if (sweep >= Math.PI * 2 - 1e-6) {
      return `M ${R} 0 A ${R} ${R} 0 1 1 ${-R} 0 A ${R} ${R} 0 1 1 ${R} 0 Z M ${r} 0 A ${r} ${r} 0 1 0 ${-r} 0 A ${r} ${r} 0 1 0 ${r} 0 Z`;
    }
    const grande = sweep > Math.PI ? 1 : 0;
    const p = (raio: number, a: number) => [raio * Math.cos(a), raio * Math.sin(a)];
    const [x1, y1] = p(R, inicio);
    const [x2, y2] = p(R, fim);
    const [x3, y3] = p(r, fim);
    const [x4, y4] = p(r, inicio);
    return `M ${x1} ${y1} A ${R} ${R} 0 ${grande} 1 ${x2} ${y2} L ${x3} ${y3} A ${r} ${r} 0 ${grande} 0 ${x4} ${y4} Z`;
  }

  const ativaFatia = visiveis.find((f) => f.chave === ativa);

  return (
    <div>
      <Legenda itens={legenda} ocultas={ocultas} alternar={alternar} />
      <div className="flex flex-col items-center gap-4 sm:flex-row sm:items-center">
        <div className="relative shrink-0">
          <svg viewBox="-80 -80 160 160" className="h-44 w-44" role="group" aria-label={descricao}>
            {total === 0 ? (
              <circle r={R} cx={0} cy={0} fill="none" stroke="var(--border)" strokeWidth={R - r} />
            ) : (
              arcos.map(({ fatia, inicio, fim, sweep }) => {
                const clicavel = !!(onSelecionar || fatia.destino);
                return (
                  <path
                    key={fatia.chave}
                    d={caminho(inicio, fim, sweep)}
                    fill={fatia.cor}
                    opacity={ativa === null || ativa === fatia.chave ? 1 : 0.55}
                    role={clicavel ? "button" : "img"}
                    tabIndex={clicavel ? 0 : -1}
                    aria-label={`${fatia.rotulo}: ${formatarValor(fatia.valor)} (${pct(fatia.valor, total)})`}
                    className={cn("focus:outline-none", clicavel && "cursor-pointer")}
                    onMouseEnter={() => setAtiva(fatia.chave)}
                    onMouseLeave={() => setAtiva(null)}
                    onFocus={() => setAtiva(fatia.chave)}
                    onBlur={() => setAtiva(null)}
                    onClick={() => (onSelecionar ? onSelecionar(fatia) : fatia.destino && router.push(fatia.destino))}
                    onKeyDown={(e) => {
                      if (clicavel && (e.key === "Enter" || e.key === " ")) {
                        e.preventDefault();
                        if (onSelecionar) onSelecionar(fatia);
                        else if (fatia.destino) router.push(fatia.destino);
                      }
                    }}
                  />
                );
              })
            )}
          </svg>
          {centro && (
            <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center text-center">
              <span className="data text-lg font-semibold text-fg">{centro.valor}</span>
              <span className="text-2xs text-fg-subtle">{centro.rotulo}</span>
            </div>
          )}
          {ativaFatia && (
            <Tooltip
              titulo={ativaFatia.rotulo}
              linhas={[
                formatarValor(ativaFatia.valor),
                `${pct(ativaFatia.valor, total)} do total visível`,
                ...(ativaFatia.destino || onSelecionar ? ["Clique para ver a lista"] : []),
              ]}
              posicaoX={50}
              acima
            />
          )}
        </div>
        <ul className="w-full min-w-0 flex-1 space-y-1.5 text-sm">
          {fatias.map((f) => {
            const oculta = ocultas.has(f.chave);
            return (
              <li key={f.chave} className={cn("flex items-baseline justify-between gap-3", oculta && "opacity-45")}>
                <span className="text-fg-muted">{f.rotulo}</span>
                <span className="data font-semibold text-fg">
                  {formatarValor(f.valor)}
                  <span className="ml-1.5 text-xs font-normal text-fg-subtle">
                    {oculta ? "oculto" : pct(f.valor, total)}
                  </span>
                </span>
              </li>
            );
          })}
        </ul>
      </div>
      <TabelaTextual linhas={fatias.map((f) => ({ rotulo: f.rotulo, valores: formatarValor(f.valor) }))} />
      {/* Atalhos de navegação para quem usa só o teclado (o gráfico já é focável; isto deixa explícito). */}
      {fatias.some((f) => f.destino) && (
        <p className="mt-3 text-xs text-fg-subtle">
          {fatias
            .filter((f) => f.destino)
            .map((f, i) => (
              <span key={f.chave}>
                {i > 0 && " · "}
                <Link href={f.destino!} className="text-primary underline-offset-2 hover:underline">
                  ver {f.rotulo.toLowerCase()}
                </Link>
              </span>
            ))}
        </p>
      )}
    </div>
  );
}

/* ================================ Apoio ================================ */

function Tooltip({
  titulo,
  linhas,
  posicaoX,
  acima = false,
}: {
  titulo: string;
  linhas: string[];
  posicaoX: number;
  acima?: boolean;
}) {
  return (
    <div
      role="status"
      className={cn(
        "pointer-events-none absolute z-10 min-w-40 -translate-x-1/2 rounded-md border border-border bg-surface px-3 py-2 text-xs shadow-md",
        acima ? "left-1/2 -top-2 -translate-y-full" : "-top-2 -translate-y-full"
      )}
      style={acima ? undefined : { left: `${posicaoX}%` }}
    >
      <p className="font-semibold text-fg">{titulo}</p>
      {linhas.map((l) => (
        <p key={l} className="text-fg-muted">{l}</p>
      ))}
    </div>
  );
}

/** Alternativa textual: o mesmo dado em lista, para leitor de tela e para impressão. */
function TabelaTextual({ linhas }: { linhas: { rotulo: string; valores: string }[] }) {
  return (
    <ul className="sr-only">
      {linhas.map((l) => (
        <li key={l.rotulo}>
          {l.rotulo}: {l.valores}
        </li>
      ))}
    </ul>
  );
}
