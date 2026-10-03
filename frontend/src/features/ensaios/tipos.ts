/**
 * Contratos da API de ensaios (backend `apps/ensaios`): transformador (óleo
 * isolante e ensaios elétricos) e fluidos lubrificantes/hidráulicos.
 *
 * Decimais dos modelos chegam como string ("40.000000", DRF); os da `avaliacao`
 * — a parte calculada da ficha, a mesma do relatório — chegam como number.
 */
import type {
  EstadoValor,
  FichaFluido,
  FichaIsolacao,
  FichaOhmica,
  FichaRelacao,
  FichaTabela,
  SituacaoEnsaio,
  StatusEnsaio,
  TipoLimite,
} from "@/features/relatorio-inspecao/tipos";

export type ModuloTransformador = "OLEO_ISOLANTE" | "ENSAIO_ELETRICO";
export type ModuloFluido = "FLUIDO_LUBRIFICANTE";
/** Tecnologias cujo lançamento é por equipamento (registro de campo + laudos por ensaio). */
export type ModuloEnsaio = ModuloTransformador | ModuloFluido;

export function ehModuloTransformador(modulo: string | null | undefined): modulo is ModuloTransformador {
  return modulo === "OLEO_ISOLANTE" || modulo === "ENSAIO_ELETRICO";
}

export function ehModuloFluido(modulo: string | null | undefined): modulo is ModuloFluido {
  return modulo === "FLUIDO_LUBRIFICANTE";
}

export function ehModuloEnsaio(modulo: string | null | undefined): modulo is ModuloEnsaio {
  return ehModuloTransformador(modulo) || ehModuloFluido(modulo);
}

/* ------------------------------ Catálogos ------------------------------- */
export type ParametroCatalogo = {
  id: number;
  ensaio: number;
  codigo: string;
  nome: string;
  simbolo: string;
  grupo: string;
  unidade: string;
  norma: string;
  tipo_limite: TipoLimite;
  limite: string | null;
  limite_superior: string | null;
  referencia_texto: string;
  casas_decimais: number;
  calculado: boolean;
  no_grafico: boolean;
  ordem: number;
};

export type EnsaioCatalogo = {
  id: number;
  sigla: string;
  nome: string;
  modulo: ModuloEnsaio;
  titulo_ficha: string;
  ordem: number;
  rotulo_conclusao: string;
  rotulo_informacoes: string;
  rotulo_proxima: string;
  nota_tecnica: string;
  parametros: ParametroCatalogo[];
  /** Fluidos: aplicações em que o ensaio vem marcado por padrão na coleta. */
  padrao_em: AplicacaoFluido[];
};

export type Opcao = { id: number; nome: string };
export type ItemChecklist = { id: number; nome: string; grupo: "GERAL" | "TANQUE_EXPANSAO"; ordem: number };
export type InstrumentoOpcao = { id: number; tipo: string; marca: string; modelo: string; numero_serie: string };

/* ----------------------- Registro de campo ------------------------------ */
export type EstadoChecklist = "OK" | "NC" | "NA";
export type LinhaChecklist = { item_checklist: number; estado: EstadoChecklist; observacao: string };

export type ColetaOleoApi = {
  id: number;
  item: number;
  data_coleta: string;
  amostrador: string;
  temperatura_amostra_c: string | null;
  temperatura_ambiente_c: string | null;
  umidade_relativa_pct: string | null;
  ponto_coleta: number | null;
  tipo_fluido: number | null;
  ensaios: number[];
  inspecao_visual: (LinhaChecklist & { id: number })[];
};

export type RegistroEletricoApi = {
  id: number;
  item: number;
  data_ensaio: string;
  analista: string;
  tap: string;
  tensao_tap_v: string | null;
  temperatura_oleo_c: string | null;
  temperatura_ambiente_c: string | null;
  umidade_relativa_pct: string | null;
  ensaios: number[];
};

export type AplicacaoFluido = "LUBRIFICANTE" | "HIDRAULICO";
export const APLICACOES: { valor: AplicacaoFluido; label: string }[] = [
  { valor: "LUBRIFICANTE", label: "Lubrificante" },
  { valor: "HIDRAULICO", label: "Hidráulico" },
];
export type CondicaoOperacional = "" | "EM_OPERACAO" | "APOS_PARADA" | "PARADO";
export const CONDICOES_OPERACIONAIS: { valor: Exclude<CondicaoOperacional, "">; label: string }[] = [
  { valor: "EM_OPERACAO", label: "Em operação" },
  { valor: "APOS_PARADA", label: "Logo após a parada" },
  { valor: "PARADO", label: "Parado" },
];

export type ProdutoFluido = {
  id: number; nome: string; fabricante: string; aplicacao: AplicacaoFluido | ""; grau_viscosidade: string;
  viscosidade_40c_cst: string | null;
};

export type ColetaFluidoApi = {
  id: number;
  item: number;
  aplicacao: AplicacaoFluido;
  produto: number | null;
  fluido_informado: string;
  grau_viscosidade: string;
  identificacao_amostra: string;
  data_coleta: string;
  amostrador: string;
  ponto_coleta: number | null;
  temperatura_fluido_c: string | null;
  temperatura_ambiente_c: string | null;
  condicao_operacional: CondicaoOperacional;
  horas_equipamento: string | null;
  horas_fluido: string | null;
  data_ultima_troca: string | null;
  complemento_recente: boolean | null;
  volume_complemento_l: string | null;
  troca_filtro_recente: boolean | null;
  intervencao_recente: string;
  observacoes: string;
  ensaios: number[];
};

