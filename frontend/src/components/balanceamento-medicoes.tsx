"use client";

import { useState } from "react";
import { Plus } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { BalanceamentoPonto, ServicoCampo } from "@/lib/types";
import { Badge, Button, Card, CriticidadeBadge, Field, Input, Select } from "@/components/ui";

const n = (v: string | number | null | undefined, casas = 2) =>
  v == null || v === "" ? "—" : Number(v).toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });

/**
 * Quantidade de planos × etapas de medição — dois conceitos diferentes que não se
 * confundem (pedido do cliente, 2026-09-10):
 *
 *  · Quantidade de planos (1 ou 2, nunca 3) — ONDE a massa de correção é fixada.
 *  · Reference/Trial/Trim Run — as três corridas de vibração de cada ponto de medição.
 *    Reference vale para todos os pontos; Trial só para o ponto de foco (maior
 *    amplitude); Trim vale para todos de novo (verifica o resultado geral).
 *
 * `QuantidadePlanos`/`PontosMedicao`/`SelecaoPontoFoco`/`TrialRun`/`TrimRun` cobrem, em
 * ordem, os passos 3-8 da interface pedida (1-2 = informações gerais/rotação, ficam na
 * tela que usa estes componentes; 9-11 = resultado/gráfico/economia, no restante da
 * tela). Todos operam sobre o mesmo `ServicoCampo`, com os mesmos endpoints que já
 * existiam (`/balanceamento-planos/`, `/balanceamento-pontos/`, `/servicos/{id}/`).
 */

/* ===================== 3. Quantidade de planos ===================== */

