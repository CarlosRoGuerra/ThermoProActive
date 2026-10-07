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
  grupo_display: "Grupo",
  ordem: "Ordem",
  categoria_tecnica_display: "Ficha técnica",
  analise_vibracao: "Vibração?",
  modulo_display: "Tecnologia",
  norma_codigo: "Norma",
  norma_edicao: "Edição",
  classe: "Classe",
  limite_ab: "A/B (mm/s)",
  limite_bc: "B/C (mm/s)",
  limite_cd: "C/D (mm/s)",
  origem_display: "Origem",
  cliente_nome: "Cliente",
  vigencia_inicio: "Vigência",
  fabricante: "Fabricante",
  aplicacao_display: "Aplicação",
  grau_viscosidade: "Grau",
  ensaio_sigla: "Ensaio",
  parametro_nome: "Parâmetro",
  tipo_display: "Tipo",
  limite_alerta: "Alerta",
  limite_critico: "Crítico",
  referencia_texto: "Meta/esperado",
  equipamento_tag: "Equipamento",
  produto_nome: "Fluido",
};

const APLICACOES_FLUIDO = [
  { valor: "LUBRIFICANTE", texto: "Lubrificante" },
  { valor: "HIDRAULICO", texto: "Hidráulico" },
];
const CLASSES_VIBRACAO = [
  { valor: "I", texto: "Classe I (até 15 kW)" },
  { valor: "G2", texto: "Grupo 2 (15 a 300 kW) — ISO 20816-3" },
  { valor: "G1", texto: "Grupo 1 (acima de 300 kW) — ISO 20816-3" },
  { valor: "II", texto: "Classe II (15–75 kW) — ISO 10816-1, histórico" },
  { valor: "III", texto: "Classe III (base rígida) — ISO 10816-1, histórico" },
  { valor: "IV", texto: "Classe IV (base flexível) — ISO 10816-1, histórico" },
];

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
      // Sem "padrão": tecnologia sem módulo não gera relatório (o sistema avisa) e
      // nunca herda o layout de outra técnica. Os "não implementado" já podem ser
      // escolhidos — o relatório avisa até o módulo existir.
      { key: "modulo_tecnico", label: "Módulo técnico do relatório", type: "escolha", escolhas: [
        { valor: "VIBRACAO", texto: "Vibração" },
        { valor: "BALANCEAMENTO", texto: "Balanceamento dinâmico (corretiva)" },
        { valor: "TERMOGRAFIA", texto: "Termografia" },
        { valor: "OLEO_ISOLANTE", texto: "Óleo isolante (transformador)" },
        { valor: "ENSAIO_ELETRICO", texto: "Ensaios elétricos — transformador (TRF)" },
        { valor: "FLUIDO_LUBRIFICANTE", texto: "Fluidos lubrificantes e hidráulicos" },
        { valor: "INSPECAO_GENERICA", texto: "Inspeção genérica (sem medições específicas)" },
        { valor: "ALINHAMENTO_EIXOS", texto: "Alinhamento a laser entre eixos (não implementado)" },
        { valor: "ALINHAMENTO_POLIAS", texto: "Alinhamento a laser entre polias (não implementado)" },
        { valor: "TERMOGRAFIA_MECANICA", texto: "Termografia — sistemas mecânicos (não implementado)" },
        { valor: "ENSAIO_ELETRICO_TC", texto: "Ensaios elétricos — TC (não implementado)" },
        { valor: "ENSAIO_ELETRICO_TP", texto: "Ensaios elétricos — TP (não implementado)" },
        { valor: "ENSAIO_ELETRICO_DJ", texto: "Ensaios elétricos — disjuntor (não implementado)" },
        { valor: "ENSAIO_ELETRICO_CS", texto: "Ensaios elétricos — chave seccionadora (não implementado)" },
        { valor: "ENSAIO_ELETRICO_RP", texto: "Ensaios elétricos — relé de proteção (não implementado)" },
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
      // Vínculos explícitos que decidem o cadastro técnico do equipamento —
      // o sistema nunca os deduz pelo nome do tipo.
      { key: "categoria_tecnica", label: "Categoria técnica (datasheet específico)", type: "escolha", escolhas: [
        { valor: "MOTOR_ELETRICO", texto: "Motor elétrico" },
        { valor: "TRANSFORMADOR", texto: "Transformador" },
      ] },
      { key: "analise_vibracao", label: "Avaliado por severidade de vibração (máquina rotativa)", type: "boolean" },
    ],
    columns: ["nome", "categoria_tecnica_display", "analise_vibracao", "descricao"],
  },
  {
    // Perfil normativo da vibração: limites por classe, com norma, origem e
    // vigência. Acordo com o cliente prevalece sobre a norma e sai identificado.
    key: "criterios-vibracao",
    label: "Critérios de severidade de vibração",
    endpoint: "criterios-vibracao",
    fields: [
      { key: "norma_codigo", label: "Norma", required: true, maxLength: 40 },
      { key: "norma_edicao", label: "Edição", maxLength: 20 },
      { key: "classe", label: "Classe da máquina", type: "escolha", required: true, escolhas: CLASSES_VIBRACAO },
      { key: "descricao_grupo", label: "Descrição do grupo", maxLength: 120 },
      { key: "limite_ab", label: "Limite A/B (mm/s RMS)", type: "number", required: true },
      { key: "limite_bc", label: "Limite B/C (mm/s RMS)", type: "number", required: true },
      { key: "limite_cd", label: "Limite C/D (mm/s RMS)", type: "number", required: true },
      { key: "origem", label: "Origem do valor", type: "escolha", required: true, escolhas: [
        { valor: "NORMA", texto: "Norma (valor publicado)" },
        { valor: "RESPONSAVEL_TECNICO", texto: "Critério do responsável técnico" },
        { valor: "ACORDO_CLIENTE", texto: "Acordo com o cliente / contrato" },
        { valor: "LEGADO", texto: "Legado (origem não documentada)" },
      ] },
      { key: "fonte", label: "Fonte (tabela da norma, ata, contrato…)", maxLength: 250 },
      { key: "cliente", label: "Só para o cliente (vazio = todos)", type: "ref", optionsEndpoint: "clientes" },
      { key: "vigencia_inicio", label: "Vigência — início", type: "date" },
      { key: "vigencia_fim", label: "Vigência — fim", type: "date" },
    ],
    columns: ["norma_codigo", "norma_edicao", "classe", "limite_ab", "limite_bc", "limite_cd", "origem_display",
      "cliente_nome", "vigencia_inicio"],
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
  // Ensaios de transformador — opções do registro da coleta de óleo.
  catSimples("tipos-fluido", "Tipos de fluido isolante"),
  {
    key: "pontos-coleta",
    label: "Pontos de coleta de amostras",
    endpoint: "pontos-coleta",
    fields: [
      { key: "nome", label: "Nome", required: true, maxLength: 250 },
      { key: "modulo", label: "Tecnologia (vazio = todas)", type: "escolha", escolhas: [
        { valor: "OLEO_ISOLANTE", texto: "Óleo isolante (transformador)" },
        { valor: "FLUIDO_LUBRIFICANTE", texto: "Fluidos lubrificantes e hidráulicos" },
      ] },
      { key: "descricao", label: "Descrição" },
    ],
    columns: ["nome", "modulo_display", "descricao"],
  },
  // Fluidos lubrificantes e hidráulicos.
  {
    key: "produtos-fluido",
    label: "Fluidos lubrificantes / hidráulicos",
    endpoint: "produtos-fluido",
    fields: [
      { key: "nome", label: "Produto", required: true, maxLength: 250 },
      { key: "fabricante", label: "Fabricante", maxLength: 80 },
      { key: "aplicacao", label: "Aplicação", type: "escolha", escolhas: APLICACOES_FLUIDO },
      { key: "grau_viscosidade", label: "Grau de viscosidade (ex.: ISO VG 46)", maxLength: 20 },
      { key: "viscosidade_40c_cst", label: "Viscosidade a 40 °C do óleo novo (cSt)", type: "number" },
      { key: "viscosidade_100c_cst", label: "Viscosidade a 100 °C do óleo novo (cSt)", type: "number" },
      { key: "indice_viscosidade", label: "Índice de viscosidade", type: "number" },
      { key: "descricao", label: "Observações" },
    ],
    columns: ["nome", "fabricante", "aplicacao_display", "grau_viscosidade"],
  },
  {
    // Regra acordada: lubrificante → FQ + EF; hidráulico → FQ + EF + CP.
    key: "solicitacoes-padrao-ensaio",
    label: "Ensaios solicitados por padrão (fluidos)",
    endpoint: "solicitacoes-padrao-ensaio",
    fields: [
      { key: "aplicacao", label: "Aplicação do fluido", type: "escolha", required: true, escolhas: APLICACOES_FLUIDO },
      { key: "ensaio", label: "Ensaio", type: "ref", required: true, optionsEndpoint: "ensaios?modulo=FLUIDO_LUBRIFICANTE" },
    ],
    columns: ["aplicacao_display", "ensaio_sigla"],
  },
  {
    // Limites de alerta/crítico por escopo (equipamento > fluido > cliente >
    // aplicação), com origem e vigência. Sem referência, o valor sai sem
    // classificação — o sistema não usa limite universal.
    key: "referencias-parametro",
    label: "Referências dos parâmetros (fluidos)",
    endpoint: "referencias-parametro",
    fields: [
      { key: "parametro", label: "Parâmetro", type: "ref", required: true,
        optionsEndpoint: "parametros-ensaio?ensaio__modulo=FLUIDO_LUBRIFICANTE" },
      { key: "tipo", label: "Tipo de referência", type: "escolha", required: true, escolhas: [
        { valor: "MAXIMO", texto: "Máximo (alerta/crítico acima do limite)" },
        { valor: "MINIMO", texto: "Mínimo (alerta/crítico abaixo do limite)" },
        { valor: "VARIACAO", texto: "Variação em relação ao valor de base (%)" },
        { valor: "CODIGO_ISO", texto: "Meta de limpeza ISO 4406 (parâmetro Código ISO)" },
        { valor: "QUALITATIVO", texto: "Resultado esperado (texto)" },
      ] },
      { key: "limite_alerta", label: "Limite de alerta (na variação, em %)", type: "number" },
      { key: "limite_critico", label: "Limite crítico (na variação, em %; na meta ISO, graus acima)", type: "number" },
      { key: "valor_base", label: "Valor de base (óleo novo / nominal)", type: "number" },
      { key: "base_grau_iso", label: "Base = grau ISO VG do fluido da amostra (ex.: ISO VG 68 → 68 cSt)", type: "boolean" },
      { key: "referencia_texto", label: "Meta ISO (X/Y/Z) ou resultado esperado", maxLength: 40 },
      { key: "equipamento", label: "Só para o equipamento", type: "ref", optionsEndpoint: "equipamentos" },
      { key: "produto", label: "Só para o fluido", type: "ref", optionsEndpoint: "produtos-fluido" },
      { key: "cliente", label: "Só para o cliente", type: "ref", optionsEndpoint: "clientes" },
      { key: "aplicacao", label: "Só para a aplicação", type: "escolha", escolhas: APLICACOES_FLUIDO },
      { key: "origem", label: "Origem", type: "escolha", required: true, escolhas: [
        { valor: "NORMA", texto: "Norma" },
        { valor: "FABRICANTE_EQUIPAMENTO", texto: "Fabricante do equipamento" },
        { valor: "FABRICANTE_FLUIDO", texto: "Fabricante do fluido" },
        { valor: "LABORATORIO", texto: "Laboratório" },
        { valor: "CLIENTE", texto: "Acordo com o cliente / contrato" },
        { valor: "OLEO_NOVO", texto: "Óleo novo (baseline medido)" },
        { valor: "RESPONSAVEL_TECNICO", texto: "Critério do responsável técnico" },
      ] },
      { key: "fonte", label: "Fonte (manual, laudo, contrato…)", maxLength: 250 },
      { key: "vigencia_inicio", label: "Vigência — início", type: "date" },
      { key: "vigencia_fim", label: "Vigência — fim", type: "date" },
      { key: "observacao", label: "Observação", type: "textarea" },
    ],
    columns: ["ensaio_sigla", "parametro_nome", "tipo_display", "limite_alerta", "limite_critico", "referencia_texto",
      "equipamento_tag", "produto_nome", "origem_display"],
  },
  {
    key: "itens-checklist-visual",
    label: "Itens da inspeção visual (óleo)",
    endpoint: "itens-checklist-visual",
    fields: [
      { key: "nome", label: "Item", required: true, maxLength: 250 },
      { key: "grupo", label: "Grupo", type: "escolha", escolhas: [
        { valor: "GERAL", texto: "Geral" },
        { valor: "TANQUE_EXPANSAO", texto: "Exclusivo para equipamentos com tanque de expansão" },
      ] },
      { key: "ordem", label: "Ordem na ficha", type: "number" },
      { key: "descricao", label: "Descrição" },
    ],
    columns: ["nome", "grupo_display", "ordem"],
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
