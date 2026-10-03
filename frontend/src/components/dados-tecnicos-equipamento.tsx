"use client";

import { useRef, useState } from "react";
import { ImagePlus } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { CategoriaTecnica, DadosTecnicosMotor, DadosTecnicosTransformador } from "@/lib/types";
import { Button, Card, Field, Input, Select } from "@/components/ds";

/**
 * Datasheet técnico específico por tipo de equipamento (Motor Elétrico, Transformador).
 *
 * Os campos entram no quadro "Dados técnicos" do formulário do equipamento assim
 * que o tipo é escolhido e são gravados junto com ele (inclusive no cadastro) —
 * PATCH se o datasheet já existe, POST se não. Mesmo endpoint que um OCR futuro
 * usaria (pré-preenche, o técnico revisa e salva — nada grava sozinho).
 */

type Datasheet = DadosTecnicosMotor | DadosTecnicosTransformador;
/** Valores do datasheet como estão nos campos (texto). */
export type ValoresDatasheet = Record<string, string>;

type CampoNum = { chave: string; label: string; passo: string; dica?: string };

const CAMPOS_MOTOR: CampoNum[] = [
  { chave: "potencia_kw", label: "Potência (kW)", passo: "0.01" },
  { chave: "tensao_v", label: "Tensão (V)", passo: "0.01" },
  { chave: "corrente_a", label: "Corrente (A)", passo: "0.01" },
  { chave: "rotacao_rpm", label: "Rotação (RPM)", passo: "1" },
  { chave: "fator_potencia", label: "Fator de potência (FP)", passo: "0.001" },
  { chave: "fator_servico", label: "Fator de serviço (FS)", passo: "0.01" },
  { chave: "rendimento_pct", label: "Rendimento (%)", passo: "0.01" },
];
const TEXTOS_MOTOR = ["classe_isolacao", "rolamento_loa", "rolamento_la", "tipo_base"];

const CAMPOS_TRANSFORMADOR: CampoNum[] = [
  { chave: "potencia_kva", label: "Potência (kVA)", passo: "0.01" },
  { chave: "tensao_primaria_v", label: "Tensão primária (V)", passo: "0.01" },
  { chave: "tensao_secundaria_v", label: "Tensão secundária (V)", passo: "0.01" },
  {
    chave: "tensao_secundaria_fase_v", label: "Tensão secundária de fase (V)", passo: "0.01",
    dica: "Ex.: 220 num 380/220 V — entra na relação nominal do R×T",
  },
  { chave: "impedancia_pct", label: "Impedância (%)", passo: "0.01" },
  { chave: "volume_oleo_l", label: "Volume de óleo (L)", passo: "0.1" },
];
const TEXTOS_TRANSFORMADOR = ["grupo_ligacao", "possui_tanque_expansao"];

const ENDPOINT: Record<Exclude<CategoriaTecnica, "">, string> = {
  MOTOR_ELETRICO: "/dados-tecnicos-motor/",
  TRANSFORMADOR: "/dados-tecnicos-transformador/",
};

function chaves(categoria: CategoriaTecnica) {
  if (categoria === "MOTOR_ELETRICO") return [...CAMPOS_MOTOR.map((c) => c.chave), ...TEXTOS_MOTOR];
  if (categoria === "TRANSFORMADOR") return [...CAMPOS_TRANSFORMADOR.map((c) => c.chave), ...TEXTOS_TRANSFORMADOR];
  return [];
}

/** Valores iniciais dos campos, a partir do datasheet salvo (ou vazios). */
export function datasheetInicial(dados: Datasheet | null): ValoresDatasheet {
  const v: ValoresDatasheet = {};
  if (!dados) return v;
  for (const [k, valor] of Object.entries(dados)) {
    if (k === "possui_tanque_expansao") v[k] = valor == null ? "" : valor ? "sim" : "nao";
    else if (valor != null && typeof valor !== "object") v[k] = String(valor);
  }
  return v;
}

/** Algum campo do datasheet foi preenchido? (sem nada, não se cria datasheet vazio) */
export function datasheetPreenchido(categoria: CategoriaTecnica, valores: ValoresDatasheet) {
  return chaves(categoria).some((k) => (valores[k] ?? "").trim() !== "");
}

/**
 * Grava o datasheet do equipamento (POST ou PATCH). Devolve o datasheet salvo,
 * ou null quando a categoria não tem datasheet ou não há nada a gravar.
 */
export async function salvarDatasheet(
  categoria: CategoriaTecnica,
  equipamentoId: number,
  existente: Datasheet | null,
  valores: ValoresDatasheet
): Promise<Datasheet | null> {
  if (!categoria || (!existente && !datasheetPreenchido(categoria, valores))) return null;
  const body: Record<string, unknown> = { equipamento: equipamentoId };
  for (const k of chaves(categoria)) {
    const texto = (valores[k] ?? "").trim();
    if (k === "possui_tanque_expansao") body[k] = texto === "" ? null : texto === "sim";
    else if (k === "tipo_base") body[k] = texto || null;
    else if (TEXTOS_MOTOR.includes(k) || TEXTOS_TRANSFORMADOR.includes(k)) body[k] = texto;
    else body[k] = texto === "" ? null : texto;
  }
  const base = ENDPOINT[categoria];
  return existente
    ? api<Datasheet>(`${base}${existente.id}/`, { method: "PATCH", body })
    : api<Datasheet>(base, { method: "POST", body });
}

