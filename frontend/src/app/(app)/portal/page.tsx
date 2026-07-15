"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  ClipboardList,
  FileBarChart,
  FileText,
  Gauge,
  ShieldCheck,
  Wrench,
  type LucideIcon,
} from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { PortalHistoricoItem, PortalVisaoGeral } from "@/lib/types";
import {
  Badge,
  Card,
  CardsSkeleton,
  CriticidadeBadge,
  EmptyState,
  StatCard,
} from "@/components/ui";
import { FadeIn, Stagger, StaggerItem } from "@/components/motion";

const HIST_ICON: Record<PortalHistoricoItem["tipo"], LucideIcon> = {
  laudo: FileText,
  inspecao: ClipboardList,
  osp: Wrench,
};

const ATALHOS: { href: string; label: string; descricao: string; icon: LucideIcon }[] = [
  { href: "/laudos", label: "Laudos", descricao: "Consultar e baixar laudos", icon: FileText },
  { href: "/inspecoes", label: "Inspeções", descricao: "Acompanhar inspeções", icon: ClipboardList },
  { href: "/osps", label: "Ordens de Serviço", descricao: "Status das OSPs", icon: Wrench },
  { href: "/relatorios", label: "Relatórios", descricao: "Exportar PDF/Excel/CSV", icon: FileBarChart },
];

function dataBR(iso: string) {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString("pt-BR");
}

