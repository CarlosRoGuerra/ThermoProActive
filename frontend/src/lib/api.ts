// Cliente HTTP da API ThermoProActive.
//
// A sessão vive em cookies HttpOnly+SameSite emitidos pela API. JavaScript nunca
// lê access/refresh tokens; para mutações envia apenas o token CSRF não sensível.
const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://127.0.0.1:8000/api";

let csrfToken = "";
let csrfEmAndamento: Promise<void> | null = null;
async function ensureCsrf() {
  if (csrfToken) return;
  if (!csrfEmAndamento) {
    csrfEmAndamento = fetch(`${API_URL}/auth/csrf/`, { credentials: "include" })
      .then(async (res) => {
        if (!res.ok) throw new ApiError(res.status, null, "Não foi possível iniciar uma sessão segura.");
        const data = await res.json() as { csrfToken?: string };
        if (!data.csrfToken) throw new ApiError(0, null, "Token de segurança não recebido.");
        csrfToken = data.csrfToken;
      })
      .finally(() => { csrfEmAndamento = null; });
  }
  return csrfEmAndamento;
}

export class ApiError extends Error {
  status: number;
  data: unknown;
  constructor(status: number, data: unknown, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

/** Erro de conexão (servidor fora do ar, offline) — status 0 por convenção. */
export function erroDeConexao(): ApiError {
  return new ApiError(0, null, "Sem conexão com o servidor.");
}

/**
 * Renovação do access token.
 *
 * Single-flight: várias telas carregam em paralelo e todas podem receber 401 ao
 * mesmo tempo. Sem isto, cada uma disparava um POST /auth/refresh/ e o
 * simplejwt com rotação invalidava o refresh das demais, derrubando a sessão.
 */
let refreshEmAndamento: Promise<boolean> | null = null;

function tryRefresh(): Promise<boolean> {
  if (refreshEmAndamento) return refreshEmAndamento;

  refreshEmAndamento = (async () => {
    try {
      await ensureCsrf();
      const res = await fetch(`${API_URL}/auth/session/refresh/`, {
        method: "POST",
        credentials: "include",
        headers: { "X-CSRFToken": csrfToken },
      });
      if (!res.ok) {
        return false;
      }
      return true;
    } catch {
      // Falha de rede: NÃO apaga a sessão — a conexão pode voltar.
      return false;
    } finally {
      // Libera na próxima volta do event loop para que os 401 simultâneos
      // desta rodada compartilhem o mesmo resultado.
      setTimeout(() => {
        refreshEmAndamento = null;
      }, 0);
    }
  })();

  return refreshEmAndamento;
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  retry?: boolean;
  /** Cancela a requisição — use com o cleanup do useEffect. */
  signal?: AbortSignal;
}

export async function api<T = unknown>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, retry = true, signal } = opts;
  // FormData (upload de arquivo) vai como multipart — o navegador define o
  // Content-Type com o boundary correto, então não o fixamos aqui.
  const isForm = typeof FormData !== "undefined" && body instanceof FormData;
  const headers: Record<string, string> = {};
  if (!isForm) headers["Content-Type"] = "application/json";
  if (!["GET", "HEAD", "OPTIONS"].includes(method.toUpperCase())) {
    await ensureCsrf();
    headers["X-CSRFToken"] = csrfToken;
  }

  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      method,
      headers,
      credentials: "include",
      signal,
      body: body === undefined ? undefined : isForm ? (body as FormData) : JSON.stringify(body),
    });
  } catch (e) {
    // Repassa o cancelamento para quem chamou distinguir de falha real.
    if (e instanceof DOMException && e.name === "AbortError") throw e;
    throw erroDeConexao();
  }

  if (res.status === 401 && retry && (await tryRefresh())) {
    return api<T>(path, { ...opts, retry: false });
  }

  if (res.status === 204) return undefined as T;

  const text = await res.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      // Resposta não-JSON (HTML de erro do proxy, por exemplo).
      data = { detail: null };
    }
  }

  if (!res.ok) {
    const registro = (data ?? {}) as Record<string, unknown>;
    const msg =
      (typeof registro.detail === "string" && registro.detail) ||
      (Object.keys(registro).length ? Object.values(registro).flat().join(" ") : "") ||
      `Erro ${res.status}`;
    throw new ApiError(res.status, data, String(msg));
  }
  return data as T;
}

/**
 * Monta query string ignorando valores vazios.
 * `qs({ page: 2, cliente: "", busca: "abc" })` → `?page=2&busca=abc`
 */
export function qs(params: Record<string, string | number | boolean | null | undefined>): string {
  const busca = new URLSearchParams();
  for (const [chave, valor] of Object.entries(params)) {
    if (valor === null || valor === undefined || valor === "") continue;
    busca.set(chave, String(valor));
  }
  const s = busca.toString();
  return s ? `?${s}` : "";
}

export async function login(
  area: "portal" | "admin",
  email: string,
  password: string,
  lembrar = false,
  codigoMfa = ""
) {
  let res: Response;
  try {
    await ensureCsrf();
    res = await fetch(`${API_URL}/auth/${area}/login/`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
      body: JSON.stringify({ email, password, lembrar, codigo_mfa: codigoMfa }),
    });
  } catch {
    throw erroDeConexao();
  }
  const text = await res.text();
  const data = text ? JSON.parse(text) : {};
  if (!res.ok) {
    throw new ApiError(res.status, data, data.detail || "Falha no login");
  }
  return data.user;
}

export async function logout() {
  await api("/auth/logout/", { method: "POST", retry: false });
}

/** Baixa um arquivo protegido por JWT (relatórios CSV/XLSX/PDF) via blob. */
export async function downloadFile(path: string, filename: string) {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { credentials: "include" });
    if (res.status === 401 && (await tryRefresh())) {
      res = await fetch(`${API_URL}${path}`, { credentials: "include" });
    }
  } catch {
    throw erroDeConexao();
  }
  if (!res.ok) {
    const text = await res.text();
    throw new ApiError(res.status, text, `Erro ${res.status} ao gerar o arquivo`);
  }

  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export { API_URL };
