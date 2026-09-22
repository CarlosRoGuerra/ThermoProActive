import { expect, test, type Page } from "@playwright/test";

/**
 * Relatório técnico — folha de manutenção corretiva de BALANCEAMENTO.
 *
 * Mesmo padrão de `auth.spec.ts`: a API é mockada por rota (`page.route`), sem
 * backend real — o objetivo aqui é a RENDERIZAÇÃO da folha a partir de um payload
 * já no formato que `apps.servicos.relatorio_corretivo` produz (coberto por teste
 * de backend em `test_relatorio_corretivo.py`), não a geração do dado em si.
 *
 * Cobre o critério de aceite do relatório de balanceamento (docs/09): Mostrador de
 * fase, Resultado do Balanceamento, Evolução da Vibração e Economia aparecem; os
 * blocos exclusivos da preditiva (Planejamento/Corretiva Prog./Finalização,
 * Espectro, Tendência, Retorno de Informação, Aceleração) não aparecem na folha
 * corretiva; sem rolagem horizontal, também no CSS de impressão (`@media print`).
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

const RELATORIO_ID = 999;

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
  numero: "RT-BAL-2026-09-22-00001", tecnologia: "Balanceamento", tecnologia_imagem: null,
  analistas: [{ nome: "Analista Teste", assinatura: null }],
  definicao_tecnica: "", definicao_fluxo_trabalho: "", definicao_legenda_imagem: "",
  pontos_medicao_imagem: null,
  data_inicio: "2026-09-22", data_termino: "2026-09-22", data_finalizacao: null,
  instrumentos: [], normas: [], glossario: [], consideracoes_finais: "",
};

const secaoB = {
  condicoes: [], componentes: [], anomalias: [], alarmes: [],
  equip_monitorados: 1, anomalias_diagnosticadas: 1, media_anomalias_por_equipamento: 1,
  diagnostico_medio: { velocidade: 12.31, aceleracao: 3.5, temperatura: null },
  custo_evitado: "0", taxa_acerto_diagnostico: null, diagnosticos_avaliados: 0,
  mtbf_dias: null, cobertura_ativos_criticos: null,
};

const secaoC = {
  total: 1,
  grupos: [{ area: "Área Teste", setor: "Setor Teste", linhas: [{ tag: "EX-1", equipamento: "Exaustor 1", condicao: "GR3" }] }],
};

/** Folha da Seção D — balanceamento corretivo completo (2 planos, ponto medido,
 *  Reference/Trial/Trim e economia inteira), no formato do payload real. */
const folhaBalanceamento = {
  osp: "1/1", area: "Área Teste", setor: "Setor Teste", tag: "EX-1", equipamento: "Exaustor 1",
  componente: "Rotor do exaustor", anomalia: "Desbalanceamento", recomendacao: "Balancear rotor",
  observacao: "", grau_risco: "GR3", grau_risco_descricao: "Risco Moderado",
  // Deliberadamente PREENCHIDO: prova que o layout SUPRIME a aceleração por
  // decisão de apresentação, não porque o dado esteja ausente do payload.
  amplitude_velocidade: "12.31", amplitude_aceleracao: "3.500",
  temperatura_medida: null, temperatura_referencia: null, delta_t: null, carga_percentual: null,
  corrente: [null, null, null, null], tensao: [null, null, null, null], analista: "Analista Teste",
  imagens: [], avaliacao: null,
  tipo_corretiva: "BALANCEAMENTO", tipo_corretiva_display: "Balanceamento dinâmico em campo",
  corretiva: {
    servico_id: 1, tipo: "BALANCEAMENTO", rotacao_hz: 29.74, rotacao_rpm: 1784, classe_iso: "II",
    ponto_foco: 1, velocidade_referencia: 12.31,
    planos: [{
      id: 1, numero: 1, descricao: "lado acoplamento",
      massa_teste_g: 30, angulo_teste: 0, massa_final_g: 100, angulo_final: 210,
    }],
    pontos: [{
      id: 1, codigo_ponto: "2H", numero_mancal: 2, direcao: "H",
      identificacao: "Motor — lado acoplamento", plano: 1,
      reference: { mms: 12.31, fase: null }, trial: { mms: 23.95, fase: 0 }, trim: { mms: 1.70, fase: 210 },
      completo: true, residual_pct: 13.8, reducao_pct: 86.2, zona_iso: "B",
      criticidade: "NORMAL", criticidade_display: "Normal", eficaz: true,
      diagnostico: "Vibração reduzida de 12,31 para 1,70 mm/s.",
    }],
    resultado: { pontos_completos: 1, reducao_media_pct: 86.2, criticidade_final: "NORMAL" },
    economia: {
      tensao_v: "440.00", corrente_antes_a: "120.00", corrente_apos_a: "110.00",
      fator_potencia: "0.850", horas_dia: "24.0", dias_ano: 365, custo_kwh: "0.6500",
      investimento: "3500.00", reducao_corrente_a: "10.00", reducao_kw: "6.4800",
      economia_kwh_ano: "56764.80", economia_rs_ano: "36897.12", payback_meses: "1.14",
      payback_dias: "34.6", retorno_ano: "10.542",
      premissas: ["Potência trifásica √3·V·I·cosφ", "Regime 24 h/dia, 365 dias/ano"],
    },
  },
};

const dossie = { cabecalho, secao_b: secaoB, secao_c: secaoC, secao_d: [folhaBalanceamento] };

