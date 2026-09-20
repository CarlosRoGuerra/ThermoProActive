"use client";

import { useState } from "react";
import Link from "next/link";
import {
  Activity,
  ArrowRight,
  Building2,
  ChartColumn,
  ClipboardList,
  Clock,
  Gauge,
  OctagonAlert,
  ScrollText,
  Timer,
  TrendingUp,
  Wrench,
} from "lucide-react";
import {
  Alert,
  BarMeter,
  Button,
  Card,
  CardHeader,
  EmptyState,
  ErrorCard,
  EstadoBadge,
  LegendaEstados,
  LoadingState,
  MetricCard,
  MetricGrid,
  PageBody,
  PageHeader,
  SegmentedControl,
  SemDado,
  SplitLayout,
  Table,
  TBody,
  TD,
  TH,
  THead,
  TR,
  cn,
} from "@/components/ds";
import { useRecurso } from "@/lib/recurso";
import { useClienteAtivo } from "@/lib/cliente-ativo";
import { inteiro, moeda, percentual, plural } from "@/lib/format";
import type { Dashboard, DashboardExecutivo } from "@/lib/types";

/* ==========================================================================
   Visão geral da operação (equipe interna)
   --------------------------------------------------------------------------
   O problema do painel anterior: cinco caixas com "Inspeções 132 · Medições
   1.847 · Críticas 12 · OSPs abertas 9 · OSPs 41". Números sem referência não
   sustentam decisão — ninguém sabe se 12 é muito.

   Aqui cada indicador declara o denominador ("12 de 1.847 medições"), o estado
   de saúde e o caminho para a lista que o explica. A ordem é de urgência:
   primeiro o que está fora do limite, depois o volume de trabalho, por último o
   acumulado.
   ========================================================================== */

type Aba = "operacional" | "executivo";

export default function DashboardPage() {
  const [aba, setAba] = useState<Aba>("operacional");
  const { clienteAtivo } = useClienteAtivo();

  return (
    <PageBody>
      <PageHeader
        icon={Gauge}
        title="Visão geral"
        description="O estado da operação agora: o que está fora do limite, o que está em execução e como o mês vem se comportando."
        selo={
          clienteAtivo ? (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-primary-subtle px-2.5 py-0.5 text-xs font-medium text-primary-subtle-fg">
              <Building2 className="h-3.5 w-3.5" aria-hidden="true" />
              {clienteAtivo.nome_fantasia || clienteAtivo.nome}
            </span>
          ) : undefined
        }
        actions={
          <SegmentedControl
            label="Recorte do painel"
            valor={aba}
            onMudar={setAba}
            opcoes={[
              { valor: "operacional", label: "Operacional", icon: Activity },
              { valor: "executivo", label: "Executivo", icon: ChartColumn },
            ]}
          />
        }
      />

      {aba === "operacional" ? <Operacional /> : <Executivo />}
    </PageBody>
  );
}

/* ============================ Operacional ============================ */

