import type { OspD } from "../tipos";
import { LINHA_MEDICAO, criarModuloInspecao } from "./inspecao/modulo";

/* Ultrassom elétrico e mecânico (Anexo I 2.3.2.6): a folha da OSP mostra a última leitura do
   equipamento até o fim do relatório — subtipo, nível em dB, ganho, distância, frequência
   quando registrada e condição (só com critério cadastrado e validado). Glossário e
   considerações vêm do backend (relatorio_tecnico/ultrassom.py). */

/* Valor ausente sai "—", nunca 0. */
const numero = (v: string | null | undefined, casas: number) =>
  v == null || v === ""
    ? "—"
    : Number(v).toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });

const SUBTIPO: Record<string, string> = { ELETRICO: "Elétrico", MECANICO: "Mecânico" };
const CONDICAO: Record<string, string> = {
  NORMAL: "Normal",
  ALERTA: "Alerta",
  CRITICO: "Crítico",
  PENDENTE: "Pendente (sem critério validado)",
};

function Linha({ rotulo, v }: { rotulo: string; v: string }) {
  return <div style={LINHA_MEDICAO}><span style={{ fontWeight: 700 }}>{rotulo}:</span> {v}</div>;
}

export function MedicoesUltrassom({ o }: { o: OspD }) {
  const u = o.ultrassom;
  return (
    <>
      <div style={{ ...LINHA_MEDICAO, fontWeight: 700 }}>Ultrassom</div>
      {!u ? (
        <Linha rotulo="Leitura" v="— (sem leitura de ultrassom até o fim do relatório)" />
      ) : (
        <>
          <Linha rotulo="Data" v={new Date(u.data).toLocaleDateString("pt-BR")} />
          <Linha rotulo="Modalidade" v={SUBTIPO[u.subtipo] ?? u.subtipo ?? "—"} />
          <Linha rotulo="Nível [dB]" v={numero(u.nivel_db, 1)} />
          <Linha rotulo="Ganho [dB]" v={numero(u.ganho_db, 1)} />
          <Linha rotulo="Distância [cm]" v={numero(u.distancia_cm, 1)} />
          <Linha rotulo="Frequência [kHz]" v={numero(u.frequencia_khz, 1)} />
          <Linha rotulo="Condição" v={CONDICAO[u.condicao] ?? u.condicao} />
        </>
      )}
    </>
  );
}

export const MODULO_ULTRASSOM = criarModuloInspecao({
  chave: "ULTRASSOM",
  Medicoes: MedicoesUltrassom,
  quadros: [],
});
