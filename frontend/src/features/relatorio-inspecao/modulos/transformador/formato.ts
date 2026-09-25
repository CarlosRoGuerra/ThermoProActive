/* Números e datas das fichas de transformador (óleo isolante e ensaios elétricos). */

import type { CadastroTransformador } from "../../tipos";
import { ddmmaaaa } from "../../shell/formato";

/**
 * Valor com as casas decimais do catálogo, em pt-BR (milhar com ponto) e
 * arredondado meio para cima, como as fichas de referência e o backend (Decimal).
 *
 * Não usa `toFixed`/`Intl` direto: 5,265 (R×O calculado) em binário é 5,26499…,
 * e a ficha imprime 5,27. O número passa antes por 15 algarismos significativos,
 * que devolvem o decimal que saiu do banco. Ausente = "" (nunca 0).
 */
export function numero(v: number | null | undefined, casas: number): string {
  if (v == null || !Number.isFinite(v)) return "";
  const texto = Math.abs(v).toPrecision(15);
  if (/e/i.test(texto)) {
    return v.toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });
  }
  const [inteiro, decimais = ""] = texto.split(".");
  const fracao = decimais.padEnd(casas + 1, "0");
  const digitos = (inteiro + fracao.slice(0, casas)).split("").map(Number);
  if (Number(fracao[casas]) >= 5) {
    let k = digitos.length - 1;
    for (; k >= 0 && digitos[k] === 9; k--) digitos[k] = 0;
    if (k < 0) digitos.unshift(1);
    else digitos[k] += 1;
  }
  const s = digitos.join("");
  const parteInteira = s.slice(0, s.length - casas).replace(/^0+(?=\d)/, "") || "0";
  const comMilhar = parteInteira.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  const resultado = casas > 0 ? `${comMilhar},${s.slice(s.length - casas)}` : comMilhar;
  return v < 0 && /[1-9]/.test(resultado) ? `-${resultado}` : resultado;
}

/** Sem zeros à direita (tensões de placa: 13,8 kV; 380 V). */
export function numeroEnxuto(v: number | null | undefined, casasMax = 3): string {
  const s = numero(v, casasMax);
  return s.includes(",") ? s.replace(/0+$/, "").replace(/,$/, "") : s;
}

/** Volts → kV da placa (13.800 V → "13,8"). */
export const kV = (volts: number | null | undefined) => (volts == null ? "" : numeroEnxuto(volts / 1000));

/** Data da ficha: vazia quando não há (a ficha de referência deixa o campo em branco). */
export const data = (iso: string | null | undefined) => (iso ? ddmmaaaa(iso) : "");

/** Tensão secundária da placa: linha / fase (380 / 220). */
export function tensaoSecundaria(c: CadastroTransformador) {
  if (c.tensao_secundaria_v == null) return "";
  const linha = numeroEnxuto(c.tensao_secundaria_v, 1);
  return c.tensao_secundaria_fase_v != null ? `${linha} / ${numeroEnxuto(c.tensao_secundaria_fase_v, 1)}` : linha;
}
