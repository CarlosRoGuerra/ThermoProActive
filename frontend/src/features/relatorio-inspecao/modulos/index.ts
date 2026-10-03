import { ApiError } from "@/lib/api";
import type { DossieShell } from "../tipos";
import type { ModuloRelatorio } from "./contrato";
import { MODULO_ENSAIO_ELETRICO } from "./eletrico";
import { MODULO_FLUIDO_LUBRIFICANTE } from "./fluido";
import { MODULO_INSPECAO_GENERICA } from "./generico";
import { MODULO_OLEO_ISOLANTE } from "./oleo";
import { MODULO_TERMOGRAFIA } from "./termografia";
import { MODULO_BALANCEAMENTO, MODULO_VIBRACAO } from "./vibracao";

export type { ConteudoCarta, ModuloRelatorio } from "./contrato";

/**
 * Registro dos módulos técnicos — espelho de
 * `backend/apps/coletas/relatorio_tecnico/modulos.py`. A chave vem do payload
 * (`modulo`), que o backend tira de `TecnologiaAnalise.modulo_tecnico`.
 *
 * Não existe módulo "padrão": o backend recusa (409, com o motivo) o relatório
 * de tecnologia sem módulo configurado ou com módulo ainda não implementado, e
 * aqui uma chave desconhecida é erro — nunca o layout da vibração no lugar.
 *
 * Tecnologia nova com relatório próprio: um arquivo em `modulos/` que exporte um
 * `ModuloRelatorio` + uma linha em `MODULOS`. O shell não muda.
 */

/* Cada módulo é tipado pelo payload que o backend monta para a sua chave; o shell
   só conhece o `DossieShell`. A conversão fica aqui, num lugar só: quem garante
   que o payload da chave X tem o formato do módulo X é o backend (mesma chave). */
const registrar = <D extends DossieShell>(m: ModuloRelatorio<D>) => m as unknown as ModuloRelatorio;

const MODULOS: Record<string, ModuloRelatorio> = Object.fromEntries(
  [
    registrar(MODULO_VIBRACAO),
    registrar(MODULO_BALANCEAMENTO),
    registrar(MODULO_TERMOGRAFIA),
    registrar(MODULO_INSPECAO_GENERICA),
    registrar(MODULO_OLEO_ISOLANTE),
    registrar(MODULO_ENSAIO_ELETRICO),
    registrar(MODULO_FLUIDO_LUBRIFICANTE),
  ].map((m) => [m.chave, m]),
);

/** Módulo sem implementação no front (backend mais novo que o front). */
export class ModuloNaoImplementadoNoFront extends Error {
  constructor(chave: string) {
    super(`O relatório do módulo técnico «${chave || "(vazio)"}» não está implementado nesta versão da tela.`);
    this.name = "ModuloNaoImplementadoNoFront";
  }
}

export function moduloDoRelatorio(d: DossieShell): ModuloRelatorio {
  const modulo = MODULOS[d.modulo];
  if (!modulo) throw new ModuloNaoImplementadoNoFront(d.modulo);
  return modulo;
}

/** Existe módulo do front para a chave do payload? (para a tela avisar em vez de quebrar) */
export function temModulo(d: DossieShell): boolean {
  return d.modulo in MODULOS;
}

/**
 * Mensagem de erro ao carregar o dossiê. Tecnologia sem módulo configurado ou
 * com módulo não implementado volta 409 com o motivo — a tela mostra o motivo.
 */
export function mensagemErroDossie(e: unknown, padrao: string): string {
  return e instanceof ApiError && e.status === 409 && e.message ? e.message : padrao;
}
