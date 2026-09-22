"use client";

/**
 * Metade inferior da folha da OSP quando a intervenção é um BALANCEAMENTO corretivo.
 *
 * O cabeçalho da folha (OSP nº, empresa, TAG, diagnóstico, Grau de Risco) é o mesmo da
 * preditiva e continua em `dossie.tsx` — aqui trocam-se os blocos que não descrevem
 * uma corretiva já executada:
 *
 *   Tendência/Espectro  → Mostrador de fase (Trim) e Evolução da Vibração
 *   Planejamento/Corretiva Prog./Finalização → Resultado do Balanceamento
 *   Retorno de Informação (ROI preditivo)    → Economia Energética Gerada
 *
 * Nada é calculado aqui: todos os números vêm prontos do backend
 * (`apps.servicos.relatorio_corretivo`), que é a mesma fonte da tela do serviço.
 * Valor ausente sai como estado de ausência — num laudo, um zero inventado é pior
 * que um campo em branco.
 */
import type { CSSProperties, ReactNode } from "react";
import { AntesDepois, MostradorPolar, type PontoGrafico } from "@/components/balanceamento-graficos";

/* ------------------------------- Tipos ------------------------------------ */
type Corrida = { mms: number; fase: number | null } | null;

export type PontoCorretiva = {
  id: number;
  codigo_ponto: string;
  numero_mancal: number;
  direcao: string;
  identificacao: string;
  plano: number | null;
  reference: Corrida;
  trial: Corrida;
  trim: Corrida;
  completo: boolean;
  residual_pct: number | null;
  reducao_pct: number | null;
  zona_iso: string;
  criticidade: string;
  criticidade_display: string;
  eficaz: boolean;
  diagnostico: string;
};

export type PlanoCorretiva = {
  id: number;
  numero: number;
  descricao: string;
  massa_teste_g: number | null;
  angulo_teste: number | null;
  massa_final_g: number | null;
  angulo_final: number | null;
};

export type EconomiaCorretiva = {
  tensao_v: string | null;
  corrente_antes_a: string | null;
  corrente_apos_a: string | null;
  fator_potencia: string | null;
  horas_dia: string | null;
  dias_ano: number | null;
  custo_kwh: string | null;
  investimento: string | null;
  reducao_corrente_a: string | null;
  reducao_kw: string | null;
  economia_kwh_ano: string | null;
  economia_rs_ano: string | null;
  payback_meses: string | null;
  payback_dias: string | null;
  retorno_ano: string | null;
  premissas: string[];
};

export type Corretiva = {
  servico_id: number;
  tipo: string;
  rotacao_hz: number | null;
  rotacao_rpm: number | null;
  classe_iso: string;
  ponto_foco: number | null;
  planos: PlanoCorretiva[];
  pontos: PontoCorretiva[];
  resultado: {
    pontos_completos: number;
    reducao_media_pct: number | null;
    criticidade_final: string | null;
  };
  economia: EconomiaCorretiva | null;
};

/* ---------------------------- Formatação ---------------------------------- */
const AUSENTE = "—";

const nm = (v: number | null | undefined, casas = 2) =>
  v == null
    ? AUSENTE
    : v.toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });

/** Decimais do DRF chegam como string; string vazia é ausência, não zero. */
const nt = (v: string | number | null | undefined, casas = 2) =>
  v == null || v === "" ? AUSENTE : nm(Number(v), casas);

const brl = (v: string | number | null | undefined) =>
  v == null || v === ""
    ? AUSENTE
    : Number(v).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

const grau = (v: number | null | undefined) => (v == null ? AUSENTE : `${nm(v, 1)}°`);
const pct = (v: number | null | undefined) => (v == null ? AUSENTE : `${nm(v, 1)}%`);

/**
 * O relatório é um documento impresso: fundo branco sempre. Os gráficos reaproveitados
 * da tela (`MostradorPolar`, `AntesDepois`) leem os tokens do tema, que no modo escuro
 * viram cores claras — ilegíveis no papel. Redeclarar os tokens do tema claro neste
 * escopo mantém um componente só para tela e impressão, sem tocar na tela de campo.
 */
const TOKENS_IMPRESSAO = {
  "--surface": "#ffffff",
  "--border": "#dde3ed",
  "--border-strong": "#c4cddc",
  "--fg": "#0b1220",
  "--fg-muted": "#515d73",
  "--fg-subtle": "#7d8899",
  "--viz-reference": "#1257c2",
  "--viz-trial": "#c07407",
  "--viz-trim": "#0f9d76",
} as CSSProperties;

