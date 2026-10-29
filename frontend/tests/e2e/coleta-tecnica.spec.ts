import { expect, test, type Page } from "@playwright/test";

const admin = {
  id: 1, email: "admin@thermo.test", nome: "Admin Teste", perfil: "ADMIN",
  perfil_display: "Administrador", nivel: "MASTER", nivel_display: "Master",
  ambiente: "BackEnd", grupo_acesso: "BackEnd-Master", is_interno: true, is_cliente: false,
  is_master: true, pode_excluir: true, pode_curar_dados_sistema: true, empresa: 1, cliente: null,
  cargo: "Diretor", conselho_classe: "", is_active: true, estado: "ACTIVE",
  email_verificado_em: "2026-01-01T00:00:00Z", exigir_troca_senha: false,
  mfa_obrigatorio: false, mfa_ativo: false,
};
const lista = (results: unknown[]) => ({ results, count: results.length, next: null, previous: null });

async function preparar(page: Page, tipo: string, erroServidor = false) {
  const enviados: Record<string, unknown>[] = [];
  const inspecao = {
    id: 1, cliente: 1, cliente_nome: "Cliente", tipo_analise: tipo, tipo_analise_display: tipo,
    tecnico: 1, tecnico_nome: "Técnico", data: "2026-10-21", status: "ABERTA", status_display: "Aberta",
    criticidade_maxima: "", qtd_medicoes: 0, observacoes: "", medicoes_vibracao: [],
    medicoes_termografia: [], medicoes_tecnicas: [], criado_em: "2026-10-21T10:00:00Z",
  };
  await page.route("**/api/**", async (route) => {
    const req = route.request();
    const caminho = new URL(req.url()).pathname;
    if (caminho.endsWith("/auth/csrf/")) return route.fulfill({ json: { csrfToken: "test" } });
    if (caminho.endsWith("/auth/me/")) return route.fulfill({ json: admin });
    if (caminho.endsWith("/inspecoes/1/")) return route.fulfill({ json: inspecao });
    if (caminho.endsWith("/equipamentos/")) return route.fulfill({ json: lista([
      { id: 1, tag: "EQ-01", nome: "Equipamento", classe_iso: "II", componentes: [] },
    ]) });
    if (caminho.endsWith("/instrumentos/")) return route.fulfill({ json: lista([
      { id: 9, tipo: "Medidor", marca: "Marca", modelo: "Modelo", numero_serie: "SN-09" },
    ]) });
    if (req.method() === "POST" && caminho.includes("/medicoes-")) {
      enviados.push(req.postDataJSON());
      if (erroServidor) return route.fulfill({ status: 400, json: { valor: ["Valor incompatível com a leitura."] } });
      return route.fulfill({ status: 201, json: { id: 10, ...req.postDataJSON() } });
    }
    return route.fulfill({ json: lista([]) });
  });
  await page.goto("/inspecoes/1");
  await expect(page.getByRole("heading", { name: "Inspeção #1" })).toBeVisible();
  return enviados;
}

async function identificar(page: Page) {
  await page.getByLabel("Equipamento", { exact: false }).selectOption("1");
  await page.getByLabel("Ponto de medição").fill("Ponto 1");
}

