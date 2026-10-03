import { expect, test, type Page } from "@playwright/test";

/**
 * Relatório de fluidos lubrificantes e hidráulicos (FQ, EF, CP) e o fim do
 * "módulo padrão = vibração". API mockada; o payload segue o formato de
 * `apps.ensaios.relatorio_fluidos` (coberto por testes de backend).
 *
 *   - mesmo shell (capa, carta, KPIs, equipamentos) e fichas próprias;
 *   - nada de vibração (ISO-10816, faixas de velocidade) em lugar nenhum;
 *   - CP com o código ISO 4406 e a meta; folhas A4 sem estouro;
 *   - tecnologia sem módulo: aviso, nunca o layout de outra técnica.
 */

const admin = {
  id: 1, email: "admin@thermo.test", nome: "Admin Teste", perfil: "ADMIN",
  perfil_display: "Administrador", nivel: "MASTER", nivel_display: "Master",
  ambiente: "BackEnd", grupo_acesso: "BackEnd-Master", is_interno: true, is_cliente: false,
  is_master: true, pode_excluir: true, pode_curar_dados_sistema: true, empresa: 1, cliente: null,
  cargo: "Diretor", conselho_classe: "", is_active: true, estado: "ACTIVE",
  email_verificado_em: "2026-01-01T00:00:00Z", exigir_troca_senha: false,
  mfa_obrigatorio: false, mfa_ativo: false,
};

const RELATORIO_ID = 998;

const cabecalho = {
  prestador: {
    nome: "ThermoProActive Ltda", cnpj: "00.000.000/0001-00", inscricao_estadual: "",
    endereco: "Rua Teste, 1", cidade_uf: "São Paulo/SP", endereco_linha1: "Rua Teste, 1",
    endereco_linha2: "01000-000 – São Paulo/SP", email: "contato@thermo.test",
    telefone: "(11) 90000-0000", site: "", logomarca: null,
  },
  empresa: "Exemplo Indústria Têxtil Ltda", nome_fantasia: "Exemplo Têxtil", cnpj: "11.111.111/0001-11",
  endereco: "Av. Exemplo, 100", cidade_uf: "Campinas/SP",
  endereco_linha1: "Av. Exemplo, 100", endereco_linha2: "13000-000 – Campinas/SP",
  contato: "", departamento: "", logomarca: null,
  numero: "RT-AFLH-2026-09-30-00020", tecnologia: "Análise de Fluídos Lubrificantes e Hidráulicos",
  tecnologia_imagem: null, analistas: [{ nome: "Analista Teste", assinatura: null }],
  definicao_tecnica: "", definicao_fluxo_trabalho: "", definicao_legenda_imagem: "", pontos_medicao_imagem: null,
  data_inicio: "2026-09-30", data_termino: "2026-09-30", data_finalizacao: null,
  instrumentos: [], normas: [{ codigo: "ASTM D445", nome: "Viscosidade cinemática", orgao: "ASTM" }],
  glossario: [], consideracoes_finais: "",
};

const carta = {
  conteudo: ["Seção A – Carta ao Cliente", "Seção D – Fichas da Análise de Fluidos [coleta da amostra e resultados FQ, EF e CP]"],
  glossario: [
    { n: "6.1", sigla: "Ensaios", texto: "" },
    { n: "6.1.1", sigla: "FQ", texto: "Físico-Química." },
    { n: "6.1.2", sigla: "EF", texto: "Espectrofotometria." },
    { n: "6.1.3", sigla: "CP", texto: "Contagem de Partículas." },
  ],
  quebras_glossario: [], consideracoes: ["Os resultados representam a condição do fluido na data da coleta."],
  paragrafos: ["Neste ciclo foi analisada 1 amostra de fluido lubrificante/hidráulico de 1 equipamento."],
};

const campanhas = [{ data: "2026-03-20", atual: false }, { data: "2026-09-30", atual: true }];
const celula = (valor: number | null) => ({ valor, texto: "", estado: "MEDIDO", metodo: "" });
const linha = (codigo: string, nome: string, unidade: string, valores: (number | null)[], extra = {}) => ({
  codigo, nome, simbolo: "", grupo: "", unidade, norma: "ASTM D445", metodo: "", casas: 1, no_grafico: true,
  qualitativo: false, valores: valores.map(celula), referencia: null, status: null, variacao_pct: null,
  sem_referencia: true, tendencia: null, ...extra,
});
const laudo = {
  solicitado: true, situacao: "REALIZADO", avaliados: 1, alertas: 1, criticas: 0, fora: 1, sem_referencia: 0,
  numero_laudo: "EX-1", criticidade: "Alerta", criticidade_codigo: "ALERTA", data_analise: "2026-10-01",
  data_proxima: "2027-03-30", conclusao: "", recomendacao: "Filtragem off-line.", informacoes_adicionais: "",
  instrumento: "", laboratorio: "Laboratório Teste",
  rotulos: { conclusao: "Conclusão", informacoes: "Informações Adicionais", proxima: "Data da Próxima Coleta" },
  notas: [], campanhas, grupos: [""], observacoes_geradas: [],
};

