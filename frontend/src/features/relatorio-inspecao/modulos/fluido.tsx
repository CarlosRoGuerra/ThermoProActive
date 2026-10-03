import { Fragment } from "react";
import type { DossieFluido } from "../tipos";
import { Contracapa } from "../shell/folhas";
import type { ModuloRelatorio } from "./contrato";
import { FichasAmostra } from "./fluidos/fichas";
import { KpisGerenciaisFluidos } from "./fluidos/gerenciais";
import { KpisFluidos } from "./fluidos/kpis";

/* Fluidos lubrificantes e hidráulicos (FQ, EF e CP). Mesmo shell das outras
   tecnologias; a carta (conteúdo, glossário FQ/EF/CP, considerações e o resumo
   do item 7) vem do backend — apps/ensaios/carta.py e relatorio_fluidos.py.
   Sem tabela normativa de outra técnica no item 5. */

function Fichas({ d }: { d: DossieFluido }) {
  return (
    <>
      <Contracapa cab={d.cabecalho} titulo={"Fichas da Análise\nde Fluidos"} />
      {d.amostras.map((a) => (
        <Fragment key={a.item_id}>
          <FichasAmostra d={d} a={a} />
        </Fragment>
      ))}
      {d.amostras.length === 0 && (
        <section className="pagina bg-white p-6">
          <p className="py-12 text-center text-sm text-slate-500">Nenhum equipamento neste relatório.</p>
        </section>
      )}
    </>
  );
}

export const MODULO_FLUIDO_LUBRIFICANTE: ModuloRelatorio<DossieFluido> = {
  chave: "FLUIDO_LUBRIFICANTE",
  carta: () => ({ paragrafosDefinicao: [] }),
  Kpis: KpisFluidos,
  KpisComplementares: KpisGerenciaisFluidos,
  Fichas,
};
