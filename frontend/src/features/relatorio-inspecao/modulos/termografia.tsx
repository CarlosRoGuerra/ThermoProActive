import type { OspD } from "../tipos";
import { LINHA_MEDICAO, criarModuloInspecao } from "./inspecao/modulo";

/* Termografia em sistemas elétricos — segue o relatório de referência do cliente
   (RT.TE-2026.05.18.02326): na OSP, a imagem térmica à esquerda e a foto do equipamento
   à direita; abaixo, as medições nos três grupos do RT.TE (temperaturas | correntes |
   carga e temperaturas corrigidas). Sem tabela normativa de vibração na carta; o
   glossário com os critérios de ΔT, o fluxo de trabalho e as considerações vêm do
   backend (relatorio_tecnico/termografia.py). */

/* Valor ausente sai "—", nunca 0: corrente ou carga não medida não é zero. */
const valor = (v: string | number | null | undefined, casas: number) =>
  v == null || v === ""
    ? "—"
    : Number(v).toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });

function Linha({ rotulo, v }: { rotulo: string; v: string }) {
  return <div style={LINHA_MEDICAO}><span style={{ fontWeight: 700 }}>{rotulo}:</span> {v}</div>;
}

const DIVISOR = { borderLeft: "0.2mm solid #cbd5e1", paddingLeft: "22mm" } as const;

/* Mesmas grandezas e a mesma ordem da OSP do RT.TE. I(N) = corrente nominal (glossário
   6.2.2). T. Medida Corrigida e T. Delta Corrigida são a correção pela carga (C.T.M.,
   6.1.5): digitadas na análise até a fórmula do cliente entrar no sistema. */
export function MedicoesTermografia({ o }: { o: OspD }) {
  const [nominal, r, s, t] = o.corrente;
  return (
    <div style={{ width: "190mm", display: "grid", gridTemplateColumns: "63mm 63mm 64mm" }}>
      <div>
        <Linha rotulo="Temp. Medida [°C]" v={valor(o.temperatura_medida, 1)} />
        <Linha rotulo="Temp. Referência [°C]" v={valor(o.temperatura_referencia, 1)} />
        <Linha rotulo="Temp. Delta [°C]" v={valor(o.delta_t, 1)} />
      </div>
      <div style={DIVISOR}>
        <Linha rotulo="I(R) [A]" v={valor(r, 2)} />
        <Linha rotulo="I(S) [A]" v={valor(s, 2)} />
        <Linha rotulo="I(T) [A]" v={valor(t, 2)} />
        <Linha rotulo="I(N) [A]" v={valor(nominal, 2)} />
      </div>
      <div style={{ ...DIVISOR, paddingLeft: "14mm" }}>
        <Linha rotulo="% Carga" v={valor(o.carga_percentual, 1)} />
        <Linha rotulo="T. Medida Corrigida [°C]" v={valor(o.temperatura_medida_corrigida, 1)} />
        <Linha rotulo="T. Delta Corrigida [°C]" v={valor(o.delta_t_corrigido, 1)} />
      </div>
    </div>
  );
}

export const MODULO_TERMOGRAFIA = criarModuloInspecao({
  chave: "TERMOGRAFIA",
  Medicoes: MedicoesTermografia,
  quadros: [{ tipo: "Imagem térmica", rotulo: "Imagem Térmica" }],
  imagensLadoALado: true,
});
