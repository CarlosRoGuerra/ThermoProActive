import type { ComponentType } from "react";
import type { DossieShell } from "../tipos";

/**
 * Contrato entre o shell do relatório e o módulo técnico de uma tecnologia.
 *
 * O shell desenha a sequência comum — CAPA → CARTA AO CLIENTE → KPIs →
 * RELAÇÃO DE EQUIPAMENTOS → FICHAS TÉCNICAS → CONCLUSÕES — com as folhas A4, o
 * timbrado, a paginação e o PDF. O módulo entrega só o que depende da técnica.
 * Os textos da carta (seções, glossário, considerações e, quando o backend os
 * gera, os parágrafos do item 7) vêm prontos no payload (`d.carta`); aqui ficam
 * só o que se desenha ou se calcula no front.
 *
 * `D` é o payload que o backend monta para a chave do módulo (ex.:
 * `DossieInspecao`, `DossieTransformador`). Registro em `./index.ts`; espelho
 * no backend em `apps/coletas/relatorio_tecnico/modulos.py`.
 */

/** Encaixes do módulo na Carta ao Cliente. */
export type ConteudoCarta = {
  /** Item 5 — tabela normativa da tecnologia (ex.: severidade ISO‑10816 na vibração). */
  Normatizacao?: ComponentType;
  /** Item 7 — parágrafos gerados no front a partir do que o módulo apurou (depois do alcance do relatório). */
  paragrafosDefinicao: string[];
};

export type ModuloRelatorio<D extends DossieShell = DossieShell> = {
  /** Mesma chave de `TecnologiaAnalise.modulo_tecnico` ("" = layout padrão). */
  chave: string;
  carta: (d: D) => ConteudoCarta;
  /** Conteúdo dos KPIs — a contracapa e a folha são do shell. */
  Kpis: ComponentType<{ d: D }>;
  /** Fichas técnicas, depois da Relação de Equipamentos, com as próprias contracapas. */
  Fichas: ComponentType<{ d: D }>;
  /** Conclusões consolidadas no fim do relatório, se o módulo tiver (nenhum tem hoje). */
  Conclusoes?: ComponentType<{ d: D }>;
};
