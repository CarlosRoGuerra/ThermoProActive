"use client";

import Link from "next/link";
import {
  Activity,
  ArrowRight,
  ClipboardCheck,
  FileChartColumn,
  Gauge,
  OctagonAlert,
  ScrollText,
  ShieldCheck,
  Wrench,
  type LucideIcon,
} from "lucide-react";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
  ErrorCard,
  EstadoBadge,
  LoadingState,
  MetricCard,
  MetricGrid,
  PageBody,
  PageHeader,
  SplitLayout,
  Timeline,
  TimelineItem,
} from "@/components/ds";
import { useRecurso } from "@/lib/recurso";
import { useAuth } from "@/lib/auth";
import { data as fmtData, plural } from "@/lib/format";
import { destinoNoPortal } from "@/lib/permissions";
import type { PortalHistoricoItem, PortalVisaoGeral } from "@/lib/types";
import { BoasVindasPortal } from "@/features/portal/onboarding";

const ICONE_HISTORICO: Record<PortalHistoricoItem["tipo"], LucideIcon> = {
  laudo: ScrollText,
  inspecao: ClipboardCheck,
  osp: Wrench,
};

const ATALHOS: { href: string; label: string; descricao: string; icon: LucideIcon }[] = [
  {
    href: "/portal/equipamentos",
    label: "Meus equipamentos",
    descricao: "Estado atual de cada máquina",
    icon: Activity,
  },
  {
    href: "/portal/inspecoes",
    label: "Inspeções",
    descricao: "O que foi medido e quando",
    icon: ClipboardCheck,
  },
  {
    href: "/portal/laudos",
    label: "Laudos técnicos",
    descricao: "Documentos assinados em PDF",
    icon: ScrollText,
  },
  {
    href: "/portal/relatorios",
    label: "Relatórios",
    descricao: "Exportar Excel, CSV ou PDF",
    icon: FileChartColumn,
  },
];

export default function PortalInicioPage() {
  const { user } = useAuth();
  const { dados, falha, carregando, recarregar } = useRecurso<PortalVisaoGeral>(
    "/portal/visao-geral/",
    "visão geral do portal"
  );

  const nomeCliente = dados?.cliente?.nome ?? "sua operação";

  return (
    <PageBody>
      <PageHeader
        title={nomeCliente}
        description={
          dados?.cliente?.cidade_uf
            ? `Acompanhamento preditivo do seu parque — ${dados.cliente.cidade_uf}.`
            : "Acompanhamento preditivo do seu parque de equipamentos."
        }
        icon={ShieldCheck}
        selo={
          dados?.cliente?.unidade_negocio ? (
            <Badge tone="neutral">{dados.cliente.unidade_negocio}</Badge>
          ) : undefined
        }
      />

      {user && <BoasVindasPortal user={user} visao={dados} />}

      {carregando ? (
        <LoadingState variante="indicadores" colunas={4} label="Carregando a visão geral…" />
      ) : falha ? (
        <ErrorCard falha={falha} onRetry={recarregar} />
      ) : dados ? (
        <Conteudo dados={dados} />
      ) : null}
    </PageBody>
  );
}

