/**
 * Payload do endpoint `/relatorios-inspecao/{id}/dossie/`.
 *
 * `DossieShell` é o que capa, carta, relação de equipamentos, paginação e PDF
 * leem — igual para qualquer tecnologia. O resto é do módulo técnico
 * (`modulos/`), com a chave em `modulo`: a família "inspeção por rota"
 * (`DadosInspecao` — vibração, termografia e o layout padrão) e os relatórios de
 * transformador (`DadosTransformador` — óleo isolante e ensaios elétricos).
 */
import type { Corretiva } from "./corretiva-balanceamento";

/* ------------------------------- Shell ------------------------------------ */
export type Instrumento = {
  tipo: string; marca: string; modelo: string; numero_serie: string;
  data_ultima_calibracao: string | null; proxima_calibracao: string | null;
  periodicidade: string; entidade_calibracao: string; software_analise: string;
};
export type Norma = { codigo: string; nome: string; orgao: string };
export type GlossTerm = { sigla: string; termo: string; descricao: string };
export type Prestador = {
  nome: string; cnpj: string; inscricao_estadual: string; endereco: string; cidade_uf: string;
  endereco_linha1: string; endereco_linha2: string;
  email: string; telefone: string; site: string; logomarca: string | null;
};
export type Cabecalho = {
  prestador: Prestador | null;
  empresa: string; nome_fantasia: string; cnpj: string; endereco: string; cidade_uf: string; contato: string; departamento: string;
  endereco_linha1: string; endereco_linha2: string;
  logomarca: string | null; numero: string; tecnologia: string; tecnologia_imagem: string | null;
  analistas: { nome: string; assinatura: string | null }[];
  definicao_tecnica: string; definicao_fluxo_trabalho: string; definicao_legenda_imagem: string; pontos_medicao_imagem: string | null;
  data_inicio: string | null; data_termino: string | null; data_finalizacao: string | null;
  instrumentos: Instrumento[]; normas: Norma[]; glossario: GlossTerm[]; consideracoes_finais: string;
};
export type LinhaC = { tag: string; equipamento: string; condicao: string };
export type GrupoC = { area: string; setor: string; linhas: LinhaC[] };
export type SecaoC = { total: number; equip_monitorados: number; grupos: GrupoC[] };

/** Termo do glossário da carta; sem `texto` = título de grupo (ex.: "6.1. Temperaturas"). */
export type TermoGlossario = { n: string; sigla: string; texto: string };
/** Textos técnicos da carta que o módulo da tecnologia fornece pelo backend —
 *  a mesma fonte da carta .docx (`textos_carta()` em relatorio_tecnico).
 *  `quebras_glossario`: termos (pelo número, ex.: "6.3") que abrem uma folha nova.
 *  `paragrafos`: item 7 — o que o módulo apurou, quando o texto sai do backend. */
export type TextosCarta = {
  conteudo: string[]; glossario: TermoGlossario[]; quebras_glossario: string[]; consideracoes: string[];
  paragrafos: string[];
};

export type DossieShell = {
  /** Chave do módulo técnico da tecnologia ("" = layout padrão). */
  modulo: string;
  cabecalho: Cabecalho;
  secao_c: SecaoC;
  carta: TextosCarta;
};