const grau = {
  sigla: "GR-3", rotulo: "GR-3", prazo_dias: 60, prazo_texto: "Intervenção em até 60 dias",
  ensaios_com_anomalia: 2, ensaios_avaliados: 2, origem: "REFERENCIAS",
};
const amostra = {
  equipamento_id: 1, data: "2026-09-30", grau_risco: grau,
  item_id: 1, tag: "UH-01", equipamento: "Unidade Hidráulica", area: "Utilidades", setor: "Hidráulica", condicao: "OK",
  cadastro: { local: "Hidráulica", identificacao: "UH-01 - Unidade Hidráulica", numero_serie: "", numero_patrimonio: "",
    fabricante: "", modelo: "", ano_fabricacao: null, tipo_equipamento: "Unidade hidráulica" },
  coleta: {
    data: "2026-09-30", identificacao_amostra: "A-1", amostrador: "Analista", aplicacao: "HIDRAULICO",
    aplicacao_display: "Hidráulico", fluido: "HLP 46", fabricante_fluido: "", grau_viscosidade: "ISO VG 46",
    ponto_coleta: "Linha de retorno, antes do filtro", temperatura_fluido_c: 45, temperatura_ambiente_c: 30,
    condicao_operacional: "Em operação", horas_equipamento: null, horas_fluido: 2400, volume_reservatorio_l: 250, data_ultima_troca: null,
    complemento_recente: null, volume_complemento_l: null, troca_filtro_recente: false, intervencao_recente: "",
    observacoes: "",
  },
  tipos_ensaio: [
    { sigla: "FQ", nome: "Físico-Química", solicitado: true },
    { sigla: "EF", nome: "Espectrofotometria", solicitado: true },
    { sigla: "CP", nome: "Contagem de Partículas", solicitado: true },
  ],
  ensaios: [
    { ...laudo, sigla: "FQ", nome: "Físico-Química", rotulo: "FQ", titulo: "RESULTADOS DO ENSAIO FQ - FÍSICO-QUÍMICA",
      status: "ALERTA", status_rotulo: "Alerta", tipo: "PARAMETROS",
      observacoes_geradas: ["Viscosidade cinemática a 40 °C: 39,2 cSt, em alerta (referência: Base 46,00 cSt)."],
      linhas: [linha("VISC40", "Viscosidade cinemática a 40 °C", "cSt", [45.6, 39.2], {
        status: "ALERTA", sem_referencia: false, variacao_pct: -14.8,
        referencia: { id: 1, tipo: "VARIACAO", tipo_display: "Variação", valor_base: 46, limite_alerta: 10,
          limite_critico: 20, referencia_texto: "", texto: "Base 46,00 cSt · Alerta ±10% · Crítico ±20%",
          origem: "FABRICANTE_FLUIDO", origem_display: "Fabricante do fluido", fonte: "Ficha técnica",
          vigencia_inicio: null, vigencia_fim: null, escopo: "Fluido" },
        tendencia: { delta_anterior: -6.4, pct_anterior: -14, pct_primeiro: -14, direcao: "DESCE", pontos: 2 } })] },
    { ...laudo, sigla: "EF", nome: "Espectrofotometria", rotulo: "EF", titulo: "RESULTADOS DO ENSAIO EF - ESPECTROFOTOMETRIA",
      status: "SEM_CRITERIO", status_rotulo: "Sem referência cadastrada", tipo: "PARAMETROS",
      grupos: ["Metais de desgaste"],
      linhas: [linha("FE", "Ferro", "ppm", [12, 58], { simbolo: "Fe", grupo: "Metais de desgaste", norma: "ASTM D5185" })] },
    { ...laudo, sigla: "CP", nome: "Contagem de Partículas", rotulo: "CP", titulo: "RESULTADOS DO ENSAIO CP - CONTAGEM DE PARTÍCULAS",
      status: "ALERTA", status_rotulo: "Alerta", tipo: "CP", grupos: ["Contagem"],
      linhas: [
        linha("P4", "Partículas > 4 µm(c)", "part./mL", [1800, 4100], { grupo: "Contagem", sem_referencia: false, casas: 0 }),
        linha("P6", "Partículas > 6 µm(c)", "part./mL", [500, 1250], { grupo: "Contagem", sem_referencia: false, casas: 0 }),
        linha("P14", "Partículas > 14 µm(c)", "part./mL", [60, 110], { grupo: "Contagem", sem_referencia: false, casas: 0 }),
      ],
      codigos: [
        { data: "2026-03-20", atual: false, codigo: "18/16/13", escalas: [18, 16, 13] },
        { data: "2026-09-30", atual: true, codigo: "19/17/14", escalas: [19, 17, 14] },
      ],
      meta: { id: 2, tipo: "CODIGO_ISO", tipo_display: "Meta", valor_base: null, limite_alerta: null, limite_critico: 3,
        referencia_texto: "17/15/12", texto: "Meta 17/15/12", origem: "FABRICANTE_EQUIPAMENTO",
        origem_display: "Fabricante do equipamento", fonte: "Manual da UH", vigencia_inicio: null, vigencia_fim: null,
        escopo: "Equipamento" },
      situacao_meta: "FORA", excesso_meta: 2 },
  ],
};