function Conteudo({ dados }: { dados: PortalVisaoGeral }) {
  const ind = dados.indicadores;
  const saudaveis = Math.max(0, ind.equipamentos_monitorados - ind.equipamentos_atencao);
  const tomDisponibilidade =
    ind.indice_disponibilidade >= 95 ? "success" : ind.indice_disponibilidade >= 80 ? "warning" : "danger";

  return (
    <>
      {/* Indicadores: cada número declara em relação a quê ele existe. */}
      <MetricGrid colunas={4}>
        <MetricCard
          label="Disponibilidade do parque"
          value={ind.indice_disponibilidade.toLocaleString("pt-BR")}
          unidade="%"
          tone={tomDisponibilidade}
          icon={Gauge}
          contexto={`${plural(saudaveis, "equipamento")} sem ocorrência crítica`}
          dica="Percentual do seu parque sem nenhuma medição crítica na última coleta. Não é disponibilidade de produção — é condição mecânica."
        />
        <MetricCard
          label="Exigem intervenção"
          value={ind.equipamentos_atencao}
          tone={ind.equipamentos_atencao > 0 ? "danger" : "success"}
          icon={OctagonAlert}
          contexto={
            ind.equipamentos_atencao > 0
              ? `de ${plural(ind.equipamentos_monitorados, "equipamento")} monitorados`
              : "Nenhuma pendência no momento"
          }
          href={ind.equipamentos_atencao > 0 ? "/portal/equipamentos?estado=critico" : undefined}
          hrefLabel="Ver quais"
        />
        <MetricCard
          label="Ordens de serviço abertas"
          value={ind.osps_abertas}
          tone={ind.osps_abertas > 0 ? "warning" : "neutral"}
          icon={Wrench}
          contexto={ind.osps_abertas > 0 ? "aguardando execução" : "Nada em aberto"}
          href="/portal/ordens-servico"
          hrefLabel="Acompanhar"
        />
        <MetricCard
          label="Laudos disponíveis"
          value={ind.laudos_disponiveis}
          icon={ScrollText}
          contexto={`${plural(ind.inspecoes, "inspeção", "inspeções")} realizadas`}
          href="/portal/laudos"
          hrefLabel="Consultar"
        />
      </MetricGrid>

      <SplitLayout
        principal={
          <Card>
            <CardHeader
              title="Requer sua atenção"
              description="Equipamentos com medição crítica na última coleta, do mais grave para o menos."
              icon={OctagonAlert}
              actions={
                dados.equipamentos_atencao.length > 0 ? (
                  <Link href="/portal/equipamentos?estado=critico">
                    <Button variant="ghost" size="sm" iconRight={ArrowRight}>
                      Ver todos
                    </Button>
                  </Link>
                ) : undefined
              }
            />
            {dados.equipamentos_atencao.length === 0 ? (
              <EmptyState
                compacto
                icon={ShieldCheck}
                title="Nenhum equipamento em condição crítica"
                description="Todo o parque monitorado está dentro dos limites das normas aplicáveis. Você será avisado aqui e por e-mail se isso mudar."
              />
            ) : (
              <ul className="divide-y divide-border">
                {dados.equipamentos_atencao.map((e) => (
                  <li key={e.equipamento__tag} className="flex items-center justify-between gap-3 py-2.5">
                    <div className="min-w-0">
                      <p className="data text-sm font-semibold text-fg">{e.equipamento__tag}</p>
                      <p className="truncate text-xs text-fg-muted">{e.equipamento__nome}</p>
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      <span className="text-xs text-fg-subtle">
                        {plural(e.ocorrencias, "ocorrência", "ocorrências")}
                      </span>
                      <EstadoBadge grau="CRITICO" tamanho="sm" mostrarSignificado />
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        }
        apoio={
          <Card>
            <CardHeader
              title="Últimos serviços"
              description="Inspeções, laudos e ordens de serviço, do mais recente."
            />
            {dados.historico.length === 0 ? (
              <EmptyState
                compacto
                icon={ClipboardCheck}
                title="Ainda sem histórico"
                description="Assim que a primeira coleta for feita no seu parque, ela aparece aqui."
                comoFunciona={[
                  "A equipe técnica executa a rota de inspeção no campo.",
                  "As medições são analisadas contra as normas (ISO, NBR).",
                  "O laudo é emitido e fica disponível para você neste portal.",
                ]}
              />
            ) : (
              <Timeline>
                {dados.historico.map((h, i) => {
                  const Icone = ICONE_HISTORICO[h.tipo];
                  const tom =
                    h.criticidade === "CRITICO"
                      ? "danger"
                      : h.criticidade === "ALERTA"
                      ? "warning"
                      : h.tipo === "laudo"
                      ? "success"
                      : "neutral";
                  return (
                    <TimelineItem
                      key={`${h.tipo}-${i}`}
                      tom={tom}
                      quando={fmtData(h.data)}
                      titulo={
                        <Link
                          href={destinoNoPortal(h.url)}
                          className="inline-flex items-center gap-1.5 rounded transition-colors hover:text-primary"
                        >
                          <Icone className="h-3.5 w-3.5 shrink-0 text-fg-subtle" aria-hidden="true" />
                          {h.titulo}
                        </Link>
                      }
                    >
                      {h.descricao && <p className="truncate">{h.descricao}</p>}
                      <p className="mt-1">
                        <Badge tone="neutral">{h.status}</Badge>
                      </p>
                    </TimelineItem>
                  );
                })}
              </Timeline>
            )}
          </Card>
        }
      />

      <section>
        <h2 className="mb-3 text-sm font-semibold text-fg">Acesso rápido</h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {ATALHOS.map((a) => {
            const Icone = a.icon;
            return (
              <Link key={a.href} href={a.href} className="group">
                <Card interactive className="h-full">
                  <div className="flex items-start justify-between">
                    <span
                      className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary-subtle text-primary"
                      aria-hidden="true"
                    >
                      <Icone className="h-[1.125rem] w-[1.125rem]" />
                    </span>
                    <ArrowRight
                      className="h-4 w-4 text-fg-subtle transition-transform duration-fast group-hover:translate-x-0.5"
                      aria-hidden="true"
                    />
                  </div>
                  <p className="mt-3 text-sm font-semibold text-fg">{a.label}</p>
                  <p className="text-xs text-fg-muted">{a.descricao}</p>
                </Card>
              </Link>
            );
          })}
        </div>
      </section>
    </>
  );
}