/* ------------------- Módulo: inspeção por rota (OSP) ---------------------- */
export type Dist = { rotulo: string; total: number; percentual: number };
export type DiagnosticoMedio = { velocidade: number | null; aceleracao: number | null; temperatura: number | null };
export type SecaoB = {
  condicoes: Dist[]; componentes: Dist[]; anomalias: Dist[]; alarmes: Dist[];
  equip_monitorados: number; anomalias_diagnosticadas: number;
  media_anomalias_por_equipamento: number; diagnostico_medio: DiagnosticoMedio;
  custo_evitado: string | number;
  taxa_acerto_diagnostico: number | null; diagnosticos_avaliados: number;
  mtbf_dias: number | null; cobertura_ativos_criticos: number | null;
};
export type AvalLinha = { rotulo: string; pred_q: string | null; pred_v: string | null; emerg_q: string | null; emerg_v: string | null };
export type Avaliacao = { linhas: AvalLinha[]; total_preditiva: string; total_emergencial: string; retorno: string };
export type ImagemOsp = { tipo: string; arquivo: string; legenda: string };
export type OspD = {
  osp: string; area: string; setor: string; tag: string; equipamento: string; componente: string;
  anomalia: string; recomendacao: string; observacao: string; grau_risco: string; grau_risco_descricao: string;
  amplitude_velocidade: string | null; amplitude_aceleracao: string | null;
  temperatura_medida: string | null; temperatura_referencia: string | null; delta_t: string | null; carga_percentual: string | null;
  /** Correção pela corrente (C.T.M.) — nulas até a fórmula ser definida com o cliente. */
  temperatura_medida_corrigida: string | null; delta_t_corrigido: string | null;
  /** [nominal, fase A/R, fase B/S, fase C/T] */
  corrente: (string | null)[]; tensao: (string | null)[]; analista: string;
  imagens: ImagemOsp[];
  avaliacao: Avaliacao | null;
  /* Manutenção corretiva: vazio nas folhas preditivas. `corretiva` traz os dados
     técnicos da intervenção já calculados no backend — com layout específico
     (hoje: balanceamento) ou só a base comum (economia), quando o tipo ainda não
     tem apresentação própria definida. */
  tipo_corretiva: string;
  tipo_corretiva_display: string;
  corretiva: Corretiva | null;
};
export type DadosInspecao = { secao_b: SecaoB; secao_d: OspD[] };

export type DossieInspecao = DossieShell & DadosInspecao;

/* ------------- Módulos de transformador (óleo isolante / elétricos) ------------
   Espelho de `backend/apps/ensaios/relatorio.py`. Números chegam como number
   (Decimal do backend); valor ausente é null — nunca zero. */
export type TipoLimite = "MAXIMO" | "MINIMO" | "FAIXA" | "QUALITATIVO" | "INFORMATIVO";
export type EstadoValor = "" | "MEDIDO" | "ABAIXO_LD" | "ABAIXO_LQ" | "NAO_DETECTADO" | "ACIMA_ESCALA" | "INDISPONIVEL";
export type SituacaoEnsaio = "REALIZADO" | "NAO_COLETADO" | "NAO_REALIZADO" | "SEM_RESULTADO";
export type StatusEnsaio = "CONFORME" | "NAO_CONFORME" | "SEM_CRITERIO" | Exclude<SituacaoEnsaio, "REALIZADO">;

export type ParametroEnsaio = {
  codigo: string; nome: string; unidade: string; norma: string; tipo_limite: TipoLimite;
  limite: number | null; limite_superior: number | null; referencia_texto: string; casas: number; no_grafico: boolean;
};
/** Valor de um parâmetro numa campanha. `conforme` null = sem critério ou sem valor. */
export type CelulaEnsaio = {
  valor: number | null; texto: string; estado: EstadoValor; conforme: boolean | null; calculado: boolean;
};
/** Barra do gráfico: valor da campanha atual em % da referência (null = sem barra). */
export type BarraReferencia = { codigo: string; nome: string; tipo_limite: TipoLimite; percentual: number | null };