export function QuantidadePlanos({
  servico,
  podeEditar,
  onMudou,
}: {
  servico: ServicoCampo;
  podeEditar: boolean;
  onMudou: () => Promise<void>;
}) {
  const { user } = useAuth();
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const quantidade = servico.planos.length >= 2 ? 2 : servico.planos.length === 1 ? 1 : null;

  async function garantirPlanos(alvo: 1 | 2) {
    setSalvando(true);
    setErro(null);
    try {
      const existentes = new Set(servico.planos.map((p) => p.numero));
      for (let numero = 1; numero <= alvo; numero++) {
        if (!existentes.has(numero)) {
          await api("/balanceamento-planos/", { method: "POST", body: { servico: servico.id, numero } });
        }
      }
      await onMudou();
    } catch (e) {
      setErro(e instanceof ApiError ? JSON.stringify(e.data) : "Falha ao definir a quantidade de planos.");
    } finally {
      setSalvando(false);
    }
  }

  async function remover(planoId: number) {
    setErro(null);
    try {
      await api(`/balanceamento-planos/${planoId}/`, { method: "DELETE" });
      await onMudou();
    } catch (e) {
      setErro(e instanceof ApiError ? JSON.stringify(e.data) : "Não foi possível remover o plano.");
    }
  }

  return (
    <Card className="space-y-3">
      <div>
        <h2 className="text-sm font-semibold text-fg">Balanceamento em</h2>
        <p className="text-xs text-fg-muted">Onde a massa de correção é fixada — nunca existe Plano 3.</p>
      </div>
      <div className="flex flex-wrap gap-2">
        {([1, 2] as const).map((opcao) => (
          <button
            key={opcao}
            type="button"
            disabled={!podeEditar || salvando || (opcao === 1 && quantidade === 2)}
            onClick={() => garantirPlanos(opcao)}
            className={`rounded-lg border px-4 py-2 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${
              quantidade === opcao
                ? "border-accent bg-accent-subtle text-accent-subtle-fg"
                : "border-border text-fg-muted hover:bg-surface-muted"
            }`}
          >
            {opcao} plano{opcao > 1 ? "s" : ""}
          </button>
        ))}
      </div>
      {quantidade === 2 && (
        <p className="text-xs text-fg-subtle">
          Para voltar a 1 plano, remova o Plano 2 abaixo (só é possível se ele ainda não tiver massa lançada).
        </p>
      )}
      {servico.planos.length > 0 && (
        <ul className="space-y-1">
          {servico.planos.map((p) => (
            <li key={p.id} className="flex items-center justify-between text-sm text-fg">
              <span>Plano {p.numero}</span>
              {podeEditar && user?.pode_excluir && (
                <button
                  onClick={() => remover(p.id)}
                  className="text-xs text-fg-subtle hover:text-[var(--danger)]"
                >
                  remover
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
      {erro && <p className="text-sm text-danger-fg">{erro}</p>}
    </Card>
  );
}

/* ===================== 4. Pontos de medição (+ Reference Run) ===================== */

const PONTO_VAZIO = {
  numero_mancal: "",
  direcao: "H",
  identificacao: "",
  plano: "" as number | "",
  reference_mms: "",
  reference_fase: "",
};

export function PontosMedicao({
  servico,
  podeEditar,
  onMudou,
  onErro,
}: {
  servico: ServicoCampo;
  podeEditar: boolean;
  onMudou: () => Promise<void>;
  onErro: (m: string | null) => void;
}) {
  const [novo, setNovo] = useState({ ...PONTO_VAZIO });
  const [aberto, setAberto] = useState(false);
  const [salvando, setSalvando] = useState(false);

  async function adicionar() {
    setSalvando(true);
    onErro(null);
    try {
      await api<BalanceamentoPonto>("/balanceamento-pontos/", {
        method: "POST",
        body: {
          servico: servico.id,
          numero_mancal: Number(novo.numero_mancal),
          direcao: novo.direcao,
          identificacao: novo.identificacao,
          plano: novo.plano || null,
          reference_mms: novo.reference_mms,
          reference_fase: novo.reference_fase,
        },
      });
      setNovo({ ...PONTO_VAZIO });
      setAberto(false);
      await onMudou();
    } catch (e) {
      onErro(e instanceof ApiError ? JSON.stringify(e.data) : "Falha ao salvar o ponto.");
    } finally {
      setSalvando(false);
    }
  }

  return (
    <Card className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-fg">Pontos de medição — Reference Run</h2>
          <p className="text-xs text-fg-muted">
            Um ponto por mancal/direção. A referência (antes da massa de teste) vale para todos.
          </p>
        </div>
        {podeEditar && (
          <Button size="sm" variant="secondary" onClick={() => setAberto(!aberto)}>
            <Plus className="h-4 w-4" />
            Adicionar ponto
          </Button>
        )}
      </div>

      {servico.pontos.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[520px] text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs text-fg-subtle">
                <th className="py-2 pr-3 font-medium">Ponto</th>
                <th className="py-2 pr-3 font-medium">Identificação</th>
                <th className="py-2 pr-3 font-medium">Plano</th>
                <th className="py-2 pr-3 font-medium">Reference (mm/s)</th>
                <th className="py-2 font-medium">Fase</th>
              </tr>
            </thead>
            <tbody>
              {servico.pontos.map((p) => (
                <tr key={p.id} className="border-b border-border last:border-0">
                  <td className="py-2 pr-3 font-medium text-fg">{p.codigo_ponto}</td>
                  <td className="py-2 pr-3 text-fg-muted">{p.identificacao || "—"}</td>
                  <td className="py-2 pr-3 text-fg-muted">
                    {servico.planos.find((pl) => pl.id === p.plano)?.numero ?? "—"}
                  </td>
                  <td className="py-2 pr-3 tabular-nums">{n(p.reference_mms)}</td>
                  <td className="py-2 tabular-nums text-fg-muted">{n(p.reference_fase, 0)}°</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {aberto && podeEditar && (
        <div className="grid gap-3 rounded-lg border border-border p-3 sm:grid-cols-4">
          <Field label="Mancal">
            <Input
              type="number"
              inputMode="numeric"
              value={novo.numero_mancal}
              onChange={(e) => setNovo({ ...novo, numero_mancal: e.target.value })}
            />
          </Field>
          <Field label="Direção">
            <Select value={novo.direcao} onChange={(e) => setNovo({ ...novo, direcao: e.target.value })}>
              <option value="H">Horizontal</option>
              <option value="V">Vertical</option>
              <option value="A">Axial</option>
            </Select>
          </Field>
          <Field label="Identificação" className="sm:col-span-2">
            <Input
              placeholder="Ex.: Motor — lado livre"
              value={novo.identificacao}
              onChange={(e) => setNovo({ ...novo, identificacao: e.target.value })}
            />
          </Field>
          {servico.planos.length > 0 && (
            <Field label="Plano corrigido por este ponto" className="sm:col-span-2">
              <Select
                value={novo.plano}
                onChange={(e) => setNovo({ ...novo, plano: e.target.value ? Number(e.target.value) : "" })}
              >
                <option value="">— nenhum (não usado no balanceamento) —</option>
                {servico.planos.map((p) => (
                  <option key={p.id} value={p.id}>Plano {p.numero}</option>
                ))}
              </Select>
            </Field>
          )}
          <Field label="Reference run (mm/s)">
            <Input
              type="number"
              step="0.01"
              inputMode="decimal"
              value={novo.reference_mms}
              onChange={(e) => setNovo({ ...novo, reference_mms: e.target.value })}
            />
          </Field>
          <Field label="Fase (°)">
            <Input
              type="number"
              step="0.1"
              inputMode="decimal"
              value={novo.reference_fase}
              onChange={(e) => setNovo({ ...novo, reference_fase: e.target.value })}
            />
          </Field>
          <div className="flex items-end sm:col-span-2">
            <Button onClick={adicionar} loading={salvando} className="w-full">
              Salvar ponto
            </Button>
          </div>
        </div>
      )}

      {servico.pontos.length === 0 && !aberto && (
        <p className="text-sm text-fg-muted">Nenhum ponto medido ainda.</p>
      )}
    </Card>
  );
}

/* ===================== 5. Seleção do ponto de foco ===================== */

export function SelecaoPontoFoco({
  servico,
  podeEditar,
  onMudou,
  onErro,
}: {
  servico: ServicoCampo;
  podeEditar: boolean;
  onMudou: () => Promise<void>;
  onErro: (m: string | null) => void;
}) {
  const [salvando, setSalvando] = useState(false);

  async function escolher(pontoId: number) {
    setSalvando(true);
    onErro(null);
    try {
      await api(`/servicos/${servico.id}/`, { method: "PATCH", body: { ponto_foco: pontoId } });
      await onMudou();
    } catch (e) {
      onErro(e instanceof ApiError ? JSON.stringify(e.data) : "Falha ao definir o ponto de foco.");
    } finally {
      setSalvando(false);
    }
  }

  return (
    <Card className="space-y-3">
      <div>
        <h2 className="text-sm font-semibold text-fg">Ponto de foco</h2>
        <p className="text-xs text-fg-muted">
          Qual ponto tem a maior amplitude — só ele recebe o Trial Run e o cálculo da correção.
        </p>
      </div>
      {servico.pontos.length === 0 ? (
        <p className="text-sm text-fg-muted">Cadastre os pontos de medição acima primeiro.</p>
      ) : (
        <div className="space-y-1.5">
          {servico.pontos.map((p) => (
            <label
              key={p.id}
              className={`flex cursor-pointer items-center gap-3 rounded-lg border px-3 py-2 text-sm transition-colors ${
                servico.ponto_foco === p.id
                  ? "border-accent bg-accent-subtle"
                  : "border-border hover:bg-surface-muted"
              } ${!podeEditar || salvando ? "cursor-not-allowed opacity-70" : ""}`}
            >
              <input
                type="radio"
                name={`ponto-foco-${servico.id}`}
                checked={servico.ponto_foco === p.id}
                disabled={!podeEditar || salvando}
                onChange={() => escolher(p.id)}
                className="h-4 w-4"
                style={{ accentColor: "var(--accent)" }}
              />
              <span className="font-mono font-semibold text-fg">{p.codigo_ponto}</span>
              {p.identificacao && <span className="text-fg-muted">{p.identificacao}</span>}
              <span className="ml-auto tabular-nums text-fg-subtle">{n(p.reference_mms)} mm/s</span>
            </label>
          ))}
        </div>
      )}
    </Card>
  );
}

/* ===================== 6-7. Trial Run (só no ponto de foco) ===================== */

export function TrialRun({
  servico,
  podeEditar,
  onMudou,
  onErro,
}: {
  servico: ServicoCampo;
  podeEditar: boolean;
  onMudou: () => Promise<void>;
  onErro: (m: string | null) => void;
}) {
  const foco = servico.pontos.find((p) => p.id === servico.ponto_foco) ?? null;
  const [trial, setTrial] = useState({ mms: foco?.trial_mms ?? "", fase: foco?.trial_fase ?? "" });
  const [massas, setMassas] = useState(() =>
    Object.fromEntries(servico.planos.map((p) => [p.id, { massa: p.massa_teste_g ?? "", angulo: p.angulo_teste ?? "" }]))
  );
  const [salvando, setSalvando] = useState<string | null>(null);

  if (!foco) {
    return (
      <Card>
        <h2 className="mb-1 text-sm font-semibold text-fg">Trial Run</h2>
        <p className="text-sm text-fg-muted">Selecione o ponto de foco acima para lançar o Trial Run.</p>
      </Card>
    );
  }

  const comparativo =
    trial.mms && foco.reference_mms
      ? ((Number(trial.mms) - Number(foco.reference_mms)) / Number(foco.reference_mms)) * 100
      : null;

  async function salvarTrial() {
    setSalvando("trial");
    onErro(null);
    try {
      await api(`/balanceamento-pontos/${foco!.id}/`, {
        method: "PATCH",
        body: { trial_mms: trial.mms || null, trial_fase: trial.fase || null },
      });
      await onMudou();
    } catch (e) {
      onErro(e instanceof ApiError ? JSON.stringify(e.data) : "Falha ao salvar o Trial Run.");
    } finally {
      setSalvando(null);
    }
  }

  async function salvarMassa(planoId: number, remover = false) {
    setSalvando(`massa-${planoId}`);
    onErro(null);
    try {
      const valores = remover ? { massa: "", angulo: "" } : massas[planoId];
      await api(`/balanceamento-planos/${planoId}/`, {
        method: "PATCH",
        body: { massa_teste_g: valores.massa || null, angulo_teste: valores.angulo || null },
      });
      if (remover) setMassas((m) => ({ ...m, [planoId]: { massa: "", angulo: "" } }));
      await onMudou();
    } catch (e) {
      onErro(e instanceof ApiError ? JSON.stringify(e.data) : "Falha ao salvar a massa de teste.");
    } finally {
      setSalvando(null);
    }
  }

  return (
    <Card className="space-y-4">
      <div>
        <h2 className="text-sm font-semibold text-fg">Trial Run — teste com a massa de teste</h2>
        <p className="text-xs text-fg-muted">
          Ponto escolhido: <span className="font-mono font-semibold text-fg">{foco.codigo_ponto}</span>
          {foco.identificacao && ` — ${foco.identificacao}`}. A massa de teste é escolha do técnico (experiência
          e tamanho do rotor) — não é calculada pelo sistema.
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <Field label="Vibração medida (mm/s)">
          <Input
            type="number"
            step="0.01"
            inputMode="decimal"
            disabled={!podeEditar}
            value={trial.mms}
            onChange={(e) => setTrial({ ...trial, mms: e.target.value })}
          />
        </Field>
        <Field label="Fase (°)">
          <Input
            type="number"
            step="0.1"
            inputMode="decimal"
            disabled={!podeEditar}
            value={trial.fase}
            onChange={(e) => setTrial({ ...trial, fase: e.target.value })}
          />
        </Field>
        {podeEditar && (
          <div className="flex items-end">
            <Button size="sm" loading={salvando === "trial"} onClick={salvarTrial} className="w-full">
              Salvar Trial Run
            </Button>
          </div>
        )}
      </div>
      {comparativo != null && (
        <p className="text-sm text-fg-muted">
          Comparado ao Reference ({n(foco.reference_mms)} mm/s):{" "}
          <strong className={comparativo >= 0 ? "text-fg" : "text-[var(--viz-trim)]"}>
            {comparativo >= 0 ? "+" : ""}
            {comparativo.toFixed(1)}%
          </strong>
        </p>
      )}

      {servico.planos.length > 0 && (
        <div className="space-y-3 border-t border-border pt-3">
          <p className="text-xs font-medium text-fg-subtle">Massa de teste por plano</p>
          {servico.planos.map((p) => {
            const valor = massas[p.id] ?? { massa: "", angulo: "" };
            const jaTemMassa = p.massa_teste_g != null;
            return (
              <div key={p.id} className="grid items-end gap-3 sm:grid-cols-[auto_1fr_1fr_auto_auto]">
                <span className="text-sm font-medium text-fg">Plano {p.numero}</span>
                <Field label="Massa de teste (g)">
                  <Input
                    type="number"
                    step="0.1"
                    inputMode="decimal"
                    disabled={!podeEditar}
                    value={valor.massa}
                    onChange={(e) => setMassas((m) => ({ ...m, [p.id]: { ...valor, massa: e.target.value } }))}
                  />
                </Field>
                <Field label="Ângulo (°)">
                  <Input
                    type="number"
                    step="0.1"
                    inputMode="decimal"
                    disabled={!podeEditar}
                    value={valor.angulo}
                    onChange={(e) => setMassas((m) => ({ ...m, [p.id]: { ...valor, angulo: e.target.value } }))}
                  />
                </Field>
                {podeEditar && (
                  <>
                    <Button size="sm" loading={salvando === `massa-${p.id}`} onClick={() => salvarMassa(p.id)}>
                      {jaTemMassa ? "Manter" : "Salvar"}
                    </Button>
                    {jaTemMassa && (
                      <Button
                        size="sm"
                        variant="ghost"
                        loading={salvando === `massa-${p.id}`}
                        onClick={() => salvarMassa(p.id, true)}
                      >
                        Remover
                      </Button>
                    )}
                  </>
                )}
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
}

/* ===================== 8. Trim Run (todos os pontos) ===================== */

export function TrimRun({
  servico,
  podeEditar,
  onMudou,
  onErro,
}: {
  servico: ServicoCampo;
  podeEditar: boolean;
  onMudou: () => Promise<void>;
  onErro: (m: string | null) => void;
}) {
  const [trims, setTrims] = useState<Record<number, { mms: string; fase: string }>>(
    Object.fromEntries(servico.pontos.map((p) => [p.id, { mms: p.trim_mms ?? "", fase: p.trim_fase ?? "" }]))
  );
  const [massas, setMassas] = useState(() =>
    Object.fromEntries(servico.planos.map((p) => [p.id, { massa: p.massa_final_g ?? "", angulo: p.angulo_final ?? "" }]))
  );
  const [salvando, setSalvando] = useState<string | null>(null);

  async function salvarTrim(pontoId: number) {
    setSalvando(`trim-${pontoId}`);
    onErro(null);
    try {
      const valor = trims[pontoId] ?? { mms: "", fase: "" };
      await api(`/balanceamento-pontos/${pontoId}/`, {
        method: "PATCH",
        body: { trim_mms: valor.mms || null, trim_fase: valor.fase || null },
      });
      await onMudou();
    } catch (e) {
      onErro(e instanceof ApiError ? JSON.stringify(e.data) : "Falha ao lançar o Trim Run.");
    } finally {
      setSalvando(null);
    }
  }

  async function salvarMassaFinal(planoId: number) {
    setSalvando(`final-${planoId}`);
    onErro(null);
    try {
      const valor = massas[planoId] ?? { massa: "", angulo: "" };
      await api(`/balanceamento-planos/${planoId}/`, {
        method: "PATCH",
        body: { massa_final_g: valor.massa || null, angulo_final: valor.angulo || null },
      });
      await onMudou();
    } catch (e) {
      onErro(e instanceof ApiError ? JSON.stringify(e.data) : "Falha ao salvar a massa de correção.");
    } finally {
      setSalvando(null);
    }
  }

  return (
    <Card className="space-y-4">
      <div>
        <h2 className="text-sm font-semibold text-fg">Trim Run — correção final</h2>
        <p className="text-xs text-fg-muted">
          Vale para todos os pontos (confirma o resultado geral, não só no ponto de foco).
        </p>
      </div>

      {servico.pontos.length === 0 ? (
        <p className="text-sm text-fg-muted">Nenhum ponto medido ainda.</p>
      ) : (
        <div className="space-y-3">
          {servico.pontos.map((p) => {
            const valor = trims[p.id] ?? { mms: "", fase: "" };
            return (
              <div key={p.id} className="rounded-lg border border-border p-3">
                <div className="mb-2 flex flex-wrap items-center gap-2 text-sm">
                  <span className="font-mono font-semibold text-fg">{p.codigo_ponto}</span>
                  {p.identificacao && <span className="text-fg-muted">{p.identificacao}</span>}
                  {p.id === servico.ponto_foco && <Badge tone="accent">foco</Badge>}
                  {p.completo && (
                    <span className="ml-auto flex items-center gap-1.5">
                      <CriticidadeBadge value={p.criticidade} />
                      {p.zona_iso && <Badge tone="neutral">Zona {p.zona_iso}</Badge>}
                      <span className="font-medium tabular-nums">{n(p.reducao_pct, 1)}% de redução</span>
                    </span>
                  )}
                </div>
                <div className="grid gap-3 sm:grid-cols-3">
                  <Field label="Vibração após correção (mm/s)">
                    <Input
                      type="number"
                      step="0.01"
                      inputMode="decimal"
                      disabled={!podeEditar}
                      value={valor.mms}
                      onChange={(e) => setTrims((t) => ({ ...t, [p.id]: { ...valor, mms: e.target.value } }))}
                    />
                  </Field>
                  <Field label="Fase (°)">
                    <Input
                      type="number"
                      step="0.1"
                      inputMode="decimal"
                      disabled={!podeEditar}
                      value={valor.fase}
                      onChange={(e) => setTrims((t) => ({ ...t, [p.id]: { ...valor, fase: e.target.value } }))}
                    />
                  </Field>
                  {podeEditar && (
                    <div className="flex items-end">
                      <Button
                        size="sm"
                        loading={salvando === `trim-${p.id}`}
                        onClick={() => salvarTrim(p.id)}
                        className="w-full"
                      >
                        Salvar Trim Run
                      </Button>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {servico.planos.length > 0 && (
        <div className="space-y-3 border-t border-border pt-3">
          <p className="text-xs font-medium text-fg-subtle">Massa de correção por plano</p>
          {servico.planos.map((p) => {
            const valor = massas[p.id] ?? { massa: "", angulo: "" };
            return (
              <div key={p.id} className="grid items-end gap-3 sm:grid-cols-[auto_1fr_1fr_auto]">
                <span className="text-sm font-medium text-fg">Plano {p.numero}</span>
                <Field label="Massa de correção (g)">
                  <Input
                    type="number"
                    step="0.1"
                    inputMode="decimal"
                    disabled={!podeEditar}
                    value={valor.massa}
                    onChange={(e) => setMassas((m) => ({ ...m, [p.id]: { ...valor, massa: e.target.value } }))}
                  />
                </Field>
                <Field label="Ângulo (°)">
                  <Input
                    type="number"
                    step="0.1"
                    inputMode="decimal"
                    disabled={!podeEditar}
                    value={valor.angulo}
                    onChange={(e) => setMassas((m) => ({ ...m, [p.id]: { ...valor, angulo: e.target.value } }))}
                  />
                </Field>
                {podeEditar && (
                  <Button size="sm" loading={salvando === `final-${p.id}`} onClick={() => salvarMassaFinal(p.id)}>
                    Salvar
                  </Button>
                )}
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
}