const ESTILOS = `
  .bal-barra { box-sizing: border-box; width: 100%; height: 6mm; line-height: 6mm; padding: 0 1mm;
    background: #16a34a; color: #fff; font-size: 12pt; font-weight: 700; text-align: center; }
  .bal-titulo { font-size: 11pt; font-weight: 700; color: #1d4ed8; line-height: 5mm; margin-bottom: 1mm; }
  .bal-bloco { break-inside: avoid; page-break-inside: avoid; }
  .bal-vazio { font-size: 9pt; color: #64748b; padding: 2mm 0; }
  .bal-tabela { width: 100%; border-collapse: collapse; font-size: 8pt; table-layout: fixed; }
  .bal-tabela th, .bal-tabela td { box-sizing: border-box; border: 0.2mm solid #b8b8b8;
    padding: 0 0.8mm; height: 4.6mm; line-height: 4.6mm; overflow: hidden; }
  .bal-tabela th { font-weight: 700; text-align: center; background: #f1f5f9; }
  .bal-tabela td.num { text-align: right; font-variant-numeric: tabular-nums; }
  .bal-tabela td.centro { text-align: center; }
  .bal-reducao { font-weight: 700; color: #0f9d76; }
  .bal-linha { font-size: 8.5pt; line-height: 4.4mm; }
  .bal-linha b { font-weight: 700; }
  .bal-destaques { display: grid; grid-template-columns: repeat(4, 1fr); gap: 2mm; margin-top: 2mm; }
  .bal-destaque { box-sizing: border-box; border: 0.2mm solid #16a34a; padding: 0.8mm;
    text-align: center; break-inside: avoid; }
  .bal-destaque span { display: block; font-size: 7.5pt; color: #475569; line-height: 3.4mm; }
  .bal-destaque strong { display: block; font-size: 11pt; font-weight: 700; color: #166534; line-height: 4.8mm; }
  .bal-colunas { display: grid; grid-template-columns: 92mm 6mm 92mm; margin-top: 2mm; }
  /* Duas colunas de pares rótulo/valor dentro de cada lista: as 15 grandezas da
     economia cabem em 4 linhas, deixando a folha A4 fechar com sobra. */
  .bal-lista { display: grid; grid-template-columns: 1fr 1fr; column-gap: 4mm; font-size: 8.5pt; }
  .bal-lista .cab { grid-column: 1 / -1; font-weight: 700; line-height: 4.2mm;
    border-bottom: 0.2mm solid #94a3b8; }
  .bal-lista .par { display: flex; justify-content: space-between; gap: 2mm; line-height: 4.2mm;
    border-bottom: 0.2mm dotted #cbd5e1; }
  .bal-lista .par span:last-child { font-variant-numeric: tabular-nums; font-weight: 700; }
  .bal-premissas { margin-top: 1.5mm; font-size: 7.5pt; color: #64748b; line-height: 3.6mm; }
`;

/* ------------------- Amplitudes (só velocidade no balanceamento) ----------- */

/**
 * No balanceamento a grandeza de interesse é a velocidade vibracional: a norma de
 * severidade (ISO 10816/20816) e o antes/depois do serviço estão todos em mm/s. A
 * aceleração continua existindo no banco e nos relatórios preditivos — só não
 * descreve este serviço.
 */
export function AmplitudeBalanceamento({ velocidade }: { velocidade: string | null }) {
  const linha = { minHeight: "5mm", lineHeight: "5mm" } as const;
  return (
    <>
      <div style={{ ...linha, fontWeight: 700 }}>Amplitudes [valor global]</div>
      <div style={linha}>
        <span style={{ fontWeight: 700 }}>Velocidade [mm/s]:</span> {velocidade ?? AUSENTE}
      </div>
    </>
  );
}

/* ------------------------ Mostrador de fase (Trim) ------------------------- */

function paraGrafico(p: PontoCorretiva): PontoGrafico {
  return {
    codigo_ponto: p.codigo_ponto,
    reference: p.reference,
    trial: p.trial,
    trim: p.trim,
    reducao_pct: p.reducao_pct,
    zona_iso: p.zona_iso,
    completo: p.completo,
  };
}

/** Ponto representado no mostrador: o foco do balanceamento; sem foco, o 1º ponto. */
function pontoDoMostrador(c: Corretiva): PontoCorretiva | null {
  return c.pontos.find((p) => p.id === c.ponto_foco) ?? c.pontos[0] ?? null;
}

function MostradorTrim({ c }: { c: Corretiva }) {
  const ponto = pontoDoMostrador(c);
  return (
    <div className="bal-bloco">
      <div className="bal-titulo">Mostrador de Fase — Trim Run</div>
      {ponto ? (
        <>
          <MostradorPolar
            ponto={paraGrafico(ponto)}
            tamanho="46mm"
            series={["trim"]}
            mensagemVazia="Trim Run ainda não informado — o mostrador final sai com a fase do Trim Run, nunca com a do Trial."
          />
          <div className="bal-linha" style={{ marginTop: "1mm" }}>
            <b>Ponto:</b> {ponto.codigo_ponto}
            {ponto.identificacao ? ` — ${ponto.identificacao}` : ""}
          </div>
        </>
      ) : (
        <p className="bal-vazio">Nenhum ponto de medição registrado neste serviço.</p>
      )}
    </div>
  );
}

