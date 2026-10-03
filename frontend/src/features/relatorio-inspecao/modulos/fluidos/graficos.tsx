import type { CodigoIsoColeta, LinhaFluido, ReferenciaFluido } from "../../tipos";
import { CATEGORICAS_KPI, STATUS_KPI } from "../../shell/kpis";
import { ddmmaaaa } from "../../shell/formato";
import { numero } from "../transformador/formato";

/* ============================================================================
   Gráficos das fichas de fluidos — tendência ao longo das coletas, desenhados
   dos valores do payload (nunca imagem).

   Skill dataviz: pequenos múltiplos, UM eixo por gráfico (cada parâmetro tem a
   própria unidade), uma série por gráfico — o título a nomeia, sem caixa de
   legenda —, marcas finas, grade discreta e texto em tinta. As linhas de
   referência usam as cores de status (alerta/crítico), sempre com rótulo em
   tinta ao lado: o amarelo de alerta tem contraste baixo (validate_palette.js:
   1,79:1) e o alívio é o rótulo + a tabela de valores logo acima.
   ========================================================================== */

const COR_SERIE = CATEGORICAS_KPI[0];
const GRADE = "#e4e2dc";
const BASE = "#b9b7b0";
const TXT = { primaria: "#0b0b0b", secundaria: "#52514e", suave: "#898781" };
const FONTE = '"Segoe UI", system-ui, -apple-system, Roboto, Arial, sans-serif';

type Campanha = { data: string | null; atual: boolean };
type Ref = { valor: number; rotulo: string; cor: string };

/** Linhas de referência de um parâmetro (alerta/crítico; na variação, base ± %). */
function linhasDeReferencia(r: ReferenciaFluido | null, casas: number): Ref[] {
  if (!r) return [];
  const saida: Ref[] = [];
  const add = (v: number | null, rotulo: string, cor: string) => {
    if (v != null && Number.isFinite(v)) saida.push({ valor: v, rotulo: `${rotulo} ${numero(v, casas)}`, cor });
  };
  if (r.tipo === "MAXIMO" || r.tipo === "MINIMO") {
    add(r.limite_alerta, "Alerta", STATUS_KPI.warning);
    add(r.limite_critico, "Crítico", STATUS_KPI.critical);
  } else if (r.tipo === "VARIACAO" && r.valor_base) {
    const b = r.valor_base;
    for (const [pct, rotulo, cor] of [[r.limite_alerta, "Alerta", STATUS_KPI.warning], [r.limite_critico, "Crítico", STATUS_KPI.critical]] as const) {
      if (pct == null) continue;
      add(b * (1 + pct / 100), rotulo, cor);
      add(b * (1 - pct / 100), rotulo, cor);
    }
  }
  return saida;
}

/** Escala "redonda" que contém os valores e as referências. */
function faixa(valores: number[]) {
  let min = Math.min(...valores);
  let max = Math.max(...valores);
  if (min === max) {
    min = min === 0 ? 0 : min * 0.9;
    max = max === 0 ? 1 : max * 1.1;
  }
  const folga = (max - min) * 0.12;
  const piso = min >= 0 && min - folga < 0 ? 0 : min - folga;
  return { min: piso, max: max + folga };
}

const curta = (iso: string | null) => (iso ? ddmmaaaa(iso).replace(/\/(\d{2})(\d{2})$/, "/$2") : "—");

