import type { OspD } from "../tipos";
import { LINHA_MEDICAO, criarModuloInspecao } from "./inspecao/modulo";

/* Resistência de isolação de motores (Anexo I 2.3.2.5.1.1): a folha da OSP mostra o último
   grupo de leituras do motor até o fim do relatório — tensão e temperatura de ensaio, R30,
   R60, R600, DAR, IP e condição (só com critério cadastrado e validado). Glossário e
   considerações vêm do backend (relatorio_tecnico/motor_rxi.py). */

/* Valor ausente sai "—", nunca 0: leitura não feita não é zero. */
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

function Linha({ rotulo, v }: { rotulo: string; v: string }) {
  return <div style={LINHA_MEDICAO}><span style={{ fontWeight: 700 }}>{rotulo}:</span> {v}</div>;
}

export function MedicoesMotorRxi({ o }: { o: OspD }) {
  const m = o.motor_rxi;
  return (
    <>
      <div style={{ ...LINHA_MEDICAO, fontWeight: 700 }}>Isolação do motor</div>
      {!m ? (
        <Linha rotulo="Leitura" v="— (sem ensaio de isolação até o fim do relatório)" />
      ) : (
        <>
          <Linha rotulo="Data" v={new Date(m.data).toLocaleDateString("pt-BR")} />
          <Linha rotulo="Tensão de ensaio [V]" v={numero(m.tensao_ensaio_v, 0)} />
          <Linha rotulo="Temperatura [°C]" v={numero(m.temperatura_c, 1)} />
          <Linha rotulo="R30 [MΩ]" v={numero(m.R30, 1)} />
          <Linha rotulo="R60 [MΩ]" v={numero(m.R60, 1)} />
          <Linha rotulo="R600 [MΩ]" v={numero(m.R600, 1)} />
          <Linha rotulo="DAR (R60/R30)" v={numero(m.DAR, 2)} />
          <Linha rotulo="IP (R600/R60)" v={numero(m.IP, 2)} />
          <Linha rotulo="Condição" v={CONDICAO[m.condicao] ?? m.condicao} />
        </>
      )}
    </>
  );
}

export const MODULO_MOTOR_RXI = criarModuloInspecao({
  chave: "MOTOR_RXI",
  Medicoes: MedicoesMotorRxi,
  quadros: [],
});