test.describe("coleta técnica contratada @coleta", () => {
  test("ODS revela fase/frequência e valida limites sem enviar leitura inválida", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    const enviados = await preparar(page, "VIBRACAO");
    await expect(page.getByLabel("Fase (°)")).toBeHidden();
    await page.getByLabel("Modalidade").selectOption("ODS");
    await identificar(page);
    await page.getByLabel("Deslocamento pico a pico").fill("1,25");
    await page.getByLabel("Frequência (Hz)").fill("60");
    await page.getByLabel("Fase (°)").fill("360");
    await page.getByRole("button", { name: "Adicionar", exact: true }).click();
    await expect(page.getByLabel("Fase (°)")).toHaveAttribute("aria-invalid", "true");
    await expect(page.getByRole("alert").filter({ hasText: "Confira os campos" })).toBeFocused();
    expect(enviados).toHaveLength(0);
    await page.getByLabel("Fase (°)").fill("359,99");
    const envio = page.waitForResponse((r) => r.url().includes("/medicoes-vibracao/") && r.request().method() === "POST");
    await page.getByRole("button", { name: "Adicionar", exact: true }).click();
    await envio;
    expect(enviados[0]).toMatchObject({ subtipo: "ODS", velocidade_rms: null, deslocamento_pp: "1.25", parametros: { frequencia_hz: "60", fase_graus: "359.99" } });
  });

  test("termografia exige ajuste de emissividade e não envia carga de outro sistema", async ({ page }) => {
    const enviados = await preparar(page, "TERMOGRAFIA");
    await expect(page.getByLabel("Emissividade")).toHaveValue("");
    await page.getByLabel("Carga (%)").fill("80");
    await page.getByLabel("Sistema", { exact: true }).selectOption("PROCESSO");
    await expect(page.getByLabel("Carga (%)")).toBeHidden();
    await identificar(page);
    await page.getByLabel("Temp. do ponto").fill("-5,5");
    await page.getByLabel("Temp. de referência").fill("0");
    await page.getByLabel("Emissividade").fill("1,1");
    await page.getByRole("button", { name: "Adicionar", exact: true }).click();
    await expect(page.getByLabel("Emissividade")).toHaveAttribute("aria-invalid", "true");
    expect(enviados).toHaveLength(0);
    await page.getByLabel("Emissividade").fill("0,85");
    const envio = page.waitForResponse((r) => r.url().includes("/medicoes-termografia/") && r.request().method() === "POST");
    await page.getByRole("button", { name: "Adicionar", exact: true }).click();
    await envio;
    expect(enviados[0]).toMatchObject({ sistema: "PROCESSO", emissividade: "0.85", carga_percentual: null, temperatura_ponto: "-5.5" });
  });

  test("TTR e resistência de motor usam campos e unidades distintos", async ({ page }) => {
    const enviados = await preparar(page, "ENSAIO_ELETRICO");
    await expect(page.getByLabel("Grandeza", { exact: true })).toContainText("Relação de transformação (TTR)");
    await expect(page.getByLabel("Valor (adimensional)")).toBeVisible();
    await page.getByLabel("Modalidade").selectOption("MOTOR_RI");
    await expect(page.getByLabel("Grandeza", { exact: true })).toContainText("Resistência de isolação (MΩ)");
    await expect(page.getByLabel("Grandeza", { exact: true }).getByRole("option", { name: /TTR/ })).toHaveCount(0);
    await identificar(page);
    await page.getByLabel("Valor (MΩ)").fill("500,25");
    await page.getByLabel("Instrumento utilizado").selectOption("9");
    const envio = page.waitForResponse((r) => r.url().includes("/medicoes-tecnicas/") && r.request().method() === "POST");
    await page.getByRole("button", { name: "Adicionar", exact: true }).click();
    await envio;
    expect(enviados[0]).toMatchObject({ subtipo: "MOTOR_RI", valor: "500.25", unidade: "MΩ", instrumento: 9 });
  });

  test("fluido mineral oferece PCB/2-FAL e hidráulico oferece contagens", async ({ page }) => {
    await preparar(page, "FLUIDOS");
    await expect(page.getByRole("combobox", { name: /^Ensaio/ }).getByRole("option", { name: "PCB", exact: true })).toHaveCount(0);
    await page.getByLabel("Modalidade").selectOption("MINERAL_ISOLANTE");
    await page.getByRole("combobox", { name: /^Ensaio/ }).selectOption("PCB");
    await expect(page.getByLabel("Valor (mg/kg)")).toBeVisible();
    await page.getByRole("combobox", { name: /^Ensaio/ }).selectOption("CR");
    await expect(page.getByLabel("Grandeza informada pelo laboratório")).toBeVisible();
    await expect(page.getByText(/definição de CR e sua correspondência/)).toBeVisible();
    await page.getByLabel("Modalidade").selectOption("HIDRAULICO");
    await page.getByRole("combobox", { name: /^Ensaio/ }).selectOption("CP");
    await expect(page.getByLabel("Grandeza", { exact: true }).getByRole("option")).toHaveCount(3);
    await expect(page.getByLabel("Valor (part./mL)")).toBeVisible();
    await expect(page.getByText(/código ISO 4406 possui três classes/)).toBeVisible();
  });

  test("erro do servidor permanece junto ao campo e preserva texto digitado", async ({ page }) => {
    await preparar(page, "ESPESSURA", true);
    await identificar(page);
    await page.getByLabel("Valor (mm)").fill("12,345");
    await page.getByRole("button", { name: "Adicionar", exact: true }).click();
    await expect(page.getByLabel("Valor (mm)")).toHaveAttribute("aria-invalid", "true");
    await expect(page.getByLabel("Valor (mm)")).toHaveValue("12,345");
    await expect(page.getByText("Valor incompatível com a leitura.", { exact: true }).last()).toBeVisible();
  });

  test("sensitiva registra avaliação qualitativa sem leitura numérica fictícia", async ({ page }) => {
    const enviados = await preparar(page, "SENSITIVA");
    await identificar(page);
    await expect(page.getByLabel(/^Valor/)).toHaveCount(0);
    await expect(page.getByLabel("Condição", { exact: true })).toHaveValue("");
    await page.getByLabel("Observação", { exact: false }).fill("Ruído intermitente observado.");
    const envio = page.waitForResponse((r) => r.url().includes("/medicoes-tecnicas/") && r.request().method() === "POST");
    await page.getByRole("button", { name: "Adicionar", exact: true }).click();
    await envio;
    expect(enviados[0]).toMatchObject({ subtipo: "SENSITIVA", valor: null, parametros: { criticidade: "", observacao: "Ruído intermitente observado." } });
  });

  test("portal distingue leitura qualitativa pendente e classificação histórica", async ({ page }) => {
    await preparar(page, "SENSITIVA");
    await page.route("**/api/auth/me/", (route) => route.fulfill({ json: {
      ...admin, is_interno: false, is_cliente: true, perfil: "CLIENTE", ambiente: "FrontEnd",
      grupo_acesso: "FrontEnd-Master", cliente: 1,
    } }));
    await page.route("**/api/inspecoes/1/", (route) => route.fulfill({ json: {
      id: 1, data: "2026-10-21", tipo_analise_display: "Sensitiva", status_display: "Em análise",
      tecnico_nome: "Técnico", criticidade_maxima: "", medicoes_vibracao: [], medicoes_termografia: [],
      medicoes_tecnicas: [
        { id: 1, equipamento_tag: "EQ-01", tipo_display: "Sensitiva", grandeza: "Inspeção sensorial", valor: null, unidade: "", valor_referencia: null, criticidade: "", classificacao_status: "PENDENTE" },
        { id: 2, equipamento_tag: "EQ-02", tipo_display: "Sensitiva", grandeza: "Legado", valor: "0", unidade: "", valor_referencia: "0", criticidade: "CRITICO", classificacao_status: "LEGADO" },
      ],
    } }));
    await page.goto("/portal/inspecoes/1");
    await expect(page.getByRole("heading", { name: "Inspeção de 21/10/2026" })).toBeVisible();
    const pendente = page.getByRole("row").filter({ hasText: "EQ-01" });
    await expect(pendente).toContainText("Avaliação qualitativa");
    await expect(pendente).toContainText("Pendente de avaliação");
    const historico = page.getByRole("row").filter({ hasText: "EQ-02" });
    await expect(historico).toContainText("Classificação histórica");
    await expect(historico).toContainText("Crítico");
    await expect(page.getByText("Avaliação técnica pendente", { exact: true })).toBeVisible();
  });
});