const kpis = {
  amostras: 1, equipamentos: 1, ensaios_solicitados: 3, ensaios_realizados: 3, ensaios_pendentes: 0,
  parametros_avaliados: 2, parametros_alerta: 2, parametros_criticos: 0, parametros_sem_referencia: 1,
  laudos_por_criticidade: [{ rotulo: "Alerta", total: 3, percentual: 100 }],
  avaliacao_ensaios: [{ rotulo: "Alerta", total: 2, percentual: 66.7 }, { rotulo: "Sem referência cadastrada", total: 1, percentual: 33.3 }],
  limpeza: { dentro: 0, fora: 1, sem_meta: 0 },
  status_por_ensaio: [
    { rotulo: "FQ", status: "ALERTA", status_rotulo: "Alerta" },
    { rotulo: "EF", status: "SEM_CRITERIO", status_rotulo: "Sem referência cadastrada" },
    { rotulo: "CP", status: "ALERTA", status_rotulo: "Alerta" },
  ],
  proxima_data: "2027-03-30",
};

const graficos = {
  condicoes: [{ rotulo: "GR-3", total: 1, percentual: 100 }],
  componentes: [{ rotulo: "Unidade hidráulica", total: 1, percentual: 100 }],
  anomalias: [{ rotulo: "Viscosidade cinemática a 40 °C", total: 1, percentual: 50 }, { rotulo: "Código ISO 4406", total: 1, percentual: 50 }],
  graus_tempo: {
    meses: ["mar/26", "set/26"],
    series: [
      { gr: "GR-1", rotulo: "GR-1", valores: [0, 0] }, { gr: "GR-2", rotulo: "GR-2", valores: [0, 0] },
      { gr: "GR-3", rotulo: "GR-3", valores: [0, 1] }, { gr: "GR-4", rotulo: "GR-4", valores: [1, 0] },
      { gr: "GR-0", rotulo: "OK", valores: [0, 0] },
    ],
  },
  equipamentos_anomalias: { meses: ["mar/26", "set/26"], monitorados: [1, 1], anomalias: [1, 1] },
  osp: { colunas: ["Aberta", "Corrigida", "Reincidente", "Não reavaliada"],
    linhas: [{ gr: "GR-3", valores: [0, 0, 1, 0] }, { gr: "GR-4", valores: [0, 0, 0, 0] }] },
};

const dossie = {
  modulo: "FLUIDO_LUBRIFICANTE", cabecalho, carta, graficos,
  secao_c: { total: 1, equip_monitorados: 1, grupos: [{ area: "Utilidades", setor: "Hidráulica", linhas: [{ tag: "UH-01", equipamento: "Unidade Hidráulica", condicao: "OK" }] }] },
  amostras: [amostra], kpis, contato_cliente: { telefone: "", email: "" },
};

async function mockApi(page: Page, resposta: { status: number; json: unknown }) {
  await page.route("**/api/**", async (route) => {
    const url = route.request().url();
    if (url.endsWith("/auth/csrf/")) {
      await route.fulfill({ status: 200, headers: { "set-cookie": "csrftoken=test; Path=/" }, json: { csrfToken: "test" } });
    } else if (url.endsWith("/auth/me/")) {
      await route.fulfill({ status: 200, json: admin });
    } else if (url.includes(`/relatorios-inspecao/${RELATORIO_ID}/dossie/`)) {
      await route.fulfill(resposta);
    } else {
      await route.fulfill({ status: 200, json: { results: [], count: 0 } });
    }
  });
}

