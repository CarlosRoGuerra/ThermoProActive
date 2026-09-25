/* Formatação comum do relatório (datas ISO do DRF e decimais que chegam como string). */

export const ddmmaaaa = (iso: string | null) => (iso ? iso.split("-").reverse().join("/") : "—");

export const num = (v: string | null) => (v == null || v === "" ? 0 : Number(v));

export const moeda = (v: string | number | null) =>
  v == null || v === "" ? "—" : num(String(v)).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

export const qtd = (v: string | null) => (v == null || v === "" ? "—" : String(num(v)));
