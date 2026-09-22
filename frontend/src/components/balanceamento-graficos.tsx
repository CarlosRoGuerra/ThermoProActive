"use client";

/**
 * Gráficos do balanceamento dinâmico — SVG/HTML inline, sem biblioteca (Cláusula 12.4).
 *
 * Os mesmos componentes servem a tela de campo e a impressão do relatório, por isso
 * todo rótulo é desenhado (nada depende de hover) e as cores vêm de tokens do tema.
 *
 * Duas mudanças deliberadas em relação à planilha de origem:
 *
 *  1. No mostrador, as agulhas aparecem. Na planilha os três vetores existem mas não
 *     são visíveis — sobra o anel colorido e um texto solto com o ângulo. Aqui cada
 *     corrida é uma agulha com comprimento proporcional à vibração, então a
 *     convergência reference → trial → trim se lê no próprio mostrador.
 *  2. O gráfico antes/depois tem UM eixo. A planilha plota mm/s à esquerda e % à
 *     direita — duas escalas para o mesmo dado, que só parecem curvas diferentes
 *     porque os eixos não batem. Aqui é mm/s, e a redução em % é rótulo.
 *
 * A paleta (--viz-reference/trial/trim) foi validada para daltonismo e contraste nos
 * temas claro e escuro. Cada corrida também tem marcador próprio (círculo, losango,
 * triângulo), então a identidade nunca depende só da cor.
 */

import type { ReactNode } from "react";

const SERIES = [
  { chave: "reference", rotulo: "Reference (antes)", cor: "var(--viz-reference)" },
  { chave: "trial", rotulo: "Trial (teste)", cor: "var(--viz-trial)" },
  { chave: "trim", rotulo: "Trim (depois)", cor: "var(--viz-trim)" },
] as const;

/** Corrida do balanceamento — `reference`, `trial` ou `trim`. */
export type SerieCorrida = (typeof SERIES)[number]["chave"];

type Corrida = { mms: number; fase: number | null } | null;

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

/** Amplitude que vira raio 1 no mostrador — a maior vibração entre todos os pontos. */
export function amplitudeMaxima(pontos: PontoGrafico[]): number {
  const valores = pontos.flatMap((p) =>
    [p.reference, p.trial, p.trim].filter(Boolean).map((c) => c!.mms)
  );
  return valores.length ? Math.max(...valores) : 0;
}

/* ===================== Mostrador polar ===================== */

const R = 100; // raio do mostrador, em unidades do viewBox

/**
 * Mesma convenção da planilha (abas `Graf-O`): 0° à direita, sentido anti-horário.
 * O y do SVG cresce para baixo, daí o sinal invertido.
 */
function ponta(fase: number, amplitude: number, maxima: number) {
  const angulo = (fase / 360) * 2 * Math.PI;
  const raio = maxima > 0 ? Math.min(amplitude / maxima, 1) * R : R;
  return { x: Math.cos(angulo) * raio, y: -Math.sin(angulo) * raio };
}

function Marcador({ tipo, x, y, cor }: { tipo: string; x: number; y: number; cor: string }) {
  // Anel na cor da superfície separa agulhas que se cruzam.
  const comum = { fill: cor, stroke: "var(--surface)", strokeWidth: 2 };
  if (tipo === "reference") return <circle cx={x} cy={y} r={6} {...comum} />;
  if (tipo === "trial")
    return <rect x={x - 5} y={y - 5} width={10} height={10} transform={`rotate(45 ${x} ${y})`} {...comum} />;
  return <polygon points={`${x},${y - 6.5} ${x + 6},${y + 4} ${x - 6},${y + 4}`} {...comum} />;
}

/**
 * Mostrador de fase de UM ponto — as corridas (reference/trial/trim) como agulhas no
 * mesmo mostrador polar, quando têm fase medida. Corrida sem fase (comum em pontos
 * antigos, de quando a fase não era coletada) simplesmente não desenha agulha — o
 * ponto ainda aparece no Antes×Depois, só não neste mostrador.
 *
 * `series` limita as corridas desenhadas. A tela de campo omite a propriedade e vê as
 * três (é assim que se acompanha a convergência); o relatório final pede só o trim,
 * porque o resultado que ficou na máquina é o do Trim Run — mostrar o Trial ali seria
 * publicar o ângulo do ensaio como se fosse o da correção.
 */
