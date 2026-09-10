"use client";

import { useRef, useState } from "react";
import { ImagePlus } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { DadosTecnicosMotor, DadosTecnicosTransformador, TipoBase } from "@/lib/types";
import { Button, Card, Field, Input, Select } from "@/components/ui";

/**
 * Datasheet técnico específico por tipo de equipamento (Motor Elétrico, Transformador).
 * Mesmo padrão de criar/editar já usado em Economia energética e Trial/Trim Run:
 * PATCH se já existe, POST se ainda não — mesmo endpoint que um OCR futuro usaria
 * (pré-preenche este formulário, o técnico revisa e clica salvar — nada grava sozinho).
 */

/* ===================== Motor elétrico ===================== */

const CAMPOS_MOTOR = [
  { chave: "potencia_kw", label: "Potência (kW)", passo: "0.01" },
  { chave: "tensao_v", label: "Tensão (V)", passo: "0.01" },
  { chave: "corrente_a", label: "Corrente (A)", passo: "0.01" },
  { chave: "rotacao_rpm", label: "Rotação (RPM)", passo: "1" },
  { chave: "fator_potencia", label: "Fator de potência (FP)", passo: "0.001" },
  { chave: "fator_servico", label: "Fator de serviço (FS)", passo: "0.01" },
  { chave: "rendimento_pct", label: "Rendimento (%)", passo: "0.01" },
] as const;

export function DadosMotor({
  equipamentoId,
  dados,
  podeEditar,
  onMudou,
}: {
  equipamentoId: number;
  dados: DadosTecnicosMotor | null;
  podeEditar: boolean;
  onMudou: () => Promise<void>;
}) {
  const [form, setForm] = useState<Record<string, string>>(() =>
    Object.fromEntries(
      CAMPOS_MOTOR.map((c) => [c.chave, dados ? String(dados[c.chave as keyof DadosTecnicosMotor] ?? "") : ""])
    )
  );
  const [classeIsolacao, setClasseIsolacao] = useState(dados?.classe_isolacao ?? "");
  const [rolamentoLoa, setRolamentoLoa] = useState(dados?.rolamento_loa ?? "");
  const [rolamentoLa, setRolamentoLa] = useState(dados?.rolamento_la ?? "");
  const [tipoBase, setTipoBase] = useState<TipoBase>(dados?.tipo_base ?? "");
  const [salvando, setSalvando] = useState(false);
  const [enviandoFoto, setEnviandoFoto] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const inputFoto = useRef<HTMLInputElement>(null);

  async function salvar() {
    setSalvando(true);
    setErro(null);
    try {
      const body: Record<string, unknown> = {
        equipamento: equipamentoId,
        classe_isolacao: classeIsolacao,
        rolamento_loa: rolamentoLoa,
        rolamento_la: rolamentoLa,
        tipo_base: tipoBase || null,
      };
      for (const c of CAMPOS_MOTOR) body[c.chave] = form[c.chave] || null;
      if (dados) await api(`/dados-tecnicos-motor/${dados.id}/`, { method: "PATCH", body });
      else await api("/dados-tecnicos-motor/", { method: "POST", body });
      await onMudou();
    } catch (e) {
      setErro(e instanceof ApiError ? JSON.stringify(e.data) : "Falha ao salvar os dados do motor.");
    } finally {
      setSalvando(false);
    }
  }

  async function enviarFoto(file: File) {
    if (!dados) {
      setErro("Salve os dados do motor antes de anexar a foto da placa.");
      return;
    }
    setEnviandoFoto(true);
    setErro(null);
    try {
      const fd = new FormData();
      fd.append("foto_placa", file);
      await api(`/dados-tecnicos-motor/${dados.id}/`, { method: "PATCH", body: fd });
      await onMudou();
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : "Falha ao enviar a foto da placa.");
    } finally {
      setEnviandoFoto(false);
      if (inputFoto.current) inputFoto.current.value = "";
    }
  }

  return (
    <Card className="space-y-4">
      <div>
        <h2 className="text-sm font-semibold text-fg">Dados técnicos — Motor elétrico</h2>
        <p className="text-xs text-fg-muted">
          Potência e tipo de base definem a Classe ISO automaticamente (acima de 75 kW).
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {CAMPOS_MOTOR.map((c) => (
          <Field key={c.chave} label={c.label}>
            <Input
              type="number"
              step={c.passo}
              inputMode="decimal"
              disabled={!podeEditar}
              value={form[c.chave]}
              onChange={(e) => setForm({ ...form, [c.chave]: e.target.value })}
            />
          </Field>
        ))}
        <Field label="Classe de isolação (ISOL)">
          <Input
            placeholder="Ex.: F"
            disabled={!podeEditar}
            value={classeIsolacao}
            onChange={(e) => setClasseIsolacao(e.target.value)}
          />
        </Field>
        <Field label="Rolamento LOA (lado oposto ao acoplamento)">
          <Input disabled={!podeEditar} value={rolamentoLoa} onChange={(e) => setRolamentoLoa(e.target.value)} />
        </Field>
        <Field label="Rolamento LA (lado do acoplamento)">
          <Input disabled={!podeEditar} value={rolamentoLa} onChange={(e) => setRolamentoLa(e.target.value)} />
        </Field>
        <Field label="Tipo de base">
          <Select disabled={!podeEditar} value={tipoBase} onChange={(e) => setTipoBase(e.target.value as TipoBase)}>
            <option value="">— não informado —</option>
            <option value="RIGIDA">Rígida</option>
            <option value="FLEXIVEL">Flexível</option>
          </Select>
        </Field>
      </div>

      {erro && <p className="text-sm text-danger-fg">{erro}</p>}

      {podeEditar && (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <input
              ref={inputFoto}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) enviarFoto(f);
              }}
            />
            <Button
              variant="secondary"
              icon={ImagePlus}
              loading={enviandoFoto}
              onClick={() => inputFoto.current?.click()}
            >
              {dados?.foto_placa ? "Trocar foto da placa" : "Anexar foto da placa"}
            </Button>
          </div>
          <Button onClick={salvar} loading={salvando}>
            {dados ? "Salvar dados do motor" : "Criar dados do motor"}
          </Button>
        </div>
      )}

      {dados?.foto_placa && (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={dados.foto_placa}
          alt="Placa de identificação do motor"
          className="max-h-48 rounded-lg border border-border object-contain"
        />
      )}
    </Card>
  );
}

