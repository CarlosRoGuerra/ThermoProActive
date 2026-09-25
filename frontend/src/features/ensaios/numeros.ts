/* Números digitados nos lançamentos de ensaio (campo de texto ↔ decimal da API). */

/**
 * Texto do campo → decimal da API ("40,5" → "40.5"). Vírgula ou ponto valem como
 * separador decimal; separador de milhar não é aceito, porque "5.000" seria
 * ambíguo (cinco mil ou cinco). Vazio → null; inválido → undefined.
 */
export function paraApi(texto: string): string | null | undefined {
  const t = texto.trim();
  if (!t) return null;
  const n = t.replace(",", ".");
  return /^-?\d+(\.\d+)?$/.test(n) ? n : undefined;
}

/** Decimal da API → texto do campo, sem zeros à direita ("40.500000" → "40,5"). */
export function paraCampo(valor: string | number | null | undefined): string {
  if (valor == null || valor === "") return "";
  const s = String(valor);
  if (!/^-?\d+(\.\d+)?$/.test(s)) return s;
  const [inteiro, decimais = ""] = s.split(".");
  const d = decimais.replace(/0+$/, "");
  return d ? `${inteiro},${d}` : inteiro;
}

export const MSG_NUMERO_INVALIDO = "Número inválido — use vírgula para decimais, sem ponto de milhar.";