/** Tendência de um parâmetro: valores das coletas + as linhas da referência cadastrada. */
export function TendenciaParametro({ linha, campanhas }: { linha: LinhaFluido; campanhas: Campanha[] }) {
  const W = 58;
  const H = 34;
  const x0 = 10;
  const x1 = W - 11;
  const yTopo = 2;
  const yBase = H - 7;
  const fonte = 2.1;
  const casas = linha.casas;
  const pontos = linha.valores.map((c, i) => ({ i, v: c.valor }));
  const validos = pontos.filter((p): p is { i: number; v: number } => p.v != null);
  const refs = linhasDeReferencia(linha.referencia, casas);
  const { min, max } = faixa([...validos.map((p) => p.v), ...refs.map((r) => r.valor)]);
  // Faixa estreita (ex.: teor de água 0 → 0) pede uma casa a mais nos rótulos do eixo.
  const casasEixo = max - min < 3 ? Math.max(casas, 1) : Math.min(casas, 1);
  const x = (i: number) => x0 + (campanhas.length > 1 ? (i / (campanhas.length - 1)) * (x1 - x0) : (x1 - x0) / 2);
  const y = (v: number) => yBase - ((v - min) / (max - min)) * (yBase - yTopo);
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
  const titulo = `${linha.nome}${linha.simbolo ? ` (${linha.simbolo})` : ""}`;
  const unidade = linha.unidade ? ` [${linha.unidade}]` : "";

  return (
    <figure style={{ margin: 0 }}>
      <figcaption style={{ fontSize: "7pt", color: TXT.primaria, marginBottom: "0.4mm", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
        {titulo}{unidade}
      </figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" style={{ display: "block", fontFamily: FONTE }}
        aria-label={`Tendência de ${titulo}: ${validos.map((p) => numero(p.v, casas)).join(", ")}`}>
        {[min, (min + max) / 2, max].map((v) => (
          <g key={v}>
            <line x1={x0} x2={x1} y1={y(v)} y2={y(v)} stroke={GRADE} strokeWidth={0.2} />
            <text x={x0 - 0.8} y={y(v) + 0.7} textAnchor="end" fontSize={fonte} fill={TXT.secundaria}
              style={{ fontVariantNumeric: "tabular-nums" }}>{numero(v, casasEixo)}</text>
          </g>
        ))}
        <line x1={x0} x2={x1} y1={yBase} y2={yBase} stroke={BASE} strokeWidth={0.25} />
        {refs.map((r, k) => (
          <g key={k}>
            <line x1={x0} x2={x1} y1={y(r.valor)} y2={y(r.valor)} stroke={r.cor} strokeWidth={0.4} strokeDasharray="1.2 0.8" />
            <text x={x1 + 0.8} y={y(r.valor) + 0.7} fontSize={1.8} fill={TXT.secundaria}>{r.rotulo.split(" ")[0]}</text>
          </g>
        ))}
        {campanhas.map((c, i) => (
          <text key={i} x={x(i)} y={yBase + 3} textAnchor="middle" fontSize={1.9} fill={TXT.secundaria}
            fontWeight={c.atual ? 700 : 400}>{curta(c.data)}</text>
        ))}
        {trechos.map((pts, k) => (
          <polyline key={k} points={pts} fill="none" stroke={COR_SERIE} strokeWidth={0.53} strokeLinejoin="round" strokeLinecap="round" />
        ))}
        {validos.map((p) => (
          <g key={p.i}>
            <circle cx={x(p.i)} cy={y(p.v)} r={0.9} fill={COR_SERIE} stroke="#fff" strokeWidth={0.4} />
            {/* Alvo de hover maior que a marca. */}
            <circle cx={x(p.i)} cy={y(p.v)} r={2.4} fill="transparent">
              <title>{`${ddmmaaaa(campanhas[p.i]?.data ?? "")}: ${numero(p.v, casas)}${linha.unidade ? ` ${linha.unidade}` : ""}`}</title>
            </circle>
          </g>
        ))}
        {ultimo && (
          <text x={x(ultimo.i)} y={y(ultimo.v) - 1.4} textAnchor="middle" fontSize={fonte} fontWeight={700} fill={TXT.primaria}>
            {numero(ultimo.v, casas)}
          </text>
        )}
      </svg>
    </figure>
  );
}

/** Quais parâmetros ganham gráfico: os com 2+ coletas, primeiro o que está em crítico/alerta. */
export function parametrosParaGrafico(linhas: LinhaFluido[], maximo: number): LinhaFluido[] {
  const peso = (l: LinhaFluido) =>
    (l.status === "CRITICA" ? 8 : l.status === "ALERTA" ? 4 : 0) + (l.referencia ? 2 : 0) + (l.no_grafico ? 1 : 0);
  return linhas
    .map((l, ordem) => ({ l, ordem }))
    .filter(({ l }) => !l.qualitativo && l.valores.filter((v) => v.valor != null).length >= 2)
    .sort((a, b) => peso(b.l) - peso(a.l) || a.ordem - b.ordem)
    .slice(0, maximo)
    .sort((a, b) => a.ordem - b.ordem)
    .map(({ l }) => l);
}

export function Tendencias({ linhas, campanhas, maximo = 4 }: { linhas: LinhaFluido[]; campanhas: Campanha[]; maximo?: number }) {
  const escolhidos = parametrosParaGrafico(linhas, maximo);
  if (!escolhidos.length) {
    return (
      <p style={{ fontSize: "8pt", color: TXT.suave, margin: "1mm 0" }}>
        A tendência aparece a partir da segunda coleta do mesmo equipamento.
      </p>
    );
  }
  return (
    <div style={{ display: "grid", gridTemplateColumns: `repeat(${escolhidos.length}, minmax(0, 1fr))`, gap: "4mm" }}>
      {escolhidos.map((l) => <TendenciaParametro key={l.codigo} linha={l} campanhas={campanhas} />)}
    </div>
  );
}

const TAMANHOS = [
  { i: 0, rotulo: "> 4 µm(c)" },
  { i: 1, rotulo: "> 6 µm(c)" },
  { i: 2, rotulo: "> 14 µm(c)" },
];

/** Código ISO 4406 por tamanho de partícula ao longo das coletas, com a meta (quando há). */
export function CodigosIso({ codigos, meta }: { codigos: CodigoIsoColeta[]; meta: number[] | null }) {
  if (codigos.filter((c) => c.codigo).length < 1) return null;
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: "4mm" }}>
      {TAMANHOS.map((t) => (
        <EscalaIso key={t.i} rotulo={t.rotulo} codigos={codigos} indice={t.i} meta={meta ? meta[t.i] : null} />
      ))}
    </div>
  );
}