/* --------------------- Resultado do balanceamento -------------------------- */

function ResultadoBalanceamento({ c }: { c: Corretiva }) {
  const completos = c.pontos.filter((p) => p.completo);
  const numeroDoPlano = (id: number | null) => c.planos.find((pl) => pl.id === id)?.numero ?? null;

  return (
    <div className="bal-bloco">
      <div className="bal-barra">Resultado do Balanceamento</div>
      {completos.length ? (
        <table className="bal-tabela" style={{ marginTop: "1.5mm" }}>
          <colgroup>
            <col style={{ width: "13mm" }} />
            <col style={{ width: "11mm" }} />
            <col style={{ width: "17mm" }} />
            <col style={{ width: "17mm" }} />
            <col style={{ width: "17mm" }} />
            <col style={{ width: "15mm" }} />
          </colgroup>
          <thead>
            <tr>
              <th>Ponto</th>
              <th>Plano</th>
              <th>Antes [mm/s]</th>
              <th>Depois [mm/s]</th>
              <th>Redução</th>
              <th>ISO</th>
            </tr>
          </thead>
          <tbody>
            {completos.map((p) => (
              <tr key={p.id}>
                <td className="centro">{p.codigo_ponto}</td>
                <td className="centro">{numeroDoPlano(p.plano) ?? AUSENTE}</td>
                <td className="num">{nm(p.reference?.mms ?? null)}</td>
                <td className="num">{nm(p.trim?.mms ?? null)}</td>
                <td className="num bal-reducao">{pct(p.reducao_pct)}</td>
                <td className="centro">{p.zona_iso || AUSENTE}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="bal-vazio">
          Trim Run ainda não informado — sem ele o serviço não tem resultado medido.
        </p>
      )}

      <div className="bal-linha" style={{ marginTop: "1.5mm" }}>
        <b>Classe ISO do equipamento:</b> {c.classe_iso || AUSENTE} &nbsp;·&nbsp;{" "}
        <b>Situação final:</b>{" "}
        {completos.length
          ? completos.find((p) => p.criticidade === c.resultado.criticidade_final)
              ?.criticidade_display || c.resultado.criticidade_final || AUSENTE
          : AUSENTE}
        {c.resultado.reducao_media_pct != null && (
          <>
            {" "}&nbsp;·&nbsp; <b>Redução média:</b>{" "}
            <span className="bal-reducao" style={{ fontSize: "10pt" }}>
              {pct(c.resultado.reducao_media_pct)}
            </span>
          </>
        )}
      </div>

      {/* A correção que FICOU na máquina: massa e ângulo finais. Massa/ângulo de
          teste pertencem ao Trial Run e não representam o resultado. */}
      {c.planos.length ? (
        c.planos.map((pl) => (
          <div key={pl.id} className="bal-linha">
            <b>Plano {pl.numero}</b>
            {pl.descricao ? ` (${pl.descricao})` : ""} — Massa de correção:{" "}
            <b>{pl.massa_final_g == null ? AUSENTE : `${nm(pl.massa_final_g)} g`}</b> · Ângulo de
            correção: <b>{grau(pl.angulo_final)}</b>
          </div>
        ))
      ) : (
        <div className="bal-linha">Nenhum plano de correção registrado.</div>
      )}
    </div>
  );
}

/* ------------------------ Evolução da vibração ----------------------------- */

function EvolucaoVibracao({ c }: { c: Corretiva }) {
  const pontos = c.pontos.filter((p) => p.reference && p.trim).map(paraGrafico);
  return (
    <div className="bal-bloco">
      <div className="bal-titulo">Evolução da Vibração</div>
      {pontos.length ? (
        <AntesDepois pontos={pontos} />
      ) : (
        <p className="bal-vazio">
          A evolução aparece quando algum ponto tiver o Trim Run medido.
        </p>
      )}
    </div>
  );
}

/* ----------------------- Economia energética gerada ------------------------ */

function Lista({ titulo, itens }: { titulo: string; itens: [string, string][] }) {
  return (
    <div className="bal-lista">
      <div className="cab">{titulo}</div>
      {itens.map(([rotulo, valor]) => (
        <div className="par" key={rotulo}>
          <span>{rotulo}</span>
          <span>{valor}</span>
        </div>
      ))}
    </div>
  );
}

function EconomiaGerada({ economia }: { economia: EconomiaCorretiva | null }) {
  if (!economia) {
    return (
      <div className="bal-bloco" style={{ marginTop: "4mm" }}>
        <div className="bal-barra">Economia Energética Gerada</div>
        <p className="bal-vazio">
          Economia energética ainda não informada para este serviço.
        </p>
      </div>
    );
  }

  // Rótulos curtos e valores sem prefixo de moeda (a unidade está no rótulo): em
  // 44mm de coluna, "R$ 36.897,12" quebraria a linha e empurraria a folha para fora
  // do A4. Os cartões de destaque acima mostram o valor formatado por extenso.
  const premissas: [string, string][] = [
    ["Tensão [V]", nt(economia.tensao_v)],
    ["Corrente antes [A]", nt(economia.corrente_antes_a)],
    ["Corrente após [A]", nt(economia.corrente_apos_a)],
    ["Fator de potência", nt(economia.fator_potencia, 3)],
    ["Operação [h/dia]", nt(economia.horas_dia, 1)],
    ["Operação [dias/ano]", economia.dias_ano == null ? AUSENTE : String(economia.dias_ano)],
    ["Energia [R$/kWh]", nt(economia.custo_kwh, 4)],
    ["Investimento [R$]", nt(economia.investimento)],
  ];
  const resultados: [string, string][] = [
    ["Redução corrente [A]", nt(economia.reducao_corrente_a)],
    ["Redução demanda [kW]", nt(economia.reducao_kw, 4)],
    ["Economia [kWh/ano]", nt(economia.economia_kwh_ano)],
    ["Economia [R$/ano]", nt(economia.economia_rs_ano)],
    ["Payback [meses]", nt(economia.payback_meses)],
    ["Payback [dias]", nt(economia.payback_dias, 1)],
    ["Retorno [×/ano]", nt(economia.retorno_ano, 2)],
  ];

  return (
    <div className="bal-bloco" style={{ marginTop: "4mm" }}>
      <div className="bal-barra">Economia Energética Gerada</div>

      <div className="bal-destaques">
        <div className="bal-destaque">
          <span>Economia [kWh/ano]</span>
          <strong>{nt(economia.economia_kwh_ano, 0)}</strong>
        </div>
        <div className="bal-destaque">
          <span>Economia [R$/ano]</span>
          <strong>{brl(economia.economia_rs_ano)}</strong>
        </div>
        <div className="bal-destaque">
          <span>Payback [meses]</span>
          <strong>{nt(economia.payback_meses)}</strong>
        </div>
        <div className="bal-destaque">
          <span>Retorno [×/ano]</span>
          <strong>{nt(economia.retorno_ano, 2)}</strong>
        </div>
      </div>

      <div className="bal-colunas">
        <Lista titulo="Entradas / premissas" itens={premissas} />
        <div />
        <Lista titulo="Resultados" itens={resultados} />
      </div>

      {/* Sem as premissas o número financeiro não se sustenta em auditoria. */}
      {economia.premissas?.length > 0 && (
        <p className="bal-premissas">{economia.premissas.join(" · ")}</p>
      )}
    </div>
  );
}

/* ------------------------------ Folha -------------------------------------- */

/**
 * Metade inferior da folha. Mantém a geometria física do gabarito
 * (90 + 10 + 80 + 10 = 190mm), para a foto continuar exatamente onde estava.
 */
export function CorpoBalanceamento({
  corretiva,
  foto,
  velocidade,
}: {
  corretiva: Corretiva;
  /** O slot da foto vem pronto da folha — o upload de evidências não muda. */
  foto: ReactNode;
  velocidade: string | null;
}) {
  return (
    <div style={TOKENS_IMPRESSAO}>
      <style>{ESTILOS}</style>

      {/* Linha 1 — Foto do equipamento | Mostrador de fase (Trim Run) */}
      <div
        style={{
          width: "190mm",
          display: "grid",
          gridTemplateColumns: "90mm 10mm 80mm 10mm",
          alignItems: "start",
          marginTop: "6mm",
        }}
      >
        <div style={{ width: "90mm" }}>
          <div style={{ marginLeft: "10mm", width: "80mm" }}>{foto}</div>
          <div style={{ height: "4mm" }} />
          <AmplitudeBalanceamento velocidade={velocidade} />
        </div>
        <div />
        <div style={{ width: "80mm" }}>
          <MostradorTrim c={corretiva} />
        </div>
        <div />
      </div>

      {/* Linha 2 — Resultado do balanceamento | Evolução da vibração */}
      <div
        style={{
          width: "190mm",
          display: "grid",
          gridTemplateColumns: "90mm 10mm 80mm 10mm",
          alignItems: "start",
          marginTop: "4mm",
        }}
      >
        <div style={{ width: "90mm" }}>
          <ResultadoBalanceamento c={corretiva} />
        </div>
        <div />
        <div style={{ width: "80mm" }}>
          <EvolucaoVibracao c={corretiva} />
        </div>
        <div />
      </div>

      <EconomiaGerada economia={corretiva.economia} />
    </div>
  );
}
