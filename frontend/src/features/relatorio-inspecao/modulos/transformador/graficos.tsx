import type { ReactNode } from "react";
import type { BarraReferencia, SerieIsolacao } from "../../tipos";
import { CATEGORICAS_KPI, STATUS_KPI } from "../../shell/kpis";
import { numero } from "./formato";

/* ============================================================================
   Gráficos das fichas de transformador, desenhados a partir dos valores do
   payload (nunca imagem colada). Skill dataviz: um eixo só, marcas finas, grade
   discreta, texto em tinta — a cor fica nas marcas — e legenda sempre que há 2+
   séries. Paleta: slots 1–3 da paleta categórica (validate_palette.js, light,
   todos os pares: PASS; o aqua fica abaixo de 3:1 no fundo — alívio: cada curva
   tem título próprio e os valores estão na tabela logo acima).

   Diferença deliberada para o relatório de referência: lá o gráfico de FQ/2-FAL
   tem dois eixos (máximos à esquerda, mínimos à direita). Os dois medem a mesma
   coisa — % da referência —, então aqui é um eixo só e as duas referências caem
   na mesma linha de 100%.
   ========================================================================== */

const COR_MAXIMO = CATEGORICAS_KPI[0];
const COR_MINIMO = CATEGORICAS_KPI[1];
const CORES_SERIES = CATEGORICAS_KPI.slice(0, 3);
const GRADE = "#e4e2dc";
const BASE = "#b9b7b0";
const TXT = { primaria: "#0b0b0b", secundaria: "#52514e", suave: "#898781" };
const FONTE = '"Segoe UI", system-ui, -apple-system, Roboto, Arial, sans-serif';

/** Passo "redondo" (1, 2, 2,5 ou 5 × 10ⁿ) para ~`alvo` intervalos até `maximo`. */
function escala(maximo: number, alvo: number) {
  const bruto = Math.max(maximo, 1e-9) / alvo;
  const mag = 10 ** Math.floor(Math.log10(bruto));
  const passo = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((p) => p >= bruto - 1e-9) ?? 10 * mag;
  const topo = Math.ceil(maximo / passo - 1e-9) * passo;
  const ticks = Array.from({ length: Math.round(topo / passo) + 1 }, (_, i) => i * passo);
  return { topo, ticks };
}

/** Quebra o rótulo em até 3 linhas de ~`max` caracteres. */
function linhas(texto: string, max: number): string[] {
  const saida: string[] = [];
  let atual = "";
  for (const palavra of texto.split(" ")) {
    const tentativa = atual ? `${atual} ${palavra}` : palavra;
    if (tentativa.length > max && atual) {
      saida.push(atual);
      atual = palavra;
    } else atual = tentativa;
  }
  if (atual) saida.push(atual);
  return saida.slice(0, 3);
}

/** Coluna com o canto de dado arredondado e a base reta. */
function coluna(x: number, largura: number, yTopo: number, yBase: number) {
  const r = Math.min(1.06, largura / 2, Math.max(0, yBase - yTopo));
  return `M${x},${yBase} L${x},${yTopo + r} Q${x},${yTopo} ${x + r},${yTopo} L${x + largura - r},${yTopo} `
    + `Q${x + largura},${yTopo} ${x + largura},${yTopo + r} L${x + largura},${yBase} Z`;
}

function Chave({ children, cor, linha = false }: { children: ReactNode; cor: string; linha?: boolean }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: "1.2mm" }}>
      <span style={linha
        ? { width: "4.5mm", height: "0.45mm", background: cor }
        : { width: "2.2mm", height: "2.2mm", background: cor, borderRadius: "0.4mm" }} />
      {children}
    </span>
  );
}

/**
 * Valores da campanha atual em % da referência de cada parâmetro (FQ, CR, PCB,
 * 2-FAL). Máximo: conforme até 100%; mínimo: conforme a partir de 100%.
 * Sem percentual (referência zero ou valor ausente) não há barra.
 */
