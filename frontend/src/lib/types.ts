// Tipos espelhando os serializers da API (backend Django/DRF).

export type Perfil =
  | "ADMIN"
  | "GESTOR"
  | "TECNICO"
  | "CLIENTE_CORP"
  | "CLIENTE_LOCAL"
  | "CLIENTE_PCM"
  | "CLIENTE_MANUT";

// Hierarquia de acesso definida com o cliente: ambiente (BackEnd/FrontEnd) × nível.
export type Nivel = "MASTER" | "SENIOR" | "PLENO" | "JUNIOR";

export interface User {
  id: number;
  email: string;
  nome: string;
  perfil: Perfil;
  perfil_display: string;
  nivel: Nivel;
  nivel_display: string;
  ambiente: string; // "BackEnd" | "FrontEnd"
  grupo_acesso: string; // ex.: "BackEnd-Master"
  is_interno: boolean;
  is_cliente: boolean;
  is_master: boolean;
  pode_excluir: boolean;
  pode_curar_dados_sistema: boolean;
  empresa: number | null;
  cliente: number | null;
  cargo: string;
  conselho_classe: string;
}

export type Criticidade = "NORMAL" | "ALERTA" | "CRITICO";

export interface Componente {
  id: number;
  equipamento: number;
  nome: string;
}

export interface Equipamento {
  id: number;
  setor: number;
  setor_nome: string;
  area_id: number;
  area_nome: string;
  cliente_id: number;
  // Hierarquia Equipamento → Sub-item (ex.: Caldeira → Exaustor)
  equipamento_pai: number | null;
  equipamento_pai_tag: string | null;
  is_subitem: boolean;
  nivel: number;
  caminho: string;
  qtd_subitens: number;
  tag: string;
  nome: string;
  tipo: string; // texto legado (espelha o nome do tipo)
  tipo_equipamento: number | null; // FK ao catálogo "Tipos de equipamento"
  tipo_equipamento_nome: string | null;
  fabricante: string;
  modelo: string;
  numero_serie: string;
  potencia_kw: string | null;
  rotacao_nominal_rpm: number | null;
  classe_iso: string;
  classe_iso_display: string;
  criticidade: string; // "" | "A" | "B" | "C"
  criticidade_display: string;
  componentes: Componente[];
}

/** Empresa CONTRATADA (prestadora de serviço) — sai no cabeçalho dos relatórios. */
export interface Empresa {
  id: number;
  nome: string; // razão social
  cnpj: string;
  cep: string;
  logradouro: string;
  numero: string;
  complemento: string;
  bairro: string;
  cidade: string;
  uf: string;
  cidade_uf: string;
  endereco_formatado: string;
  contato_gestor: string;
  departamento: string;
  logomarca: string | null;
}

export interface Cliente {
  id: number;
  // Identificação
  nome: string; // razão social
  nome_fantasia: string;
  cnpj: string;
  unidade_negocio: string;
  // Endereço estruturado (preenchido pela busca de CEP)
  cep: string;
  logradouro: string;
  numero: string;
  complemento: string;
  bairro: string;
  cidade: string;
  uf: string;
  cidade_uf: string;
  endereco_formatado: string;
  // Contato
  contato_gestor: string;
  departamento: string;
  email: string;
  telefone: string;
  logomarca: string | null;
}

export interface MedicaoVibracao {
  id: number;
  inspecao: number;
  equipamento: number;
  equipamento_tag: string;
  componente: number | null;
  componente_nome: string | null;
  ponto_medicao: string;
  direcao: "H" | "V" | "A";
  direcao_display: string;
  rotacao_rpm: number | null;
  velocidade_rms: string;
  aceleracao_rms: string | null;
  deslocamento_pp: string | null;
  fator_crista: string | null;
  temperatura: string | null;
  zona_iso: string;
  criticidade: Criticidade;
  criticidade_display: string;
  diagnostico_sugerido: string;
  data_hora: string;
}

export interface MedicaoTermografia {
  id: number;
  inspecao: number;
  equipamento: number;
  equipamento_tag: string;
  componente: number | null;
  componente_nome: string | null;
  ponto_medicao: string;
  sistema: string;
  sistema_display: string;
  temperatura_ponto: string;
  temperatura_referencia: string;
  temperatura_ambiente: string | null;
  emissividade: string;
  carga_percentual: string | null;
  delta_t: string;
  criticidade: Criticidade;
  criticidade_display: string;
  diagnostico_sugerido: string;
  data_hora: string;
}

