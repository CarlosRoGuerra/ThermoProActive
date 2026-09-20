/**
 * Progresso de uma análise de campo — derivado dos ItemInspecao.
 *
 * Regra do sistema (backend `Carregamento.itens_pendentes`): um equipamento está
 * CONCLUÍDO quando tem condição definida. É essa mesma regra que libera a
 * transferência, então a barra da tela e o botão de transferir nunca discordam.
 *
 * Os estados por equipamento são DERIVADOS para a interface — não existem no
 * banco e não substituem `StatusCarregamento` (EM_CAMPO / TRANSFERIDA /
 * DESCARTADA), que continua sendo o estado real do carregamento.
 */
import type { CarregamentoLista, ItemInspecao } from "@/lib/types";

export type EstadoItem =
  /** Sem condição definida: bloqueia a transferência. */
  | "PENDENTE"
  /** Condição definida que não exige ação — equipamento liberado. */
  | "SEM_ACAO"
  /** Condição definida, exige ação e já tem análise registrada. */
  | "COM_ACHADO"
  /** Condição exige ação, mas nenhuma análise foi registrada ainda. */
  | "INCOMPLETO";

export const ROTULO_ESTADO: Record<EstadoItem, string> = {
  PENDENTE: "Pendente",
  SEM_ACAO: "Sem ação",
  COM_ACHADO: "Com achado",
  INCOMPLETO: "Falta a análise",
};

export const EXPLICACAO_ESTADO: Record<EstadoItem, string> = {
  PENDENTE: "Defina a condição deste equipamento antes de concluir a análise.",
  SEM_ACAO: "Equipamento inspecionado sem necessidade de ação.",
  COM_ACHADO: "Análise registrada — segue para a Análise final.",
  INCOMPLETO: "A condição escolhida exige ação: registre ao menos uma análise.",
};

/** Ordem de urgência: o que trava a transferência aparece primeiro. */
export const ORDEM_ESTADO: EstadoItem[] = ["PENDENTE", "INCOMPLETO", "COM_ACHADO", "SEM_ACAO"];

export function pesoEstado(estado: EstadoItem): number {
  return ORDEM_ESTADO.indexOf(estado);
}

/**
 * Estado de um equipamento na folha de campo.
 *
 * `gera_acao` vem do catálogo Condicao — não é enum do frontend.
 */
export function estadoDoItem(item: ItemInspecao): EstadoItem {
  if (item.condicao == null) return "PENDENTE";
  const exigeAcao = !!item.condicao_gera_acao;
  const temAchado = (item.achados?.length ?? 0) > 0;
  if (!exigeAcao) return temAchado ? "COM_ACHADO" : "SEM_ACAO";
  return temAchado ? "COM_ACHADO" : "INCOMPLETO";
}

export type Progresso = {
  total: number;
  concluidos: number;
  pendentes: number;
  incompletos: number;
  comAchado: number;
  achados: number;
  percentual: number;
};

/** Progresso a partir dos itens (folha de campo aberta). */
export function progressoDosItens(itens: ItemInspecao[]): Progresso {
  const total = itens.length;
  let pendentes = 0;
  let incompletos = 0;
  let comAchado = 0;
  let achados = 0;

  for (const item of itens) {
    achados += item.achados?.length ?? 0;
    const estado = estadoDoItem(item);
    if (estado === "PENDENTE") pendentes += 1;
    else if (estado === "INCOMPLETO") incompletos += 1;
    else if (estado === "COM_ACHADO") comAchado += 1;
  }

  const concluidos = total - pendentes;
  return {
    total,
    concluidos,
    pendentes,
    incompletos,
    comAchado,
    achados,
    percentual: total > 0 ? Math.round((concluidos / total) * 100) : 0,
  };
}

/** Progresso a partir da listagem (onde só existem as contagens do servidor). */
export function progressoDaLista(c: CarregamentoLista): Progresso {
  const total = c.qtd_itens ?? 0;
  const pendentes = c.qtd_pendentes ?? 0;
  const concluidos = Math.max(0, total - pendentes);
  return {
    total,
    concluidos,
    pendentes,
    incompletos: 0, // a listagem não distingue: exigiria carregar os achados
    comAchado: 0,
    achados: c.qtd_achados ?? 0,
    percentual: total > 0 ? Math.round((concluidos / total) * 100) : 0,
  };
}

/* ==========================================================================
   Agrupamento da listagem em visões operacionais.
   --------------------------------------------------------------------------
   São recortes de UX sobre o status real, não status novos:
     em_andamento     EM_CAMPO com pelo menos um equipamento já concluído
     nao_iniciadas    EM_CAMPO sem nenhum equipamento concluído
     concluidas       EM_CAMPO com tudo preenchido — pronta para transferir
     transferidas     TRANSFERIDA
   ========================================================================== */

export type VisaoCampo = "em_andamento" | "nao_iniciadas" | "concluidas" | "transferidas";

export function visaoDoCarregamento(c: CarregamentoLista): VisaoCampo {
  if (c.status !== "EM_CAMPO") return "transferidas";
  const total = c.qtd_itens ?? 0;
  const pendentes = c.qtd_pendentes ?? 0;
  if (total > 0 && pendentes === 0) return "concluidas";
  if (pendentes === total) return "nao_iniciadas";
  return "em_andamento";
}

export const ROTULO_VISAO: Record<VisaoCampo, string> = {
  em_andamento: "Em andamento",
  nao_iniciadas: "Não iniciadas",
  concluidas: "Prontas para transferir",
  transferidas: "Transferidas",
};