export function GraficoReferencia({ barras }: { barras: BarraReferencia[] }) {
  const W = 184;
  const H = 52;
  const x0 = 13;
  const x1 = W - 2;
  const yTopo = 3;
  const yBase = H - 12;
  const comValor = barras.filter((b) => b.percentual != null);
  const maior = Math.max(0, ...comValor.map((b) => b.percentual as number));
  const { topo, ticks } = escala(Math.max(120, maior * 1.05), 6);
  const y = (v: number) => yBase - (Math.min(v, topo) / topo) * (yBase - yTopo);
  const banda = (x1 - x0) / Math.max(barras.length, 1);
  const largura = Math.min(6.4, banda * 0.45);
  const fonte = 2.3;
  const porLinha = Math.max(8, Math.floor(banda / (fonte * 0.52)));
  const temMaximo = barras.some((b) => b.tipo_limite === "MAXIMO");
  const temMinimo = barras.some((b) => b.tipo_limite === "MINIMO");

  return (
    <figure style={{ margin: 0 }}>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "5mm", fontSize: "7pt", color: TXT.secundaria, margin: "0.5mm 0 1mm" }}>
        {temMaximo && <Chave cor={COR_MAXIMO}>% da referência máxima (conforme até 100%)</Chave>}
        {temMinimo && <Chave cor={COR_MINIMO}>% da referência mínima (conforme a partir de 100%)</Chave>}
        <Chave cor={TXT.secundaria} linha>Referência (100%)</Chave>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="Valores obtidos em percentual da referência de cada parâmetro"
        style={{ display: "block", fontFamily: FONTE }}>
        {ticks.map((v) => (
          <g key={v}>
            <line x1={x0} x2={x1} y1={y(v)} y2={y(v)} stroke={GRADE} strokeWidth={0.2} />
            <text x={x0 - 1.2} y={y(v) + 0.8} textAnchor="end" fontSize={fonte} fill={TXT.secundaria}
              style={{ fontVariantNumeric: "tabular-nums" }}>{v}</text>
          </g>
        ))}
        <text transform={`translate(3 ${(yTopo + yBase) / 2}) rotate(-90)`} textAnchor="middle" fontSize={fonte} fill={TXT.secundaria}>
          % da referência
        </text>

        {barras.map((b, i) => {
          const centro = x0 + banda * (i + 0.5);
          const pct = b.percentual;
          const minimo = b.tipo_limite === "MINIMO";
          const fora = pct != null && (minimo ? pct < 100 : pct > 100);
          const rotulo = linhas(b.nome, porLinha);
          return (
            <g key={b.codigo}>
              <title>
                {pct == null
                  ? `${b.nome}: sem percentual (referência zero ou valor ausente)`
                  : `${b.nome}: ${numero(pct, 1)}% da referência ${minimo ? "mínima" : "máxima"}${fora ? " — fora da referência" : ""}`}
              </title>
              {/* Área de toque maior que a marca (tooltip). */}
              <rect x={centro - banda / 2} y={yTopo} width={banda} height={yBase - yTopo} fill="transparent" />
              {pct != null && pct > 0 && (
                <path d={coluna(centro - largura / 2, largura, y(pct), yBase)} fill={minimo ? COR_MINIMO : COR_MAXIMO} />
              )}
              {fora && (
                <text x={centro} y={y(pct as number) - 1.2} textAnchor="middle" fontSize={2.8} fontWeight={700} fill={STATUS_KPI.critical}>✕</text>
              )}
              <text x={centro} y={yBase + 3.4} textAnchor="middle" fontSize={fonte} fill={TXT.secundaria}>
                {rotulo.map((l, k) => <tspan key={k} x={centro} dy={k === 0 ? 0 : fonte * 1.2}>{l}</tspan>)}
              </text>
            </g>
          );
        })}

        <line x1={x0} x2={x1} y1={yBase} y2={yBase} stroke={BASE} strokeWidth={0.25} />
        <line x1={x0} x2={x1} y1={y(100)} y2={y(100)} stroke={TXT.secundaria} strokeWidth={0.4} />
        {comValor.length === 0 && (
          <text x={(x0 + x1) / 2} y={(yTopo + yBase) / 2 + 6} textAnchor="middle" fontSize={2.8} fill={TXT.suave}>
            Sem resultado nesta campanha
          </text>
        )}
      </svg>
    </figure>
  );
}

/**
 * Curvas da resistência de isolação (R×I), uma por ligação — pequenos
 * múltiplos, cada um com o próprio eixo (as ligações têm ordens de grandeza
 * diferentes e o que se lê é a forma da curva). Tempos em sequência, como na
 * ficha de referência; marcadores nos 60 s e 600 s (base do IP) e valor no fim.
 */
