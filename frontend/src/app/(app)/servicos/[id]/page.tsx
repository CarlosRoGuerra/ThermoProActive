"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { Gauge, Plus, Trash2, Zap } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type {
  BalanceamentoPlano,
  BalanceamentoPonto,
  EconomiaEnergetica,
  ServicoCampo,
} from "@/lib/types";
import {
  Badge,
  Button,
  Card,
  CriticidadeBadge,
  Field,
  Input,
  PageHeader,
  Select,
  Spinner,
  StatCard,
} from "@/components/ui";
import {
  AntesDepois,
  MostradorPolar,
  amplitudeMaxima,
  type PontoGrafico,
} from "@/components/balanceamento-graficos";

const n = (v: string | number | null | undefined, casas = 2) =>
  v == null || v === ""
    ? "—"
    : Number(v).toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });

const reais = (v: string | null) =>
  v == null ? "—" : Number(v).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

/** Converte o ponto da API no formato que os gráficos consomem. */
function paraGrafico(p: BalanceamentoPonto): PontoGrafico {
  const corrida = (mms: string | null, fase: string | null) =>
    mms != null && fase != null ? { mms: Number(mms), fase: Number(fase) } : null;
  return {
    codigo_ponto: p.codigo_ponto,
    reference: corrida(p.reference_mms, p.reference_fase),
    trial: corrida(p.trial_mms, p.trial_fase),
    trim: corrida(p.trim_mms, p.trim_fase),
    reducao_pct: p.reducao_pct != null ? Number(p.reducao_pct) : null,
    zona_iso: p.zona_iso,
    completo: p.completo,
  };
}

export default function ServicoDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const podeEditar = !!user?.is_interno;
  const [servico, setServico] = useState<ServicoCampo | null>(null);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  const carregar = useCallback(async () => {
    setServico(await api<ServicoCampo>(`/servicos/${id}/`));
  }, [id]);

  useEffect(() => {
    carregar().finally(() => setLoading(false));
  }, [carregar]);

  const pontosGrafico = useMemo(
    () => (servico?.pontos ?? []).map(paraGrafico),
    [servico]
  );
  const maxima = useMemo(() => amplitudeMaxima(pontosGrafico), [pontosGrafico]);

  if (loading) return <Spinner />;
  if (!servico) return <p className="text-sm text-fg-muted">Serviço não encontrado.</p>;

  return (
    <div className="space-y-5">
      <PageHeader
        title={`${servico.equipamento_tag} — ${servico.tipo_display}`}
        description={`${servico.equipamento_nome} · ${servico.cliente_nome} · ${servico.data_execucao
          .split("-")
          .reverse()
          .join("/")}`}
        icon={Gauge}
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Rotação" value={servico.rotacao_rpm ? `${servico.rotacao_rpm} RPM` : "—"} hint={servico.rotacao_hz ? `${n(servico.rotacao_hz)} Hz` : undefined} />
        <StatCard label="Planos de correção" value={servico.numero_planos || "—"} />
        <StatCard
          label="Redução média"
          value={servico.reducao_media_pct ? `${n(servico.reducao_media_pct, 1)}%` : "—"}
          tone={servico.reducao_media_pct ? "ok" : "default"}
        />
        <StatCard label="Classe ISO" value={servico.classe_iso || "—"} hint="Base do veredito" />
      </div>

      {erro && <p className="text-sm text-[var(--danger)]">{erro}</p>}

      <Planos servico={servico} podeEditar={podeEditar} onMudou={carregar} onErro={setErro} />
      <Pontos servico={servico} podeEditar={podeEditar} onMudou={carregar} onErro={setErro} />

      {pontosGrafico.some((p) => p.reference) && (
        <div className="grid gap-5 lg:grid-cols-2">
          <Card>
            <h2 className="mb-4 text-sm font-semibold text-fg">Mostrador de fase</h2>
            <div className="flex flex-wrap gap-6">
              {pontosGrafico.map((p) => (
                <div key={p.codigo_ponto}>
                  <p className="mb-1 text-xs font-medium text-fg-muted">Mancal {p.codigo_ponto}</p>
                  <MostradorPolar ponto={p} maxima={maxima} tamanho={260} />
                </div>
              ))}
            </div>
          </Card>
          <Card>
            <h2 className="mb-4 text-sm font-semibold text-fg">Antes × Depois</h2>
            <AntesDepois pontos={pontosGrafico} />
          </Card>
        </div>
      )}

      <Economia servico={servico} podeEditar={podeEditar} onMudou={carregar} onErro={setErro} />
    </div>
  );
}

