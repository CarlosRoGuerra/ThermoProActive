import type { OspD } from "../tipos";
import { LINHA_MEDICAO, criarModuloInspecao } from "./inspecao/modulo";

/* Espessura (Anexo I 2.3.2.7): a folha da OSP mostra a última medição do equipamento
   até o fim do relatório — nominal, medida, perda, taxa de corrosão e condição. A
   condição só aparece com limite cadastrado e validado; sem ele, fica "pendente".
   Glossário e considerações vêm do backend (relatorio_tecnico/espessura.py). */

/* Valor ausente sai "—", nunca 0. */
const numero = (v: string | null | undefined, casas: number) =>
  v == null || v === ""
    ? "—"
    : Number(v).toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });

const CONDICAO: Record<string, string> = {
  NORMAL: "Normal",
  ALERTA: "Alerta",
  CRITICO: "Crítico",
  PENDENTE: "Pendente (sem limite validado)",
};

function Linha({ rotulo, v }: { rotulo: string; v: string }) {
  return <div style={LINHA_MEDICAO}><span style={{ fontWeight: 700 }}>{rotulo}:</span> {v}</div>;
}

export function MedicoesEspessura({ o }: { o: OspD }) {
  const e = o.espessura;
  return (
    <>
      <div style={{ ...LINHA_MEDICAO, fontWeight: 700 }}>Espessura</div>
      {!e ? (
        <Linha rotulo="Leitura" v="— (sem medição de espessura até o fim do relatório)" />
      ) : (
        <>
          <Linha rotulo="Data" v={new Date(e.data).toLocaleDateString("pt-BR")} />
          <Linha rotulo="Material" v={e.material || "—"} />
          <Linha rotulo="Nominal [mm]" v={numero(e.nominal_mm, 2)} />
          <Linha rotulo="Medida [mm]" v={numero(e.medida_mm, 2)} />
          <Linha rotulo="Perda [%]" v={numero(e.perda_percentual, 2)} />
          <Linha rotulo="Taxa de corrosão [mm/ano]" v={numero(e.taxa_mm_ano, 4)} />
          <Linha rotulo="Condição" v={CONDICAO[e.condicao] ?? e.condicao} />
        </>
      )}
    </>
  );
}

export const MODULO_ESPESSURA = criarModuloInspecao({
  chave: "ESPESSURA",
  Medicoes: MedicoesEspessura,
  quadros: [],
});
