/**
 * Contratos da API de ensaios de transformador (backend `apps/ensaios`).
 *
 * Decimais dos modelos chegam como string ("40.000000", DRF); os da `avaliacao`
 * — a parte calculada da ficha, a mesma do relatório — chegam como number.
 */
import type {
  EstadoValor,
  FichaIsolacao,
  FichaOhmica,
  FichaRelacao,
  FichaTabela,
  SituacaoEnsaio,
  StatusEnsaio,
  TipoLimite,
} from "@/features/relatorio-inspecao/tipos";

export type ModuloTransformador = "OLEO_ISOLANTE" | "ENSAIO_ELETRICO";

export function ehModuloTransformador(modulo: string | null | undefined): modulo is ModuloTransformador {
  return modulo === "OLEO_ISOLANTE" || modulo === "ENSAIO_ELETRICO";
}

/* ------------------------------ Catálogos ------------------------------- */
export type ParametroCatalogo = {
  id: number;
  ensaio: number;
  codigo: string;
  nome: string;
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
  modulo: ModuloTransformador;
  titulo_ficha: string;
  ordem: number;
  rotulo_conclusao: string;
  rotulo_informacoes: string;
  rotulo_proxima: string;
  nota_tecnica: string;
  parametros: ParametroCatalogo[];
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
};

export type Criticidade = "" | "ROTINA" | "ALERTA" | "CRITICA";

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
  origem: string;
  valores: ValorApi[];
  avaliacao: Avaliacao;
};

/* ------------------------- Fila do lançamento --------------------------- */
export type EnsaioNaFila = { sigla: string; nome: string; solicitado: boolean; situacao: SituacaoEnsaio | null };

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
export function tipoDoEnsaio(sigla: string): "TABELA" | "RXT" | "RXI" | "RXO" {
  return sigla === "RXT" || sigla === "RXI" || sigla === "RXO" ? sigla : "TABELA";
}
