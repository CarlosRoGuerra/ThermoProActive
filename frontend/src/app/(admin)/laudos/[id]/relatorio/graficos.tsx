"use client";

/**
 * Gráficos gerenciais da Seção B — SVG puro, sem biblioteca externa.
 *
 * Decisões de forma:
 *  · Distribuições (condições, componentes, anomalias) usam BARRAS HORIZONTAIS
 *    ordenadas por magnitude, e não pizza. Com 11 a 16 fatias de tamanho
 *    parecido, a pizza vira um alvo colorido ilegível — e ainda pior impressa.
 *  · Velocidade (mm/s) e aceleração (g) ficam em gráficos SEPARADOS: unidades
 *    diferentes nunca dividem o mesmo eixo.
 *  · Toda série tem rótulo direto e tabela de dados ao lado, de modo que a cor
 *    nunca é a única forma de identificar a informação.
 */

export type Fatia = { rotulo: string; valor: number; percentual: number; cor: string };

const TEXTO = "#111827";
const SECUNDARIO = "#4b5563";
const GRADE = "#e5e7eb";

/* ==================== Barras horizontais (distribuição) ==================== */
export function BarrasHorizontais({
  dados,
  unidade = "ocorrências",
}: {
  dados: Fatia[];
  unidade?: string;
}) {
  if (dados.length === 0) {
    return <p className="py-6 text-center text-[9pt] text-[color:var(--doc-muted)]">Sem dados no período.</p>;
  }
  const maxV = Math.max(...dados.map((d) => d.valor), 1);
  const alturaLinha = 20;
  const larguraRotulo = 132;
  const larguraBarra = 300;
  const altura = dados.length * alturaLinha + 8;

  return (
    <svg viewBox={`0 0 ${larguraRotulo + larguraBarra + 46} ${altura}`} className="w-full" role="img">
      {dados.map((d, i) => {
        const y = i * alturaLinha + 4;
        const w = Math.max((d.valor / maxV) * larguraBarra, 2);
        return (
          <g key={d.rotulo}>
            <text x={larguraRotulo - 6} y={y + 11} textAnchor="end" fontSize="8.5" fill={TEXTO}>
              {d.rotulo}
            </text>
            {/* Cantos arredondados só na ponta do dado, ancorado na linha de base. */}
            <rect x={larguraRotulo} y={y + 2} width={w} height={12} rx="3" fill={d.cor} />
            <text x={larguraRotulo + w + 6} y={y + 11} fontSize="8.5" fill={SECUNDARIO}>
              {d.valor} · {d.percentual}%
            </text>
          </g>
        );
      })}
      <text x={larguraRotulo} y={altura - 1} fontSize="7" fill={SECUNDARIO}>
        {unidade}
      </text>
    </svg>
  );
}

