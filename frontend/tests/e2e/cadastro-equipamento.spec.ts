import { expect, test, type Page } from "@playwright/test";

/**
 * Cadastro de equipamento — o TIPO decide os dados técnicos (vínculo explícito
 * do catálogo, nunca o nome). API mockada por rota, como nos outros specs.
 *
 *   Transformador → só dados de transformador; sem Classe ISO, RPM ou FP de motor.
 *   Motor elétrico → só dados de motor + severidade de vibração.
 *   Tipo sem categoria → nenhum campo de motor; aviso de onde configurar.
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

const TIPOS = [
  { id: 1, nome: "Transformador", categoria_tecnica: "TRANSFORMADOR", analise_vibracao: false },
  { id: 2, nome: "Motor elétrico", categoria_tecnica: "MOTOR_ELETRICO", analise_vibracao: true },
  { id: 3, nome: "Painel de comando", categoria_tecnica: "", analise_vibracao: false },
  // Nome sugestivo, sem categoria: o sistema NÃO deduz pelo nome.
  { id: 4, nome: "Transformador seco", categoria_tecnica: "", analise_vibracao: false },
  { id: 5, nome: "Bomba centrífuga", categoria_tecnica: "", analise_vibracao: true },
];

async function mockApi(page: Page) {
  await page.route("**/api/**", async (route) => {
    const url = route.request().url();
    if (url.endsWith("/auth/csrf/")) {
      await route.fulfill({ status: 200, headers: { "set-cookie": "csrftoken=test; Path=/" }, json: { csrfToken: "test" } });
    } else if (url.endsWith("/auth/me/")) {
      await route.fulfill({ status: 200, json: admin });
    } else if (url.includes("/tipos-equipamento/")) {
      await route.fulfill({ status: 200, json: { results: TIPOS, count: TIPOS.length, next: null, previous: null } });
    } else {
      await route.fulfill({ status: 200, json: { results: [], count: 0, next: null, previous: null } });
    }
  });
}

async function escolherTipo(page: Page, nome: string) {
  await page.locator("select").filter({ has: page.locator("option", { hasText: "Selecione…" }) }).first()
    .selectOption({ label: nome });
}

test.describe("cadastro técnico por tipo de equipamento @cadastro", () => {
  test.beforeEach(async ({ page }) => {
    await mockApi(page);
    await page.goto("/equipamentos/novo");
    await expect(page.getByRole("heading", { name: "Novo equipamento" })).toBeVisible();
  });

  test("transformador mostra só os dados do transformador", async ({ page }) => {
    await escolherTipo(page, "Transformador");
    await expect(page.getByText("Dados técnicos — Transformador")).toBeVisible();
    await expect(page.getByLabel("Potência (kVA)")).toBeVisible();
    await expect(page.getByLabel("Grupo de ligação")).toBeVisible();
    const texto = await page.locator("main").innerText();
    for (const proibido of ["Classe ISO", "Classe da máquina", "Severidade de vibração", "Rotação (RPM)",
      "Fator de potência", "Potência (kW)", "Rolamento"]) {
      expect(texto, `"${proibido}" não pode aparecer no transformador`).not.toContain(proibido);
    }
  });

  test("motor mostra só os dados do motor e a severidade de vibração", async ({ page }) => {
    await escolherTipo(page, "Motor elétrico");
    await expect(page.getByText("Dados técnicos — Motor elétrico")).toBeVisible();
    await expect(page.getByLabel("Rotação (RPM)")).toBeVisible();
    await expect(page.getByLabel("Fator de potência (FP)")).toBeVisible();
    await expect(page.getByText("Severidade de vibração")).toBeVisible();
    const texto = await page.locator("main").innerText();
    for (const proibido of ["Potência (kVA)", "Grupo de ligação", "Tanque de expansão", "Impedância"]) {
      expect(texto, `"${proibido}" não pode aparecer no motor`).not.toContain(proibido);
    }
  });

  test("tipo sem categoria não ganha campos de motor nem pelo nome", async ({ page }) => {
    for (const nome of ["Painel de comando", "Transformador seco"]) {
      await escolherTipo(page, nome);
      await expect(page.getByText(`O tipo «${nome}» não tem ficha técnica específica`)).toBeVisible();
      const texto = await page.locator("main").innerText();
      for (const proibido of ["Potência (kW)", "Rotação (RPM)", "Potência (kVA)", "Severidade de vibração"]) {
        expect(texto, `"${proibido}" não pode aparecer em «${nome}»`).not.toContain(proibido);
      }
    }
  });

  test("máquina rotativa sem datasheet tem só a classe de vibração", async ({ page }) => {
    await escolherTipo(page, "Bomba centrífuga");
    await expect(page.getByText("Severidade de vibração")).toBeVisible();
    await expect(page.getByLabel("Classe da máquina")).toBeEnabled();
    await expect(page.getByLabel("Rotação (RPM)")).toHaveCount(0);
    // Grupos da ISO 20816-3 (desde 07/10/2026); as classes II–IV da ISO 10816-1 não são oferecidas.
    const opcoes = await page.getByLabel("Classe da máquina").locator("option").allInnerTexts();
    expect(opcoes).toEqual(["Selecione…", "Classe I — até 15 kW", "Grupo 2 — 15 a 300 kW (ISO 20816-3)",
      "Grupo 1 — acima de 300 kW (ISO 20816-3)"]);
  });
});