export default function PortalPage() {
  const { user } = useAuth();
  const [data, setData] = useState<PortalVisaoGeral | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api<PortalVisaoGeral>("/portal/visao-geral/")
      .then(setData)
      .finally(() => setLoading(false));
  }, []);

  const nomeCliente = data?.cliente?.nome ?? "sua operação";
  const primeiroNome = user?.nome?.split(" ")[0] ?? "";

  if (loading || !data) {
    return (
      <div className="space-y-6">
        <div className="skeleton h-24 w-full rounded-2xl" />
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
          {Array.from({ length: 5 }).map((_, i) => (
            <Card key={i}>
              <div className="skeleton h-3 w-16" />
              <div className="skeleton mt-3 h-7 w-12" />
            </Card>
          ))}
        </div>
        <CardsSkeleton count={2} />
      </div>
    );
  }

  const ind = data.indicadores;
  const dispTone = ind.indice_disponibilidade >= 90 ? "ok" : ind.indice_disponibilidade >= 70 ? "warn" : "crit";

  return (
    <div className="space-y-6">
      {/* Boas-vindas — Portal do Cliente (Anexo I 2.7.1) */}
      <FadeIn>
        <div className="overflow-hidden rounded-2xl border border-border bg-gradient-to-br from-accent-subtle to-surface p-6 lg:p-7">
          <div className="flex items-start gap-4">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-accent text-accent-fg shadow-sm">
              <ShieldCheck className="h-6 w-6" />
            </div>
            <div className="min-w-0">
              <p className="text-sm text-fg-muted">
                Portal do Cliente{primeiroNome && ` · Olá, ${primeiroNome}`}
              </p>
              <h1 className="mt-0.5 truncate text-xl font-semibold tracking-tight text-fg">
                {nomeCliente}
              </h1>
              <p className="mt-1 text-sm text-fg-muted">
                Acompanhe a saúde do seu parque, laudos e ordens de serviço em tempo real.
                {data.cliente?.cidade_uf ? ` — ${data.cliente.cidade_uf}` : ""}
              </p>
            </div>
          </div>
        </div>
      </FadeIn>

      {/* Indicadores de desempenho (Anexo I 2.7.1.1.7) */}
      <Stagger className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        {[
          {
            label: "Disponibilidade",
            value: `${ind.indice_disponibilidade}%`,
            icon: Gauge,
            tone: dispTone,
            hint: "Parque sem ocorrência crítica",
          },
          { label: "Equipamentos", value: ind.equipamentos_monitorados, icon: Activity },
          {
            label: "Requer atenção",
            value: ind.equipamentos_atencao,
            icon: AlertTriangle,
            tone: ind.equipamentos_atencao > 0 ? ("crit" as const) : ("ok" as const),
          },
          {
            label: "OSPs em aberto",
            value: ind.osps_abertas,
            icon: Wrench,
            tone: ind.osps_abertas > 0 ? ("warn" as const) : ("default" as const),
          },
          { label: "Laudos disponíveis", value: ind.laudos_disponiveis, icon: FileText },
        ].map((s) => (
          <StaggerItem key={s.label}>
            <StatCard
              label={s.label}
              value={s.value}
              icon={s.icon}
              tone={(s.tone as "default" | "ok" | "warn" | "crit") ?? "default"}
              hint={s.hint}
            />
          </StaggerItem>
        ))}
      </Stagger>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Requer sua atenção */}
        <Card>
          <h2 className="mb-4 text-sm font-semibold text-fg">Requer sua atenção</h2>
          {data.equipamentos_atencao.length === 0 ? (
            <EmptyState
              icon={ShieldCheck}
              title="Tudo sob controle"
              description="Nenhum equipamento do seu parque está em condição crítica no momento."
            />
          ) : (
            <ul className="divide-y divide-border">
              {data.equipamentos_atencao.map((e) => (
                <li key={e.equipamento__tag} className="flex items-center justify-between py-2.5">
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-fg">{e.equipamento__tag}</p>
                    <p className="truncate text-xs text-fg-muted">{e.equipamento__nome}</p>
                  </div>
                  <Badge tone="danger" dot>
                    {e.ocorrencias} ocorrência(s)
                  </Badge>
                </li>
              ))}
            </ul>
          )}
        </Card>

        {/* Histórico de serviços (Anexo I 2.7.1.1.5) */}
        <Card>
          <h2 className="mb-4 text-sm font-semibold text-fg">Histórico de serviços</h2>
          {data.historico.length === 0 ? (
            <EmptyState
              icon={ClipboardList}
              title="Sem registros ainda"
              description="As inspeções, laudos e ordens de serviço aparecerão aqui."
            />
          ) : (
            <ul className="space-y-1">
              {data.historico.map((h, i) => {
                const Icon = HIST_ICON[h.tipo];
                return (
                  <li key={`${h.tipo}-${i}`}>
                    <Link
                      href={h.url}
                      className="group flex items-start gap-3 rounded-lg px-2 py-2 transition-colors hover:bg-surface-muted"
                    >
                      <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-surface-muted text-fg-subtle">
                        <Icon className="h-4 w-4" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center justify-between gap-2">
                          <p className="truncate text-sm font-medium text-fg">{h.titulo}</p>
                          <span className="shrink-0 text-xs text-fg-subtle">{dataBR(h.data)}</span>
                        </div>
                        {h.descricao && (
                          <p className="truncate text-xs text-fg-muted">{h.descricao}</p>
                        )}
                        <div className="mt-1 flex items-center gap-2">
                          <Badge tone="neutral">{h.status}</Badge>
                          {h.criticidade && <CriticidadeBadge value={h.criticidade} />}
                        </div>
                      </div>
                    </Link>
                  </li>
                );
              })}
            </ul>
          )}
        </Card>
      </div>

      {/* Acesso rápido */}
      <div>
        <h2 className="mb-3 text-sm font-semibold text-fg">Acesso rápido</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {ATALHOS.map((a) => {
            const Icon = a.icon;
            return (
              <Link key={a.href} href={a.href}>
                <Card interactive className="group h-full">
                  <div className="flex items-start justify-between">
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent-subtle text-accent">
                      <Icon className="h-5 w-5" />
                    </div>
                    <ArrowRight className="h-4 w-4 text-fg-subtle transition-transform group-hover:translate-x-0.5" />
                  </div>
                  <p className="mt-3 text-sm font-semibold text-fg">{a.label}</p>
                  <p className="text-xs text-fg-muted">{a.descricao}</p>
                </Card>
              </Link>
            );
          })}
        </div>
      </div>
    </div>
  );
}
