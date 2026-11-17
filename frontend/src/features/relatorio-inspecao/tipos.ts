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
import type { EvidenciaLaudo } from "@/lib/types";

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
  /** Personalização textual no mesmo espaço da capa, preservando a geometria. */
  titulo_documento?: string;
  prestador: Prestador | null;
  empresa: string; nome_fantasia: string; cnpj: string; endereco: string; cidade_uf: string; contato: string; departamento: string;
  endereco_linha1: string; endereco_linha2: string;
  logomarca: string | null; numero: string; tecnologia: string; tecnologia_imagem: string | null;
  analistas: { nome: string; assinatura: string | null }[];
  definicao_tecnica: string; definicao_fluxo_trabalho: string; definicao_legenda_imagem: string; pontos_medicao_imagem: string | null;
  data_inicio: string | null; data_termino: string | null; data_finalizacao: string | null;
  /** Data "Upload das OSP´s" informada à mão (ausente em laudos emitidos antes do campo existir). */
  data_upload_osps?: string | null;
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
  /** Estrutura da carta. Ausentes (laudos já emitidos, outros módulos) = modelo padrão:
   *  item 7 "Definição da Técnica", instrumentação em lista e sem a data das OSPs.
   *  A termografia elétrica segue o RT.TE do cliente (ver relatorio_tecnico/modulos.py). */
  definicao_tecnica?: boolean;
  instrumentacao_numerada?: boolean;
  mostra_data_osps?: boolean;
  /** Data "Upload das OSP´s" já resolvida (informada ou a de geração das OSPs). */
  data_upload_osps?: string | null;
  /** Vibração/balanceamento: critério de severidade vigente por classe e as notas do que não é da norma. */
  tabela_severidade?: LinhaSeveridade[];
  notas_severidade?: string[];
};

/** Critério aplicado a uma classe na tabela de severidade (limites em mm/s RMS, como string decimal). */
export type LinhaSeveridade = {
  classe: string; rotulo: string; norma: string; edicao: string; descricao_grupo: string;
  /** "RIGIDO" | "FLEXIVEL" nos grupos da ISO 20816-3; "" = qualquer suporte. */
  suporte?: string;
  limites: { ab: string; bc: string; cd: string };
  /** Limites de deslocamento (µm RMS), quando a norma do grupo publica. */
  deslocamento?: { ab: string; bc: string; cd: string } | null;
  origem: "NORMA" | "RESPONSAVEL_TECNICO" | "ACORDO_CLIENTE" | "LEGADO"; origem_display: string; fonte: string;
  referencia_norma: { limites: { ab: string; bc: string; cd: string } } | null;
};

