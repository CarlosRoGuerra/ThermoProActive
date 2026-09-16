"use client";

/**
 * Gráficos do balanceamento dinâmico — SVG/HTML inline, sem biblioteca (Cláusula 12.4).
 *
 * Os mesmos componentes servem a tela de campo e a impressão do relatório, por isso
 * todo rótulo é desenhado (nada depende de hover) e as cores vêm de tokens do tema.
 *
 * A fase deixou de ser coletada em Reference/Trial/Trim (pedido do cliente,
 * 2026-09-16) — o mostrador polar que existia aqui foi aposentado (ele só fazia
 * sentido com 3 vetores de ângulo variável; sem fase não sobra o que desenhar). O que
 * resta é puramente amplitude, então o gráfico de referência passa a ser o
 * Antes×Depois — agora com o Trial como um terceiro ponto no mesmo eixo, cobrindo a
 * mesma leitura de "convergiu?" sem fingir ter uma dimensão de dado que não existe.
 *
 * A paleta (--viz-reference/trial/trim) foi validada para daltonismo e contraste nos
 * temas claro e escuro.
 */

type Corrida = { mms: number } | null;

export interface PontoGrafico {
  codigo_ponto: string;
  reference: Corrida;
  trial: Corrida;
  trim: Corrida;
  reducao_pct: number | null;
  zona_iso?: string;
  completo?: boolean;
}

const num = (v: number, casas = 2) =>
  v.toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });

/** Maior amplitude entre reference/trial/trim dos pontos informados. */
export function amplitudeMaxima(pontos: PontoGrafico[]): number {
  const valores = pontos.flatMap((p) =>
    [p.reference, p.trial, p.trim].filter(Boolean).map((c) => c!.mms)
  );
  return valores.length ? Math.max(...valores) : 0;
}

/* ===================== Antes × Depois ===================== */

/**
 * Um eixo só (mm/s). Cada ponto é uma barra-haltere do reference ao trim (com o trial
 * marcado no meio do trajeto, quando existir); a redução em % é rótulo direto, não um
 * segundo eixo.
 */
export function AntesDepois({ pontos }: { pontos: PontoGrafico[] }) {
  const completos = pontos.filter((p) => p.reference && p.trim);
  if (!completos.length) {
    return (
      <p className="text-sm text-fg-muted">
        O gráfico aparece quando algum ponto tiver o trim run medido.
      </p>
    );
  }

  const maxima = amplitudeMaxima(completos);
  const escala = (v: number) => (maxima > 0 ? (v / maxima) * 100 : 0); // % da largura

  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => ({ f, valor: maxima * f }));

  return (
    <figure className="m-0">
      <div className="space-y-4">
        {completos.map((p) => {
          const x1 = escala(p.trim!.mms);
          const x0 = escala(p.reference!.mms);
          const xTrial = p.trial ? escala(p.trial.mms) : null;
          const todos = [x0, x1, ...(xTrial != null ? [xTrial] : [])];
          const [menor, maior] = [Math.min(...todos), Math.max(...todos)];
          return (
            <div key={p.codigo_ponto}>
              <div className="mb-1 flex flex-wrap items-baseline justify-between gap-x-2 gap-y-0.5 text-xs">
                <span className="font-medium text-fg">Mancal {p.codigo_ponto}</span>
                <span className="tabular-nums text-fg-muted">
                  {num(p.reference!.mms)}
                  {p.trial && ` → ${num(p.trial.mms)}`} → {num(p.trim!.mms)} mm/s
                  {p.reducao_pct != null && (
                    <span className="ml-2 font-semibold text-[var(--viz-trim)]">
                      −{num(p.reducao_pct, 1)}%
                    </span>
                  )}
                </span>
              </div>
              <div className="relative h-5">
                <div className="absolute inset-x-0 top-1/2 h-px -translate-y-1/2 bg-border" />
                <div
                  className="absolute top-1/2 h-[3px] -translate-y-1/2 rounded-full"
                  style={{
                    left: `${menor}%`,
                    width: `${maior - menor}%`,
                    background: "var(--border-strong)",
                  }}
                />
                <span
                  className="absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full ring-2 ring-[var(--surface)]"
                  style={{ left: `${x0}%`, background: "var(--viz-reference)" }}
                  title={`Reference: ${num(p.reference!.mms)} mm/s`}
                />
                {xTrial != null && (
                  <span
                    className="absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full ring-2 ring-[var(--surface)]"
                    style={{ left: `${xTrial}%`, background: "var(--viz-trial)" }}
                    title={`Trial: ${num(p.trial!.mms)} mm/s`}
                  />
                )}
                <span
                  className="absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full ring-2 ring-[var(--surface)]"
                  style={{ left: `${x1}%`, background: "var(--viz-trim)" }}
                  title={`Trim: ${num(p.trim!.mms)} mm/s`}
                />
              </div>
            </div>
          );
        })}
      </div>

      <div className="relative mt-1 h-5 border-t border-border">
        {ticks.map((t) => (
          <span
            key={t.f}
            className="absolute top-1 -translate-x-1/2 text-[10px] tabular-nums text-fg-subtle"
            style={{ left: `${t.f * 100}%` }}
          >
            {num(t.valor, 1)}
          </span>
        ))}
      </div>

      <figcaption className="mt-4 flex flex-wrap items-center gap-4 text-xs text-fg-muted">
        <span className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full" style={{ background: "var(--viz-reference)" }} />
          Reference (antes)
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full" style={{ background: "var(--viz-trial)" }} />
          Trial (teste)
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full" style={{ background: "var(--viz-trim)" }} />
          Trim (depois)
        </span>
        <span className="ml-auto text-fg-subtle">Velocidade em mm/s</span>
      </figcaption>
    </figure>
  );
}