export function MostradorPolar({
  ponto,
  tamanho = 280,
  series,
  mensagemVazia,
}: {
  ponto: PontoGrafico;
  /** Lado do SVG. Aceita medida CSS ("46mm") para caber no slot impresso. */
  tamanho?: number | string;
  series?: readonly SerieCorrida[];
  /** Texto quando nenhuma corrida visível tem fase — nunca cair em outra corrida. */
  mensagemVazia?: ReactNode;
}) {
  const visiveis = series ? SERIES.filter((s) => series.includes(s.chave)) : SERIES;
  const corridas = visiveis.map((s) => ({ ...s, dado: ponto[s.chave] })).filter(
    (c) => c.dado && c.dado.fase != null
  );
  // Escala LOCAL a este ponto e às corridas VISÍVEIS. Com as três à vista (tela de
  // campo) isso é a amplitude do ponto, como sempre foi: elas precisam ser
  // comparáveis entre si, e normalizar contra a amplitude de OUTRO ponto do serviço
  // distorceria o raio. Com uma corrida só (o trim, no relatório final) a agulha
  // ocupa o raio inteiro — ali o que se lê é o ÂNGULO da correção; a amplitude está
  // escrita na legenda e desenhada no antes/depois. Sem isso o trim, que por
  // definição é o menor valor, viraria um ponto colado no centro.
  const soVisivel = (chave: SerieCorrida) =>
    visiveis.some((s) => s.chave === chave) ? ponto[chave] : null;
  const maxima = amplitudeMaxima([
    {
      ...ponto,
      reference: soVisivel("reference"),
      trial: soVisivel("trial"),
      trim: soVisivel("trim"),
    },
  ]);

  if (!corridas.length) {
    return (
      <p className="text-sm text-fg-muted">
        {mensagemVazia ?? (
          <>
            Sem fase medida em nenhuma corrida deste ponto — lance a fase no Reference,
            Trial ou Trim Run para o mostrador aparecer.
          </>
        )}
      </p>
    );
  }

  return (
    <figure className="m-0">
      <svg
        viewBox="-150 -150 300 300"
        width={tamanho}
        height={tamanho}
        role="img"
        aria-label={`Mostrador de fase do ponto ${ponto.codigo_ponto}`}
        className="max-w-full"
      >
        {/* Graduação de 30° — a marcação do mostrador, não um dado. Neutra de
            propósito: colorir os 12 setores competiria com as agulhas, que são o
            que se precisa ler. */}
        {Array.from({ length: 12 }, (_, i) => {
          const g = (i * 30 * Math.PI) / 180;
          const eixo = i % 3 === 0;
          return (
            <line
              key={i}
              x1={Math.cos(g) * (R - (eixo ? 14 : 8))}
              y1={-Math.sin(g) * (R - (eixo ? 14 : 8))}
              x2={Math.cos(g) * R}
              y2={-Math.sin(g) * R}
              stroke="var(--border-strong)"
              strokeWidth={eixo ? 2 : 1}
            />
          );
        })}
        <circle cx={0} cy={0} r={R} fill="none" stroke="var(--border)" strokeWidth={2} />
        <line x1={-R} y1={0} x2={R} y2={0} stroke="var(--border)" strokeWidth={1} strokeDasharray="4 4" />
        <line x1={0} y1={-R} x2={0} y2={R} stroke="var(--border)" strokeWidth={1} strokeDasharray="4 4" />
        {/* Ponto de origem ANTES das corridas: um balanceamento bem-sucedido deixa o
            Trim com raio pequeno (perto do centro, por definição — é o resultado
            esperado); desenhar a origem depois esconderia esse marcador embaixo dela. */}
        <circle cx={0} cy={0} r={3} fill="var(--fg-subtle)" />

        {[
          { t: "0°", x: R + 20, y: 4 },
          { t: "90°", x: 0, y: -R - 12 },
          { t: "180°", x: -R - 22, y: 4 },
          { t: "270°", x: 0, y: R + 22 },
        ].map((l) => (
          <text
            key={l.t}
            x={l.x}
            y={l.y}
            textAnchor="middle"
            className="fill-[var(--fg-subtle)] text-[11px]"
          >
            {l.t}
          </text>
        ))}

        {corridas.map((c) => {
          const p = ponta(c.dado!.fase!, c.dado!.mms, maxima);
          return (
            <g key={c.chave}>
              <title>{`${c.rotulo}: ${num(c.dado!.mms)} mm/s a ${num(c.dado!.fase!, 1)}°`}</title>
              <line x1={0} y1={0} x2={p.x} y2={p.y} stroke={c.cor} strokeWidth={2} />
              <Marcador tipo={c.chave} x={p.x} y={p.y} cor={c.cor} />
            </g>
          );
        })}
      </svg>

      <figcaption className="mt-2 space-y-1">
        {corridas.map((c) => (
          <div key={c.chave} className="flex items-center gap-2 text-xs text-fg-muted">
            <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: c.cor }} />
            <span className="text-fg-subtle">{c.rotulo}</span>
            <span className="ml-auto tabular-nums text-fg">
              {num(c.dado!.mms)} mm/s · {num(c.dado!.fase!, 1)}°
            </span>
          </div>
        ))}
      </figcaption>
    </figure>
  );
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
