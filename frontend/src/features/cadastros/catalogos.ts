/**
 * Catálogos do sistema — DEFINIÇÃO, não interface.
 *
 * Cada entrada descreve uma tabela de referência (endpoint, campos, colunas e
 * quem pode editar). A tela `/cadastros` é genérica: ela lê estas definições e
 * monta lista e formulário. Acrescentar um catálogo novo é acrescentar um objeto
 * aqui — nenhuma tela precisa ser escrita.
 *
 * Antes isto vivia dentro da própria página, que passava de 890 linhas
 * misturando dados de domínio, formulário dinâmico, tabela e paginação.
 */

export type FieldType = "text" | "textarea" | "number" | "color" | "multiref" | "date" | "escolha" | "ref" | "boolean" | "image";
export type FieldDef = {
  key: string;
  label: string;
  type?: FieldType;
  required?: boolean;
  optionsEndpoint?: string; // para type "multiref" e "ref"
  escolhas?: { valor: string; texto: string }[]; // para type "escolha"
  escopoClienteAtivo?: boolean; // "ref" cujas opções pertencem ao cliente ativo (ex.: áreas)
  maxLength?: number; // limite espelhando o max_length do modelo
  valorNumerico?: boolean; // "escolha" cujo `valor` é um id/número (ex.: periodicidade em meses) — default: string (CharField choices)
};
export type CatalogDef = {
  key: string;
  label: string;
  endpoint: string;
  fields: FieldDef[];
  columns: string[];
  // Registros que pertencem ao cliente ativo (Áreas/Setores). `param` filtra a
  // lista; `injeta` acrescenta o cliente ao criar (só a Área tem cliente direto).
  escopoCliente?: { param: string; injeta?: boolean };
  // "interno": qualquer usuário interno edita (dados operacionais do cliente).
  // Ausente: só o nível Master (dados de referência do sistema).
  permissao?: "interno";
};

// Rótulos amigáveis para os cabeçalhos das colunas (evita "tecnologias_display").
export const COL_LABELS: Record<string, string> = {
  codigo: "Código",
  nome: "Nome",
  orgao: "Órgão",
  descricao: "Descrição",
  sigla: "Sigla",
  nivel: "Nível",
  cor: "Cor",
  tecnologias_display: "Tecnologias",
  tipo: "Tipo",
  marca: "Marca",
  modelo: "Modelo",
  numero_serie: "Nº de série",
  data_ultima_calibracao: "Última calibração",
  entidade_calibracao: "Entidade de calibração",
  periodicidade_display: "Frequência",
  proxima_calibracao: "Próxima calibração",
  software_analise: "Software",
  complemento: "Complemento",
  area_nome: "Área",
  gera_acao: "Gera análise?",
};

// Estrutura do cliente ativo (Cliente → Área → Setor). NÃO é dado de sistema:
// aparece dentro do cliente, não em "Dados de sistema".
export const CATALOGOS_CLIENTE: CatalogDef[] = [
  {
    key: "areas",
    label: "Áreas",
    endpoint: "areas",
    escopoCliente: { param: "cliente", injeta: true },
    permissao: "interno",
    fields: [
      { key: "codigo", label: "Código", maxLength: 20 },
      { key: "nome", label: "Nome da área", required: true, maxLength: 120 },
      { key: "complemento", label: "Complemento", maxLength: 120 },
    ],
    columns: ["codigo", "nome", "complemento"],
  },
  {
    key: "setores",
    label: "Setores",
    endpoint: "setores",
    escopoCliente: { param: "area__cliente" },
    permissao: "interno",
    fields: [
      {
        key: "area",
        label: "Área",
        type: "ref",
        required: true,
        optionsEndpoint: "areas",
        escopoClienteAtivo: true,
      },
      { key: "codigo", label: "Código", maxLength: 20 },
      { key: "nome", label: "Nome do setor", required: true, maxLength: 120 },
      { key: "complemento", label: "Complemento", maxLength: 120 },
    ],
    columns: ["codigo", "nome", "complemento", "area_nome"],
  },
];