function Operacional() {
  const { dados, falha, carregando, recarregar } = useRecurso<Dashboard>(
    "/dashboard/",
    "painel operacional"
  );

  if (carregando) return <LoadingState variante="indicadores" colunas={4} label="Carregando indicadores…" />;
  if (falha) return <ErrorCard falha={falha} onRetry={recarregar} />;
  if (!dados) return null;

  const c = dados.medicoes_por_criticidade;
  const total = dados.total_medicoes;
  const foraDoLimite = (c.ALERTA ?? 0) + (c.CRITICO ?? 0);
  const conformidade = total > 0 ? ((c.NORMAL ?? 0) / total) * 100 : 100;
  const criticos = dados.equipamentos_criticos;

  return (
    <>
      {criticos.length > 0 && (
        <Alert
          tone="danger"
          title={`${plural(criticos.length, "equipamento")} em condição crítica`}
          actions={
            <Link href="/osps">
              <Button size="sm" variant="secondary" iconRight={ArrowRight}>
                Ver ordens de serviço
              </Button>
            </Link>
          }
        >
          Cada um deles já tem ordem de serviço aberta automaticamente. O risco cresce enquanto o
          equipamento seguir operando nessa condição.
        </Alert>
      )}

      <MetricGrid colunas={4}>
        <MetricCard
          label="Medições críticas"
          value={inteiro(c.CRITICO ?? 0)}
          tone={(c.CRITICO ?? 0) > 0 ? "danger" : "success"}
          icon={OctagonAlert}
          contexto={total > 0 ? `de ${inteiro(total)} medições registradas` : "nenhuma medição ainda"}
          dica="Medição acima do limite da norma aplicável. Gera ordem de serviço automaticamente."
        />
        <MetricCard
          label="Equipamentos a intervir"
          value={inteiro(criticos.length)}
          tone={criticos.length > 0 ? "danger" : "success"}
          icon={Activity}
          contexto={
            criticos.length > 0 ? "com pelo menos uma medição crítica" : "parque dentro dos limites"
          }
        />
        <MetricCard
          label="Conformidade das medições"
          value={percentual(conformidade)}
          tone={conformidade >= 95 ? "success" : conformidade >= 80 ? "warning" : "danger"}
          icon={Gauge}
          contexto={`${inteiro(foraDoLimite)} fora do limite aceitável`}
          dica="Percentual de medições classificadas como Normal sobre o total registrado."
        />
        <MetricCard
          label="Ordens em aberto"
          value={inteiro(dados.osps_abertas)}
          tone={dados.osps_abertas > 0 ? "warning" : "neutral"}
          icon={Wrench}
          contexto={`de ${inteiro(dados.osps_total)} no histórico`}
          href="/osps"
          hrefLabel="Acompanhar"
        />
      </MetricGrid>

      <SplitLayout
        principal={
          <Card>
            <CardHeader
              title="Onde intervir primeiro"
              description="Equipamentos com medição crítica, do maior número de ocorrências para o menor."
              icon={OctagonAlert}
              actions={
                <Link href="/inspecoes/final">
                  <Button variant="ghost" size="sm" iconRight={ArrowRight}>
                    Análise final
                  </Button>
                </Link>
              }
            />
            {criticos.length === 0 ? (
              <EmptyState
                compacto
                icon={Gauge}
                title="Nenhum equipamento em condição crítica"
                description="Todas as medições registradas estão dentro dos limites das normas aplicáveis."
              />
            ) : (
              <ul className="divide-y divide-border">
                {criticos.map((e) => (
                  <li
                    key={e.equipamento__tag}
                    className="flex items-center justify-between gap-3 py-2.5"
                  >
                    <div className="min-w-0">
                      <p className="data text-sm font-semibold text-fg">{e.equipamento__tag}</p>
                      <p className="truncate text-xs text-fg-muted">{e.equipamento__nome}</p>
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      <span className="text-xs text-fg-subtle">
                        {plural(e.ocorrencias, "ocorrência", "ocorrências")}
                      </span>
                      <EstadoBadge grau="CRITICO" tamanho="sm" />
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        }
        apoio={
          <>
            <Card>
              <CardHeader
                title="Distribuição das medições"
                description={`${inteiro(total)} medições classificadas pelas regras de cada tecnologia.`}
                dica="A classificação é automática: cada tecnologia tem a sua norma e o seu limite."
              />
              {total === 0 ? (
                <EmptyState
                  compacto
                  icon={Activity}
                  title="Sem medições registradas"
                  description="Os números aparecem assim que a primeira coleta for lançada."
                />
              ) : (
                <>
                  <BarMeter
                    total={total}
                    itens={[
                      { label: "Normal", valor: c.NORMAL ?? 0, tom: "success" },
                      { label: "Alerta", valor: c.ALERTA ?? 0, tom: "warning" },
                      { label: "Crítico", valor: c.CRITICO ?? 0, tom: "danger" },
                    ]}
                  />
                  <div className="mt-4 border-t border-border pt-3">
                    <LegendaEstados graus={["NORMAL", "ALERTA", "CRITICO"]} />
                  </div>
                </>
              )}
            </Card>

            <Card>
              <CardHeader title="Volume de trabalho" icon={ClipboardList} />
              <dl className="space-y-3 text-sm">
                {[
                  ["Inspeções registradas", inteiro(dados.total_inspecoes)],
                  ["Inspeções em aberto", inteiro(dados.inspecoes_abertas)],
                  ["Medições lançadas", inteiro(dados.total_medicoes)],
                ].map(([rotulo, valor]) => (
                  <div key={rotulo} className="flex items-baseline justify-between gap-3">
                    <dt className="text-fg-muted">{rotulo}</dt>
                    <dd className="data font-semibold text-fg">{valor}</dd>
                  </div>
                ))}
              </dl>
            </Card>
          </>
        }
      />
    </>
  );
}

/* ============================ Executivo ============================ */

function Executivo() {
  const { dados, falha, carregando, recarregar } = useRecurso<DashboardExecutivo>(
    "/dashboard/executivo/",
    "painel executivo"
  );

  if (carregando) return <LoadingState variante="indicadores" colunas={4} label="Carregando indicadores…" />;
  if (falha) return <ErrorCard falha={falha} onRetry={recarregar} />;
  if (!dados) return null;

  const k = dados.kpis;
  const economia = Math.max(0, dados.custos.estimado - dados.custos.real);
  const maxEvolucao = Math.max(1, ...dados.evolucao.map((m) => Math.max(m.criticas, m.osps)));

  return (
    <>
      <MetricGrid colunas={4}>
        <MetricCard
          label="Ordens concluídas"
          value={percentual(k.taxa_conclusao, 0)}
          tone={k.taxa_conclusao >= 80 ? "success" : k.taxa_conclusao >= 50 ? "warning" : "danger"}
          icon={TrendingUp}
          contexto={`${inteiro(k.osps_finalizadas)} de ${inteiro(k.osps_total)} ordens`}
        />
        <MetricCard
          label="Tempo médio de reparo"
          value={k.mttr_horas != null ? inteiro(k.mttr_horas) : "—"}
          unidade={k.mttr_horas != null ? "h" : undefined}
          icon={Timer}
          contexto="da abertura à finalização da ordem"
          dica="MTTR — Mean Time To Repair. Quanto menor, mais rápida a resposta da manutenção."
        />
        <MetricCard
          label="Tempo entre falhas"
          value={k.mtbf_dias != null ? inteiro(k.mtbf_dias) : "—"}
          unidade={k.mtbf_dias != null ? "dias" : undefined}
          icon={Clock}
          contexto="intervalo médio entre ocorrências críticas"
          dica="MTBF — Mean Time Between Failures. Quanto maior, mais confiável o parque."
        />
        <MetricCard
          label="Economia da preditiva"
          value={moeda(economia, true)}
          tone={economia > 0 ? "success" : "neutral"}
          icon={ScrollText}
          contexto={`custo real ${moeda(dados.custos.real, true)} contra ${moeda(
            dados.custos.estimado,
            true
          )} estimados`}
          dica="Diferença entre o custo estimado das intervenções e o custo real executado."
        />
      </MetricGrid>

      <SplitLayout
        principal={
          <Card>
            <CardHeader
              title="Seis meses de operação"
              description="Medições críticas e ordens abertas por mês — a leitura é a tendência, não o valor absoluto."
            />
            <p className="mb-4 flex flex-wrap gap-4 text-xs text-fg-muted">
              <span className="inline-flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-sm bg-danger" aria-hidden="true" /> Medições
                críticas
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-sm bg-primary" aria-hidden="true" /> Ordens
                abertas
              </span>
            </p>
            {dados.evolucao.length === 0 ? (
              <EmptyState compacto icon={ChartColumn} title="Sem histórico suficiente" />
            ) : (
              <div className="flex h-44 items-end justify-between gap-2" role="img" aria-label="Evolução mensal de medições críticas e ordens abertas">
                {dados.evolucao.map((m) => (
                  <div key={m.mes} className="flex min-w-0 flex-1 flex-col items-center gap-1.5">
                    <div className="flex h-32 w-full items-end justify-center gap-1">
                      <div
                        className="w-1/2 rounded-t bg-danger/85 transition-[height] duration-slow ease-out"
                        style={{ height: `${(m.criticas / maxEvolucao) * 100}%` }}
                        title={`${m.criticas} medições críticas em ${m.mes}`}
                      />
                      <div
                        className="w-1/2 rounded-t bg-primary/85 transition-[height] duration-slow ease-out"
                        style={{ height: `${(m.osps / maxEvolucao) * 100}%` }}
                        title={`${m.osps} ordens abertas em ${m.mes}`}
                      />
                    </div>
                    <span className="truncate text-2xs text-fg-subtle">{m.mes.slice(0, 5)}</span>
                  </div>
                ))}
              </div>
            )}
          </Card>
        }
        apoio={
          <Card>
            <CardHeader
              title="Custo estimado × realizado"
              description="A diferença é o que a preditiva evitou em intervenção emergencial."
            />
            <BarMeter
              formatarValor={(v) => moeda(v, true)}
              total={Math.max(dados.custos.estimado, dados.custos.real, 1)}
              itens={[
                { label: "Estimado", valor: dados.custos.estimado, tom: "neutral" },
                { label: "Realizado", valor: dados.custos.real, tom: "primary" },
              ]}
            />
            <div className="mt-4 rounded-lg bg-success-subtle px-3 py-2.5">
              <p className="text-xs text-success-fg">
                Economia acumulada:{" "}
                <span className="data font-semibold">{moeda(economia)}</span>
              </p>
            </div>
          </Card>
        }
      />

      <section>
        <CardHeader
          title="Desempenho por cliente"
          description="Volume de ordens, conclusão e custo realizado em cada unidade atendida."
        />
        {dados.performance.length === 0 ? (
          <Card padding={false}>
            <EmptyState
              icon={Building2}
              title="Nenhum cliente com atividade registrada"
              description="Os números aparecem conforme as ordens de serviço são abertas e concluídas."
            />
          </Card>
        ) : (
          <Table legenda="Desempenho por cliente: ordens, concluídas, medições críticas e custo realizado">
            <THead>
              <TH>Cliente</TH>
              <TH className="text-right">Ordens</TH>
              <TH className="text-right">Concluídas</TH>
              <TH className="text-right">Conclusão</TH>
              <TH className="text-right">Críticas</TH>
              <TH className="text-right">Custo realizado</TH>
            </THead>
            <TBody>
              {dados.performance.map((p) => {
                const taxa = p.osps > 0 ? (p.finalizadas / p.osps) * 100 : 0;
                return (
                  <TR key={p.cliente}>
                    <TD className="font-medium text-fg">{p.cliente}</TD>
                    <TD className="text-right" tecnico>
                      {inteiro(p.osps)}
                    </TD>
                    <TD className="text-right" tecnico>
                      {inteiro(p.finalizadas)}
                    </TD>
                    <TD className="text-right" tecnico>
                      <span
                        className={cn(
                          "font-medium",
                          taxa >= 80 ? "text-success-fg" : taxa >= 50 ? "text-warning-fg" : "text-danger-fg"
                        )}
                      >
                        {percentual(taxa, 0)}
                      </span>
                    </TD>
                    <TD className="text-right" tecnico>
                      {p.criticas > 0 ? (
                        <span className="font-medium text-danger-fg">{inteiro(p.criticas)}</span>
                      ) : (
                        <SemDado>0</SemDado>
                      )}
                    </TD>
                    <TD className="text-right" tecnico>
                      {moeda(p.custo_real)}
                    </TD>
                  </TR>
                );
              })}
            </TBody>
          </Table>
        )}
      </section>
    </>
  );
}