/* ===================== Planos ===================== */

const PLANO_VAZIO = {
  numero: 1,
  descricao: "",
  massa_teste_g: "",
  angulo_teste: "",
  massa_final_g: "",
  angulo_final: "",
};

function Planos({
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
  const [novo, setNovo] = useState({ ...PLANO_VAZIO });
  const [aberto, setAberto] = useState(false);
  const [salvando, setSalvando] = useState(false);

  async function adicionar() {
    setSalvando(true);
    onErro(null);
    try {
      await api<BalanceamentoPlano>("/balanceamento-planos/", {
        method: "POST",
        body: {
          servico: servico.id,
          numero: novo.numero,
          descricao: novo.descricao,
          massa_teste_g: novo.massa_teste_g || null,
          angulo_teste: novo.angulo_teste || null,
          massa_final_g: novo.massa_final_g || null,
          angulo_final: novo.angulo_final || null,
        },
      });
      setNovo({ ...PLANO_VAZIO, numero: servico.numero_planos + 2 });
      setAberto(false);
      await onMudou();
    } catch (e) {
      onErro(e instanceof ApiError ? JSON.stringify(e.data) : "Falha ao salvar o plano.");
    } finally {
      setSalvando(false);
    }
  }

  async function remover(planoId: number) {
    await api(`/balanceamento-planos/${planoId}/`, { method: "DELETE" });
    await onMudou();
  }

  return (
    <Card className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-fg">Planos de correção</h2>
          <p className="text-xs text-fg-muted">
            Onde a massa é fixada. Um ou dois — era a escolha entre duas abas da planilha.
          </p>
        </div>
        {podeEditar && (
          <Button
            size="sm"
            variant="secondary"
            onClick={() => {
              setNovo({ ...PLANO_VAZIO, numero: servico.numero_planos + 1 });
              setAberto(!aberto);
            }}
          >
            <Plus className="h-4 w-4" />
            Adicionar plano
          </Button>
        )}
      </div>

      {servico.planos.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2">
          {servico.planos.map((p) => (
            <div key={p.id} className="rounded-lg border border-border bg-surface-muted p-3">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm font-medium text-fg">Plano {p.numero}</p>
                  {p.descricao && <p className="text-xs text-fg-muted">{p.descricao}</p>}
                </div>
                {podeEditar && (
                  <button
                    onClick={() => remover(p.id)}
                    className="text-fg-subtle hover:text-[var(--danger)]"
                    aria-label={`Remover plano ${p.numero}`}
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                )}
              </div>
              <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
                <dt className="text-fg-subtle">Massa de teste</dt>
                <dd className="tabular-nums text-fg">
                  {n(p.massa_teste_g, 1)} g @ {n(p.angulo_teste, 0)}°
                </dd>
                <dt className="text-fg-subtle">Massa final</dt>
                <dd className="tabular-nums text-fg">
                  {n(p.massa_final_g, 1)} g @ {n(p.angulo_final, 0)}°
                </dd>
              </dl>
            </div>
          ))}
        </div>
      )}

      {aberto && podeEditar && (
        <div className="grid gap-3 rounded-lg border border-border p-3 sm:grid-cols-3">
          <Field label="Plano nº">
            <Input
              type="number"
              value={novo.numero}
              onChange={(e) => setNovo({ ...novo, numero: Number(e.target.value) })}
            />
          </Field>
          <Field label="Descrição" className="sm:col-span-2">
            <Input
              placeholder="Ex.: lado acoplamento"
              value={novo.descricao}
              onChange={(e) => setNovo({ ...novo, descricao: e.target.value })}
            />
          </Field>
          <Field label="Massa de teste (g)">
            <Input
              type="number"
              step="0.1"
              inputMode="decimal"
              value={novo.massa_teste_g}
              onChange={(e) => setNovo({ ...novo, massa_teste_g: e.target.value })}
            />
          </Field>
          <Field label="Ângulo do teste (°)">
            <Input
              type="number"
              step="0.1"
              inputMode="decimal"
              value={novo.angulo_teste}
              onChange={(e) => setNovo({ ...novo, angulo_teste: e.target.value })}
            />
          </Field>
          <div className="flex items-end">
            <Button onClick={adicionar} loading={salvando} className="w-full">
              Salvar plano
            </Button>
          </div>
        </div>
      )}

      {servico.planos.length === 0 && !aberto && (
        <p className="text-sm text-fg-muted">Nenhum plano registrado ainda.</p>
      )}
    </Card>
  );
}

