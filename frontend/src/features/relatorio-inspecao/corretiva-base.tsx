"use client";

/**
 * Base compartilhada da folha de manutenção corretiva — formatação, tokens de
 * impressão, o bloco de Economia energética (comum a qualquer tipo de corretiva,
 * não só balanceamento) e o corpo NEUTRO para tipos sem layout técnico definido.
 *
 * Hoje só o Balanceamento tem apresentação própria (`corretiva-balanceamento.tsx`,
 * que importa os utilitários daqui). Um tipo sem montador específico no backend
 * (ex.: Alinhamento a laser — o cliente confirmou que tem particularidades ainda
 * em discussão) cai em `CorpoCorretivaGenerico`: mostra o que já é comum a
 * QUALQUER corretiva executada (identificação do tipo, foto, Economia quando
 * cadastrada) e NADA além disso — nenhuma tolerância, offset, angularidade, calço
 * ou resultado de laser é inventado. `dossie.tsx` decide entre este corpo neutro,
 * `CorpoBalanceamento` e o layout preditivo a partir de `tipo_corretiva`.
 */
import type { CSSProperties, ReactNode } from "react";

/* ---------------------------- Formatação ---------------------------------- */
export const AUSENTE = "—";

export const nm = (v: number | null | undefined, casas = 2) =>
  v == null
    ? AUSENTE
    : v.toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });

/** Decimais do DRF chegam como string; string vazia é ausência, não zero. */
export const nt = (v: string | number | null | undefined, casas = 2) =>
  v == null || v === "" ? AUSENTE : nm(Number(v), casas);

export const brl = (v: string | number | null | undefined) =>
  v == null || v === ""
    ? AUSENTE
    : Number(v).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

export const grau = (v: number | null | undefined) => (v == null ? AUSENTE : `${nm(v, 1)}°`);
export const pct = (v: number | null | undefined) => (v == null ? AUSENTE : `${nm(v, 1)}%`);

/**
 * O relatório é um documento impresso: fundo branco sempre. Os gráficos reaproveitados
 * da tela (`MostradorPolar`, `AntesDepois`) leem os tokens do tema, que no modo escuro
 * viram cores claras — ilegíveis no papel. Redeclarar os tokens do tema claro neste
 * escopo mantém um componente só para tela e impressão, sem tocar na tela de campo.
 */
export const TOKENS_IMPRESSAO = {
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

/** Estilos da folha corretiva — comuns (barra/bloco/lista/economia) e do
 *  balanceamento (tabela/reducao). Uma única folha de estilos evita duas cópias
 *  divergindo com o tempo; classes não usadas por um corpo específico são inertes. */
export const ESTILOS_CORRETIVA = `
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

/* ----------------------- Economia energética gerada ------------------------
 * Modelo comum a QUALQUER manutenção corretiva (balanceamento e alinhamento —
 * `EconomiaEnergetica` é 1-para-1 com o `ServicoCampo`, sem distinção de tipo).
 * Por isso o componente mora aqui, não no arquivo do balanceamento. */

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

export function EconomiaGerada({ economia }: { economia: EconomiaCorretiva | null }) {
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

/* ------------------------ Corpo corretivo neutro --------------------------- */

/**
 * Metade inferior da folha para uma manutenção corretiva SEM layout técnico
 * definido (hoje: Alinhamento a laser). Mantém a geometria física do gabarito
 * (90 + 10 + 80 + 10 = 190mm) — a foto continua exatamente onde estava.
 *
 * Propositalmente NÃO mostra "Resultado do Alinhamento" nem qualquer variação
 * disso: como não há dado real de tolerância/offset/angularidade ainda, exibir
 * um bloco de resultado (mesmo vazio) sugeriria que o sistema já mede isso.
 */
export function CorpoCorretivaGenerico({
  tipoDisplay,
  economia,
  foto,
}: {
  /** Rótulo humano do tipo (`tipo_corretiva_display` do payload). */
  tipoDisplay: string;
  economia: EconomiaCorretiva | null;
  foto: ReactNode;
}) {
  return (
    <div style={TOKENS_IMPRESSAO}>
      <style>{ESTILOS_CORRETIVA}</style>

      <p style={{ fontSize: "12pt", fontWeight: 700, color: "#1d4ed8", marginTop: "6mm", marginBottom: 0 }}>
        Manutenção Corretiva — {tipoDisplay}
      </p>

      <div
        style={{
          width: "190mm", display: "grid", gridTemplateColumns: "90mm 10mm 80mm 10mm",
          alignItems: "start", marginTop: "3mm",
        }}
      >
        <div style={{ width: "90mm" }}>
          <div style={{ marginLeft: "10mm", width: "80mm" }}>{foto}</div>
        </div>
        <div />
        <div style={{ width: "80mm" }} className="bal-bloco">
          <p className="bal-vazio" style={{ padding: 0 }}>
            Os dados técnicos desta intervenção serão apresentados conforme o modelo
            específico de {tipoDisplay.toLowerCase()}, ainda em definição.
          </p>
        </div>
        <div />
      </div>

      <EconomiaGerada economia={economia} />
    </div>
  );
}