function EscalaIso({ rotulo, codigos, indice, meta }: { rotulo: string; codigos: CodigoIsoColeta[]; indice: number; meta: number | null }) {
  const W = 58;
  const H = 32;
  const x0 = 7;
  const x1 = W - 9;
  const yTopo = 2;
  const yBase = H - 7;
  const pontos = codigos.map((c, i) => ({ i, v: c.escalas[indice] ?? null }));
  const validos = pontos.filter((p): p is { i: number; v: number } => p.v != null);
  const todos = [...validos.map((p) => p.v), ...(meta != null ? [meta] : [])];
  const min = Math.max(0, Math.min(...todos) - 1);
  const max = Math.max(...todos) + 1;
  const x = (i: number) => x0 + (codigos.length > 1 ? (i / (codigos.length - 1)) * (x1 - x0) : (x1 - x0) / 2);
  const y = (v: number) => yBase - ((v - min) / (max - min)) * (yBase - yTopo);
  const marcas = Array.from({ length: max - min + 1 }, (_, k) => min + k).filter((v, k, a) => a.length <= 6 || k % 2 === 0);
  return (
    <figure style={{ margin: 0 }}>
      <figcaption style={{ fontSize: "7pt", color: TXT.primaria, marginBottom: "0.4mm" }}>Código ISO 4406 — {rotulo}</figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" style={{ display: "block", fontFamily: FONTE }}
        aria-label={`Número de escala ISO 4406 ${rotulo}: ${validos.map((p) => p.v).join(", ")}${meta != null ? `; meta ${meta}` : ""}`}>
        {marcas.map((v) => (
          <g key={v}>
            <line x1={x0} x2={x1} y1={y(v)} y2={y(v)} stroke={GRADE} strokeWidth={0.2} />
            <text x={x0 - 0.8} y={y(v) + 0.7} textAnchor="end" fontSize={2} fill={TXT.secundaria}>{v}</text>
          </g>
        ))}
        <line x1={x0} x2={x1} y1={yBase} y2={yBase} stroke={BASE} strokeWidth={0.25} />
        {meta != null && (
          <g>
            <line x1={x0} x2={x1} y1={y(meta)} y2={y(meta)} stroke={TXT.secundaria} strokeWidth={0.4} strokeDasharray="1.2 0.8" />
            <text x={x1 + 0.8} y={y(meta) + 0.7} fontSize={1.8} fill={TXT.secundaria}>Meta</text>
          </g>
        )}
        {codigos.map((c, i) => (
          <text key={i} x={x(i)} y={yBase + 3} textAnchor="middle" fontSize={1.9} fill={TXT.secundaria} fontWeight={c.atual ? 700 : 400}>
            {curta(c.data)}
          </text>
        ))}
        <polyline points={validos.map((p) => `${x(p.i)},${y(p.v)}`).join(" ")} fill="none" stroke={COR_SERIE}
          strokeWidth={0.53} strokeLinejoin="round" strokeLinecap="round" />
        {validos.map((p) => (
          <g key={p.i}>
            <circle cx={x(p.i)} cy={y(p.v)} r={0.9} fill={COR_SERIE} stroke="#fff" strokeWidth={0.4} />
            <circle cx={x(p.i)} cy={y(p.v)} r={2.4} fill="transparent">
              <title>{`${ddmmaaaa(codigos[p.i]?.data ?? "")}: ${p.v}${meta != null ? ` (meta ${meta})` : ""}`}</title>
            </circle>
          </g>
        ))}
        {validos.length > 0 && (
          <text x={x(validos[validos.length - 1].i)} y={y(validos[validos.length - 1].v) - 1.4} textAnchor="middle"
            fontSize={2.1} fontWeight={700} fill={TXT.primaria}>{validos[validos.length - 1].v}</text>
        )}
      </svg>
    </figure>
  );
}