async function mockApiComDossie(page: Page) {
  await page.route("**/api/**", async (route) => {
    const url = route.request().url();
    if (url.endsWith("/auth/csrf/")) {
      await route.fulfill({ status: 200, headers: { "set-cookie": "csrftoken=test; Path=/" }, json: { csrfToken: "test" } });
    } else if (url.endsWith("/auth/me/")) {
      await route.fulfill({ status: 200, json: admin });
    } else if (url.includes(`/relatorios-inspecao/${RELATORIO_ID}/dossie/`)) {
      await route.fulfill({ status: 200, json: dossie });
    } else {
      await route.fulfill({ status: 200, json: { results: [], count: 0 } });
    }
  });
}

/** A seção física (`.pagina`) que contém esta folha — escopo das checagens de
 *  ausência, para não colidir com rótulos de mesmo nome em outras seções do
 *  relatório (ex.: "Aceleração RMS (g)" é um KPI da Seção B, sempre presente e
 *  sem relação com o bloco de amplitudes da OSP). */
function folha(page: Page) {
  return page.locator("section.pagina", { hasText: "OSP nº. 1/1" });
}

test.describe("relatório corretivo de balanceamento @relatorio", () => {
  test("folha mostra mostrador, resultado, evolução e economia — sem blocos preditivos", async ({ page }) => {
    await mockApiComDossie(page);
    await page.goto(`/relatorios-inspecao/${RELATORIO_ID}`);

    const secao = folha(page);
    await expect(secao).toBeVisible();

    // Presentes: o novo layout do balanceamento corretivo.
    await expect(secao.getByText("Mostrador de Fase — Trim Run")).toBeVisible();
    await expect(secao.getByText("Resultado do Balanceamento")).toBeVisible();
    await expect(secao.getByText("Evolução da Vibração")).toBeVisible();
    await expect(secao.getByText("Economia Energética Gerada")).toBeVisible();

    // O resultado usa o ângulo do TRIM (210°) — nunca o do Trial (0°) — e a massa
    // final do plano, nunca a de teste.
    await expect(secao.getByText(/Ângulo da\s+massa de correção:\s*210,0°/)).toBeVisible();
    await expect(secao.getByText(/100,00\s*g/)).toBeVisible();

    // Ausentes NESTA folha: blocos exclusivos da preditiva.
    const texto = await secao.innerText();
    for (const rotulo of [
      "Planejamento", "Corretiva Prog.", "Finalização OSP",
      "Espectro", "Tendência", "Retorno de Informação", "Aceleração",
    ]) {
      expect(texto, `"${rotulo}" não deveria aparecer na folha de balanceamento`).not.toContain(rotulo);
    }
    // Só a velocidade aparece no bloco de amplitudes.
    expect(texto).toContain("Velocidade [mm/s]");
  });

  test("folha corretiva sem rolagem horizontal, em tela e na impressão", async ({ page }) => {
    await mockApiComDossie(page);
    await page.goto(`/relatorios-inspecao/${RELATORIO_ID}`);
    await expect(folha(page)).toBeVisible();

    const semRolagem = async () => {
      const tamanhos = await page.evaluate(() => ({
        scroll: document.documentElement.scrollWidth,
        client: document.documentElement.clientWidth,
      }));
      expect(tamanhos.scroll).toBeLessThanOrEqual(tamanhos.client);
    };

    await semRolagem();
    await page.emulateMedia({ media: "print" });
    await semRolagem();
  });
});

test.describe("relatório preditivo — regressão @relatorio", () => {
  test("relatório sem manutenção corretiva mantém o layout preditivo", async ({ page }) => {
    const folhaPreditiva = {
      ...folhaBalanceamento,
      osp: "2/2", tipo_corretiva: "", tipo_corretiva_display: "", corretiva: null,
      imagens: [
        { tipo: "Linha de tendência", arquivo: "https://example.test/tendencia.png", legenda: "" },
        { tipo: "Espectro", arquivo: "https://example.test/espectro.png", legenda: "" },
      ],
    };
    await page.route("**/api/**", async (route) => {
      const url = route.request().url();
      if (url.endsWith("/auth/csrf/")) {
        await route.fulfill({ status: 200, headers: { "set-cookie": "csrftoken=test; Path=/" }, json: { csrfToken: "test" } });
      } else if (url.endsWith("/auth/me/")) {
        await route.fulfill({ status: 200, json: admin });
      } else if (url.includes(`/relatorios-inspecao/${RELATORIO_ID}/dossie/`)) {
        await route.fulfill({
          status: 200,
          json: { ...dossie, secao_d: [folhaPreditiva] },
        });
      } else {
        await route.fulfill({ status: 200, json: { results: [], count: 0 } });
      }
    });

    await page.goto(`/relatorios-inspecao/${RELATORIO_ID}`);
    const secao = page.locator("section.pagina", { hasText: "OSP nº. 2/2" });
    await expect(secao).toBeVisible();

    // Layout preditivo intacto: aceleração, planejamento e os slots de imagem antigos.
    await expect(secao.getByText("Aceleração [g")).toBeVisible();
    await expect(secao.getByText("Planejamento")).toBeVisible();
    await expect(secao.getByText("Corretiva Prog.")).toBeVisible();
    await expect(secao.getByText("Finalização OSP")).toBeVisible();
    const texto = await secao.innerText();
    for (const rotulo of ["Mostrador de Fase", "Resultado do Balanceamento", "Evolução da Vibração"]) {
      expect(texto).not.toContain(rotulo);
    }
  });
});
