/** Opções de coleta do Anexo I 2.3. Os rótulos/unidades não definem limites. */
export type OpcaoColeta = { valor: string; label: string };
export type GrandezaColeta = { label: string; unidade: string; livre?: boolean };

export const SUBTIPOS_VIBRACAO: OpcaoColeta[] = [
  { valor: "MEC_DINAMICO", label: "Sistemas mecânicos dinâmicos" },
  { valor: "ODS", label: "ODS — Operational Deflection Shape" },
  { valor: "MEC_ESTATICO", label: "Sistemas mecânicos estáticos" },
];

export const SUBTIPOS_TECNICOS: Record<string, OpcaoColeta[]> = {
  FLUIDOS: [
    { valor: "HIDRAULICO", label: "Fluido hidráulico" },
    { valor: "LUBRIFICANTE", label: "Fluido lubrificante" },
    { valor: "MINERAL_ISOLANTE", label: "Óleo mineral isolante" },
  ],
  ENSAIO_ELETRICO: [
    { valor: "TRANSFORMADOR_TTR", label: "Transformador — TTR / RxT" },
    { valor: "TRANSFORMADOR_RI", label: "Transformador — isolação / RxI" },
    { valor: "TRANSFORMADOR_RO", label: "Transformador — resistência ôhmica / RxO" },
    { valor: "MOTOR_RI", label: "Motor — resistência de isolação" },
  ],
  ULTRASSOM: [
    { valor: "ELETRICO", label: "Ultrassom elétrico" },
    { valor: "MECANICO", label: "Ultrassom mecânico" },
  ],
  CORRETIVA: [
    { valor: "ALINHAMENTO_EIXOS", label: "Alinhamento a laser entre eixos" },
    { valor: "ALINHAMENTO_POLIAS", label: "Alinhamento a laser entre polias" },
    { valor: "BALANCEAMENTO", label: "Balanceamento dinâmico em campo" },
  ],
  ESPESSURA: [{ valor: "ESPESSURA", label: "Medição de espessura" }],
  SENSITIVA: [{ valor: "SENSITIVA", label: "Inspeção sensitiva" }],
  QUALIDADE_ENERGIA: [{ valor: "QUALIDADE_ENERGIA", label: "Qualidade de energia" }],
};

export function ensaiosDoFluido(subtipo: string): OpcaoColeta[] {
  return [
    { valor: "FQ", label: "FQ — físico-química" },
    { valor: "CR", label: "CR — definição técnica a confirmar" },
    ...(subtipo === "MINERAL_ISOLANTE"
      ? [{ valor: "PCB", label: "PCB" }, { valor: "2FAL", label: "2-FAL" }]
      : [{ valor: "CP", label: "Contagem de partículas" }]),
  ];
}

/** Grandezas já existentes no banco/catálogos; nenhuma referência é presumida. */
export function grandezasDaColeta(tipo: string, subtipo: string, ensaio: string): GrandezaColeta[] {
  if (tipo === "FLUIDOS") {
    if (ensaio === "CR") return [{ label: "Grandeza do ensaio CR", unidade: "", livre: true }];
    if (ensaio === "PCB") return [{ label: "Teor de PCB", unidade: "mg/kg" }];
    if (ensaio === "2FAL") return [{ label: "2-Furfural (2-FAL)", unidade: "mg/kg" }];
    if (ensaio === "CP") return [
      { label: "Partículas > 4 µm(c)", unidade: "part./mL" },
      { label: "Partículas > 6 µm(c)", unidade: "part./mL" },
      { label: "Partículas > 14 µm(c)", unidade: "part./mL" },
    ];
    return [
      { label: "Teor de água", unidade: "ppm" },
      { label: "Viscosidade cinemática a 40 °C", unidade: "cSt" },
      { label: "Número de acidez (TAN)", unidade: "mgKOH/g" },
    ];
  }
  if (tipo === "ENSAIO_ELETRICO") {
    if (subtipo === "TRANSFORMADOR_TTR") return [
      { label: "Relação de transformação (TTR)", unidade: "" },
      { label: "Desvio da relação de transformação", unidade: "%" },
    ];
    return subtipo === "TRANSFORMADOR_RO"
      ? [{ label: "Resistência ôhmica", unidade: "Ω" }]
      : [{ label: "Resistência de isolação", unidade: "MΩ" }];
  }
  if (tipo === "ULTRASSOM") return [{ label: "Nível de ultrassom", unidade: "dB" }];
  if (tipo === "ESPESSURA") return [{ label: "Espessura", unidade: "mm" }];
  if (tipo === "CORRETIVA") return subtipo === "BALANCEAMENTO"
    ? [{ label: "Balanceamento residual", unidade: "g·mm" }]
    : [{ label: "Desalinhamento", unidade: "mm/100mm" }];
  if (tipo === "SENSITIVA") return [{ label: "Inspeção sensorial", unidade: "" }];
  if (tipo === "QUALIDADE_ENERGIA") return [
    { label: "THD de tensão", unidade: "%" },
    { label: "THD de corrente", unidade: "%" },
    { label: "Desequilíbrio de tensão", unidade: "%" },
  ];
  return [];
}

/** Aceita decimal brasileiro sem adivinhar separador de milhar. */
export function decimalColeta(texto: string): string | null | undefined {
  const n = texto.trim().replace(",", ".");
  if (!n) return null;
  return /^-?\d+(\.\d+)?$/.test(n) && Number.isFinite(Number(n)) ? n : undefined;
}
