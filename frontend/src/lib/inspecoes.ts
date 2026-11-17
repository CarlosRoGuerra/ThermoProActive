// Helpers do fluxo de inspeção (formulário de análise campo/escritório).
import type { Achado } from "./types";

export type TecnologiaTipo = "vibracao" | "termografia" | "outro";

/**
 * Grupo de campos específicos da análise pelo módulo técnico da tecnologia
 * (`TecnologiaAnalise.modulo_tecnico`) — vínculo explícito, nunca o nome do
 * catálogo. Tecnologia de outro módulo não ganha campos de outra técnica (o
 * balanceamento tem o próprio formulário, o da manutenção corretiva).
 */
export function tecnologiaTipo(modulo: string | null | undefined): TecnologiaTipo {
  if (modulo === "VIBRACAO") return "vibracao";
  if (modulo === "TERMOGRAFIA") return "termografia";
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
  deslocamento_global: string;
  temperatura_medida: string;
  temperatura_referencia: string;
  carga_percentual: string;
  temperatura_ambiente: string;
  /** "" | "R" | "S" | "T" | "MAIOR" — qual corrente vale na correção pela carga. */
  fase_anomalia: string;
  corrente_nominal: string;
  corrente_a: string;
  corrente_b: string;
  corrente_c: string;
  tensao_nominal: string;
  tensao_a: string;
  tensao_b: string;
  tensao_c: string;
  condicao: string;
};

const CAMPOS_NUMERICOS: (keyof AchadoForm)[] = [
  "aceleracao_global", "velocidade_global", "deslocamento_global", "temperatura_medida", "temperatura_referencia",
  "carga_percentual", "temperatura_ambiente",
  "corrente_nominal", "corrente_a", "corrente_b", "corrente_c",
  "tensao_nominal", "tensao_a", "tensao_b", "tensao_c",
];

const CAMPOS_FK: (keyof AchadoForm)[] = ["tipo_componente", "tipo_anomalia", "recomendacao", "condicao"];

