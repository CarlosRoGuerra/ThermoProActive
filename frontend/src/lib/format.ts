/**
 * Formatação pt-BR — um lugar só.
 *
 * Antes cada tela tinha a sua cópia (`ddmmaaaa` aparecia em 9 arquivos, moeda em
 * 5), o que produzia divergências: umas mostravam "—" para vazio, outras "null".
 * Regra: valor ausente vira SEMPRE o travessão `—`, nunca texto técnico.
 */

/** Travessão usado para "sem informação" em toda a interface. */
export const VAZIO = "—";

const vazio = (v: unknown) => v === null || v === undefined || v === "";

/* ==========================================================================
   Datas — a API entrega ISO (YYYY-MM-DD ou timestamp completo).
   ========================================================================== */

/** `2026-03-08` → `08/03/2026`. Não cria Date: evita deslocar o dia por fuso. */
export function data(iso: string | null | undefined): string {
  if (vazio(iso)) return VAZIO;
  const somenteData = String(iso).slice(0, 10);
  const [a, m, d] = somenteData.split("-");
  return a && m && d ? `${d}/${m}/${a}` : String(iso);
}

/** `2026-03-08T14:32:00Z` → `08/03/2026 11:32` (fuso do navegador). */
export function dataHora(iso: string | null | undefined): string {
  if (vazio(iso)) return VAZIO;
  const d = new Date(String(iso));
  if (Number.isNaN(d.getTime())) return String(iso);
  return d.toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Tempo relativo curto: "agora", "há 5 min", "há 3 d". Para feeds e alertas. */
export function tempoRelativo(iso: string | null | undefined): string {
  if (vazio(iso)) return VAZIO;
  const d = new Date(String(iso));
  if (Number.isNaN(d.getTime())) return String(iso);
  const seg = Math.round((Date.now() - d.getTime()) / 1000);
  if (seg < 60) return "agora";
  const min = Math.round(seg / 60);
  if (min < 60) return `há ${min} min`;
  const h = Math.round(min / 60);
  if (h < 24) return `há ${h} h`;
  const dias = Math.round(h / 24);
  if (dias < 30) return `há ${dias} d`;
  return data(iso);
}

/** Dias entre hoje e a data (negativo = passado). Usado no SLA. */
export function diasAte(iso: string | null | undefined): number | null {
  if (vazio(iso)) return null;
  const alvo = new Date(`${String(iso).slice(0, 10)}T00:00:00`);
  if (Number.isNaN(alvo.getTime())) return null;
  const hoje = new Date();
  hoje.setHours(0, 0, 0, 0);
  return Math.round((alvo.getTime() - hoje.getTime()) / 86_400_000);
}

/* ==========================================================================
   Números — a API manda decimais como string (DRF DecimalField).
   ========================================================================== */

function paraNumero(v: string | number | null | undefined): number | null {
  if (vazio(v)) return null;
  const n = typeof v === "number" ? v : Number(String(v).replace(",", "."));
  return Number.isFinite(n) ? n : null;
}

/** Número com casas fixas: `1234.5` → `1.234,50`. */
export function numero(v: string | number | null | undefined, casas = 2): string {
  const n = paraNumero(v);
  if (n === null) return VAZIO;
  return n.toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });
}

/** Inteiro com separador de milhar: `12345` → `12.345`. */
export function inteiro(v: string | number | null | undefined): string {
  const n = paraNumero(v);
  return n === null ? VAZIO : Math.round(n).toLocaleString("pt-BR");
}

/** Moeda: `1234.5` → `R$ 1.234,50`. `compacto` corta os centavos (dashboards). */
export function moeda(v: string | number | null | undefined, compacto = false): string {
  const n = paraNumero(v);
  if (n === null) return VAZIO;
  return n.toLocaleString("pt-BR", {
    style: "currency",
    currency: "BRL",
    maximumFractionDigits: compacto ? 0 : 2,
    minimumFractionDigits: compacto ? 0 : 2,
  });
}

/** Percentual: `98.72` → `98,7%`. O valor já vem em pontos percentuais. */
export function percentual(v: string | number | null | undefined, casas = 1): string {
  const n = paraNumero(v);
  if (n === null) return VAZIO;
  return `${n.toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas })}%`;
}

/** Grandeza com unidade: `numeroUnidade(4.5, "mm/s")` → `4,50 mm/s`. */
export function numeroUnidade(
  v: string | number | null | undefined,
  unidade: string,
  casas = 2
): string {
  const n = paraNumero(v);
  return n === null ? VAZIO : `${numero(n, casas)} ${unidade}`;
}

/* ==========================================================================
   Documentos e contatos — máscara só na exibição; o valor cru vai para a API.
   ========================================================================== */

/** `12345678000190` → `12.345.678/0001-90`. Devolve como veio se não tiver 14 dígitos. */
export function cnpj(v: string | null | undefined): string {
  if (vazio(v)) return VAZIO;
  const d = String(v).replace(/\D/g, "");
  if (d.length !== 14) return String(v);
  return `${d.slice(0, 2)}.${d.slice(2, 5)}.${d.slice(5, 8)}/${d.slice(8, 12)}-${d.slice(12)}`;
}

/** `12345678901` → `123.456.789-01`. */
export function cpf(v: string | null | undefined): string {
  if (vazio(v)) return VAZIO;
  const d = String(v).replace(/\D/g, "");
  if (d.length !== 11) return String(v);
  return `${d.slice(0, 3)}.${d.slice(3, 6)}.${d.slice(6, 9)}-${d.slice(9)}`;
}

/** `11987654321` → `(11) 98765-4321`. */
export function telefone(v: string | null | undefined): string {
  if (vazio(v)) return VAZIO;
  const d = String(v).replace(/\D/g, "");
  if (d.length === 11) return `(${d.slice(0, 2)}) ${d.slice(2, 7)}-${d.slice(7)}`;
  if (d.length === 10) return `(${d.slice(0, 2)}) ${d.slice(2, 6)}-${d.slice(6)}`;
  return String(v);
}

/* ==========================================================================
   Texto
   ========================================================================== */

/** Iniciais para avatar: "Carlos Roberto Silva" → "CS". */
export function iniciais(nome: string | null | undefined): string {
  if (vazio(nome)) return "?";
  const partes = String(nome).trim().split(/\s+/).filter(Boolean);
  if (partes.length === 1) return partes[0].slice(0, 2).toUpperCase();
  return `${partes[0][0]}${partes[partes.length - 1][0]}`.toUpperCase();
}

/** Primeiro nome, para saudação. */
export function primeiroNome(nome: string | null | undefined): string {
  if (vazio(nome)) return "";
  return String(nome).trim().split(/\s+/)[0];
}

/** Qualquer valor exibível, com travessão no lugar de vazio. */
export function texto(v: unknown): string {
  return vazio(v) ? VAZIO : String(v);
}

/** Pluralização simples: `plural(3, "equipamento")` → "3 equipamentos". */
export function plural(n: number, singular: string, pluralForma?: string): string {
  const palavra = n === 1 ? singular : pluralForma ?? `${singular}s`;
  return `${inteiro(n)} ${palavra}`;
}

/** Remove acentos e baixa a caixa — para busca e ordenação tolerantes. */
export function normalizar(v: unknown): string {
  return String(v ?? "")
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase();
}

/** Comparador pt-BR para ordenação de tabelas (números dentro de TAGs incluídos). */
export function compararTexto(a: unknown, b: unknown): number {
  return String(a ?? "").localeCompare(String(b ?? ""), "pt-BR", {
    sensitivity: "base",
    numeric: true,
  });
}
