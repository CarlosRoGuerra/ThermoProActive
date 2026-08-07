"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { Paginated } from "@/lib/types";
import { type AchadoForm, type TecnologiaTipo, deltaTPreview } from "@/lib/inspecoes";
import { Field, Input, Select, Textarea } from "@/components/ui";

type CatOpt = {
  id: number;
  nome: string;
  tecnologias_display?: { id: number; nome: string }[];
};
type CondOpt = { id: number; nome: string; sigla?: string };

/** Mantém itens sem tecnologia (universais) ou vinculados à tecnologia atual. */
function filtrarPorTecnologia(itens: CatOpt[], tecnologiaId: number): CatOpt[] {
  return itens.filter((i) => {
    const tecs = i.tecnologias_display ?? [];
    return tecs.length === 0 || tecs.some((t) => t.id === tecnologiaId);
  });
}

/**
 * Campos editáveis de uma análise (achado). Reutilizado no formulário de campo e
 * na edição do escritório. Os campos específicos variam pela tecnologia.
 */
export function AchadoCampos({
  form,
  setForm,
  tipo,
  tecnologiaId,
}: {
  form: AchadoForm;
  setForm: (f: AchadoForm) => void;
  tipo: TecnologiaTipo;
  tecnologiaId: number;
}) {
  const [componentes, setComponentes] = useState<CatOpt[]>([]);
  const [anomalias, setAnomalias] = useState<CatOpt[]>([]);
  const [recomendacoes, setRecomendacoes] = useState<CatOpt[]>([]);
  const [condicoes, setCondicoes] = useState<CondOpt[]>([]);

  useEffect(() => {
    api<Paginated<CatOpt>>("/tipos-componente/?page_size=1000")
      .then((d) => setComponentes(d.results))
      .catch(() => setComponentes([]));
    api<Paginated<CatOpt>>("/tipos-anomalia/?page_size=1000")
      .then((d) => setAnomalias(d.results))
      .catch(() => setAnomalias([]));
    api<Paginated<CatOpt>>("/tipos-recomendacao/?page_size=1000")
      .then((d) => setRecomendacoes(d.results))
      .catch(() => setRecomendacoes([]));
    api<Paginated<CondOpt>>("/condicoes/?page_size=1000")
      .then((d) => setCondicoes(d.results))
      .catch(() => setCondicoes([]));
  }, []);

  const compFiltrados = useMemo(() => filtrarPorTecnologia(componentes, tecnologiaId), [componentes, tecnologiaId]);
  const anomFiltradas = useMemo(() => filtrarPorTecnologia(anomalias, tecnologiaId), [anomalias, tecnologiaId]);
  const recFiltradas = useMemo(() => filtrarPorTecnologia(recomendacoes, tecnologiaId), [recomendacoes, tecnologiaId]);

  const set = (campo: keyof AchadoForm, valor: string) => setForm({ ...form, [campo]: valor });
  const deltaT = deltaTPreview(form.temperatura_medida, form.temperatura_referencia);

  return (
    <div className="space-y-5">
      {/* Condição / grau de risco DESTA análise (por análise; reclassificável). */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Field label="Condição / Grau de risco">
          <Select value={form.condicao} onChange={(e) => set("condicao", e.target.value)}>
            <option value="">— selecione —</option>
            {condicoes.map((c) => (
              <option key={c.id} value={c.id}>
                {c.sigla ? `${c.sigla} — ${c.nome}` : c.nome}
              </option>
            ))}
          </Select>
        </Field>
      </div>

      {/* --- Comum a todas as tecnologias --- */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Field label="Tipo de componente">
          <Select value={form.tipo_componente} onChange={(e) => set("tipo_componente", e.target.value)}>
            <option value="">— selecione —</option>
            {compFiltrados.map((c) => (
              <option key={c.id} value={c.id}>{c.nome}</option>
            ))}
          </Select>
        </Field>
        <Field label="Componente (texto)">
          <Input
            value={form.componente_texto}
            maxLength={120}
            placeholder="Ex.: DJ5"
            onChange={(e) => set("componente_texto", e.target.value)}
          />
        </Field>
        <Field label="Detalhe do componente" className="sm:col-span-2">
          <Input
            value={form.detalhe}
            maxLength={200}
            placeholder="Uso interno (ex.: nº da imagem no termovisor) — não sai para o cliente"
            onChange={(e) => set("detalhe", e.target.value)}
          />
        </Field>
        <Field label="Tipo de anomalia">
          <Select value={form.tipo_anomalia} onChange={(e) => set("tipo_anomalia", e.target.value)}>
            <option value="">— selecione —</option>
            {anomFiltradas.map((a) => (
              <option key={a.id} value={a.id}>{a.nome}</option>
            ))}
          </Select>
        </Field>
        <Field label="Anomalia (texto)">
          <Input
            value={form.anomalia_texto}
            placeholder="Ex.: lado da linha, fases R e S"
            onChange={(e) => set("anomalia_texto", e.target.value)}
          />
        </Field>
        <Field label="Recomendação">
          <Select value={form.recomendacao} onChange={(e) => set("recomendacao", e.target.value)}>
            <option value="">— selecione —</option>
            {recFiltradas.map((r) => (
              <option key={r.id} value={r.id}>{r.nome}</option>
            ))}
          </Select>
        </Field>
        <Field label="Recomendação (texto)">
          <Input value={form.recomendacao_texto} onChange={(e) => set("recomendacao_texto", e.target.value)} />
        </Field>
        <Field label="Observações" className="sm:col-span-2">
          <Textarea
            value={form.observacoes}
            rows={2}
            onChange={(e) => set("observacoes", e.target.value)}
          />
        </Field>
      </div>

      {/* --- Vibração --- */}
      {tipo === "vibracao" && (
        <div>
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-fg-subtle">
            Vibração — valores globais
          </h3>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label="Global de aceleração (g)">
              <Input
                type="number"
                inputMode="decimal"
                value={form.aceleracao_global}
                onChange={(e) => set("aceleracao_global", e.target.value)}
              />
            </Field>
            <Field label="Global de velocidade (mm/s)">
              <Input
                type="number"
                inputMode="decimal"
                value={form.velocidade_global}
                onChange={(e) => set("velocidade_global", e.target.value)}
              />
            </Field>
          </div>
        </div>
      )}

      {/* --- Termografia --- */}
      {tipo === "termografia" && (
        <div className="space-y-5">
          <div>
            <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-fg-subtle">
              Termografia — temperaturas
            </h3>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
              <Field label="Temperatura medida (°C)">
                <Input
                  type="number"
                  inputMode="decimal"
                  value={form.temperatura_medida}
                  onChange={(e) => set("temperatura_medida", e.target.value)}
                />
              </Field>
              <Field label="Temperatura de referência (°C)">
                <Input
                  type="number"
                  inputMode="decimal"
                  value={form.temperatura_referencia}
                  onChange={(e) => set("temperatura_referencia", e.target.value)}
                />
              </Field>
              <Field label="ΔT (°C) — calculado">
                <Input value={deltaT ?? "—"} disabled readOnly />
              </Field>
              <Field label="Carga (%)">
                <Input
                  type="number"
                  inputMode="decimal"
                  value={form.carga_percentual}
                  onChange={(e) => set("carga_percentual", e.target.value)}
                />
              </Field>
            </div>
          </div>

          <div>
            <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-fg-subtle">
              Grandezas elétricas (nominal + fases A/B/C · R/S/T)
            </h3>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
              <Field label="Corrente nominal (A)">
                <Input type="number" inputMode="decimal" value={form.corrente_nominal} onChange={(e) => set("corrente_nominal", e.target.value)} />
              </Field>
              <Field label="Corrente A/R">
                <Input type="number" inputMode="decimal" value={form.corrente_a} onChange={(e) => set("corrente_a", e.target.value)} />
              </Field>
              <Field label="Corrente B/S">
                <Input type="number" inputMode="decimal" value={form.corrente_b} onChange={(e) => set("corrente_b", e.target.value)} />
              </Field>
              <Field label="Corrente C/T">
                <Input type="number" inputMode="decimal" value={form.corrente_c} onChange={(e) => set("corrente_c", e.target.value)} />
              </Field>
              <Field label="Tensão nominal (V)">
                <Input type="number" inputMode="decimal" value={form.tensao_nominal} onChange={(e) => set("tensao_nominal", e.target.value)} />
              </Field>
              <Field label="Tensão A/R">
                <Input type="number" inputMode="decimal" value={form.tensao_a} onChange={(e) => set("tensao_a", e.target.value)} />
              </Field>
              <Field label="Tensão B/S">
                <Input type="number" inputMode="decimal" value={form.tensao_b} onChange={(e) => set("tensao_b", e.target.value)} />
              </Field>
              <Field label="Tensão C/T">
                <Input type="number" inputMode="decimal" value={form.tensao_c} onChange={(e) => set("tensao_c", e.target.value)} />
              </Field>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
