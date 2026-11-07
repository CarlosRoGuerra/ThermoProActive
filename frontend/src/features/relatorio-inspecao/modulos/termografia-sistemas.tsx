import type { OspD } from "../tipos";
import { LINHA_MEDICAO, criarModuloInspecao } from "./inspecao/modulo";

/* Termografia de sistemas mecânicos (dinâmicos e estáticos) e de processos industriais
   (Anexo I 2.3.2.2.2–4). Mesma família da termografia elétrica, mas sem o bloco de correntes
   nem de carga elétrica: o docs/12 registra que a carga elétrica não se aplica a esses
   sistemas. Glossário e considerações vêm do backend (relatorio_tecnico/termografia_sistemas.py). */

/* Valor ausente sai "—", nunca 0: temperatura não medida não é zero. */
const valor = (v: string | number | null | undefined, casas: number) =>
  v == null || v === ""
    ? "—"
    : Number(v).toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });

function Linha({ rotulo, v }: { rotulo: string; v: string }) {
  return <div style={LINHA_MEDICAO}><span style={{ fontWeight: 700 }}>{rotulo}:</span> {v}</div>;
}

export function MedicoesTermografiaSistema({ o }: { o: OspD }) {
  return (
    <>
      <div style={{ ...LINHA_MEDICAO, fontWeight: 700 }}>Medições</div>
      <Linha rotulo="Temp. Medida [°C]" v={valor(o.temperatura_medida, 1)} />
      <Linha rotulo="Temp. Referência [°C]" v={valor(o.temperatura_referencia, 1)} />
      <Linha rotulo="Temp. Delta [°C]" v={valor(o.delta_t, 1)} />
    </>
  );
}

export const MODULO_TERMOGRAFIA_MECANICA = criarModuloInspecao({
  chave: "TERMOGRAFIA_MECANICA",
  Medicoes: MedicoesTermografiaSistema,
  quadros: [{ tipo: "Imagem térmica", rotulo: "Imagem Térmica" }],
});

export const MODULO_TERMO_PROCESSOS = criarModuloInspecao({
  chave: "TERMO_PROCESSOS",
  Medicoes: MedicoesTermografiaSistema,
  quadros: [{ tipo: "Imagem térmica", rotulo: "Imagem Térmica" }],
});
