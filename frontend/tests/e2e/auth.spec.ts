import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const cliente = {
  id: 2, email: "cliente@empresa.test", nome: "Cliente Teste", perfil: "CLIENTE_PCM",
  perfil_display: "Cliente — PCM", nivel: "PLENO", nivel_display: "Pleno",
  ambiente: "FrontEnd", grupo_acesso: "FrontEnd-Pleno", is_interno: false, is_cliente: true,
  is_master: false, pode_excluir: false, pode_curar_dados_sistema: false,
  empresa: null, cliente: 1, cargo: "PCM", conselho_classe: "", is_active: true,
  estado: "ACTIVE", email_verificado_em: "2026-01-01T00:00:00Z", exigir_troca_senha: false,
  mfa_obrigatorio: false, mfa_ativo: false,
};

const admin = {
  ...cliente, id: 1, email: "admin@thermo.test", nome: "Admin Teste", perfil: "ADMIN",
  perfil_display: "Administrador", nivel: "MASTER", nivel_display: "Master",
  ambiente: "BackEnd", grupo_acesso: "BackEnd-Master", is_interno: true, is_cliente: false,
  is_master: true, pode_excluir: true, pode_curar_dados_sistema: true, empresa: 1, cliente: null,
};

async function mockApi(page: Page, user: typeof cliente | null = null) {
  await page.route("**/api/**", async (route) => {
    const url = route.request().url();
    if (url.endsWith("/auth/csrf/")) {
      await route.fulfill({ status: 200, headers: { "set-cookie": "csrftoken=test; Path=/" }, json: { csrfToken: "test" } });
    } else if (url.endsWith("/auth/me/") && user) {
      await route.fulfill({ status: 200, json: user });
    } else if (url.endsWith("/auth/me/") || url.endsWith("/auth/session/refresh/")) {
      await route.fulfill({ status: 401, json: { detail: "Sem sessão" } });
    } else {
      await route.fulfill({ status: 200, json: { results: [], count: 0 } });
    }
  });
}

