import type { OspD, QualidadeLeituraOsp } from "../tipos";
import { LINHA_MEDICAO, criarModuloInspecao } from "./inspecao/modulo";

/* Qualidade de energia (Anexo I 2.3.2.10): a folha da OSP mostra, para cada grandeza
   (THD de tensão, THD de corrente e desequilíbrio de tensão), a última leitura do
   equipamento até o fim do relatório, com a janela de agregação e a condição (só com
   critério cadastrado e validado). Glossário e considerações vêm do backend
   (relatorio_tecnico/qualidade_energia.py). */

/* Valor ausente sai "—", nunca 0. */
const numero = (v: string | null | undefined, casas: number) =>
  v == null || v === ""
    ? "—"
    : Number(v).toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });

const CONDICAO: Record<string, string> = {
  NORMAL: "Normal",
  ALERTA: "Alerta",
  CRITICO: "Crítico",
  PENDENTE: "Pendente (sem critério validado)",
};

const GRANDEZAS = ["THD de tensão", "THD de corrente", "Desequilíbrio de tensão"] as const;

function Linha({ rotulo, v }: { rotulo: string; v: string }) {
  return <div style={LINHA_MEDICAO}><span style={{ fontWeight: 700 }}>{rotulo}:</span> {v}</div>;
}

function Leitura({ rotulo, l }: { rotulo: string; l: QualidadeLeituraOsp | null | undefined }) {
  if (!l) return <Linha rotulo={rotulo} v="— (sem leitura até o fim do relatório)" />;
  return (
    <>
      <Linha rotulo={`${rotulo} [%]`} v={numero(l.valor, 2)} />
      <Linha rotulo="Janela de agregação" v={l.janela_agregacao || "—"} />
      <Linha rotulo="Condição" v={CONDICAO[l.condicao] ?? l.condicao} />
    </>
  );
}

export function MedicoesQualidadeEnergia({ o }: { o: OspD }) {
  const q = o.qualidade_energia;
  return (
    <>
      <div style={{ ...LINHA_MEDICAO, fontWeight: 700 }}>Qualidade de energia</div>
      {!q ? (
        <Linha rotulo="Leitura" v="— (sem medição de qualidade de energia até o fim do relatório)" />
      ) : (
        GRANDEZAS.map((g) => <Leitura key={g} rotulo={g} l={q[g]} />)
      )}
    </>
  );
}

export const MODULO_QUALIDADE_ENERGIA = criarModuloInspecao({
  chave: "QUALIDADE_ENERGIA",
  Medicoes: MedicoesQualidadeEnergia,
  quadros: [],
});