type FichaBase = {
  sigla: string; nome: string; rotulo: string; titulo: string; solicitado: boolean;
  situacao: SituacaoEnsaio; status: StatusEnsaio; status_rotulo: string; avaliados: number; fora: number;
  numero_laudo: string; criticidade: string; data_analise: string | null; data_proxima: string | null;
  conclusao: string; recomendacao: string; informacoes_adicionais: string; instrumento: string;
  rotulos: { conclusao: string; informacoes: string; proxima: string };
  notas: string[];
};
/** FQ, CR, PCB e 2-FAL: uma coluna por parâmetro, uma linha por campanha (a atual por último). */
export type FichaTabela = FichaBase & {
  tipo: "TABELA"; parametros: ParametroEnsaio[];
  campanhas: { data: string | null; atual: boolean; valores: Record<string, CelulaEnsaio> }[];
  grafico: BarraReferencia[]; indicadores: Record<string, number | null>; gp_estimado: boolean;
};
export type FaseRelacao = { serie: string; medido: number | null; erro: number | null; conforme: boolean | null };
export type FichaRelacao = FichaBase & {
  tipo: "RXT";
  campanhas: { data: string | null; atual: boolean; nominal: number | null; nominal_calculada: boolean; fases: FaseRelacao[] }[];
  limite: { inferior: number | null; superior: number | null; norma: string };
};
export type SerieIsolacao = {
  nome: string; tensao: number | null; pontos: { tempo: number | null; valor: number | null; estado: EstadoValor }[];
  ip: number | null; ia: number | null; ip_conforme: boolean | null;
};
export type FichaIsolacao = FichaBase & {
  tipo: "RXI"; series: SerieIsolacao[]; tempos: number[]; criterio_ip: { limite: number | null; norma: string };
};
export type LinhaOhmica = { tipo: "Corrigido" | "Calculado" | "Medido"; valores: Record<string, number | null> };
export type FichaOhmica = FichaBase & {
  tipo: "RXO";
  campanhas: { data: string | null; atual: boolean; tap: string; temperatura_oleo_c: number | null; linhas: LinhaOhmica[] }[];
  pares: { codigo: string; nome: string; unidade: string; casas: number }[];
  correcao: { temperatura_referencia_c: number; constante: number };
};
export type FichaEnsaio = FichaTabela | FichaRelacao | FichaIsolacao | FichaOhmica;

export type CadastroTransformador = {
  local: string; identificacao: string; numero_serie: string; numero_patrimonio: string; fabricante: string;
  ano_fabricacao: number | null; tipo_equipamento: string; modelo: string;
  potencia_kva: number | null; tensao_primaria_v: number | null; tensao_secundaria_v: number | null;
  tensao_secundaria_fase_v: number | null; impedancia_pct: number | null; grupo_ligacao: string;
  volume_oleo_l: number | null; possui_tanque_expansao: boolean | null;
};
export type ColetaOleo = {
  data: string | null; amostrador: string; temperatura_amostra_c: number | null; temperatura_ambiente_c: number | null;
  umidade_relativa_pct: number | null; ponto_coleta: string; tipo_fluido: string;
};
export type ItemInspecaoVisual = {
  grupo: "GERAL" | "TANQUE_EXPANSAO"; item: string; estado: "OK" | "NC" | "NA"; observacao: string; foto: string | null;
};
export type RegistroEnsaioEletrico = {
  data: string | null; analista: string; tap: string; tensao_tap_v: number | null; temperatura_oleo_c: number | null;
  temperatura_ambiente_c: number | null; umidade_relativa_pct: number | null;
};
export type Transformador = {
  item_id: number; tag: string; equipamento: string; area: string; setor: string; condicao: string;
  cadastro: CadastroTransformador;
  tipos_ensaio: { sigla: string; nome: string; solicitado: boolean }[];
  /** Óleo isolante. */
  coleta?: ColetaOleo | null; inspecao_visual?: ItemInspecaoVisual[];
  /** Ensaios elétricos. */
  registro?: RegistroEnsaioEletrico | null;
  ensaios: FichaEnsaio[];
};
export type KpisTransformador = {
  transformadores: number; ensaios_solicitados: number; ensaios_realizados: number;
  parametros_avaliados: number; parametros_fora: number; status_ensaios: Dist[];
  status_por_ensaio: { rotulo: string; status: StatusEnsaio; status_rotulo: string }[];
  proxima_data: string | null;
  /** Óleo isolante. */
  inspecao_visual?: Dist[];
  /** Ensaios elétricos. */
  maior_erro_relacao?: number | null; limite_erro_relacao?: number | null; menor_ip?: number | null;
};
export type DadosTransformador = {
  transformadores: Transformador[]; kpis: KpisTransformador;
  contato_cliente: { telefone: string; email: string };
};
export type DossieTransformador = DossieShell & DadosTransformador;