export type DossieShell = {
  evidencias_laudo?: EvidenciaLaudo[];
  /** Chave do módulo técnico da tecnologia (sempre explícita; sem módulo o backend recusa). */
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
/** Valores numéricos: o dossiê os entrega como número JSON (Decimal → float no DRF); laudos antigos, como texto. */
type ValorNum = string | number | null;
export type AvalLinha = { rotulo: string; pred_q: ValorNum; pred_v: ValorNum; emerg_q: ValorNum; emerg_v: ValorNum };
export type Avaliacao = { linhas: AvalLinha[]; total_preditiva: string; total_emergencial: string; retorno: string };
export type ImagemOsp = { tipo: string; arquivo: string; legenda: string };
export type OspD = {
  osp: string; area: string; setor: string; tag: string; equipamento: string; componente: string;
  anomalia: string; recomendacao: string; observacao: string; grau_risco: string; grau_risco_descricao: string;
  amplitude_velocidade: string | null; amplitude_aceleracao: string | null;
  amplitude_deslocamento?: string | null;
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
  /** Espessura (2.3.2.7): só no módulo ESPESSURA; null = sem medição no período. */
  espessura?: EspessuraOsp | null;
  /** Isolação de motor (2.3.2.5.1.1): só no módulo MOTOR_RXI; null = sem ensaio no período. */
  motor_rxi?: MotorRxiOsp | null;
  /** Ultrassom (2.3.2.6): só no módulo ULTRASSOM; null = sem leitura no período. */
  ultrassom?: UltrassomOsp | null;
  /** Qualidade de energia (2.3.2.10): última leitura de cada grandeza; null = sem medição no período. */
  qualidade_energia?: Record<string, QualidadeLeituraOsp | null> | null;
  /** Alinhamento a laser (2.3.2.8.1.1–2): último serviço até o fim do relatório; null = sem serviço. */
  alinhamento?: AlinhamentoOsp | null;
  /** Termografia mecânica/processos: condição do ΔT pelo critério validado (null nos outros módulos). */
  termografia_criterio?: TermografiaCriterioOsp | null;
};

/** Condição do ΔT (sistema mecânico ou de processo). Sem critério validado: PENDENTE, com o que falta. */
export type TermografiaCriterioOsp = {
  condicao: "NORMAL" | "ALERTA" | "CRITICO" | "PENDENTE";
  limites: Record<string, string>;
  criterio: CriterioOrigemOsp;
  pendencia: string;
};

/** Um serviço de alinhamento, antes ou depois da correção. Números chegam como texto. */
export type AlinhamentoFaseOsp = { medicao_id: number; data: string; rpm: string | null;
  angular_mm_100mm: string | null; paralelo_mm: string | null;
  correcao_pe_vertical_mm: string | null; correcao_pe_horizontal_mm: string | null };

/** Origem de um critério validado (LimiteAlarmeSerie) — o relatório mostra de onde vem o limite. */
export type CriterioOrigemOsp = { id: number; origem: string; origem_display: string; fonte: string; validacao: string } | null;

export type AlinhamentoOsp = {
  data: string; ponto: string;
  antes: AlinhamentoFaseOsp | null; depois: AlinhamentoFaseOsp | null;
  reducao_angular_pct: string | null; reducao_paralelo_pct: string | null;
  condicao: "NORMAL" | "ALERTA" | "CRITICO" | "PENDENTE";
  criterio_validado: boolean;
  criterio: { angular: CriterioOrigemOsp; paralelo: CriterioOrigemOsp };
  limites: { angular: Record<string, string>; paralelo: Record<string, string> };
  pendencias: string[];
};

/** Última leitura de uma grandeza de qualidade de energia. Números chegam como texto. */
export type QualidadeLeituraOsp = {
  data: string; valor: string; janela_agregacao: string;
  condicao: "NORMAL" | "ALERTA" | "CRITICO" | "PENDENTE";
  criterio_validado: boolean;
};

/** Última leitura de ultrassom do equipamento até o fim do relatório. Números chegam como texto. */
export type UltrassomOsp = {
  data: string; subtipo: string; grandeza: string; nivel_db: string;
  ganho_db: string | null; distancia_cm: string | null; frequencia_khz: string | null;
  condicao: "NORMAL" | "ALERTA" | "CRITICO" | "PENDENTE";
  criterio_validado: boolean;
};

/** Último grupo de leituras de isolação do motor até o fim do relatório. Números chegam como texto. */
export type MotorRxiOsp = {
  data: string; ponto: string; tensao_ensaio_v: string; temperatura_c: string; ligacao: string;
  R30: string | null; R60: string | null; R600: string | null; DAR: string | null; IP: string | null;
  condicao: "NORMAL" | "ALERTA" | "CRITICO" | "PENDENTE";
  criterio_validado: boolean;
};

/** Última medição de espessura do equipamento até o fim do relatório. Números chegam como texto. */
export type EspessuraOsp = {
  data: string; material: string; nominal_mm: string | null; medida_mm: string;
  perda_percentual: string | null; taxa_mm_ano: string | null;
  condicao: "NORMAL" | "ALERTA" | "CRITICO" | "PENDENTE";
  criterio_validado: boolean;
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

/* ------------ Módulo: fluidos lubrificantes e hidráulicos (FQ, EF, CP) ------------
   Espelho de `backend/apps/ensaios/relatorio_fluidos.py`. Cada ficha é uma tabela
   parâmetro × coleta (até 6, a atual por último); a referência é a cadastrada para
   o escopo (equipamento/fluido/cliente/aplicação) com origem e vigência. */
export type EstadoFluido = "ROTINA" | "ALERTA" | "CRITICA";
export type StatusFluido = EstadoFluido | "SEM_CRITERIO" | Exclude<SituacaoEnsaio, "REALIZADO">;
export type ReferenciaFluido = {
  id: number; tipo: "MAXIMO" | "MINIMO" | "VARIACAO" | "QUEDA" | "AUMENTO" | "CODIGO_ISO" | "QUALITATIVO"; tipo_display: string;
  valor_base: number | null; limite_alerta: number | null; limite_critico: number | null; referencia_texto: string;
  /** Variação com base no valor do óleo novo do fluido da coleta (`valor_base` já resolvido). */
  base_oleo_novo?: boolean;
  /** Pronto para imprimir: "Alerta > 50,0 · Crítico > 100,0 ppm". */
  texto: string;
  origem: string; origem_display: string; fonte: string;
  vigencia_inicio: string | null; vigencia_fim: string | null; escopo: string;
};
export type CelulaFluido = { valor: number | null; texto: string; estado: EstadoValor; metodo: string };
export type TendenciaFluido = {
  delta_anterior: number; pct_anterior: number | null; pct_primeiro: number | null;
  direcao: "SOBE" | "DESCE" | "ESTAVEL"; pontos: number;
} | null;
export type LinhaFluido = {
  codigo: string; nome: string; simbolo: string; grupo: string; unidade: string; norma: string; metodo: string;
  casas: number; no_grafico: boolean; qualitativo: boolean;
  /** Uma célula por coleta, na ordem de `campanhas`. */
  valores: CelulaFluido[];
  referencia: ReferenciaFluido | null; status: EstadoFluido | null; variacao_pct: number | null;
  /** Valor do óleo novo (ficha técnica do fluido da coleta): viscosidade a 40 °C, densidade a 15 °C ou IV. */
  oleo_novo?: number | null;
  /** Pronto para imprimir: "Óleo novo: 0,8870 · a 20 °C · ASTM D1298". */
  oleo_novo_texto?: string;
  /** Tem valor na coleta atual e nenhuma referência cadastrada. */
  sem_referencia: boolean; tendencia: TendenciaFluido;
};
export type CodigoIsoColeta = { data: string | null; atual: boolean; codigo: string | null; escalas: (number | null)[] };
export type FichaFluido = {
  /** Observações montadas só com as referências cadastradas (um item por parâmetro fora da referência). */
  observacoes_geradas: string[];
  sigla: string; nome: string; rotulo: string; titulo: string; solicitado: boolean;
  situacao: SituacaoEnsaio; status: StatusFluido; status_rotulo: string;
  avaliados: number; alertas: number; criticas: number; fora: number; sem_referencia: number;
  numero_laudo: string; criticidade: string; criticidade_codigo: string;
  data_analise: string | null; data_proxima: string | null;
  conclusao: string; recomendacao: string; informacoes_adicionais: string; instrumento: string; laboratorio: string;
  rotulos: { conclusao: string; informacoes: string; proxima: string };
  notas: string[];
  campanhas: { data: string | null; atual: boolean }[];
  linhas: LinhaFluido[]; grupos: string[];
  tipo: "PARAMETROS" | "CP";
  /** CP: código ISO 4406 de cada coleta e a meta de limpeza (quando cadastrada). */
  codigos?: CodigoIsoColeta[]; meta?: ReferenciaFluido | null;
  situacao_meta?: "DENTRO" | "FORA" | "SEM_META" | null; excesso_meta?: number | null;
};
export type ColetaFluidoRelatorio = {
  data: string | null; identificacao_amostra: string; amostrador: string;
  aplicacao: "LUBRIFICANTE" | "HIDRAULICO"; aplicacao_display: string;
  fluido: string; fabricante_fluido: string; grau_viscosidade: string; ponto_coleta: string;
  temperatura_fluido_c: number | null; temperatura_ambiente_c: number | null; condicao_operacional: string;
  horas_equipamento: number | null; horas_fluido: number | null; volume_reservatorio_l: number | null;
  data_ultima_troca: string | null;
  complemento_recente: boolean | null; volume_complemento_l: number | null; troca_filtro_recente: boolean | null;
  intervencao_recente: string; observacoes: string;
};
export type GrauSigla = "GR-0" | "GR-1" | "GR-2" | "GR-3" | "GR-4";
/** Grau de risco da amostra: GR-1 vem da condição marcada em campo; os demais, do nº de ensaios com anomalia. */
export type GrauRisco = {
  sigla: GrauSigla; rotulo: string; prazo_dias: number | null; prazo_texto: string;
  ensaios_com_anomalia: number; ensaios_avaliados: number; origem: "REFERENCIAS" | "ANALISTA";
};
export type AmostraFluido = {
  equipamento_id: number; data: string | null; grau_risco: GrauRisco | null;
  item_id: number; tag: string; equipamento: string; area: string; setor: string; condicao: string;
  cadastro: {
    local: string; identificacao: string; numero_serie: string; numero_patrimonio: string; fabricante: string;
    modelo: string; ano_fabricacao: number | null; tipo_equipamento: string;
  };
  coleta: ColetaFluidoRelatorio | null;
  tipos_ensaio: { sigla: string; nome: string; solicitado: boolean }[];
  ensaios: FichaFluido[];
};
export type KpisFluido = {
  amostras: number; equipamentos: number; ensaios_solicitados: number; ensaios_realizados: number;
  ensaios_pendentes: number; parametros_avaliados: number; parametros_alerta: number; parametros_criticos: number;
  parametros_sem_referencia: number; laudos_por_criticidade: Dist[]; avaliacao_ensaios: Dist[];
  limpeza: { dentro: number; fora: number; sem_meta: number };
  status_por_ensaio: { rotulo: string; status: StatusFluido; status_rotulo: string }[];
  proxima_data: string | null;
};
/** Indicadores da Seção B (relatório-modelo do laboratório). */
export type GraficosFluido = {
  condicoes: Dist[]; componentes: Dist[]; anomalias: Dist[];
  graus_tempo: { meses: string[]; series: { gr: GrauSigla; rotulo: string; valores: number[] }[] };
  equipamentos_anomalias: { meses: string[]; monitorados: number[]; anomalias: number[] };
  osp: { colunas: string[]; linhas: { gr: GrauSigla; valores: number[] }[] };
};
/** Uma rota (coleta do mês) do relatório do trimestre: o mês sem desvio não gera envio. */
export type EnvioMensal = { carregamento: number; data_coleta: string; amostras: number; desvios: number };
export type DadosFluido = {
  /** Recorte pedido na URL (envio do mês): só a rota e, opcionalmente, só as amostras com desvio. */
  recorte: { carregamento?: number; somente_desvios?: boolean };
  envios_mensais: EnvioMensal[];
  graficos: GraficosFluido;
  amostras: AmostraFluido[]; kpis: KpisFluido; contato_cliente: { telefone: string; email: string };
};
export type DossieFluido = DossieShell & DadosFluido;
