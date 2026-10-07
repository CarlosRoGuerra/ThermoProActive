import { Fragment } from "react";
import Link from "next/link";
import { Printer } from "lucide-react";
import type { DossieFluido } from "../tipos";
import { ddmmaaaa } from "../shell/formato";
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
  // No envio do mês (recorte), só as fichas: sem a contracapa do relatório do trimestre.
  const recorte = !!d.recorte?.carregamento;
  return (
    <>
      {!recorte && <Contracapa cab={d.cabecalho} titulo={"Fichas da Análise\nde Fluidos"} />}
      {d.amostras.map((a) => (
        <Fragment key={a.item_id}>
          <FichasAmostra d={d} a={a} />
        </Fragment>
      ))}
      {d.amostras.length === 0 && (
        <section className="pagina bg-white p-6">
          <p className="py-12 text-center text-sm text-slate-500">
            {recorte ? "Nenhuma amostra com desvio nesta coleta — não há fichas a enviar." : "Nenhum equipamento neste relatório."}
          </p>
        </section>
      )}
    </>
  );
}

/**
 * Envio do mês: o relatório é do trimestre (coletas mensais na mesma numeração), e
 * a cada mês só vão as fichas das amostras com desvio (GR-1 a GR-4). Mês sem desvio
 * não gera envio. O relatório completo sai no fim do trimestre.
 */
function PainelEnvioMensal({ d, relatorioId }: { d: DossieFluido; relatorioId: number }) {
  if (!d.envios_mensais?.length) return null;
  return (
    <div>
      <h2 className="text-sm font-semibold text-fg">Envio mensal — fichas com desvio</h2>
      <p className="mt-1 text-xs text-fg-muted">
        Cada coleta do trimestre gera um envio só com as amostras com desvio (GR-1 a GR-4). Sem desvio, não há envio.
        O relatório completo do trimestre é o documento abaixo.
      </p>
      <ul className="mt-3 divide-y divide-border">
        {d.envios_mensais.map((e) => (
          <li key={e.carregamento} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
            <span>
              Coleta de <b>{ddmmaaaa(e.data_coleta)}</b> · {e.amostras} amostra{e.amostras === 1 ? "" : "s"} ·{" "}
              {e.desvios ? <b>{e.desvios} com desvio</b> : "nenhum desvio"}
            </span>
            {e.desvios > 0 ? (
              <Link
                href={`/imprimir/${relatorioId}?carregamento=${e.carregamento}&somente_desvios=1`}
                className="inline-flex items-center gap-1.5 text-xs font-medium text-primary hover:underline"
              >
                <Printer className="h-3.5 w-3.5" /> Fichas com desvio (PDF)
              </Link>
            ) : (
              <span className="text-xs text-fg-muted">Sem envio neste mês</span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

export const MODULO_FLUIDO_LUBRIFICANTE: ModuloRelatorio<DossieFluido> = {
  chave: "FLUIDO_LUBRIFICANTE",
  carta: () => ({ paragrafosDefinicao: [] }),
  Kpis: KpisFluidos,
  KpisComplementares: KpisGerenciaisFluidos,
  Painel: PainelEnvioMensal,
  Fichas,
};