// Tabelas de referência do sistema (curadoria do nível Master).
export const CATALOGOS_SISTEMA: CatalogDef[] = [
  {
    key: "normas",
    label: "Normas (NBRs)",
    endpoint: "normas",
    fields: [
      { key: "codigo", label: "Código", required: true, maxLength: 40 },
      { key: "nome", label: "Título", required: true, maxLength: 250 },
      { key: "orgao", label: "Órgão", maxLength: 40 },
      {
        key: "tecnologias",
        label: "Tecnologias aplicáveis",
        type: "multiref",
        optionsEndpoint: "tecnologias-analise",
      },
    ],
    columns: ["codigo", "nome", "orgao", "tecnologias_display"],
  },
  {
    key: "tecnologias",
    label: "Tecnologias de análise",
    endpoint: "tecnologias-analise",
    fields: [
      { key: "nome", label: "Nome", required: true },
      { key: "sigla", label: "Sigla" },
      { key: "tipo_corretiva", label: "Análise de manutenção corretiva", type: "escolha", escolhas: [
        { valor: "", texto: "Não se aplica" },
        { valor: "BALANCEAMENTO", texto: "Balanceamento" },
        { valor: "ALINHAMENTO", texto: "Alinhamento a laser" },
      ] },
      // Qual módulo monta a parte técnica do relatório (medições, quadros de
      // imagem, tabela da carta). Explícito — nunca deduzido pelo nome.
      { key: "modulo_tecnico", label: "Módulo técnico do relatório", type: "escolha", escolhas: [
        { valor: "", texto: "Padrão — inspeção por rota" },
        { valor: "VIBRACAO", texto: "Vibração" },
        { valor: "TERMOGRAFIA", texto: "Termografia" },
        { valor: "OLEO_ISOLANTE", texto: "Óleo isolante (transformador)" },
        { valor: "ENSAIO_ELETRICO", texto: "Ensaios elétricos (transformador)" },
      ] },
      { key: "imagem", label: "Imagem/ícone (capa do relatório)", type: "image" },
      { key: "definicao_tecnica", label: "Definição — texto introdutório (item 7 da carta)", type: "textarea" },
      { key: "definicao_fluxo_trabalho", label: "Definição — etapas do fluxo de trabalho (1 por linha)", type: "textarea" },
      { key: "definicao_legenda_imagem", label: "Definição — legenda antes da imagem", type: "text" },
      { key: "imagem_pontos_medicao", label: "Imagem dos pontos de medição", type: "image" },
    ],
    columns: ["nome", "sigla"],
  },
  {
    key: "instrumentos",
    label: "Instrumentação",
    endpoint: "instrumentos",
    fields: [
      { key: "tipo", label: "Tipo de instrumento", required: true },
      { key: "marca", label: "Marca" },
      { key: "modelo", label: "Modelo" },
      { key: "numero_serie", label: "Nº de série" },
      { key: "data_ultima_calibracao", label: "Última calibração", type: "date" },
      {
        key: "periodicidade_calibracao",
        label: "Frequência de calibração",
        type: "escolha",
        escolhas: [
          { valor: "6", texto: "Semestral" },
          { valor: "12", texto: "Anual" },
          { valor: "24", texto: "Bienal" },
          { valor: "36", texto: "Trienal" },
        ],
        valorNumerico: true,
      },
      { key: "entidade_calibracao", label: "Entidade de calibração" },
      { key: "software_analise", label: "Software de análise" },
      {
        key: "tecnologias",
        label: "Tecnologias aplicáveis",
        type: "multiref",
        optionsEndpoint: "tecnologias-analise",
      },
    ],
    columns: [
      "tipo", "marca", "modelo", "numero_serie",
      "periodicidade_display", "proxima_calibracao", "tecnologias_display",
    ],
  },
  {
    key: "tipos-equipamento",
    label: "Tipos de equipamento",
    endpoint: "tipos-equipamento",
    fields: [
      { key: "nome", label: "Nome", required: true },
      { key: "descricao", label: "Descrição" },
      { key: "categoria_tecnica", label: "Categoria técnica (datasheet específico)", type: "escolha", escolhas: [
        { valor: "", texto: "Nenhuma — sem dados técnicos específicos" },
        { valor: "MOTOR_ELETRICO", texto: "Motor elétrico" },
        { valor: "TRANSFORMADOR", texto: "Transformador" },
      ] },
    ],
    columns: ["nome", "descricao"],
  },
  catComTecnologias("tipos-componente", "Tipos de componente"),
  catComTecnologias("tipos-anomalia", "Tipos de anomalia"),
  catComTecnologias("tipos-recomendacao", "Tipos de recomendação"),
  {
    key: "criticidades",
    label: "Tipos de criticidade",
    endpoint: "tipos-criticidade",
    fields: [
      { key: "nome", label: "Nome", required: true },
      { key: "nivel", label: "Nível", type: "number" },
      { key: "cor", label: "Cor", type: "color" },
    ],
    columns: ["nome", "nivel", "cor"],
  },
  {
    // Condição do equipamento na inspeção — alimenta o campo "Condição" da folha
    // de campo. "gera_acao" = ao selecioná-la, o campo exige registrar uma análise.
    key: "condicoes",
    label: "Condição do Equipamento",
    endpoint: "condicoes",
    fields: [
      { key: "sigla", label: "Sigla", maxLength: 20 },
      { key: "nome", label: "Nome (nomenclatura)", required: true, maxLength: 250 },
      { key: "gera_acao", label: "Gera análise?", type: "boolean" },
      { key: "nivel", label: "Nível", type: "number" },
      { key: "cor", label: "Cor", type: "color" },
      { key: "descricao", label: "Descritivo" },
    ],
    columns: ["sigla", "nome", "gera_acao", "nivel", "cor"],
  },
  catSimples("classificacoes-inspecao", "Classificações de inspeção"),
  catSimples("tipos-inspecao", "Tipos de inspeção"),
  catSimples("falhas-recorrentes", "Falhas recorrentes"),
  catSimples("grupos-acesso", "Grupos de acesso"),
];