test.describe("entradas separadas @auth @critical", () => {
  test("portal do cliente tem identidade e cadastro próprios", async ({ page }) => {
    await mockApi(page);
    await page.goto("/portal/login");
    await expect(page.getByRole("heading", { name: "Bem-vindo ao ThermoProActive" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Solicitar acesso" })).toBeVisible();
    await expect(page.getByRole("textbox", { name: /^E-mail/ })).toHaveAttribute("autocomplete", "email");
    await expect(page.getByLabel(/^Senha/)).toHaveAttribute("autocomplete", "current-password");
  });

  test("admin é restrito e não oferece cadastro público", async ({ page }) => {
    await mockApi(page);
    await page.goto("/admin/login");
    await expect(page.getByRole("heading", { name: "Área Administrativa" })).toBeVisible();
    await expect(page.getByText("Acesso exclusivo para colaboradores autorizados.")).toBeVisible();
    await expect(page.getByRole("link", { name: /cadastrar|solicitar acesso/i })).toHaveCount(0);
  });

  test("login incorreto preserva os campos e mostra erro genérico", async ({ page }) => {
    await mockApi(page);
    await page.route("**/api/auth/portal/login/", (route) => route.fulfill({ status: 401, json: { detail: "E-mail ou senha incorretos." } }));
    await page.goto("/portal/login");
    await page.getByRole("textbox", { name: /^E-mail/ }).fill("pessoa@empresa.test");
    await page.getByLabel(/^Senha/).fill("senha incorreta");
    await page.getByRole("button", { name: "Entrar" }).click();
    await expect(page.getByRole("alert").filter({ hasText: "E-mail ou senha incorretos" })).toBeVisible();
    await expect(page.getByRole("textbox", { name: /^E-mail/ })).toHaveValue("pessoa@empresa.test");
  });

  test("cliente entra no portal e não permanece na área administrativa", async ({ page }) => {
    await mockApi(page, cliente);
    await page.route("**/api/auth/portal/login/", (route) => route.fulfill({ status: 200, json: { user: cliente } }));
    await page.goto("/portal/login");
    await page.getByRole("textbox", { name: /^E-mail/ }).fill(cliente.email);
    await page.getByLabel(/^Senha/).fill("frase senha longa para teste");
    await page.getByRole("button", { name: "Entrar" }).click();
    await expect(page).toHaveURL(/\/portal\/dashboard/);
    await page.goto("/admin/dashboard");
    await expect(page).not.toHaveURL(/\/admin\/dashboard$/);
  });

  test("administrador entra no dashboard administrativo", async ({ page }) => {
    await mockApi(page, admin);
    await page.route("**/api/auth/admin/login/", (route) => route.fulfill({ status: 200, json: { user: admin } }));
    await page.goto("/admin/login");
    await page.getByRole("textbox", { name: /^E-mail corporativo/ }).fill(admin.email);
    await page.getByLabel(/^Senha/).fill("frase senha longa para teste");
    await page.getByRole("button", { name: "Acessar painel" }).click();
    await expect(page).toHaveURL(/\/admin\/dashboard/);
  });
});

test.describe("recuperação e cadastro @auth", () => {
  test("esqueci senha sempre exibe resposta neutra", async ({ page }) => {
    await mockApi(page);
    await page.route("**/api/auth/portal/esqueci-senha/", (route) => route.fulfill({ status: 200, json: { detail: "Se existir uma conta associada a esse e-mail, enviaremos as instruções para recuperação." } }));
    await page.goto("/portal/esqueci-senha");
    await page.getByRole("textbox", { name: /^E-mail/ }).fill("qualquer@empresa.test");
    await page.getByRole("button", { name: "Enviar instruções" }).click();
    await expect(page.getByText(/Se existir uma conta/)).toBeVisible();
  });

  test("reset rejeita senha curta antes de chamar a API", async ({ page }) => {
    await mockApi(page);
    await page.goto("/portal/redefinir-senha?token=token-valido-comprido-para-o-teste");
    await page.getByLabel(/^Nova senha/).fill("curta");
    await page.getByLabel(/^Confirmar nova senha/).fill("curta");
    await page.getByRole("button", { name: "Redefinir senha" }).click();
    await expect(page.getByRole("alert").filter({ hasText: "pelo menos 15 caracteres" })).toBeVisible();
  });

  test("cadastro em etapas valida e preserva os dados ao voltar", async ({ page }) => {
    await mockApi(page);
    await page.goto("/portal/cadastro");
    await page.getByRole("button", { name: "Continuar" }).click();
    await expect(page.getByRole("alert").filter({ hasText: "Revise os campos" })).toBeVisible();
    await page.getByRole("textbox", { name: /^Nome completo/ }).fill("Pessoa Responsável");
    await page.getByRole("textbox", { name: /^E-mail profissional/ }).fill("pessoa@empresa.test");
    await page.getByRole("textbox", { name: /^Telefone \/ celular/ }).fill("11999999999");
    await page.getByRole("button", { name: "Continuar" }).click();
    await expect(page.getByRole("textbox", { name: /^Razão social/ })).toBeVisible();
    await page.getByRole("button", { name: "Voltar" }).click();
    await expect(page.getByRole("textbox", { name: /^Nome completo/ })).toHaveValue("Pessoa Responsável");
  });

  test("convite expirado apresenta recuperação sem erro técnico", async ({ page }) => {
    await mockApi(page);
    await page.route("**/api/auth/convites/expirado/", (route) => route.fulfill({ status: 410, json: { valid: false } }));
    await page.goto("/portal/convite/expirado");
    await expect(page.getByRole("heading", { name: "Este convite não é mais válido." })).toBeVisible();
  });

  test("termos e privacidade são documentos públicos acessíveis", async ({ page }) => {
    await mockApi(page);
    await page.goto("/termos");
    await expect(page.getByRole("heading", { name: "Termos de Uso" })).toBeVisible();
    await page.goto("/privacidade");
    await expect(page.getByRole("heading", { name: "Política de Privacidade" })).toBeVisible();
  });
});

test.describe("responsividade, teclado e WCAG @a11y", () => {
  for (const width of [320, 375, 430, 768, 1024, 1280, 1440, 1920]) {
    test(`login do cliente sem rolagem horizontal em ${width}px`, async ({ page }) => {
      await mockApi(page);
      await page.setViewportSize({ width, height: 900 });
      await page.goto("/portal/login");
      await expect(page.getByRole("heading", { name: "Bem-vindo ao ThermoProActive" })).toBeVisible();
      const tamanhos = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, client: document.documentElement.clientWidth }));
      expect(tamanhos.scroll).toBeLessThanOrEqual(tamanhos.client);
    });
  }

  test("login permanece operável em celular na horizontal", async ({ page }) => {
    await mockApi(page);
    await page.setViewportSize({ width: 844, height: 390 });
    await page.goto("/portal/login");
    await expect(page.getByRole("heading", { name: "Bem-vindo ao ThermoProActive" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Entrar" })).toBeVisible();
    const tamanhos = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, client: document.documentElement.clientWidth }));
    expect(tamanhos.scroll).toBeLessThanOrEqual(tamanhos.client);
  });

  test("login permite teclado, colar senha e alternar visibilidade", async ({ page }) => {
    await mockApi(page);
    await page.goto("/portal/login");
    await page.getByRole("textbox", { name: /^E-mail/ }).focus();
    await page.keyboard.insertText("pessoa@empresa.test");
    await page.keyboard.press("Tab");
    await page.keyboard.insertText("senha colada pelo gerenciador");
    await page.getByRole("button", { name: "Mostrar senha" }).click();
    await expect(page.getByLabel(/^Senha/)).toHaveAttribute("type", "text");
  });

  for (const rota of ["/portal/login", "/admin/login", "/portal/esqueci-senha"]) {
    test(`sem violações WCAG AA detectáveis em ${rota}`, async ({ page }) => {
      await mockApi(page);
      await page.emulateMedia({ reducedMotion: "reduce" });
      await page.goto(rota);
      if (rota.startsWith("/portal/")) {
        await expect(page.locator(".animate-slide-up")).toHaveCSS("opacity", "1");
      }
      const resultado = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]).analyze();
      expect(resultado.violations, JSON.stringify(resultado.violations, null, 2)).toEqual([]);
    });
  }

  test("tema escuro do portal não tem violações WCAG AA detectáveis", async ({ page }) => {
    await mockApi(page);
    await page.emulateMedia({ colorScheme: "dark", reducedMotion: "reduce" });
    await page.goto("/portal/login");
    await expect(page.locator(".animate-slide-up")).toHaveCSS("opacity", "1");
    const resultado = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]).analyze();
    expect(resultado.violations, JSON.stringify(resultado.violations, null, 2)).toEqual([]);
  });

  test("não produz erros de hidratação ou console", async ({ page }) => {
    const erros: string[] = [];
    page.on("console", (msg) => {
      const texto = msg.text();
      const sessaoAusenteEsperada = texto.includes("Failed to load resource") && texto.includes("401");
      if (msg.type() === "error" && !sessaoAusenteEsperada) erros.push(texto);
    });
    await mockApi(page);
    await page.goto("/portal/login");
    await expect(page.getByRole("button", { name: "Entrar" })).toBeVisible();
    expect(erros).toEqual([]);
  });
});
