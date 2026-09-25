import type { OspD } from "../tipos";
import { LINHA_MEDICAO, criarModuloInspecao } from "./inspecao/modulo";

/* Termografia: medições da OSP conforme o relatório de referência do cliente
   (RT.TE-2026.02.12.02307) e a imagem térmica no quadro da direita (decisão de
   24/09/2026). Sem tabela normativa de vibração na carta; o glossário com os
   critérios de ΔT e as considerações vêm do backend (relatorio_tecnico/termografia.py). */

/* Valor ausente sai "—", nunca 0: corrente ou carga não medida não é zero. */
const valor = (v: string | number | null | undefined, casas: number) =>
  v == null || v === ""
    ? "—"
    : Number(v).toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });

function Linha({ rotulo, v }: { rotulo: string; v: string }) {
  return <div style={LINHA_MEDICAO}><span style={{ fontWeight: 700 }}>{rotulo}:</span> {v}</div>;
}

/* Mesmas grandezas da OSP do RT.TE, em duas colunas dentro dos 90mm da
   coluna esquerda: temperaturas | correntes por fase. I(N) = corrente nominal
   (glossário 6.2.2), a confirmar com o cliente. */
export function MedicoesTermografia({ o }: { o: OspD }) {
  const [nominal, r, s, t] = o.corrente;
  return (
    <>
      <div style={{ ...LINHA_MEDICAO, fontWeight: 700 }}>Medições</div>
      <div style={{ display: "grid", gridTemplateColumns: "58mm 32mm" }}>
        <div>
          <Linha rotulo="Temp. Medida [°C]" v={valor(o.temperatura_medida, 1)} />
          <Linha rotulo="Temp. Referência [°C]" v={valor(o.temperatura_referencia, 1)} />
          <Linha rotulo="Temp. Delta [°C]" v={valor(o.delta_t, 1)} />
          <Linha rotulo="% Carga" v={valor(o.carga_percentual, 1)} />
          <Linha rotulo="T. Medida Corrigida [°C]" v={valor(o.temperatura_medida_corrigida, 1)} />
          <Linha rotulo="T. Delta Corrigida [°C]" v={valor(o.delta_t_corrigido, 1)} />
        </div>
        <div>
          <Linha rotulo="I(R) [A]" v={valor(r, 2)} />
          <Linha rotulo="I(S) [A]" v={valor(s, 2)} />
          <Linha rotulo="I(T) [A]" v={valor(t, 2)} />
          <Linha rotulo="I(N) [A]" v={valor(nominal, 2)} />
        </div>
      </div>
    </>
  );
}

export const MODULO_TERMOGRAFIA = criarModuloInspecao({
  chave: "TERMOGRAFIA",
  Medicoes: MedicoesTermografia,
  quadros: [{ tipo: "Imagem térmica", rotulo: "Imagem Térmica" }],
});
