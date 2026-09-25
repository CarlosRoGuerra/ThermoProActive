import { Fragment, type ComponentType } from "react";
import type { Cabecalho, DossieTransformador, FichaEnsaio, KpisTransformador, Transformador } from "../../tipos";
import { Contracapa } from "../../shell/folhas";
import type { ModuloRelatorio } from "../contrato";
import { FichaIsolacao, FichaOhmica, FichaRelacao } from "./fichas-eletricas";
import { FichaParametros } from "./fichas-oleo";
import { KpisTransformadores } from "./kpis";

/**
 * Família "transformador": um relatório por família de ensaios (óleo isolante,
 * ensaios elétricos), com a sequência de fichas por transformador —
 * registro de campo → uma ficha por ensaio. Cada módulo da família declara só a
 * ficha de registro, os rótulos e o que vai no terceiro quadro de texto.
 * Os textos da carta (inclusive o resumo do item 7) vêm do backend.
 */
export type ConfigTransformador = {
  /** Mesma chave de `TecnologiaAnalise.modulo_tecnico`. */
  chave: string;
  /** Contracapa das fichas (Seção D). */
  tituloFichas: string;
  /** Ficha 1 de cada transformador: registro da coleta / dos ensaios. */
  Registro: ComponentType<{ d: DossieTransformador; t: Transformador }>;
  /** Terceiro quadro de texto da ficha (informações adicionais ou instrumentação). */
  informacoes: (f: FichaEnsaio) => string;
  /** Indicadores próprios do módulo nos KPIs. */
  KpisExtras?: ComponentType<{ k: KpisTransformador }>;
};

function FichaDoEnsaio({ cab, f, t, informacoes }: { cab: Cabecalho; f: FichaEnsaio; t: Transformador; informacoes: string }) {
  switch (f.tipo) {
    case "RXT": return <FichaRelacao cab={cab} f={f} t={t} informacoes={informacoes} />;
    case "RXI": return <FichaIsolacao cab={cab} f={f} informacoes={informacoes} />;
    case "RXO": return <FichaOhmica cab={cab} f={f} t={t} informacoes={informacoes} />;
    default: return <FichaParametros cab={cab} f={f} informacoes={informacoes} />;
  }
}

export function criarModuloTransformador(cfg: ConfigTransformador): ModuloRelatorio<DossieTransformador> {
  const { Registro } = cfg;
  function Fichas({ d }: { d: DossieTransformador }) {
    const cab = d.cabecalho;
    return (
      <>
        <Contracapa cab={cab} titulo={cfg.tituloFichas} />
        {d.transformadores.map((t) => (
          <Fragment key={t.item_id}>
            <Registro d={d} t={t} />
            {t.ensaios.map((f) => (
              <FichaDoEnsaio key={f.sigla} cab={cab} f={f} t={t} informacoes={cfg.informacoes(f)} />
            ))}
          </Fragment>
        ))}
        {d.transformadores.length === 0 && (
          <section className="pagina bg-white p-6">
            <p className="py-12 text-center text-sm text-slate-500">Nenhum transformador neste relatório.</p>
          </section>
        )}
      </>
    );
  }
  function Kpis({ d }: { d: DossieTransformador }) {
    return <KpisTransformadores d={d} Extras={cfg.KpisExtras} />;
  }
  return {
    chave: cfg.chave,
    carta: () => ({ paragrafosDefinicao: [] }),
    Kpis,
    Fichas,
  };
}