export function formVazio(): AchadoForm {
  return {
    tipo_componente: "", componente_texto: "", detalhe: "", tipo_anomalia: "",
    anomalia_texto: "", recomendacao: "", recomendacao_texto: "", observacoes: "",
    aceleracao_global: "", velocidade_global: "", deslocamento_global: "", temperatura_medida: "",
    temperatura_referencia: "", carga_percentual: "", temperatura_ambiente: "",
    fase_anomalia: "", corrente_nominal: "",
    corrente_a: "", corrente_b: "", corrente_c: "", tensao_nominal: "",
    tensao_a: "", tensao_b: "", tensao_c: "", condicao: "",
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
    deslocamento_global: s(a.deslocamento_global),
    temperatura_medida: s(a.temperatura_medida),
    temperatura_referencia: s(a.temperatura_referencia),
    carga_percentual: s(a.carga_percentual),
    temperatura_ambiente: s(a.temperatura_ambiente),
    fase_anomalia: a.fase_anomalia ?? "",
    corrente_nominal: s(a.corrente_nominal),
    corrente_a: s(a.corrente_a),
    corrente_b: s(a.corrente_b),
    corrente_c: s(a.corrente_c),
    tensao_nominal: s(a.tensao_nominal),
    tensao_a: s(a.tensao_a),
    tensao_b: s(a.tensao_b),
    tensao_c: s(a.tensao_c),
    condicao: s(a.condicao),
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

/* ---------------------------------------------------------------------------
   Correção da temperatura pela carga (C.T.M.) — PRÉVIA para o formulário.
   A conta que vale é a do backend (`apps/coletas/correcao_carga.py`, fonte única do
   relatório); esta repete as mesmas regras só para o analista ver o resultado enquanto
   digita. Mudou lá, mude aqui.

     ΔT1 = TM − TA;  ΔT2 = ΔT1 × (I2 / I1)²;  I2 = 0,90 × In;  T2 = TA + ΔT2
   --------------------------------------------------------------------------- */
const CARGA_ALVO = 90;
const LIMITE_TEMPERATURA = 99999.9;

export type PreviaCorrecao = {
  carga: number | null;
  cargaCalculada: boolean;
  corrente: number | null;
  fase: string;
  fator: number | null;
  medidaCorrigida: number | null;
  deltaCorrigido: number | null;
  pendencia: string;
};

const numOuNulo = (v: string) => (v.trim() === "" || Number.isNaN(Number(v)) ? null : Number(v));
/** Uma casa, meio para cima (145,714 → 145,7), como no backend. */
const umaCasa = (v: number) => Math.sign(v) * Math.round(Math.abs(v) * 10 + 1e-9) / 10;

export function correcaoCargaPreview(form: AchadoForm): PreviaCorrecao {
  const pend: string[] = [];
  const tm = numOuNulo(form.temperatura_medida);
  const tr = numOuNulo(form.temperatura_referencia);
  const ta = numOuNulo(form.temperatura_ambiente);
  const nominal = numOuNulo(form.corrente_nominal);
  const medidas = (
    [["R", form.corrente_a], ["S", form.corrente_b], ["T", form.corrente_c]] as const
  ).flatMap(([f, v]) => (numOuNulo(v) == null ? [] : [[f, numOuNulo(v) as number] as const]));

  let corrente: number | null = null;
  let fase = "";
  let carga = numOuNulo(form.carga_percentual);
  let cargaCalculada = false;
  let razao: number | null = null;

  if (nominal != null && nominal > 0 && medidas.length > 0) {
    const f = form.fase_anomalia;
    if (f === "R" || f === "S" || f === "T") {
      const m = medidas.find(([x]) => x === f);
      fase = f;
      if (m) corrente = m[1];
      else pend.push(`A corrente da fase ${f} não foi medida.`);
    } else if (f === "MAIOR" || medidas.length === 1) {
      const m = medidas.reduce((a, b) => (b[1] > a[1] ? b : a));
      [fase, corrente] = [m[0], m[1]];
    } else {
      pend.push("Há corrente medida em mais de uma fase: informe a fase da anomalia.");
    }
    if (corrente != null) {
      razao = corrente / nominal;
      carga = umaCasa(razao * 100);
      cargaCalculada = true;
    }
  } else if (carga != null) {
    razao = carga / 100;
  }

  const base: PreviaCorrecao = { carga, cargaCalculada, corrente, fase, fator: null, medidaCorrigida: null, deltaCorrigido: null, pendencia: "" };
  if (tm == null) return base;
  if (razao == null) return { ...base, pendencia: pend.join(" ") || "Informe a corrente nominal e a de trabalho, ou o % de carga." };
  if (razao <= 0) return { ...base, pendencia: "Com carga zero não há como corrigir a temperatura." };
  if (razao * 100 >= CARGA_ALVO) return { ...base, pendencia: `A carga já atinge ${CARGA_ALVO} % da nominal: a correção não se aplica.` };

  const fator = (CARGA_ALVO / 100 / razao) ** 2;
  const corrigida = (v: number) => {
    const r = umaCasa(v);
    if (Math.abs(r) > LIMITE_TEMPERATURA) {
      pend.push("A carga é baixa demais para extrapolar: o valor corrigido passa do limite do campo.");
      return null;
    }
    return r;
  };
  const medidaCorrigida = ta != null ? corrigida(ta + (tm - ta) * fator) : null;
  const deltaCorrigido = tr != null ? corrigida((tm - tr) * fator) : null;
  if (ta == null) pend.push("Informe a temperatura ambiente para corrigir a temperatura medida.");
  return { ...base, fator, medidaCorrigida, deltaCorrigido, pendencia: Array.from(new Set(pend)).join(" ") };
}

/** ΔT ao vivo (medida − referência) para exibição no formulário. */
export function deltaTPreview(medida: string, referencia: string): string | null {
  if (medida === "" || referencia === "") return null;
  const d = Number(medida) - Number(referencia);
  return Number.isNaN(d) ? null : d.toFixed(1);
}
