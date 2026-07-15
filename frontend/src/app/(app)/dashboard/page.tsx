"use client";

import { useEffect, useState } from "react";
import {
  Activity,
  AlertTriangle,
  ClipboardList,
  Clock,
  DollarSign,
  Gauge,
  ShieldAlert,
  Timer,
  TrendingUp,
  Wrench,
} from "lucide-react";
import { api } from "@/lib/api";
import type { Dashboard, DashboardExecutivo } from "@/lib/types";
import {
  Card,
  CardsSkeleton,
  EmptyState,
  PageHeader,
  StatCard,
  Table,
  TBody,
  TD,
  TH,
  THead,
  TR,
  cn,
} from "@/components/ui";
import { Stagger, StaggerItem } from "@/components/motion";

const BRL = (v: number) =>
  v.toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });

export default function DashboardPage() {
  const [aba, setAba] = useState<"operacional" | "executivo">("operacional");

  return (
    <div className="space-y-6">
      <PageHeader
        icon={Gauge}
        title="Dashboard"
        description="Indicadores de manutenção preditiva (Anexo I 2.8)."
      />

      <div className="inline-flex rounded-lg border border-border bg-surface p-0.5 shadow-xs">
        {(["operacional", "executivo"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setAba(t)}
            className={cn(
              "rounded-md px-4 py-1.5 text-sm font-medium capitalize transition-colors duration-150",
              aba === t ? "bg-accent text-accent-fg shadow-xs" : "text-fg-muted hover:text-fg"
            )}
          >
            {t}
          </button>
        ))}
      </div>

      {aba === "operacional" ? <Operacional /> : <Executivo />}
    </div>
  );
}

