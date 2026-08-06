// Helpers do fluxo de inspeção (formulário de análise campo/escritório).
import type { Achado } from "./types";

export type TecnologiaTipo = "vibracao" | "termografia" | "outro";

/** Deduz o grupo de campos específicos a partir do nome da tecnologia (catálogo livre). */
export function tecnologiaTipo(nome: string | null | undefined): TecnologiaTipo {
  const n = (nome ?? "").toLowerCase();
  if (n.includes("vibra")) return "vibracao";
  if (n.includes("termo") || n.includes("termografia") || n.includes("infraverm")) return "termografia";
  return "outro";
}

// Estado do formulário: tudo string (inputs controlados); convertido no envio.
export type AchadoForm = {
  tipo_componente: string;
  componente_texto: string;
  detalhe: string;
  tipo_anomalia: string;
  anomalia_texto: string;
  recomendacao: string;
  recomendacao_texto: string;
  observacoes: string;
  aceleracao_global: string;
  velocidade_global: string;
  temperatura_medida: string;
  temperatura_referencia: string;
  carga_percentual: string;
  corrente_nominal: string;
  corrente_a: string;
  corrente_b: string;
  corrente_c: string;
  tensao_nominal: string;
  tensao_a: string;
  tensao_b: string;
  tensao_c: string;
  grau_risco: string;
};

const CAMPOS_NUMERICOS: (keyof AchadoForm)[] = [
  "aceleracao_global", "velocidade_global", "temperatura_medida", "temperatura_referencia",
  "carga_percentual", "corrente_nominal", "corrente_a", "corrente_b", "corrente_c",
  "tensao_nominal", "tensao_a", "tensao_b", "tensao_c",
];

const CAMPOS_FK: (keyof AchadoForm)[] = ["tipo_componente", "tipo_anomalia", "recomendacao", "grau_risco"];

export function formVazio(): AchadoForm {
  return {
    tipo_componente: "", componente_texto: "", detalhe: "", tipo_anomalia: "",
    anomalia_texto: "", recomendacao: "", recomendacao_texto: "", observacoes: "",
    aceleracao_global: "", velocidade_global: "", temperatura_medida: "",
    temperatura_referencia: "", carga_percentual: "", corrente_nominal: "",
    corrente_a: "", corrente_b: "", corrente_c: "", tensao_nominal: "",
    tensao_a: "", tensao_b: "", tensao_c: "", grau_risco: "",
  };
}

const s = (v: string | number | null | undefined) => (v == null ? "" : String(v));

export function formDeAchado(a: Achado): AchadoForm {
  return {
    tipo_componente: s(a.tipo_componente),
    componente_texto: a.componente_texto ?? "",
    detalhe: a.detalhe ?? "",
    tipo_anomalia: s(a.tipo_anomalia),
    anomalia_texto: a.anomalia_texto ?? "",
    recomendacao: s(a.recomendacao),
    recomendacao_texto: a.recomendacao_texto ?? "",
    observacoes: a.observacoes ?? "",
    aceleracao_global: s(a.aceleracao_global),
    velocidade_global: s(a.velocidade_global),
    temperatura_medida: s(a.temperatura_medida),
    temperatura_referencia: s(a.temperatura_referencia),
    carga_percentual: s(a.carga_percentual),
    corrente_nominal: s(a.corrente_nominal),
    corrente_a: s(a.corrente_a),
    corrente_b: s(a.corrente_b),
    corrente_c: s(a.corrente_c),
    tensao_nominal: s(a.tensao_nominal),
    tensao_a: s(a.tensao_a),
    tensao_b: s(a.tensao_b),
    tensao_c: s(a.tensao_c),
    grau_risco: s(a.grau_risco),
  };
}

/** Converte o form em corpo para a API: FKs e números vazios viram null. */
export function payloadDeForm(form: AchadoForm): Record<string, unknown> {
  const body: Record<string, unknown> = {};
  for (const [chave, valor] of Object.entries(form) as [keyof AchadoForm, string][]) {
    if (CAMPOS_FK.includes(chave)) {
      body[chave] = valor === "" ? null : Number(valor);
    } else if (CAMPOS_NUMERICOS.includes(chave)) {
      body[chave] = valor === "" ? null : valor; // DecimalField aceita string
    } else {
      body[chave] = valor;
    }
  }
  return body;
}

/** ΔT ao vivo (medida − referência) para exibição no formulário. */
export function deltaTPreview(medida: string, referencia: string): string | null {
  if (medida === "" || referencia === "") return null;
  const d = Number(medida) - Number(referencia);
  return Number.isNaN(d) ? null : d.toFixed(1);
}
