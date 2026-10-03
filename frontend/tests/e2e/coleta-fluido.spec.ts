import { expect, test, type Page } from "@playwright/test";

/**
 * Coleta de amostra de fluido — a aplicação marca os ensaios padrão acordados:
 * lubrificante → FQ + EF (CP não vem marcada); hidráulico → FQ + EF + CP.
 * API mockada; a regra em si é testada no backend (SolicitacaoPadraoEnsaio).
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

const item = {
  id: 1, carregamento: 1, carregamento_status: "TRANSFERIDA", relatorio: 20, numero: "RT-AFLH-1",
  cliente: 1, cliente_nome: "Exemplo", tecnologia: 3, tecnologia_nome: "Fluidos", modulo: "FLUIDO_LUBRIFICANTE",
  data_coleta: "2026-09-30", analista_nome: "Analista", equipamento: 1, equipamento_tag: "RED-01",
  equipamento_nome: "Redutor", area_nome: "Área", setor_nome: "Setor", condicao: 1, condicao_sigla: "OK",
  condicao_nome: "OK", registro: null, ensaios: [], pendentes: 0, aplicacao: null, fluido: null,
  tipo_equipamento_nome: "Redutor",
};

const ensaio = (id: number, sigla: string, nome: string, padrao: string[]) => ({
  id, sigla, nome, modulo: "FLUIDO_LUBRIFICANTE", titulo_ficha: nome, ordem: id, rotulo_conclusao: "Conclusão",
  rotulo_informacoes: "Informações Adicionais", rotulo_proxima: "Data da Próxima Coleta", nota_tecnica: "",
  parametros: [], padrao_em: padrao,
});
const ENSAIOS = [
  ensaio(1, "FQ", "Físico-Química", ["HIDRAULICO", "LUBRIFICANTE"]),
  ensaio(2, "EF", "Espectrofotometria", ["HIDRAULICO", "LUBRIFICANTE"]),
  ensaio(3, "CP", "Contagem de Partículas", ["HIDRAULICO"]),
];
const lista = (results: unknown[]) => ({ results, count: results.length, next: null, previous: null });

async function mockApi(page: Page) {
  await page.route("**/api/**", async (route) => {
    const url = route.request().url();
    if (url.endsWith("/auth/csrf/")) {
      await route.fulfill({ status: 200, headers: { "set-cookie": "csrftoken=test; Path=/" }, json: { csrfToken: "test" } });
    } else if (url.endsWith("/auth/me/")) {
      await route.fulfill({ status: 200, json: admin });
    } else if (url.includes("/fluidos-inspecao/1/")) {
      await route.fulfill({ status: 200, json: item });
    } else if (url.includes("/ensaios/?modulo=FLUIDO_LUBRIFICANTE")) {
      await route.fulfill({ status: 200, json: lista(ENSAIOS) });
    } else {
      await route.fulfill({ status: 200, json: lista([]) });
    }
  });
}

test.describe("coleta de fluido @fluidos", () => {
  test("a aplicação marca os ensaios padrão acordados", async ({ page }) => {
    await mockApi(page);
    await page.goto("/inspecoes/final/fluido/1");
    await expect(page.getByText("Coleta da amostra de fluido")).toBeVisible();

    const fq = page.getByLabel("FQ — Físico-Química");
    const ef = page.getByLabel("EF — Espectrofotometria");
    const cp = page.getByLabel("CP — Contagem de Partículas");

    await page.getByRole("radio", { name: "Lubrificante" }).click();
    await expect(fq).toBeChecked();
    await expect(ef).toBeChecked();
    await expect(cp).not.toBeChecked();

    await page.getByRole("radio", { name: "Hidráulico" }).click();
    await expect(fq).toBeChecked();
    await expect(ef).toBeChecked();
    await expect(cp).toBeChecked();

    // CP continua disponível para o lubrificante, quando contratada.
    await page.getByRole("radio", { name: "Lubrificante" }).click();
    await expect(cp).toBeEnabled();
    await cp.check();
    await expect(page.getByText("CP marcada num lubrificante")).toBeVisible();
  });
});