export function CurvasIsolacao({ series, tempos }: { series: SerieIsolacao[]; tempos: number[] }) {
  if (!series.length || !tempos.length) return null;
  return (
    <div style={{ display: "grid", gridTemplateColumns: `repeat(${series.length}, minmax(0, 1fr))`, gap: "5mm" }}>
      {series.map((s, i) => <CurvaIsolacao key={s.nome} serie={s} tempos={tempos} cor={CORES_SERIES[i % CORES_SERIES.length]} />)}
    </div>
  );
}

function CurvaIsolacao({ serie, tempos, cor }: { serie: SerieIsolacao; tempos: number[]; cor: string }) {
  const W = 58;
  const H = 36;
  const x0 = 9.5;
  const x1 = W - 8;
  const yTopo = 2.5;
  const yBase = H - 8;
  const fonte = 2.1;
  const pontos = tempos.map((t, i) => ({ t, i, v: serie.pontos.find((p) => p.tempo === t)?.valor ?? null }));
  const validos = pontos.filter((p): p is { t: number; i: number; v: number } => p.v != null);
  const { topo, ticks } = escala(Math.max(1, ...validos.map((p) => p.v)), 3);
  const x = (i: number) => x0 + (tempos.length > 1 ? (i / (tempos.length - 1)) * (x1 - x0) : (x1 - x0) / 2);
  const y = (v: number) => yBase - (v / topo) * (yBase - yTopo);

  // Linha interrompida onde falta leitura (ausente não é zero).
  const trechos: string[] = [];
  let atual: string[] = [];
  for (const p of pontos) {
    if (p.v == null) {
      if (atual.length) trechos.push(atual.join(" "));
      atual = [];
    } else atual.push(`${x(p.i)},${y(p.v)}`);
  }
  if (atual.length) trechos.push(atual.join(" "));
  const ultimo = validos[validos.length - 1];
  const destaques = validos.filter((p) => p.t === 60 || p.t === 600);

  return (
    <figure style={{ margin: 0 }}>
      <figcaption style={{ display: "flex", alignItems: "center", gap: "1.5mm", fontSize: "7.5pt", color: TXT.primaria, marginBottom: "0.5mm" }}>
        <span style={{ width: "4.5mm", height: "0.6mm", background: cor, borderRadius: "0.3mm" }} />
        {serie.nome} [MΩ]
      </figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label={`Resistência de isolação ${serie.nome} ao longo do tempo`}
        style={{ display: "block", fontFamily: FONTE }}>
        {ticks.map((v) => (
          <g key={v}>
            <line x1={x0} x2={x1} y1={y(v)} y2={y(v)} stroke={GRADE} strokeWidth={0.2} />
            <text x={x0 - 1} y={y(v) + 0.7} textAnchor="end" fontSize={fonte} fill={TXT.secundaria}
              style={{ fontVariantNumeric: "tabular-nums" }}>{numero(v, 0)}</text>
          </g>
        ))}
        <line x1={x0} x2={x1} y1={yBase} y2={yBase} stroke={BASE} strokeWidth={0.25} />
        {pontos.map((p) => (p.i % 2 === 0 ? (
          <text key={p.t} x={x(p.i)} y={yBase + 3} textAnchor="middle" fontSize={fonte} fill={TXT.secundaria}>{p.t}</text>
        ) : null))}
        <text x={(x0 + x1) / 2} y={H - 0.8} textAnchor="middle" fontSize={fonte} fill={TXT.suave}>Tempo [s]</text>

        {trechos.map((pts, k) => (
          <polyline key={k} points={pts} fill="none" stroke={cor} strokeWidth={0.53} strokeLinejoin="round" strokeLinecap="round" />
        ))}
        {destaques.map((p) => (
          <circle key={p.t} cx={x(p.i)} cy={y(p.v)} r={1.1} fill={cor} stroke="#fff" strokeWidth={0.53} />
        ))}
        {ultimo && (
          <text x={x(ultimo.i) + 1.6} y={y(ultimo.v) + 0.8} fontSize={fonte} fill={TXT.primaria}>{numero(ultimo.v, 0)}</text>
        )}
        {validos.map((p) => (
          <circle key={`h${p.t}`} cx={x(p.i)} cy={y(p.v)} r={2} fill="transparent">
            <title>{`${p.t} s: ${numero(p.v, 0)} MΩ`}</title>
          </circle>
        ))}
      </svg>
    </figure>
  );
}
