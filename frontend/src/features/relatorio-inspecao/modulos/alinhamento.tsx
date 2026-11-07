import type { AlinhamentoOsp, OspD } from "../tipos";
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

function Fase({ rotulo, f }: { rotulo: string; f: AlinhamentoOsp["antes"] }) {
  if (!f) return <Linha rotulo={rotulo} v="— (não registrado)" />;
  return (
    <>
      <Linha rotulo={`${rotulo} — angular [mm/100 mm]`} v={numero(f.angular_mm_100mm, 3)} />
      <Linha rotulo={`${rotulo} — paralelo [mm]`} v={numero(f.paralelo_mm, 3)} />
      <Linha rotulo={`${rotulo} — rpm`} v={numero(f.rpm, 0)} />
    </>
  );
}

export function MedicoesAlinhamento({ o }: { o: OspD }) {
  const a = o.alinhamento;
  return (
    <>
      <div style={{ ...LINHA_MEDICAO, fontWeight: 700 }}>Alinhamento a laser</div>
      {!a ? (
        <Linha rotulo="Serviço" v="— (sem alinhamento até o fim do relatório)" />
      ) : (
        <>
          <Linha rotulo="Data" v={new Date(a.data).toLocaleDateString("pt-BR")} />
          <Fase rotulo="Antes" f={a.antes} />
          <Fase rotulo="Depois" f={a.depois} />
          <Linha rotulo="Redução angular [%]" v={numero(a.reducao_angular_pct, 1)} />
          <Linha rotulo="Redução paralelo [%]" v={numero(a.reducao_paralelo_pct, 1)} />
          <Linha rotulo="Condição" v={CONDICAO[a.condicao] ?? a.condicao} />
        </>
      )}
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