/* ===================== Transformador ===================== */

const CAMPOS_TRANSFORMADOR = [
  { chave: "potencia_kva", label: "Potência (kVA)", passo: "0.01" },
  { chave: "tensao_primaria_v", label: "Tensão primária (V)", passo: "0.01" },
  { chave: "tensao_secundaria_v", label: "Tensão secundária (V)", passo: "0.01" },
  { chave: "impedancia_pct", label: "Impedância (%)", passo: "0.01" },
] as const;

export function DadosTransformador({
  equipamentoId,
  dados,
  podeEditar,
  onMudou,
}: {
  equipamentoId: number;
  dados: DadosTecnicosTransformador | null;
  podeEditar: boolean;
  onMudou: () => Promise<void>;
}) {
  const [form, setForm] = useState<Record<string, string>>(() =>
    Object.fromEntries(
      CAMPOS_TRANSFORMADOR.map((c) => [
        c.chave,
        dados ? String(dados[c.chave as keyof DadosTecnicosTransformador] ?? "") : "",
      ])
    )
  );
  const [grupoLigacao, setGrupoLigacao] = useState(dados?.grupo_ligacao ?? "");
  const [salvando, setSalvando] = useState(false);
  const [enviandoFoto, setEnviandoFoto] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const inputFoto = useRef<HTMLInputElement>(null);

  async function salvar() {
    setSalvando(true);
    setErro(null);
    try {
      const body: Record<string, unknown> = { equipamento: equipamentoId, grupo_ligacao: grupoLigacao };
      for (const c of CAMPOS_TRANSFORMADOR) body[c.chave] = form[c.chave] || null;
      if (dados) await api(`/dados-tecnicos-transformador/${dados.id}/`, { method: "PATCH", body });
      else await api("/dados-tecnicos-transformador/", { method: "POST", body });
      await onMudou();
    } catch (e) {
      setErro(e instanceof ApiError ? JSON.stringify(e.data) : "Falha ao salvar os dados do transformador.");
    } finally {
      setSalvando(false);
    }
  }

  async function enviarFoto(file: File) {
    if (!dados) {
      setErro("Salve os dados do transformador antes de anexar a foto da placa.");
      return;
    }
    setEnviandoFoto(true);
    setErro(null);
    try {
      const fd = new FormData();
      fd.append("foto_placa", file);
      await api(`/dados-tecnicos-transformador/${dados.id}/`, { method: "PATCH", body: fd });
      await onMudou();
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : "Falha ao enviar a foto da placa.");
    } finally {
      setEnviandoFoto(false);
      if (inputFoto.current) inputFoto.current.value = "";
    }
  }

  return (
    <Card className="space-y-4">
      <div>
        <h2 className="text-sm font-semibold text-fg">Dados técnicos — Transformador</h2>
        <p className="text-xs text-fg-muted">Campos específicos deste tipo — não usa os campos de motor.</p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {CAMPOS_TRANSFORMADOR.map((c) => (
          <Field key={c.chave} label={c.label}>
            <Input
              type="number"
              step={c.passo}
              inputMode="decimal"
              disabled={!podeEditar}
              value={form[c.chave]}
              onChange={(e) => setForm({ ...form, [c.chave]: e.target.value })}
            />
          </Field>
        ))}
        <Field label="Grupo de ligação">
          <Input
            placeholder="Ex.: Dyn1"
            disabled={!podeEditar}
            value={grupoLigacao}
            onChange={(e) => setGrupoLigacao(e.target.value)}
          />
        </Field>
      </div>

      {erro && <p className="text-sm text-danger-fg">{erro}</p>}

      {podeEditar && (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <input
              ref={inputFoto}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) enviarFoto(f);
              }}
            />
            <Button
              variant="secondary"
              icon={ImagePlus}
              loading={enviandoFoto}
              onClick={() => inputFoto.current?.click()}
            >
              {dados?.foto_placa ? "Trocar foto da placa" : "Anexar foto da placa"}
            </Button>
          </div>
          <Button onClick={salvar} loading={salvando}>
            {dados ? "Salvar dados do transformador" : "Criar dados do transformador"}
          </Button>
        </div>
      )}

      {dados?.foto_placa && (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={dados.foto_placa}
          alt="Placa de identificação do transformador"
          className="max-h-48 rounded-lg border border-border object-contain"
        />
      )}
    </Card>
  );
}