/* ------------------------------ Resultados ------------------------------ */
export type ValorApi = {
  parametro: number;
  parametro_codigo?: string;
  serie: string;
  posicao: string | null;
  valor: string | null;
  valor_texto: string;
  estado: Exclude<EstadoValor, "">;
  limite_deteccao: string | null;
  /** Método/norma do laboratório, quando difere da norma do catálogo. */
  metodo?: string;
};

export type Criticidade = "" | "ROTINA" | "ALERTA" | "CRITICA";

/** Fluidos: a ficha calculada (referência, estado e tendência por parâmetro; código ISO e meta). */
export type AvaliacaoFluido = Pick<
  FichaFluido,
  "tipo" | "status" | "status_rotulo" | "avaliados" | "fora" | "alertas" | "criticas" | "sem_referencia" |
  "campanhas" | "linhas" | "grupos" | "codigos" | "meta" | "situacao_meta" | "excesso_meta"
>;

export function ehAvaliacaoFluido(a: Avaliacao | AvaliacaoFluido | null | undefined): a is AvaliacaoFluido {
  return !!a && "linhas" in a;
}

/** Parte calculada da ficha (mesmas regras do relatório), devolvida ao salvar. */
export type Avaliacao = {
  tipo: "TABELA" | "RXT" | "RXI" | "RXO";
  status: StatusEnsaio;
  status_rotulo: string;
  avaliados: number;
  fora: number;
} & Partial<Pick<FichaTabela, "indicadores" | "gp_estimado">> & {
  campanhas?: (FichaTabela["campanhas"][number] | FichaRelacao["campanhas"][number] | FichaOhmica["campanhas"][number])[];
} & Partial<Pick<FichaRelacao, "limite">> &
  Partial<Pick<FichaIsolacao, "series" | "tempos" | "criterio_ip">>;

export type ResultadoApi = {
  id: number;
  item: number;
  ensaio: number;
  ensaio_sigla: string;
  situacao: SituacaoEnsaio;
  numero_laudo: string;
  criticidade: Criticidade;
  data_analise: string | null;
  data_proxima: string | null;
  conclusao: string;
  recomendacao: string;
  informacoes_adicionais: string;
  instrumento: number | null;
  laboratorio: string;
  origem: string;
  valores: ValorApi[];
  avaliacao: Avaliacao | AvaliacaoFluido;
};

/* ------------------------- Fila do lançamento --------------------------- */
export type EnsaioNaFila = { sigla: string; nome: string; solicitado: boolean; situacao: SituacaoEnsaio | null };

/** Um equipamento numa rota de ensaios — base comum de transformador e fluidos. */
export type ItemEnsaio = Omit<TransformadorInspecao, "modulo" | "possui_tanque_expansao"> & { modulo: ModuloEnsaio };

/** Um equipamento numa rota de fluidos lubrificantes/hidráulicos (`/fluidos-inspecao/`). */
export type FluidoInspecao = ItemEnsaio & {
  modulo: ModuloFluido;
  aplicacao: AplicacaoFluido | null;
  fluido: string | null;
  tipo_equipamento_nome: string | null;
};

/** Um transformador numa rota de óleo ou de ensaios elétricos (`/transformadores-inspecao/`). */
export type TransformadorInspecao = {
  id: number;
  carregamento: number;
  carregamento_status: "EM_CAMPO" | "TRANSFERIDA" | "DESCARTADA";
  relatorio: number | null;
  numero: string | null;
  cliente: number;
  cliente_nome: string;
  tecnologia: number;
  tecnologia_nome: string;
  modulo: ModuloTransformador;
  data_coleta: string;
  analista_nome: string;
  equipamento: number;
  equipamento_tag: string;
  equipamento_nome: string;
  area_nome: string;
  setor_nome: string;
  condicao: number | null;
  condicao_sigla: string | null;
  condicao_nome: string | null;
  possui_tanque_expansao: boolean | null;
  registro: { id: number; data: string | null } | null;
  ensaios: EnsaioNaFila[];
  /** Ensaios solicitados que ainda não têm laudo (realizado, não coletado ou não realizado). */
  pendentes: number;
};

export const SITUACOES: { valor: SituacaoEnsaio; label: string }[] = [
  { valor: "REALIZADO", label: "Realizado" },
  { valor: "SEM_RESULTADO", label: "Aguardando resultado" },
  { valor: "NAO_COLETADO", label: "Amostra não coletada" },
  { valor: "NAO_REALIZADO", label: "Não realizado" },
];

export const CRITICIDADES: { valor: Criticidade; label: string }[] = [
  { valor: "", label: "—" },
  { valor: "ROTINA", label: "Rotina" },
  { valor: "ALERTA", label: "Alerta" },
  { valor: "CRITICA", label: "Crítica" },
];

/** Como a ficha organiza o ensaio: tabela de parâmetros ou um dos elétricos. */
export function tipoDoEnsaio(sigla: string, modulo?: ModuloEnsaio): "TABELA" | "RXT" | "RXI" | "RXO" {
  if (modulo && modulo !== "ENSAIO_ELETRICO") return "TABELA";
  return sigla === "RXT" || sigla === "RXI" || sigla === "RXO" ? sigla : "TABELA";
}
