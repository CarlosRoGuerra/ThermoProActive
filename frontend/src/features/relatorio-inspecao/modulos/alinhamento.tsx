import type { AlinhamentoOsp, CriterioOrigemOsp, OspD } from "../tipos";
import { LINHA_MEDICAO, criarModuloInspecao } from "./inspecao/modulo";

/* Alinhamento a laser entre eixos e polias (Anexo I 2.3.2.8.1.1–2): a folha da OSP mostra o último
   serviço do equipamento até o fim do relatório — antes e depois da correção nos dois planos, rpm,
   correções nos pés, redução e condição (só com tolerância cadastrada e validada). Glossário e
   considerações vêm do backend (relatorio_tecnico/alinhamento.py). */

/* Valor ausente sai "—", nunca 0. */
const numero = (v: string | null | undefined, casas: number) =>
  v == null || v === ""
    ? "—"
    : Number(v).toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });

const CONDICAO: Record<string, string> = {
  NORMAL: "Dentro da tolerância",
  ALERTA: "Alerta",
  CRITICO: "Crítico",
  PENDENTE: "Pendente (sem tolerância validada)",
};

function Linha({ rotulo, v }: { rotulo: string; v: string }) {
  return <div style={LINHA_MEDICAO}><span style={{ fontWeight: 700 }}>{rotulo}:</span> {v}</div>;
}

/* Sem quebra de linha nas células: cada linha a mais (5 mm) empurra o "Retorno de Informação" para outra folha. */
const CELULA_TABELA = {
  padding: "0 1mm", textAlign: "right" as const, fontVariantNumeric: "tabular-nums" as const,
  whiteSpace: "nowrap" as const, lineHeight: "5mm",
};

/* Origem do critério que classificou: nunca um acordo sai como norma (ver OrigemCriterio). */
const textoCriterio = (c: CriterioOrigemOsp | undefined) => (c ? `${c.origem_display} — ${c.fonte || "fonte não informada"}` : null);

/* Antes × depois e os limites numa tabela: a lista corrida (uma linha por valor) não cabia na folha da OSP. */
function TabelaAntesDepois({ a }: { a: AlinhamentoOsp }) {
  const limite = (l: Record<string, string> | undefined, k: string) => (l?.[k] ? numero(l[k], 2) : "—");
  const linhas: [string, string, string, string, string, string][] = [
    ["Angular [mm/100 mm]", numero(a.antes?.angular_mm_100mm, 3), numero(a.depois?.angular_mm_100mm, 3),
      numero(a.reducao_angular_pct, 1), limite(a.limites?.angular, "ALERTA"), limite(a.limites?.angular, "CRITICO")],
    ["Paralelo [mm]", numero(a.antes?.paralelo_mm, 3), numero(a.depois?.paralelo_mm, 3),
      numero(a.reducao_paralelo_pct, 1), limite(a.limites?.paralelo, "ALERTA"), limite(a.limites?.paralelo, "CRITICO")],
    ["Rotação [rpm]", numero(a.antes?.rpm, 0), numero(a.depois?.rpm, 0), "", "", ""],
  ];
  return (
    <table style={{ ...LINHA_MEDICAO, borderCollapse: "collapse", width: "90mm" }}>
      <thead>
        <tr>
          <th style={{ ...CELULA_TABELA, textAlign: "left", paddingLeft: 0 }} />
          {["Antes", "Depois", "Red. [%]", "Alerta ≥", "Crítico ≥"].map((t) => <th key={t} style={{ ...CELULA_TABELA, fontWeight: 700 }}>{t}</th>)}
        </tr>
      </thead>
      <tbody>
        {linhas.map(([rotulo, ...valores]) => (
          <tr key={rotulo}>
            <td style={{ ...CELULA_TABELA, textAlign: "left", paddingLeft: 0, fontWeight: 700 }}>{rotulo}</td>
            {valores.map((v, i) => <td key={i} style={CELULA_TABELA}>{v}</td>)}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function MedicoesAlinhamento({ o }: { o: OspD }) {
  const a = o.alinhamento;
  if (!a) {
    return (
      <>
        <div style={{ ...LINHA_MEDICAO, fontWeight: 700 }}>Alinhamento a laser</div>
        <Linha rotulo="Serviço" v="— (sem alinhamento até o fim do relatório)" />
      </>
    );
  }
  const angular = textoCriterio(a.criterio?.angular);
  const paralelo = textoCriterio(a.criterio?.paralelo);
  return (
    <>
      <div style={{ ...LINHA_MEDICAO, fontWeight: 700 }}>Alinhamento a laser — {new Date(a.data).toLocaleDateString("pt-BR")}</div>
      <TabelaAntesDepois a={a} />
      <Linha rotulo="Condição" v={CONDICAO[a.condicao] ?? a.condicao} />
      {angular && angular === paralelo ? (
        <Linha rotulo="Critério" v={angular} />
      ) : (
        <>
          {angular && <Linha rotulo="Critério angular" v={angular} />}
          {paralelo && <Linha rotulo="Critério paralelo" v={paralelo} />}
        </>
      )}
      {(a.pendencias ?? []).map((p) => <Linha key={p} rotulo="Pendente" v={p} />)}
    </>
  );
}

export const MODULO_ALINHAMENTO_EIXOS = criarModuloInspecao({
  chave: "ALINHAMENTO_EIXOS",
  Medicoes: MedicoesAlinhamento,
  quadros: [],
});

export const MODULO_ALINHAMENTO_POLIAS = criarModuloInspecao({
  chave: "ALINHAMENTO_POLIAS",
  Medicoes: MedicoesAlinhamento,
  quadros: [],
});