export interface MedicaoTecnica {
  id: number;
  inspecao: number;
  equipamento: number;
  equipamento_tag: string;
  componente: number | null;
  componente_nome: string | null;
  tipo: string;
  tipo_display: string;
  ponto_medicao: string;
  grandeza: string;
  valor: string;
  unidade: string;
  valor_referencia: string | null;
  parametros: Record<string, unknown>;
  criticidade: Criticidade;
  criticidade_display: string;
  diagnostico_sugerido: string;
  data_hora: string;
}

export interface Inspecao {
  id: number;
  cliente: number;
  cliente_nome: string;
  tipo_analise: string;
  tipo_analise_display: string;
  tecnico: number;
  tecnico_nome: string;
  data: string;
  status: string;
  status_display: string;
  observacoes: string;
  criticidade_maxima: Criticidade;
  qtd_medicoes: number;
  medicoes_vibracao: MedicaoVibracao[];
  medicoes_termografia: MedicaoTermografia[];
  medicoes_tecnicas: MedicaoTecnica[];
  criado_em: string;
}

export interface OrdemServico {
  id: number;
  numero: string;
  cliente: number;
  cliente_nome: string;
  equipamento: number;
  equipamento_tag: string;
  inspecao: number | null;
  titulo: string;
  descricao: string;
  prioridade: "BAIXA" | "MEDIA" | "ALTA" | "URGENTE";
  prioridade_display: string;
  status: string;
  status_display: string;
  criticidade_origem: Criticidade | "";
  gerada_automaticamente: boolean;
  responsavel: number | null;
  responsavel_nome: string | null;
  sla_data: string | null;
  sla_vencido: boolean;
  finalizada_em: string | null;
  criado_em: string;
}

export interface Laudo {
  id: number;
  numero: string;
  versao: number;
  inspecao: number;
  cliente_nome: string;
  titulo: string;
  criticidade_geral: Criticidade | "";
  diagnostico: string;
  recomendacoes: string;
  conclusao: string;
  responsavel: number;
  responsavel_nome: string;
  responsavel_conselho: string;
  status: string;
  status_display: string;
  data_emissao: string | null;
  criado_em: string;
}

export interface Notificacao {
  id: number;
  evento: string;
  evento_display: string;
  titulo: string;
  mensagem: string;
  url: string;
  nivel: "INFO" | "ALERTA" | "CRITICO";
  nivel_display: string;
  canais_enviados: string[];
  lida: boolean;
  lida_em: string | null;
  criado_em: string;
}

export interface DashboardExecutivo {
  kpis: {
    osps_total: number;
    osps_finalizadas: number;
    taxa_conclusao: number;
    mttr_horas: number | null;
    mtbf_dias: number | null;
  };
  custos: { real: number; estimado: number };
  evolucao: { mes: string; criticas: number; osps: number }[];
  performance: {
    cliente: string;
    osps: number;
    finalizadas: number;
    criticas: number;
    custo_real: number;
  }[];
}

export interface Dashboard {
  total_inspecoes: number;
  inspecoes_abertas: number;
  total_medicoes: number;
  medicoes_por_criticidade: Record<Criticidade, number>;
  equipamentos_criticos: {
    equipamento__tag: string;
    equipamento__nome: string;
    ocorrencias: number;
  }[];
  osps_abertas: number;
  osps_total: number;
}

export interface ReportDef {
  key: string;
  nome: string;
  descricao: string;
  categoria: string;
  interno_only: boolean;
}

export interface ReportData {
  titulo: string;
  colunas: string[];
  linhas: (string | number)[][];
  total_linhas: number;
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

// Portal do Cliente — Anexo I 2.7 (dashboard personalizado, indicadores e histórico).
export interface PortalHistoricoItem {
  tipo: "laudo" | "inspecao" | "osp";
  titulo: string;
  descricao: string;
  data: string;
  status: string;
  criticidade: Criticidade | "";
  url: string;
}

export interface EquipamentoAtencao {
  equipamento__tag: string;
  equipamento__nome: string;
  ocorrencias: number;
}

export interface PortalVisaoGeral {
  cliente: { nome: string; unidade_negocio: string; cidade_uf: string } | null;
  indicadores: {
    equipamentos_monitorados: number;
    equipamentos_atencao: number;
    indice_disponibilidade: number;
    inspecoes: number;
    osps_abertas: number;
    laudos_disponiveis: number;
  };
  equipamentos_atencao: EquipamentoAtencao[];
  historico: PortalHistoricoItem[];
}