/* ============ Barras empilhadas por mês (composição no tempo) ============ */
export function BarrasEmpilhadas({
  meses,
}: {
  meses: { mes: string; total: number; series: { gr: string; valor: number; cor: string }[] }[];
}) {
  if (meses.length === 0) {
    return <p className="py-6 text-center text-[9pt] text-[color:var(--doc-muted)]">Sem dados no período.</p>;
  }
  const L = 460, A = 150, padB = 22, padT = 14, padL = 26;
  const maxTotal = Math.max(...meses.map((m) => m.total), 1);
  const plotA = A - padB - padT;
  const passo = (L - padL) / meses.length;
  const largura = Math.min(38, passo * 0.6);

  return (
    <svg viewBox={`0 0 ${L} ${A}`} className="w-full" role="img">
      {[0, 0.5, 1].map((g) => {
        const y = padT + g * plotA;
        return (
          <g key={g}>
            <line x1={padL} y1={y} x2={L} y2={y} stroke={GRADE} strokeWidth="1" />
            <text x={padL - 4} y={y + 3} textAnchor="end" fontSize="7" fill={SECUNDARIO}>
              {Math.round(maxTotal * (1 - g))}
            </text>
          </g>
        );
      })}
      {meses.map((m, i) => {
        const cx = padL + passo * i + passo / 2;
        let y = padT + plotA;
        return (
          <g key={m.mes}>
            {m.series.map((s) => {
              if (!s.valor) return null;
              const h = (s.valor / maxTotal) * plotA;
              y -= h;
              return (
                <rect
                  key={s.gr}
                  x={cx - largura / 2}
                  y={y}
                  width={largura}
                  height={Math.max(h - 2, 1)} /* 2px de respiro entre segmentos */
                  fill={s.cor}
                />
              );
            })}
            <text x={cx} y={padT + plotA - (m.total / maxTotal) * plotA - 4} textAnchor="middle" fontSize="7.5" fill={TEXTO} fontWeight="600">
              {m.total}
            </text>
            <text x={cx} y={A - 8} textAnchor="middle" fontSize="7.5" fill={SECUNDARIO}>
              {m.mes}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

/* ============ Linhas: duas séries de mesma unidade (contagem) ============ */
export function LinhasComparativas({
  dados,
}: {
  dados: { mes: string; equipamentos: number; anomalias: number }[];
}) {
  if (dados.length === 0) {
    return <p className="py-6 text-center text-[9pt] text-[color:var(--doc-muted)]">Sem dados no período.</p>;
  }
  const L = 460, A = 150, padB = 22, padT = 14, padL = 26;
  const plotA = A - padB - padT;
  const max = Math.max(...dados.flatMap((d) => [d.equipamentos, d.anomalias]), 1);
  const x = (i: number) => padL + (dados.length === 1 ? (L - padL) / 2 : (i * (L - padL - 10)) / (dados.length - 1));
  const y = (v: number) => padT + (1 - v / max) * plotA;

  const serie = (chave: "equipamentos" | "anomalias", cor: string) => {
    const pts = dados.map((d, i) => `${x(i).toFixed(1)},${y(d[chave]).toFixed(1)}`);
    return (
      <g>
        <polyline points={pts.join(" ")} fill="none" stroke={cor} strokeWidth="2" strokeLinejoin="round" />
        {dados.map((d, i) => (
          <circle key={i} cx={x(i)} cy={y(d[chave])} r="3.2" fill={cor} stroke="#fff" strokeWidth="1.5" />
        ))}
      </g>
    );
  };

  return (
    <svg viewBox={`0 0 ${L} ${A}`} className="w-full" role="img">
      {[0, 0.5, 1].map((g) => {
        const yy = padT + g * plotA;
        return (
          <g key={g}>
            <line x1={padL} y1={yy} x2={L} y2={yy} stroke={GRADE} strokeWidth="1" />
            <text x={padL - 4} y={yy + 3} textAnchor="end" fontSize="7" fill={SECUNDARIO}>
              {Math.round(max * (1 - g))}
            </text>
          </g>
        );
      })}
      {serie("equipamentos", "#2a78d6")}
      {serie("anomalias", "#c9401f")}
      {dados.map((d, i) => (
        <text key={i} x={x(i)} y={A - 8} textAnchor="middle" fontSize="7.5" fill={SECUNDARIO}>
          {d.mes}
        </text>
      ))}
    </svg>
  );
}

/* ====== Amplitude: uma unidade por gráfico, com linha de referência ====== */
export function AmplitudeGrafico({
  dados,
  campoPico,
  campoLimite,
  cor,
  unidade,
}: {
  dados: Record<string, string | number | null>[];
  campoPico: string;
  campoLimite: string;
  cor: string;
  unidade: string;
}) {
  const pontos = dados.filter((d) => d[campoPico] != null);
  if (pontos.length === 0) {
    return <p className="py-6 text-center text-[9pt] text-[color:var(--doc-muted)]">Sem medições no período.</p>;
  }
  const L = 300, A = 130, padB = 20, padT = 14, padL = 26;
  const plotA = A - padB - padT;
  const vals = pontos.map((d) => Number(d[campoPico]));
  const limites = pontos.map((d) => Number(d[campoLimite] ?? 0));
  const max = Math.max(...vals, ...limites, 1) * 1.15;
  const x = (i: number) => padL + (pontos.length === 1 ? (L - padL) / 2 : (i * (L - padL - 10)) / (pontos.length - 1));
  const y = (v: number) => padT + (1 - v / max) * plotA;

  return (
    <svg viewBox={`0 0 ${L} ${A}`} className="w-full" role="img">
      <line x1={padL} y1={padT + plotA} x2={L} y2={padT + plotA} stroke={GRADE} strokeWidth="1" />
      {/* Linha de referência (limite aceitável) — tracejada, recessiva. */}
      <line
        x1={padL}
        y1={y(limites[0])}
        x2={L}
        y2={y(limites[0])}
        stroke={SECUNDARIO}
        strokeWidth="1"
        strokeDasharray="4 3"
      />
      <text x={L} y={y(limites[0]) - 3} textAnchor="end" fontSize="7" fill={SECUNDARIO}>
        limite {limites[0]}
      </text>
      <polyline
        points={pontos.map((d, i) => `${x(i).toFixed(1)},${y(Number(d[campoPico])).toFixed(1)}`).join(" ")}
        fill="none"
        stroke={cor}
        strokeWidth="2"
        strokeLinejoin="round"
      />
      {pontos.map((d, i) => (
        <g key={i}>
          <circle cx={x(i)} cy={y(Number(d[campoPico]))} r="3.2" fill={cor} stroke="#fff" strokeWidth="1.5" />
          <text x={x(i)} y={y(Number(d[campoPico])) - 7} textAnchor="middle" fontSize="7" fill={TEXTO}>
            {Number(d[campoPico]).toLocaleString("pt-BR")}
          </text>
          <text x={x(i)} y={A - 6} textAnchor="middle" fontSize="7" fill={SECUNDARIO}>
            {String(d.mes)}
          </text>
        </g>
      ))}
      <text x={padL} y={10} fontSize="7" fill={SECUNDARIO}>
        {unidade}
      </text>
    </svg>
  );
}

/* ==================== Legenda (sempre para ≥ 2 séries) ==================== */
export function Legenda({ itens }: { itens: { rotulo: string; cor: string }[] }) {
  return (
    <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1">
      {itens.map((i) => (
        <span key={i.rotulo} className="inline-flex items-center gap-1.5 text-[8pt]">
          <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: i.cor }} />
          <span style={{ color: SECUNDARIO }}>{i.rotulo}</span>
        </span>
      ))}
    </div>
  );
}

/* ==================== Tabela de dados que acompanha o gráfico ============ */
export function TabelaDados({
  colunas,
  linhas,
}: {
  colunas: string[];
  linhas: (string | number)[][];
}) {
  return (
    <table className="w-full text-[7.5pt]">
      <thead>
        <tr className="border-b border-[color:var(--doc-line)]">
          {colunas.map((c) => (
            <th key={c} className="py-0.5 text-left font-semibold" style={{ color: SECUNDARIO }}>
              {c}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {linhas.map((l, i) => (
          <tr key={i}>
            {l.map((v, j) => (
              <td key={j} className={j === 0 ? "py-0.5" : "py-0.5 text-right font-mono"}>
                {v}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