function Operacional() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api<Dashboard>("/dashboard/").then(setData).finally(() => setLoading(false));
  }, []);

  if (loading || !data) {
    return (
      <>
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
          {Array.from({ length: 5 }).map((_, i) => (
            <Card key={i}>
              <div className="skeleton h-3 w-16" />
              <div className="skeleton mt-3 h-7 w-12" />
            </Card>
          ))}
        </div>
        <CardsSkeleton count={2} />
      </>
    );
  }

  const c = data.medicoes_por_criticidade;
  return (
    <>
      <Stagger className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        {[
          { label: "Inspeções", value: data.total_inspecoes, icon: ClipboardList },
          { label: "Medições", value: data.total_medicoes, icon: Activity },
          { label: "Críticas", value: c.CRITICO, icon: ShieldAlert, tone: "crit" as const },
          { label: "OSPs abertas", value: data.osps_abertas, icon: Wrench, tone: "warn" as const },
          { label: "OSPs (total)", value: data.osps_total, icon: Wrench },
        ].map((s) => (
          <StaggerItem key={s.label}>
            <StatCard label={s.label} value={s.value} icon={s.icon} tone={s.tone ?? "default"} />
          </StaggerItem>
        ))}
      </Stagger>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <h2 className="mb-4 text-sm font-semibold text-fg">Medições por criticidade</h2>
          <div className="space-y-3.5">
            {(
              [
                ["Normal", c.NORMAL, "bg-success"],
                ["Alerta", c.ALERTA, "bg-warning"],
                ["Crítico", c.CRITICO, "bg-danger"],
              ] as const
            ).map(([label, value, color]) => {
              const pct = data.total_medicoes > 0 ? Math.round((value / data.total_medicoes) * 100) : 0;
              return (
                <div key={label}>
                  <div className="mb-1.5 flex justify-between text-sm">
                    <span className="text-fg-muted">{label}</span>
                    <span className="font-medium text-fg">
                      {value} <span className="text-fg-subtle">({pct}%)</span>
                    </span>
                  </div>
                  <div className="h-2 w-full overflow-hidden rounded-full bg-surface-muted">
                    <div className={cn("h-full rounded-full transition-[width] duration-500 ease-out", color)} style={{ width: `${pct}%` }} />
                  </div>
                </div>
              );
            })}
          </div>
        </Card>

        <Card>
          <h2 className="mb-4 text-sm font-semibold text-fg">Equipamentos críticos</h2>
          {data.equipamentos_criticos.length === 0 ? (
            <EmptyState icon={AlertTriangle} title="Nenhum equipamento crítico" description="Todos os equipamentos monitorados estão dentro dos limites aceitáveis." />
          ) : (
            <ul className="divide-y divide-border">
              {data.equipamentos_criticos.map((e) => (
                <li key={e.equipamento__tag} className="flex items-center justify-between py-2.5">
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-fg">{e.equipamento__tag}</p>
                    <p className="truncate text-xs text-fg-muted">{e.equipamento__nome}</p>
                  </div>
                  <span className="shrink-0 rounded-full bg-danger-subtle px-2 py-0.5 text-xs font-medium text-danger-fg ring-1 ring-inset ring-danger/20">
                    {e.ocorrencias} ocorrência(s)
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </>
  );
}

function Executivo() {
  const [data, setData] = useState<DashboardExecutivo | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api<DashboardExecutivo>("/dashboard/executivo/").then(setData).finally(() => setLoading(false));
  }, []);

  if (loading || !data) {
    return (
      <>
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
          {Array.from({ length: 5 }).map((_, i) => (
            <Card key={i}>
              <div className="skeleton h-3 w-16" />
              <div className="skeleton mt-3 h-7 w-12" />
            </Card>
          ))}
        </div>
        <CardsSkeleton count={2} />
      </>
    );
  }

  const k = data.kpis;
  const maxEvo = Math.max(1, ...data.evolucao.map((m) => Math.max(m.criticas, m.osps)));

  return (
    <>
      <Stagger className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        {[
          { label: "Taxa de conclusão", value: `${k.taxa_conclusao}%`, icon: TrendingUp },
          { label: "MTTR", value: k.mttr_horas != null ? `${k.mttr_horas} h` : "—", icon: Timer, hint: "Tempo médio de reparo" },
          { label: "MTBF", value: k.mtbf_dias != null ? `${k.mtbf_dias} d` : "—", icon: Clock, hint: "Entre falhas" },
          { label: "OSPs finalizadas", value: `${k.osps_finalizadas}/${k.osps_total}`, icon: Wrench },
          { label: "Custo real", value: BRL(data.custos.real), icon: DollarSign, tone: "warn" as const },
        ].map((s) => (
          <StaggerItem key={s.label}>
            <StatCard label={s.label} value={s.value} icon={s.icon} tone={s.tone ?? "default"} hint={s.hint} />
          </StaggerItem>
        ))}
      </Stagger>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Evolução histórica */}
        <Card>
          <h2 className="mb-1 text-sm font-semibold text-fg">Evolução histórica (6 meses)</h2>
          <p className="mb-4 flex gap-4 text-xs text-fg-muted">
            <span className="inline-flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-danger" /> Críticas</span>
            <span className="inline-flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-accent" /> OSPs</span>
          </p>
          <div className="flex h-40 items-end justify-between gap-2">
            {data.evolucao.map((m) => (
              <div key={m.mes} className="flex flex-1 flex-col items-center gap-1.5">
                <div className="flex h-32 w-full items-end justify-center gap-1">
                  <div
                    className="w-1/2 rounded-t bg-danger/80 transition-all duration-500 ease-out"
                    style={{ height: `${(m.criticas / maxEvo) * 100}%` }}
                    title={`${m.criticas} críticas`}
                  />
                  <div
                    className="w-1/2 rounded-t bg-accent/80 transition-all duration-500 ease-out"
                    style={{ height: `${(m.osps / maxEvo) * 100}%` }}
                    title={`${m.osps} OSPs`}
                  />
                </div>
                <span className="text-[10px] text-fg-subtle">{m.mes.slice(0, 5)}</span>
              </div>
            ))}
          </div>
        </Card>

        {/* Custos */}
        <Card>
          <h2 className="mb-4 text-sm font-semibold text-fg">Custos de manutenção</h2>
          <div className="space-y-4">
            {(
              [
                ["Custo estimado", data.custos.estimado, "bg-fg-subtle"],
                ["Custo real", data.custos.real, "bg-accent"],
              ] as const
            ).map(([label, value, color]) => {
              const max = Math.max(data.custos.estimado, data.custos.real, 1);
              return (
                <div key={label}>
                  <div className="mb-1.5 flex justify-between text-sm">
                    <span className="text-fg-muted">{label}</span>
                    <span className="font-semibold text-fg">{BRL(value)}</span>
                  </div>
                  <div className="h-2.5 w-full overflow-hidden rounded-full bg-surface-muted">
                    <div className={cn("h-full rounded-full transition-[width] duration-500 ease-out", color)} style={{ width: `${(value / max) * 100}%` }} />
                  </div>
                </div>
              );
            })}
            <p className="pt-1 text-xs text-fg-subtle">
              Economia vs. estimado:{" "}
              <span className="font-medium text-success-fg">
                {BRL(Math.max(0, data.custos.estimado - data.custos.real))}
              </span>
            </p>
          </div>
        </Card>
      </div>

      {/* Performance por unidade */}
      <div>
        <h2 className="mb-3 text-sm font-semibold text-fg">Performance por unidade</h2>
        {data.performance.length === 0 ? (
          <Card><EmptyState icon={Activity} title="Sem dados" description="Nenhuma unidade com atividade registrada." /></Card>
        ) : (
          <Table>
            <THead><TH>Cliente</TH><TH>OSPs</TH><TH>Finalizadas</TH><TH>Críticas</TH><TH>Custo real</TH></THead>
            <TBody>
              {data.performance.map((p) => (
                <TR key={p.cliente}>
                  <TD className="font-medium text-fg">{p.cliente}</TD>
                  <TD>{p.osps}</TD>
                  <TD>{p.finalizadas}</TD>
                  <TD>{p.criticas}</TD>
                  <TD>{BRL(p.custo_real)}</TD>
                </TR>
              ))}
            </TBody>
          </Table>
        )}
      </div>
    </>
  );
}