test.describe("relatório de fluidos lubrificantes e hidráulicos @relatorio", () => {
  test("fichas FQ, EF e CP no shell comum, sem conteúdo de vibração", async ({ page }) => {
    await mockApi(page, { status: 200, json: dossie });
    await page.goto(`/relatorios-inspecao/${RELATORIO_ID}`);
    const area = page.locator(".print-area");
    await expect(area.getByText("REGISTRO DE DADOS DE COLETA DE AMOSTRA DE FLUIDO")).toBeVisible();
    await expect(area.getByText("RESULTADOS DO ENSAIO FQ - FÍSICO-QUÍMICA")).toBeVisible();
    await expect(area.getByText("RESULTADOS DO ENSAIO EF - ESPECTROFOTOMETRIA")).toBeVisible();
    await expect(area.getByText("RESULTADOS DO ENSAIO CP - CONTAGEM DE PARTÍCULAS")).toBeVisible();
    await expect(area.getByText("Amostras analisadas")).toBeVisible();
    await expect(area.getByText("Fora da meta")).toBeVisible();
    await expect(area.getByText("19/17/14").first()).toBeVisible();

    // Seção B (gráficos gerenciais) e o diagnóstico de cada ficha, como no relatório-modelo.
    for (const titulo of ["Status das Condições (Grau de Risco)", "Status dos Componentes", "Status dos Graus de Risco",
      "Equipamentos Inspecionados × Anomalias Diagnosticadas", "Controle das O.S.P.'s"]) {
      await expect(area.getByText(titulo, { exact: false }).first()).toBeVisible();
    }
    await expect(area.getByText("Intervenção em até 60 dias").first()).toBeVisible();
    await expect(area.getByText("Volume do Reservatório")).toBeVisible();
    await expect(area.getByText("Viscosidade cinemática a 40 °C: 39,2 cSt, em alerta")).toBeVisible();
    await expect(area.getByText("Intensificar monitoramento").first()).toBeVisible();

    const texto = await area.innerText();
    for (const vibracao of ["10816", "20816", "Faixas de Velocidade", "Amplitudes", "mm/s"]) {
      expect(texto, `"${vibracao}" não pode aparecer no relatório de fluidos`).not.toContain(vibracao);
    }
    // Quadro "Espectro" da vibração (palavra inteira — "Espectrofotometria" é o EF).
    expect(texto).not.toMatch(/Espectro/);
  });

  test("toda folha é uma A4 sem estouro e sem rolagem horizontal", async ({ page }) => {
    await mockApi(page, { status: 200, json: dossie });
    await page.goto(`/relatorios-inspecao/${RELATORIO_ID}`);
    await expect(page.getByText("RESULTADOS DO ENSAIO CP - CONTAGEM DE PARTÍCULAS")).toBeVisible();
    const folhas = await page.locator(".print-area > section, .print-area .carta-doc > section").evaluateAll((els) =>
      els.map((el) => ({ altura: el.getBoundingClientRect().height, estouro: el.scrollHeight - el.clientHeight })));
    expect(folhas.length).toBeGreaterThan(8);
    for (const [i, f] of folhas.entries()) {
      expect(f.estouro, `folha ${i} com conteúdo além da A4`).toBeLessThanOrEqual(2);
      expect(Math.round(f.altura), `folha ${i} fora da altura A4`).toBeLessThanOrEqual(1124);
    }
    const largura = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(largura).toBeLessThanOrEqual(0);
  });
});

test.describe("sem módulo padrão de vibração @relatorio", () => {
  test("tecnologia sem módulo configurado mostra o motivo, não o layout da vibração", async ({ page }) => {
    await mockApi(page, {
      status: 409,
      json: { detail: "A tecnologia «Alinhamento» não tem módulo técnico configurado.", codigo: "modulo_nao_configurado" },
    });
    await page.goto(`/relatorios-inspecao/${RELATORIO_ID}`);
    await expect(page.getByText("não tem módulo técnico configurado")).toBeVisible();
    await expect(page.getByText("Faixas de Velocidade")).toHaveCount(0);
  });

  test("payload de módulo desconhecido não cai no layout de outra técnica", async ({ page }) => {
    await mockApi(page, { status: 200, json: { ...dossie, modulo: "ALINHAMENTO_EIXOS" } });
    await page.goto(`/relatorios-inspecao/${RELATORIO_ID}`);
    await expect(page.getByText("não está disponível nesta versão da tela")).toBeVisible();
    await expect(page.getByText("Faixas de Velocidade")).toHaveCount(0);
    await expect(page.getByText("Amplitudes [valor global]")).toHaveCount(0);
  });
});
