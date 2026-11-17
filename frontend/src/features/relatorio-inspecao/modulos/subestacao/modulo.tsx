import { Fragment } from "react";
import { Contracapa } from "../../shell/folhas";
import type { ModuloRelatorio } from "../contrato";
import { FichaEnsaioSubestacao, RegistroSubestacaoFicha } from "./fichas";
import { KpisSubestacao } from "./kpis";
import type { DossieSubestacao } from "./tipos";

/* ==========================================================================
   Família "subestação": um relatório por tipo de equipamento (TC, TP, DJ, CS, RP),
   com a sequência de fichas por equipamento — registro e dados de placa → uma
   ficha por ensaio. Espelho de `ModuloEnsaioSubestacao` (apps/ensaios/relatorio_subestacao.py).
   A carta vem do backend (textos_carta); aqui só se desenha.
   ========================================================================== */

export type ConfigSubestacao = {
  /** Mesma chave de `TecnologiaAnalise.modulo_tecnico`. */
  chave: string;
  /** Nome do equipamento em caixa alta, para o título do registro. */
  rotuloCaixa: string;
  /** Contracapa das fichas (Seção D). */
  tituloFichas: string;
};

export function criarModuloSubestacao(cfg: ConfigSubestacao): ModuloRelatorio<DossieSubestacao> {
  function Fichas({ d }: { d: DossieSubestacao }) {
    const cab = d.cabecalho;
    return (
      <>
        <Contracapa cab={cab} titulo={cfg.tituloFichas} />
        {d.equipamentos.map((e) => (
          <Fragment key={e.item_id}>
            <RegistroSubestacaoFicha d={d} e={e}
              titulo={`REGISTRO DE DADOS DOS ENSAIOS ELÉTRICOS — ${cfg.rotuloCaixa}`} />
            {e.ensaios.map((f) => (
              <FichaEnsaioSubestacao key={f.sigla} cab={cab} f={f} />
            ))}
          </Fragment>
        ))}
        {d.equipamentos.length === 0 && (
          <section className="pagina bg-white p-6">
            <p className="py-12 text-center text-sm text-slate-500">Nenhum equipamento neste relatório.</p>
          </section>
        )}
      </>
    );
  }
  function Kpis({ d }: { d: DossieSubestacao }) {
    return <KpisSubestacao d={d} />;
  }
  return {
    chave: cfg.chave,
    carta: () => ({ paragrafosDefinicao: [] }),
    Kpis,
    Fichas,
  };
}

export const MODULO_ENSAIO_TC = criarModuloSubestacao({
  chave: "ENSAIO_ELETRICO_TC", rotuloCaixa: "TRANSFORMADOR DE CORRENTE",
  tituloFichas: "Fichas dos\nEnsaios Elétricos de TC",
});
export const MODULO_ENSAIO_TP = criarModuloSubestacao({
  chave: "ENSAIO_ELETRICO_TP", rotuloCaixa: "TRANSFORMADOR DE POTENCIAL",
  tituloFichas: "Fichas dos\nEnsaios Elétricos de TP",
});
export const MODULO_ENSAIO_DJ = criarModuloSubestacao({
  chave: "ENSAIO_ELETRICO_DJ", rotuloCaixa: "DISJUNTOR",
  tituloFichas: "Fichas dos\nEnsaios Elétricos de Disjuntor",
});
export const MODULO_ENSAIO_CS = criarModuloSubestacao({
  chave: "ENSAIO_ELETRICO_CS", rotuloCaixa: "CHAVE SECCIONADORA",
  tituloFichas: "Fichas dos\nEnsaios Elétricos de Chave Seccionadora",
});
export const MODULO_ENSAIO_RP = criarModuloSubestacao({
  chave: "ENSAIO_ELETRICO_RP", rotuloCaixa: "RELÉ DE PROTEÇÃO",
  tituloFichas: "Fichas dos\nEnsaios Elétricos de Relé de Proteção",
});
