import type { DossieInspecao } from "../../tipos";
import type { ModuloRelatorio } from "../contrato";
import { paragrafoAnomalias } from "./carta";
import { FichasOsp, type TecnologiaInspecao } from "./folha-osp";
import { KpisInspecao } from "./kpis";

export { LINHA_MEDICAO, type QuadroImagem, type TecnologiaInspecao } from "./folha-osp";

/**
 * Família "inspeção por rota": KPIs de condições/anomalias/OSPs, uma folha de OSP
 * por análise e a carta do modelo Word (textos no backend). Cada tecnologia da
 * família (vibração, termografia…) só declara as medições, os quadros de imagem
 * e a tabela normativa.
 */
export function criarModuloInspecao(tecnologia: TecnologiaInspecao): ModuloRelatorio<DossieInspecao> {
  function Fichas({ d }: { d: DossieInspecao }) {
    return <FichasOsp d={d} tecnologia={tecnologia} />;
  }
  return {
    chave: tecnologia.chave,
    carta: (d) => ({
      Normatizacao: tecnologia.Normatizacao,
      paragrafosDefinicao: [paragrafoAnomalias(d)],
    }),
    Kpis: KpisInspecao,
    Fichas,
  };
}
