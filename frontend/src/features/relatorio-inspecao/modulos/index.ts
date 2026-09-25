import type { DossieShell } from "../tipos";
import type { ModuloRelatorio } from "./contrato";
import { MODULO_ENSAIO_ELETRICO } from "./eletrico";
import { criarModuloInspecao } from "./inspecao/modulo";
import { MODULO_OLEO_ISOLANTE } from "./oleo";
import { MODULO_TERMOGRAFIA } from "./termografia";
import { AmplitudesVibracao, MODULO_VIBRACAO, QUADROS_VIBRACAO, TabelaISO10816 } from "./vibracao";

export type { ConteudoCarta, ModuloRelatorio } from "./contrato";

/**
 * Registro dos módulos técnicos — espelho de
 * `backend/apps/coletas/relatorio_tecnico/modulos.py`. A chave vem do payload
 * (`modulo`), que o backend tira de `TecnologiaAnalise.modulo_tecnico`.
 *
 * Tecnologia nova com relatório próprio: um arquivo em `modulos/` que exporte um
 * `ModuloRelatorio` + uma linha em `MODULOS`. O shell não muda.
 */

/* Tecnologia sem módulo próprio (Sensitiva, Balanceamento, Qualidade de Energia…)
   segue com o layout aprovado de sempre — o da vibração (decisão de 24/09/2026,
   "manter como está"). */
const MODULO_PADRAO = criarModuloInspecao({
  chave: "",
  Medicoes: AmplitudesVibracao,
  quadros: QUADROS_VIBRACAO,
  Normatizacao: TabelaISO10816,
});

/* Cada módulo é tipado pelo payload que o backend monta para a sua chave; o shell
   só conhece o `DossieShell`. A conversão fica aqui, num lugar só: quem garante
   que o payload da chave X tem o formato do módulo X é o backend (mesma chave). */
const registrar = <D extends DossieShell>(m: ModuloRelatorio<D>) => m as unknown as ModuloRelatorio;

const MODULOS: Record<string, ModuloRelatorio> = Object.fromEntries(
  [
    registrar(MODULO_VIBRACAO),
    registrar(MODULO_TERMOGRAFIA),
    registrar(MODULO_OLEO_ISOLANTE),
    registrar(MODULO_ENSAIO_ELETRICO),
  ].map((m) => [m.chave, m]),
);

export function moduloDoRelatorio(d: DossieShell): ModuloRelatorio {
  return MODULOS[d.modulo] ?? registrar(MODULO_PADRAO);
}