/** Campos do datasheet da categoria, dentro do quadro "Dados técnicos". */
export function CamposDatasheet({
  categoria, valores, onMudar, disabled = false,
}: {
  categoria: CategoriaTecnica;
  valores: ValoresDatasheet;
  onMudar: (v: ValoresDatasheet) => void;
  disabled?: boolean;
}) {
  const set = (k: string, valor: string) => onMudar({ ...valores, [k]: valor });
  const numero = (c: CampoNum) => (
    <Field key={c.chave} label={c.label} hint={c.dica}>
      <Input
        type="number"
        step={c.passo}
        inputMode="decimal"
        disabled={disabled}
        value={valores[c.chave] ?? ""}
        onChange={(e) => set(c.chave, e.target.value)}
      />
    </Field>
  );

  if (categoria === "MOTOR_ELETRICO") {
    return (
      <>
        {CAMPOS_MOTOR.map(numero)}
        <Field label="Classe de isolação (ISOL)">
          <Input placeholder="Ex.: F" disabled={disabled} value={valores.classe_isolacao ?? ""}
            onChange={(e) => set("classe_isolacao", e.target.value)} />
        </Field>
        <Field label="Rolamento LOA (lado oposto ao acoplamento)">
          <Input disabled={disabled} value={valores.rolamento_loa ?? ""} onChange={(e) => set("rolamento_loa", e.target.value)} />
        </Field>
        <Field label="Rolamento LA (lado do acoplamento)">
          <Input disabled={disabled} value={valores.rolamento_la ?? ""} onChange={(e) => set("rolamento_la", e.target.value)} />
        </Field>
        <Field label="Tipo de base">
          <Select disabled={disabled} value={valores.tipo_base ?? ""} onChange={(e) => set("tipo_base", e.target.value)}>
            <option value="">— não informado —</option>
            <option value="RIGIDA">Rígida</option>
            <option value="FLEXIVEL">Flexível</option>
          </Select>
        </Field>
      </>
    );
  }
  if (categoria === "TRANSFORMADOR") {
    return (
      <>
        {CAMPOS_TRANSFORMADOR.map(numero)}
        <Field label="Grupo de ligação" hint="Ex.: Dyn1">
          <Input disabled={disabled} value={valores.grupo_ligacao ?? ""} onChange={(e) => set("grupo_ligacao", e.target.value)} />
        </Field>
        <Field label="Tanque de expansão" hint="Sem tanque, os itens exclusivos da inspeção visual já vêm NA">
          <Select disabled={disabled} value={valores.possui_tanque_expansao ?? ""}
            onChange={(e) => set("possui_tanque_expansao", e.target.value)}>
            <option value="">Não informado</option>
            <option value="sim">Possui</option>
            <option value="nao">Não possui</option>
          </Select>
        </Field>
      </>
    );
  }
  return null;
}

/** Foto da placa — só depois que o datasheet existe (é um arquivo do datasheet). */
export function FotoPlaca({
  categoria, dados, onMudou,
}: {
  categoria: Exclude<CategoriaTecnica, "">;
  dados: Datasheet;
  onMudou: () => Promise<void>;
}) {
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const alvo = categoria === "MOTOR_ELETRICO" ? "do motor" : "do transformador";

  async function enviar(file: File) {
    setEnviando(true);
    setErro(null);
    try {
      const fd = new FormData();
      fd.append("foto_placa", file);
      await api(`${ENDPOINT[categoria]}${dados.id}/`, { method: "PATCH", body: fd });
      await onMudou();
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : "Falha ao enviar a foto da placa.");
    } finally {
      setEnviando(false);
      if (input.current) input.current.value = "";
    }
  }

  return (
    <Card className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-fg">Foto da placa {alvo}</h2>
          <p className="text-xs text-fg-muted">Registro da placa de identificação para conferência dos dados técnicos.</p>
        </div>
        <input
          ref={input}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) enviar(f);
          }}
        />
        <Button variant="secondary" icon={ImagePlus} loading={enviando} onClick={() => input.current?.click()}>
          {dados.foto_placa ? "Trocar foto da placa" : "Anexar foto da placa"}
        </Button>
      </div>
      {erro && <p className="text-sm text-danger-fg">{erro}</p>}
      {dados.foto_placa && (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={dados.foto_placa} alt={`Placa de identificação ${alvo}`}
          className="max-h-48 rounded-lg border border-border object-contain" />
      )}
    </Card>
  );
}
