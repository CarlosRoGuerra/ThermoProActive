"use client";

import { useMemo, useState } from "react";
import { Zap } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { PontosMedicao, QuantidadePlanos, SelecaoPontoFoco, TrialRun, TrimRun } from "@/components/balanceamento-medicoes";
import { pontosUsados } from "@/lib/balanceamento";
import type { BalanceamentoPonto, EconomiaEnergetica, ServicoCampo } from "@/lib/types";
import { Badge, Button, Card, Field, Input, StatCard } from "@/components/ui";
import { AntesDepois, MostradorPolar, type PontoGrafico } from "@/components/balanceamento-graficos";

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

/**
 * Painel de resultado/edição da manutenção corretiva (Serviços de campo): quantidade de
 * planos, pontos de medição, ponto de foco, Trial/Trim Run, resultado (StatCards),
 * gráficos e Economia energética — nessa ordem (pedido do cliente, 2026-09-10: plano
 * físico ≠ etapa de medição). Reaproveitado tanto pela página legada `/servicos/[id]`
 * quanto pela Análise final das Inspeções.
 */
export function ServicoCampoPainel({
  servico,
  podeEditar,
  onMudou,
}: {
  servico: ServicoCampo;
  podeEditar: boolean;
  onMudou: () => Promise<void>;
}) {
  const [erro, setErro] = useState<string | null>(null);
  // Só os pontos que de fato participaram do balanceamento (o foco + qualquer ponto
  // vinculado a um plano) — não um gráfico/card por mancal que existe no equipamento.
  // Os demais pontos continuam salvos (relatório técnico), só não geram gráfico.
  const usados = useMemo(() => pontosUsados(servico), [servico]);
  const pontosGrafico = useMemo(() => usados.map(paraGrafico), [usados]);
  const planoDoPonto = (ponto: BalanceamentoPonto) =>
    servico.planos.find((p) => p.id === ponto.plano) ?? null;

  return (
    <div className="space-y-5">
      {erro && <p className="text-sm text-[var(--danger)]">{erro}</p>}

      <QuantidadePlanos servico={servico} podeEditar={podeEditar} onMudou={onMudou} />
      <PontosMedicao servico={servico} podeEditar={podeEditar} onMudou={onMudou} onErro={setErro} />
      <SelecaoPontoFoco servico={servico} podeEditar={podeEditar} onMudou={onMudou} onErro={setErro} />
      <TrialRun servico={servico} podeEditar={podeEditar} onMudou={onMudou} onErro={setErro} />
      <TrimRun servico={servico} podeEditar={podeEditar} onMudou={onMudou} onErro={setErro} />

      {/* Resultado */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Rotação" value={servico.rotacao_rpm ? `${servico.rotacao_rpm} RPM` : "—"} hint={servico.rotacao_hz ? `${n(servico.rotacao_hz)} Hz` : undefined} />
        <StatCard label="Planos de correção" value={servico.numero_planos || "—"} />
        <StatCard
          label="Redução média"
          value={servico.reducao_media_pct != null ? `${n(servico.reducao_media_pct, 1)}%` : "—"}
          tone={servico.reducao_media_pct != null && Number(servico.reducao_media_pct) > 0 ? "ok" : "default"}
        />
        <StatCard label="Classe ISO" value={servico.classe_iso || "—"} hint="Base do veredito" />
      </div>

      <Card className="space-y-4">
        <div>
          <h2 className="text-sm font-semibold text-fg">Resultado do balanceamento</h2>
          <p className="text-xs text-fg-muted">Só os pontos usados — não todos os medidos.</p>
        </div>
        {usados.length === 0 ? (
          <p className="text-sm text-fg-muted">
            Defina o ponto de foco (ou vincule um ponto a um plano) para ver o resultado.
          </p>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2">
            {usados.map((ponto) => {
              const plano = planoDoPonto(ponto);
              const antes = ponto.reference_mms != null ? Number(ponto.reference_mms) : null;
              const depois = ponto.trim_mms != null ? Number(ponto.trim_mms) : null;
              const reducaoMms = antes != null && depois != null ? antes - depois : null;
              const reducaoPct = ponto.reducao_pct != null ? Number(ponto.reducao_pct) : null;
              return (
                <div key={ponto.id} className="rounded-lg border border-border p-3">
                  <div className="mb-2 flex flex-wrap items-center gap-2">
                    <span className="font-mono text-sm font-semibold text-fg">{ponto.codigo_ponto}</span>
                    {ponto.identificacao && <span className="text-xs text-fg-muted">{ponto.identificacao}</span>}
                    {ponto.id === servico.ponto_foco && <Badge tone="accent">foco</Badge>}
                  </div>
                  <dl className="grid grid-cols-2 gap-x-3 gap-y-1.5 text-sm">
                    <dt className="text-fg-subtle">Vibração antes</dt>
                    <dd className="text-right tabular-nums text-fg">{antes != null ? `${n(antes)} mm/s` : "—"}</dd>
                    <dt className="text-fg-subtle">Vibração depois</dt>
                    <dd className="text-right tabular-nums text-fg">{depois != null ? `${n(depois)} mm/s` : "ainda não medido"}</dd>
                    <dt className="text-fg-subtle">Redução</dt>
                    <dd className="text-right tabular-nums text-fg">{reducaoMms != null ? `${n(reducaoMms)} mm/s` : "—"}</dd>
                    <dt className="text-fg-subtle">Redução percentual</dt>
                    <dd className="text-right tabular-nums font-medium text-fg">
                      {reducaoPct != null ? `${n(reducaoPct, 1)}%` : "—"}
                    </dd>
                    <dt className="text-fg-subtle">Plano utilizado</dt>
                    <dd className="text-right text-fg">{plano ? `Plano ${plano.numero}` : "—"}</dd>
                    <dt className="text-fg-subtle">Massa de correção</dt>
                    <dd className="text-right tabular-nums text-fg">
                      {plano?.massa_final_g != null ? `${n(plano.massa_final_g, 1)} g` : "—"}
                    </dd>
                    <dt className="text-fg-subtle">Ângulo de correção</dt>
                    <dd className="text-right tabular-nums text-fg">
                      {plano?.angulo_final != null ? `${n(plano.angulo_final, 0)}°` : "—"}
                    </dd>
                  </dl>
                </div>
              );
            })}
          </div>
        )}
      </Card>

      {/* Gráfico — um mostrador por ponto usado (nunca um por mancal do equipamento) */}
      {pontosGrafico.some((p) => p.reference) && (
        <div className="grid gap-5 lg:grid-cols-2">
          <Card>
            <h2 className="mb-4 text-sm font-semibold text-fg">Mostrador de fase</h2>
            <div className="flex flex-wrap gap-6">
              {usados.map((ponto, i) => {
                const plano = planoDoPonto(ponto);
                return (
                  <div key={ponto.id}>
                    <p className="mb-1 text-xs font-medium text-fg-muted">
                      {plano ? `Plano ${plano.numero} — ` : ""}
                      {ponto.codigo_ponto}
                      {ponto.identificacao ? ` — ${ponto.identificacao}` : ""}
                    </p>
                    <MostradorPolar ponto={pontosGrafico[i]} tamanho={260} />
                  </div>
                );
              })}
            </div>
          </Card>
          <Card>
            <h2 className="mb-4 text-sm font-semibold text-fg">Antes × Depois</h2>
            <AntesDepois pontos={pontosGrafico} />
          </Card>
        </div>
      )}

      <Economia servico={servico} podeEditar={podeEditar} onMudou={onMudou} onErro={setErro} />
    </div>
  );
}

/* ===================== Economia energética ===================== */

// Digitados pelo técnico a cada serviço — nada tem valor sugerido (decisão do
// Fabrício, 08/09/2026). Tensão e fator de potência SAEM desta lista: vêm do cadastro
// do equipamento quando existem (ver tensaoAuto/fpAuto abaixo).
const ECONOMIA_CAMPOS = [
  { chave: "corrente_antes_a", label: "Corrente antes do balanceamento (A)", passo: "0.01" },
  { chave: "corrente_apos_a", label: "Corrente depois do balanceamento (A)", passo: "0.01" },
  { chave: "horas_dia", label: "Regime diário (h)", passo: "0.1" },
  { chave: "dias_ano", label: "Dias de operação/ano", passo: "1" },
  { chave: "custo_kwh", label: "Custo da energia (R$/kWh)", passo: "0.0001" },
  { chave: "investimento", label: "Investimento realizado (R$)", passo: "0.01" },
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
  const tensaoAuto = servico.equipamento_tensao_nominal;
  const fpAuto = servico.equipamento_fator_potencia_nominal;
  const [form, setForm] = useState<Record<string, string>>(() =>
    Object.fromEntries(
      ECONOMIA_CAMPOS.map((c) => [c.chave, e ? String(e[c.chave as keyof EconomiaEnergetica] ?? "") : ""])
    )
  );
  // Tensão/FP: do cadastro do equipamento quando existem (usuário não redigita); só
  // viram campo manual quando o cadastro não tem o dado — nunca um valor assumido.
  const [tensaoManual, setTensaoManual] = useState(() => e?.tensao_v ?? "");
  const [fpManual, setFpManual] = useState(() => e?.fator_potencia ?? "");
  const tensaoEfetiva = tensaoAuto ?? tensaoManual;
  const fpEfetiva = fpAuto ?? fpManual;
  const [salvando, setSalvando] = useState(false);

  const completo =
    ECONOMIA_CAMPOS.every((c) => form[c.chave] !== "") && tensaoEfetiva !== "" && fpEfetiva !== "";

  const previaKw = useMemo(() => {
    const v = Number(tensaoEfetiva);
    const di = Number(form.corrente_antes_a) - Number(form.corrente_apos_a);
    const fp = Number(fpEfetiva);
    if (!v || !fp || !form.corrente_antes_a || !form.corrente_apos_a) return null;
    return (v * di * fp * Math.sqrt(3)) / 1000;
  }, [tensaoEfetiva, fpEfetiva, form.corrente_antes_a, form.corrente_apos_a]);

  async function salvar() {
    setSalvando(true);
    onErro(null);
    try {
      const corpo = { servico: servico.id, ...form, tensao_v: tensaoEfetiva, fator_potencia: fpEfetiva };
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
          Corrente, regime, dias, tarifa e investimento são medidos/informados a cada
          serviço — nenhum tem valor sugerido.
        </p>
      </div>

      {podeEditar && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Field label="Tensão do motor (V)">
            {tensaoAuto != null ? (
              <Input value={`${n(tensaoAuto, 0)} (do cadastro do equipamento)`} disabled readOnly />
            ) : (
              <Input
                type="number"
                step="0.01"
                inputMode="decimal"
                value={tensaoManual}
                onChange={(ev) => setTensaoManual(ev.target.value)}
                placeholder="Cadastro sem tensão nominal"
              />
            )}
          </Field>
          <Field label="Fator de potência">
            {fpAuto != null ? (
              <Input value={`${n(fpAuto, 3)} (do cadastro do equipamento)`} disabled readOnly />
            ) : (
              <Input
                type="number"
                step="0.001"
                inputMode="decimal"
                value={fpManual}
                onChange={(ev) => setFpManual(ev.target.value)}
                placeholder="Cadastro sem FP nominal"
              />
            )}
          </Field>
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

      {podeEditar && tensaoAuto == null && (
        <p className="text-xs text-[var(--warning-fg)]">
          Faltam dados cadastrais: o equipamento {servico.equipamento_tag} não tem
          tensão nominal cadastrada — cadastre em Equipamentos para preencher
          automaticamente da próxima vez.
        </p>
      )}
      {podeEditar && fpAuto == null && (
        <p className="text-xs text-[var(--warning-fg)]">
          Faltam dados cadastrais: o equipamento {servico.equipamento_tag} não tem fator
          de potência nominal cadastrado — cadastre em Equipamentos para preencher
          automaticamente da próxima vez.
        </p>
      )}

      {previaKw != null && (
        <p className="rounded-lg bg-surface-muted px-3 py-2 text-sm text-fg-muted">
          {n(tensaoEfetiva, 0)} V × {n(Number(form.corrente_antes_a) - Number(form.corrente_apos_a))} A
          × {n(fpEfetiva, 3)} × √3 ={" "}
          <strong className="text-fg">{n(previaKw, 3)} kW</strong> de redução de demanda (prévia).
        </p>
      )}

      {podeEditar && (
        <div className="flex items-center justify-end gap-3">
          {!completo && (
            <span className="text-xs text-fg-subtle">
              Preencha todos os campos (inclusive tensão/FP, se o cadastro não tiver) para calcular.
            </span>
          )}
          <Button onClick={salvar} loading={salvando} disabled={!completo}>
            {e ? "Recalcular" : "Calcular economia"}
          </Button>
        </div>
      )}

      {e && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Redução de corrente" value={`${n(e.reducao_corrente_a)} A`} />
            <StatCard label="Redução de potência (demanda)" value={`${n(e.reducao_kw, 3)} kW`} />
            <StatCard label="Economia de energia (anual)" value={`${n(e.economia_kwh_ano, 0)} kWh/ano`} />
            <StatCard label="Economia financeira (anual)" value={`${reais(e.economia_rs_ano)}/ano`} tone="ok" />
            <StatCard
              label="Payback"
              value={e.payback_meses != null ? `${n(e.payback_meses, 1)} meses` : "—"}
              hint={
                e.payback_meses != null
                  ? `investimento ÷ economia anual, convertido para meses — retorno de ${n(e.retorno_ano, 2)}×/ano`
                  : "sem investimento ou sem economia, não há payback"
              }
            />
          </div>

          <EconomiaTransparencia e={e} />

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

/**
 * "Não esconder as fórmulas" — mostra, passo a passo, como cada número foi calculado,
 * com os valores REAIS já salvos (não um cálculo paralelo no front: zero risco de a
 * fórmula mostrada divergir do resultado exibido). Período e unidade explícitos em
 * cada linha, como pedido.
 */
function EconomiaTransparencia({ e }: { e: EconomiaEnergetica }) {
  const passos = [
    {
      titulo: "1. Redução de corrente",
      formula: "corrente antes − corrente depois",
      conta: `${n(e.corrente_antes_a)} A − ${n(e.corrente_apos_a)} A = ${n(e.reducao_corrente_a)} A`,
    },
    {
      titulo: "2. Redução de potência (demanda)",
      formula: "tensão × redução de corrente × fator de potência × √3 ÷ 1000",
      conta: `${n(e.tensao_v, 0)} V × ${n(e.reducao_corrente_a)} A × ${n(e.fator_potencia, 3)} × √3 ÷ 1000 = ${n(e.reducao_kw, 3)} kW`,
    },
    {
      titulo: "3. Economia de energia — por ano",
      formula: "redução de potência × regime diário × dias de operação por ano",
      conta: `${n(e.reducao_kw, 3)} kW × ${n(e.horas_dia, 1)} h/dia × ${e.dias_ano} dias/ano = ${n(e.economia_kwh_ano, 0)} kWh/ano`,
    },
    {
      titulo: "4. Economia financeira — por ano",
      formula: "economia de energia (kWh/ano) × custo da energia (R$/kWh)",
      conta: `${n(e.economia_kwh_ano, 0)} kWh/ano × R$ ${n(e.custo_kwh, 4)}/kWh = ${reais(e.economia_rs_ano)}/ano`,
    },
    {
      titulo: "5. Payback — em meses",
      formula: "(investimento ÷ economia financeira ANUAL) × 12 meses",
      conta:
        e.payback_meses != null && e.investimento != null
          ? `${reais(e.investimento)} ÷ ${reais(e.economia_rs_ano)}/ano = ${n(
              Number(e.investimento) / Number(e.economia_rs_ano),
              3
            )} ano × 12 meses = ${n(e.payback_meses, 1)} meses`
          : "Sem investimento informado, ou sem economia financeira no período — não há payback a calcular (não é assumido como zero).",
    },
  ];

  return (
    <details className="rounded-lg border border-border p-3">
      <summary className="cursor-pointer text-sm font-medium text-fg">
        Como chegamos a esses números
      </summary>
      <ol className="mt-3 space-y-3">
        {passos.map((p) => (
          <li key={p.titulo}>
            <p className="text-xs font-semibold text-fg">{p.titulo}</p>
            <p className="text-xs text-fg-subtle">{p.formula}</p>
            <p className="mt-0.5 font-mono text-xs text-fg">{p.conta}</p>
          </li>
        ))}
      </ol>
    </details>
  );
}
