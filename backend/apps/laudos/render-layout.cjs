/* Imprime as rotas existentes. Entrada privada por stdin; nenhum endpoint público
 * ou cookie real é criado. APIs são satisfeitas exclusivamente pelo snapshot. */
const { createRequire } = require('node:module');
const { resolve } = require('node:path');
let chromium;
try { ({ chromium } = require('playwright')); }
catch { ({ chromium } = createRequire(resolve(__dirname, '../../../../frontend/package.json'))('playwright')); }

async function render(input) {
  const { snapshot: s, frontend, timeout = 90000, maxPaginas = 1000 } = input;
  if (s?.schema !== 'laudo_v1' || !['inspecao', 'relatorio'].includes(s.origem?.tipo)) throw Error('snapshot');
  const origin = new URL(frontend).origin;
  if (!['127.0.0.1', 'localhost', '[::1]', 'frontend'].includes(new URL(origin).hostname)) throw Error('origin');
  const modular = s.origem.tipo === 'relatorio';
  const path = modular ? `/imprimir/${Number(s.origem.id)}` : `/laudos/${Number(s.laudo.id)}/relatorio`;
  const dataPath = modular ? `/api/relatorios-inspecao/${Number(s.origem.id)}/dossie/` : `/api/laudos/${Number(s.laudo.id)}/relatorio-tecnico/`;
  const user = { id: s.assinatura?.usuario_id || 1, nome: s.laudo.responsavel_nome,
    email: 'renderer@localhost', perfil: 'ADMIN', nivel: 'MASTER', ambiente: 'BackEnd',
    is_interno: true, is_cliente: false, is_master: true, is_active: true, estado: 'ACTIVE',
    exigir_troca_senha: false, mfa_obrigatorio: false, mfa_ativo: true };
  const browser = await chromium.launch({ headless: true });
  try {
    const context = await browser.newContext({ serviceWorkers: 'block', viewport: { width: 1440, height: 1000 } });
    const page = await context.newPage();
    page.setDefaultTimeout(timeout);
    await context.route('**/*', async route => {
      const request = route.request(), url = new URL(request.url());
      const headers = { 'access-control-allow-origin': origin, 'access-control-allow-credentials': 'true',
        'access-control-allow-headers': 'content-type', 'access-control-allow-methods': 'GET, OPTIONS' };
      if (url.pathname.startsWith('/api/')) {
        if (request.method() === 'OPTIONS') return route.fulfill({ status: 204, headers });
        let body;
        if (url.pathname === dataPath) body = s.relatorio;
        else if (url.pathname === '/api/auth/me/') body = user;
        else if (url.pathname === `/api/laudos/${Number(s.laudo.id)}/documento/`) body = s;
        else if (url.pathname === '/api/notificacoes/nao-lidas/') body = { total: 0 };
        else return route.fulfill({ status: 404, headers, json: { detail: 'Fonte indisponível no snapshot.' } });
        return route.fulfill({ status: 200, headers, json: body });
      }
      // Somente página e assets locais; nunca busca imagens/evidências externas.
      if (url.origin === origin && (url.pathname === path || url.pathname.startsWith('/_next/') || /\.(woff2?|ttf|css|js|svg|png|ico)$/.test(url.pathname))) return route.continue();
      return route.abort('blockedbyclient');
    });
    await page.goto(origin + path, { waitUntil: 'domcontentloaded', timeout });
    await page.locator('[data-pdf-pronto="true"]').waitFor({ timeout });
    await page.evaluate(async () => {
      await document.fonts.ready;
      await Promise.all(Array.from(document.images).map(im => im.complete ? null : new Promise(resolve => { im.onload = im.onerror = resolve; })));
      if (Array.from(document.images).some(im => !im.complete || im.naturalWidth === 0)) throw Error('imagem ausente');
    });
    const paginas = await page.locator(modular ? '.pagedjs_page' : '.folha').count();
    if (!paginas || paginas > maxPaginas) throw Error('paginacao');
    const pdf = await page.pdf({ format: 'A4', printBackground: true, preferCSSPageSize: true,
      displayHeaderFooter: false, margin: { top: 0, right: 0, bottom: 0, left: 0 }, timeout });
    process.stdout.write(pdf);
  } finally { await browser.close(); }
}

let data = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => { data += chunk; });
process.stdin.on('end', () => {
  render(JSON.parse(data)).catch(() => { process.stderr.write('Falha no renderer local do layout original.\n'); process.exitCode = 1; });
});
