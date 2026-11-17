import type { Dist, DossieShell, StatusEnsaio, SituacaoEnsaio, TipoLimite } from "../../tipos";

/* Espelho de `backend/apps/ensaios/relatorio_subestacao.py` — ensaios elétricos de subestação
   (TC, TP, DJ, CS e RP). Um payload por relatório; cada equipamento tem o registro e uma ficha
   por ensaio solicitado ou lançado. */

export type CadastroSubestacao = {
  local: string; identificacao: string; numero_serie: string; numero_patrimonio: string; fabricante: string;
  ano_fabricacao: number | null; tipo_equipamento: string; modelo: string;
  tensao_nominal_kv: number | null; corrente_nominal_a: number | null; relacao_texto: string;
  relacao_transformacao: number | null; classe_exatidao: string; carga_nominal_va: number | null;
  numero_nucleos: number | null; polaridade: string; numero_polos: number | null;
  capacidade_interrupcao_ka: number | null; mecanismo: string; funcoes_protecao: string[];
};

export type RegistroSubestacao = {
  data: string | null; analista: string; temperatura_equipamento_c: number | null;
  temperatura_ambiente_c: number | null; umidade_relativa_pct: number | null;
} | null;

export type ColunaSubestacao = {
  codigo: string; nome: string; unidade: string; casas: number; calculado: boolean; tipo_limite: TipoLimite; norma: string;
};

export type CelulaSubestacao = { valor: number | null; texto: string; conforme: boolean | null };

type FichaBase = {
  sigla: string; nome: string; rotulo: string; titulo: string; solicitado: boolean;
  situacao: SituacaoEnsaio; status: StatusEnsaio; status_rotulo: string; avaliados: number; fora: number;
  numero_laudo: string; criticidade: string; data_analise: string | null; data_proxima: string | null;
  conclusao: string; recomendacao: string; informacoes_adicionais: string; instrumento: string;
  rotulos: { conclusao: string; informacoes: string; proxima: string };
  notas: string[];
};

/** Medições por série: uma linha por fase, polo, núcleo ou função; colunas calculadas quando há critério. */
export type FichaMedicao = FichaBase & {
  tipo: "MEDICAO";
  colunas: ColunaSubestacao[];
  linhas: { serie: string; celulas: Record<string, CelulaSubestacao> }[];
  indicadores: Record<string, number | null>;
  criterio: { norma: string; classe: string; relacao_nominal: number | null; admissivel: number | null } | null;
};

/** Curva de excitação: tensão × corrente por núcleo, com a tensão de joelho. */
export type FichaCurva = FichaBase & {
  tipo: "CURVA";
  colunas: ColunaSubestacao[];
  series: string[];
  tabela: { tensao: number; correntes: Record<string, number | null> }[];
  joelhos: Record<string, number | null>;
  grafico: { nome: string; pontos: { tensao: number; corrente: number }[] }[];
};

export type FichaSubestacao = FichaMedicao | FichaCurva;

export type EquipamentoSubestacao = {
  item_id: number; tag: string; equipamento: string; area: string; setor: string; condicao: string;
  cadastro: CadastroSubestacao;
  tipos_ensaio: { sigla: string; nome: string; solicitado: boolean }[];
  registro: RegistroSubestacao;
  ensaios: FichaSubestacao[];
};

export type DestaqueSubestacao = {
  rotulo: string; valor: number | null; unidade: string; casas: number; detalhe: string;
};

export type KpisSubestacao = {
  equipamentos: number; ensaios_solicitados: number; ensaios_realizados: number;
  parametros_avaliados: number; parametros_fora: number; status_ensaios: Dist[];
  status_por_ensaio: { rotulo: string; status: StatusEnsaio; status_rotulo: string }[];
  proxima_data: string | null;
  destaques: DestaqueSubestacao[];
};

export type DadosSubestacao = {
  equipamentos: EquipamentoSubestacao[]; kpis: KpisSubestacao;
  contato_cliente: { telefone: string; email: string };
};

export type DossieSubestacao = DossieShell & DadosSubestacao;