/* ===================== Pontos — as três corridas ===================== */

const PONTO_VAZIO = {
  numero_mancal: "",
  direcao: "H",
  plano: "" as number | "",
  reference_mms: "",
  reference_fase: "",
  trial_mms: "",
  trial_fase: "",
  trim_mms: "",
  trim_fase: "",
};

function Pontos({
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
  const [editando, setEditando] = useState<number | null>(null);
  const [trim, setTrim] = useState({ trim_mms: "", trim_fase: "" });

  // Prévia da redução enquanto o técnico digita — a planilha só mostrava no fim.
  const previa = useMemo(() => {
    const ref = Number(novo.reference_mms);
    const tr = Number(novo.trim_mms);
    if (!ref || !novo.trim_mms || ref <= 0) return null;
    return { reducao: (1 - tr / ref) * 100, residual: (tr / ref) * 100 };
  }, [novo.reference_mms, novo.trim_mms]);

  async function adicionar() {
    setSalvando(true);
    onErro(null);
    try {
      await api<BalanceamentoPonto>("/balanceamento-pontos/", {
        method: "POST",
        body: {
          servico: servico.id,
          plano: novo.plano || null,
          numero_mancal: Number(novo.numero_mancal),
          direcao: novo.direcao,
          reference_mms: novo.reference_mms,
          reference_fase: novo.reference_fase,
          trial_mms: novo.trial_mms || null,
          trial_fase: novo.trial_fase || null,
          trim_mms: novo.trim_mms || null,
          trim_fase: novo.trim_fase || null,
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

  async function fecharTrim(pontoId: number) {
    setSalvando(true);
    try {
      await api(`/balanceamento-pontos/${pontoId}/`, {
        method: "PATCH",
        body: { trim_mms: trim.trim_mms, trim_fase: trim.trim_fase },
      });
      setEditando(null);
      setTrim({ trim_mms: "", trim_fase: "" });
      await onMudou();
    } catch (e) {
      onErro(e instanceof ApiError ? JSON.stringify(e.data) : "Falha ao lançar o trim run.");
    } finally {
      setSalvando(false);
    }
  }

  return (
    <Card className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-fg">Pontos de medição</h2>
          <p className="text-xs text-fg-muted">
            Reference → Trial → Trim. Dá para salvar sem o trim e voltar depois de aplicar a
            massa final.
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
          <table className="w-full min-w-[720px] text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs text-fg-subtle">
                <th className="py-2 pr-3 font-medium">Ponto</th>
                <th className="py-2 pr-3 font-medium" colSpan={2}>
                  Reference (antes)
                </th>
                <th className="py-2 pr-3 font-medium" colSpan={2}>
                  Trial
                </th>
                <th className="py-2 pr-3 font-medium" colSpan={2}>
                  Trim (depois)
                </th>
                <th className="py-2 pr-3 font-medium">Redução</th>
                <th className="py-2 font-medium">Resultado</th>
              </tr>
              <tr className="border-b border-border text-left text-[10px] text-fg-subtle">
                <th />
                <th className="pb-1 pr-3 font-normal">mm/s</th>
                <th className="pb-1 pr-3 font-normal">fase</th>
                <th className="pb-1 pr-3 font-normal">mm/s</th>
                <th className="pb-1 pr-3 font-normal">fase</th>
                <th className="pb-1 pr-3 font-normal">mm/s</th>
                <th className="pb-1 pr-3 font-normal">fase</th>
                <th />
                <th />
              </tr>
            </thead>
            <tbody>
              {servico.pontos.map((p) => (
                <tr key={p.id} className="border-b border-border last:border-0">
                  <td className="py-2 pr-3 font-medium text-fg">{p.codigo_ponto}</td>
                  <td className="py-2 pr-3 tabular-nums">{n(p.reference_mms)}</td>
                  <td className="py-2 pr-3 tabular-nums text-fg-muted">{n(p.reference_fase, 0)}°</td>
                  <td className="py-2 pr-3 tabular-nums">{n(p.trial_mms)}</td>
                  <td className="py-2 pr-3 tabular-nums text-fg-muted">
                    {p.trial_fase ? `${n(p.trial_fase, 0)}°` : "—"}
                  </td>
                  <td className="py-2 pr-3 tabular-nums">{n(p.trim_mms)}</td>
                  <td className="py-2 pr-3 tabular-nums text-fg-muted">
                    {p.trim_fase ? `${n(p.trim_fase, 0)}°` : "—"}
                  </td>
                  <td className="py-2 pr-3 tabular-nums font-medium">
                    {p.reducao_pct ? `${n(p.reducao_pct, 1)}%` : "—"}
                  </td>
                  <td className="py-2">
                    {p.completo ? (
                      <span className="flex flex-wrap items-center gap-1.5">
                        <CriticidadeBadge value={p.criticidade} />
                        {p.zona_iso && <Badge tone="neutral">Zona {p.zona_iso}</Badge>}
                      </span>
                    ) : podeEditar && editando === p.id ? (
                      <span className="flex items-center gap-1">
                        <Input
                          className="h-8 w-20"
                          placeholder="mm/s"
                          inputMode="decimal"
                          value={trim.trim_mms}
                          onChange={(e) => setTrim({ ...trim, trim_mms: e.target.value })}
                        />
                        <Input
                          className="h-8 w-16"
                          placeholder="fase"
                          inputMode="decimal"
                          value={trim.trim_fase}
                          onChange={(e) => setTrim({ ...trim, trim_fase: e.target.value })}
                        />
                        <Button size="sm" loading={salvando} onClick={() => fecharTrim(p.id)}>
                          OK
                        </Button>
                      </span>
                    ) : (
                      <span className="flex items-center gap-2">
                        <Badge tone="warning">Em andamento</Badge>
                        {podeEditar && (
                          <button
                            className="text-xs text-accent hover:underline"
                            onClick={() => setEditando(p.id)}
                          >
                            lançar trim
                          </button>
                        )}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {aberto && podeEditar && (
        <div className="space-y-3 rounded-lg border border-border p-3">
          <div className="grid gap-3 sm:grid-cols-3">
            <Field label="Mancal">
              <Input
                type="number"
                inputMode="numeric"
                value={novo.numero_mancal}
                onChange={(e) => setNovo({ ...novo, numero_mancal: e.target.value })}
              />
            </Field>
            <Field label="Direção">
              <Select
                value={novo.direcao}
                onChange={(e) => setNovo({ ...novo, direcao: e.target.value })}
              >
                <option value="H">Horizontal</option>
                <option value="V">Vertical</option>
                <option value="A">Axial</option>
              </Select>
            </Field>
            <Field label="Plano corrigido">
              <Select
                value={novo.plano}
                onChange={(e) =>
                  setNovo({ ...novo, plano: e.target.value ? Number(e.target.value) : "" })
                }
              >
                <option value="">—</option>
                {servico.planos.map((p) => (
                  <option key={p.id} value={p.id}>
                    Plano {p.numero}
                  </option>
                ))}
              </Select>
            </Field>
          </div>

          {[
            { titulo: "Reference run (antes)", mms: "reference_mms", fase: "reference_fase", obrigatorio: true },
            { titulo: "Trial run (com a massa de teste)", mms: "trial_mms", fase: "trial_fase", obrigatorio: false },
            { titulo: "Trim run (resultado final)", mms: "trim_mms", fase: "trim_fase", obrigatorio: false },
          ].map((bloco) => (
            <div key={bloco.mms} className="grid gap-3 sm:grid-cols-[1fr_1fr_2fr]">
              <Field label={`${bloco.titulo} — mm/s`}>
                <Input
                  type="number"
                  step="0.01"
                  inputMode="decimal"
                  value={novo[bloco.mms as keyof typeof novo] as string}
                  onChange={(e) => setNovo({ ...novo, [bloco.mms]: e.target.value })}
                />
              </Field>
              <Field label="Fase (°)">
                <Input
                  type="number"
                  step="0.1"
                  inputMode="decimal"
                  value={novo[bloco.fase as keyof typeof novo] as string}
                  onChange={(e) => setNovo({ ...novo, [bloco.fase]: e.target.value })}
                />
              </Field>
              {!bloco.obrigatorio && (
                <p className="self-end pb-2 text-xs text-fg-subtle">
                  Pode ficar em branco e ser lançado depois.
                </p>
              )}
            </div>
          ))}

          {previa && (
            <p className="rounded-lg bg-surface-muted px-3 py-2 text-sm">
              Redução de{" "}
              <strong className="text-[var(--viz-trim)]">{previa.reducao.toFixed(1)}%</strong> —
              residual de {previa.residual.toFixed(1)}%.
            </p>
          )}

          <div className="flex justify-end">
            <Button onClick={adicionar} loading={salvando}>
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

/* ===================== Economia energética ===================== */

const ECONOMIA_CAMPOS = [
  { chave: "tensao_v", label: "Tensão do motor (V)", passo: "0.01" },
  { chave: "corrente_antes_a", label: "Corrente antes (A)", passo: "0.01" },
  { chave: "corrente_apos_a", label: "Corrente após (A)", passo: "0.01" },
  { chave: "fator_potencia", label: "Fator de potência", passo: "0.001" },
  { chave: "horas_dia", label: "Regime diário (h)", passo: "0.1" },
  { chave: "dias_ano", label: "Dias de operação/ano", passo: "1" },
  { chave: "custo_kwh", label: "Custo da energia (R$/kWh)", passo: "0.0001" },
] as const;

function Economia({
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
  const e = servico.economia;
  const [form, setForm] = useState<Record<string, string>>(() =>
    Object.fromEntries(
      ECONOMIA_CAMPOS.map((c) => [c.chave, e ? String(e[c.chave as keyof EconomiaEnergetica] ?? "") : ""])
    )
  );
  const [salvando, setSalvando] = useState(false);

  // Nenhum campo tem valor sugerido: tudo é medido no motor, naquele dia.
  const completo = ECONOMIA_CAMPOS.every((c) => form[c.chave] !== "");

  const previaKw = useMemo(() => {
    const v = Number(form.tensao_v);
    const di = Number(form.corrente_antes_a) - Number(form.corrente_apos_a);
    const fp = Number(form.fator_potencia);
    if (!v || !fp || !form.corrente_antes_a || !form.corrente_apos_a) return null;
    return (v * di * fp * Math.sqrt(3)) / 1000;
  }, [form]);

  async function salvar() {
    setSalvando(true);
    onErro(null);
    try {
      const corpo = { servico: servico.id, ...form };
      if (e) await api(`/economias/${e.id}/`, { method: "PATCH", body: corpo });
      else await api("/economias/", { method: "POST", body: corpo });
      await onMudou();
    } catch (err) {
      onErro(err instanceof ApiError ? JSON.stringify(err.data) : "Falha ao salvar a economia.");
    } finally {
      setSalvando(false);
    }
  }

  return (
    <Card className="space-y-4">
      <div>
        <h2 className="flex items-center gap-2 text-sm font-semibold text-fg">
          <Zap className="h-4 w-4 text-fg-subtle" />
          Economia energética gerada
        </h2>
        <p className="text-xs text-fg-muted">
          Todas as grandezas são medidas no motor, neste serviço — nenhuma vem preenchida.
        </p>
      </div>

      {podeEditar && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {ECONOMIA_CAMPOS.map((c) => (
            <Field key={c.chave} label={c.label}>
              <Input
                type="number"
                step={c.passo}
                inputMode="decimal"
                value={form[c.chave]}
                onChange={(e2) => setForm({ ...form, [c.chave]: e2.target.value })}
              />
            </Field>
          ))}
        </div>
      )}

      {previaKw != null && (
        <p className="rounded-lg bg-surface-muted px-3 py-2 text-sm text-fg-muted">
          {n(form.tensao_v, 0)} V × {n(Number(form.corrente_antes_a) - Number(form.corrente_apos_a))} A
          × {n(form.fator_potencia, 2)} × √3 ={" "}
          <strong className="text-fg">{n(previaKw, 3)} kW</strong> de redução de demanda.
        </p>
      )}

      {podeEditar && (
        <div className="flex items-center justify-end gap-3">
          {!completo && (
            <span className="text-xs text-fg-subtle">Preencha os 7 campos para calcular.</span>
          )}
          <Button onClick={salvar} loading={salvando} disabled={!completo}>
            {e ? "Recalcular" : "Calcular economia"}
          </Button>
        </div>
      )}

      {e && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Redução de demanda" value={`${n(e.reducao_kw, 3)} kW`} />
            <StatCard label="Economia anual" value={`${n(e.economia_kwh_ano, 0)} kWh`} />
            <StatCard label="Economia anual" value={reais(e.economia_rs_ano)} tone="ok" />
            <StatCard
              label="Payback"
              value={e.payback_meses ? `${n(e.payback_meses, 1)} meses` : "—"}
              hint={e.retorno_ano ? `retorno de ${n(e.retorno_ano, 2)}×/ano` : undefined}
            />
          </div>
          {e.premissas?.length > 0 && (
            <div className="rounded-lg border border-border bg-surface-muted p-3">
              <p className="mb-1 text-xs font-medium text-fg">Premissas do cálculo</p>
              <ul className="list-inside list-disc space-y-0.5 text-xs text-fg-muted">
                {e.premissas.map((p) => (
                  <li key={p}>{p}</li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </Card>
  );
}