// Lista completa (para resolver ?item=... vindo de qualquer menu).
export const CATALOGOS = [...CATALOGOS_CLIENTE, ...CATALOGOS_SISTEMA];

function catSimples(endpoint: string, label: string): CatalogDef {
  return {
    key: endpoint,
    label,
    endpoint,
    fields: [
      { key: "nome", label: "Nome", required: true },
      { key: "descricao", label: "Descrição" },
    ],
    columns: ["nome", "descricao"],
  };
}

// Catálogo simples + vínculo com tecnologias de análise (facilita filtrar por atividade).
function catComTecnologias(endpoint: string, label: string): CatalogDef {
  return {
    key: endpoint,
    label,
    endpoint,
    fields: [
      { key: "nome", label: "Nome", required: true },
      { key: "descricao", label: "Descrição" },
      {
        key: "tecnologias",
        label: "Tecnologias aplicáveis",
        type: "multiref",
        optionsEndpoint: "tecnologias-analise",
      },
      ...(endpoint === "tipos-recomendacao" ? [{
        key: "anomalias", label: "Anomalias compatíveis (balanceamento)",
        type: "multiref" as const, optionsEndpoint: "tipos-anomalia",
      }] : []),
    ],
    columns: ["nome", "descricao", "tecnologias_display"],
  };
}

/** Rótulo amigável de coluna — evita "tecnologias_display" na tela. */
export function rotuloColuna(coluna: string): string {
  return COL_LABELS[coluna] ?? coluna.charAt(0).toUpperCase() + coluna.slice(1);
}
