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
  Download,
  Repeat,
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
  Field,
  Input,
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
  useToast,
} from "@/components/ds";
import { downloadFile, qs } from "@/lib/api";
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
type Periodo = { data_inicio: string; data_fim: string };

export default function DashboardPage() {
  const [aba, setAba] = useState<Aba>("operacional");
  const { clienteAtivo } = useClienteAtivo();
  // Período e cliente vão ao SERVIDOR; a exportação usa os mesmos parâmetros,
  // então o arquivo traz exatamente os números da tela.
  const [periodo, setPeriodo] = useState<Periodo>({ data_inicio: "", data_fim: "" });
  const [baixando, setBaixando] = useState<string | null>(null);
  const toast = useToast();
  const parametros = { cliente: clienteAtivo?.id, ...periodo };

  async function exportar(formato: "xlsx" | "pdf" | "csv") {
    setBaixando(formato);
    try {
      const chave = aba === "operacional" ? "painel-operacional" : "painel-executivo";
      await downloadFile(`/relatorios/${chave}/${qs({ ...parametros, formato })}`, `${chave}.${formato}`);
    } catch (e) {
      toast.erro("Não foi possível exportar", { descricao: e instanceof Error ? e.message : undefined });
    } finally {
      setBaixando(null);
    }
  }

  return (
    <PageBody>
      <PageHeader
        icon={Gauge}
        title="Visão geral"
        description={
          clienteAtivo
            ? `O estado da operação de ${clienteAtivo.nome_fantasia || clienteAtivo.nome} agora: o que está fora do limite, o que está em execução e como o mês vem se comportando. Desative o cliente na barra lateral para ver todas as unidades.`
            : "O estado da operação agora, somando todos os clientes: o que está fora do limite, o que está em execução e como o mês vem se comportando. Ative um cliente na barra lateral para entrar no ambiente dele."
        }
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

      <Card>
        <div className="flex flex-wrap items-end gap-3">
          <Field label="De" htmlFor="painel-de">
            <Input id="painel-de" type="date" value={periodo.data_inicio}
              onChange={(e) => setPeriodo((p) => ({ ...p, data_inicio: e.target.value }))} />
          </Field>
          <Field label="Até" htmlFor="painel-ate">
            <Input id="painel-ate" type="date" value={periodo.data_fim}
              onChange={(e) => setPeriodo((p) => ({ ...p, data_fim: e.target.value }))} />
          </Field>
          {(periodo.data_inicio || periodo.data_fim) && (
            <Button variant="ghost" size="sm" onClick={() => setPeriodo({ data_inicio: "", data_fim: "" })}>
              Todo o histórico
            </Button>
          )}
          <div className="ml-auto flex flex-wrap gap-2">
            {(["xlsx", "pdf", "csv"] as const).map((f) => (
              <Button key={f} variant="secondary" size="sm" icon={Download} loading={baixando === f}
                onClick={() => void exportar(f)}>
                {f === "xlsx" ? "Excel" : f.toUpperCase()}
              </Button>
            ))}
          </div>
        </div>
        <p className="mt-2 text-xs text-fg-muted">
          O período vale para volumes (inspeções, medições, ordens, custos, MTTR/MTBF). Ordens em aberto e
          SLA vencido são sempre a situação de hoje.
        </p>
      </Card>

      {aba === "operacional" ? <Operacional periodo={periodo} /> : <Executivo periodo={periodo} />}
    </PageBody>
  );
}

/* ============================ Operacional ============================ */

function Operacional({ periodo }: { periodo: Periodo }) {
  // Com um cliente ativado na barra lateral, o painel entra no ambiente dele;
  // sem nenhum, mostra a operação inteira. O recorte é feito no servidor — ver
  // `recorte_cliente` em apps/coletas/views.py.
  const { clienteAtivo } = useClienteAtivo();
  const { dados, falha, carregando, recarregar } = useRecurso<Dashboard>(
    `/dashboard/${qs({ cliente: clienteAtivo?.id, ...periodo })}`,
    "painel operacional"
  );

  if (carregando) return <LoadingState variante="indicadores" colunas={4} label="Carregando indicadores…" />;
  if (falha) return <ErrorCard falha={falha} onRetry={recarregar} />;
  if (!dados) return null;

  const c = dados.medicoes_por_criticidade;
  const total = dados.total_medicoes;
  const pendentes = dados.medicoes_pendentes ?? c.PENDENTE ?? 0;
  const foraDoLimite = (c.ALERTA ?? 0) + (c.CRITICO ?? 0);
  const conformidade = total > 0 ? ((c.NORMAL ?? 0) / total) * 100 : null;
  const criticos = dados.equipamentos_criticos;
  const sla = dados.sla_atendimento;
  const disp = dados.disponibilidade;
  const recorrentes = dados.falhas_recorrentes;

  return (
    <>
      {pendentes > 0 && <Alert tone="warning" title="Classificações pendentes">
        {inteiro(pendentes)} medições aguardam avaliação ou critério técnico aplicável. Valide o critério antes de concluir a condição dos equipamentos.
      </Alert>}
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
          Medição crítica abre ordem de serviço automaticamente; confira na lista se a ordem de cada um
          segue aberta. O risco cresce enquanto o equipamento seguir operando nessa condição.
        </Alert>
      )}

      <MetricGrid colunas={4}>
        <MetricCard
          label="Medições críticas"
          value={inteiro(c.CRITICO ?? 0)}
          tone={(c.CRITICO ?? 0) > 0 ? "danger" : "success"}
          icon={OctagonAlert}
          contexto={total > 0 ? `de ${inteiro(total)} medições registradas` : "nenhuma medição ainda"}
          dica="Medição classificada como crítica pelo critério registrado ou pela avaliação técnica. Gera ordem de serviço automaticamente."
        />
        <MetricCard
          label="Equipamentos a intervir"
          value={inteiro(criticos.length)}
          tone={criticos.length > 0 ? "danger" : "success"}
          icon={Activity}
          contexto={
            criticos.length > 0 ? "com pelo menos uma medição crítica" : "sem ocorrência crítica identificada"
          }
        />
        <MetricCard
          label="Conformidade das medições"
          value={conformidade === null ? "—" : percentual(conformidade)}
          tone={conformidade === null ? "neutral" : pendentes > 0 ? "warning" : conformidade >= 95 ? "success" : conformidade >= 80 ? "warning" : "danger"}
          icon={Gauge}
          contexto={`${inteiro(foraDoLimite)} em alerta/críticas · ${inteiro(pendentes)} pendentes`}
          dica="Percentual de medições classificadas como Normal sobre o total registrado."
        />
        <MetricCard
          label="Ordens em aberto"
          value={inteiro(dados.osps_abertas)}
          tone={dados.osps_abertas > 0 ? "warning" : "neutral"}
          icon={Wrench}
          contexto={`${inteiro(dados.osps_sla_vencido)} com SLA vencido · ${inteiro(dados.osps_total)} no período`}
          href="/osps"
          hrefLabel="Acompanhar"
        />
      </MetricGrid>

      <MetricGrid colunas={4}>
        <MetricCard
          label="SLA de atendimento"
          value={percentual(sla.percentual, 0)}
          tone={sla.percentual === null ? "neutral" : sla.percentual >= 90 ? "success" : sla.percentual >= 70 ? "warning" : "danger"}
          icon={Clock}
          contexto={
            sla.finalizadas_com_prazo > 0
              ? `${inteiro(sla.no_prazo)} de ${inteiro(sla.finalizadas_com_prazo)} finalizadas no prazo`
              : "nenhuma ordem finalizada no período"
          }
          dica="Ordens não canceladas, abertas no período e finalizadas até a data do SLA, sobre as finalizadas que tinham prazo."
        />
        <MetricCard
          label="Disponibilidade (indicativa)"
          value={percentual(disp.percentual)}
          tone={disp.percentual === null ? "neutral" : disp.percentual >= 95 ? "success" : disp.percentual >= 80 ? "warning" : "danger"}
          icon={Gauge}
          contexto={`${inteiro(disp.equipamentos_com_critica)} de ${inteiro(disp.equipamentos_ativos)} equipamentos ativos com medição crítica`}
          dica="Indicador provisório: equipamentos ativos sem medição crítica no período, sobre o total de ativos. Não mede horas de parada — a definição de disponibilidade ainda depende do cliente."
        />
        <MetricCard
          label="Falhas recorrentes"
          value={inteiro(recorrentes.total_equipamentos)}
          tone={recorrentes.total_equipamentos > 0 ? "warning" : "neutral"}
          icon={Repeat}
          contexto={`equipamentos com 2+ ordens · ${inteiro(recorrentes.osps_reincidentes)} reincidentes`}
          dica="Indicador provisório: equipamentos com duas ou mais ordens não canceladas no período. Reincidente = marcado assim na reavaliação."
        />
        <MetricCard
          label="Inspeções no período"
          value={inteiro(dados.total_inspecoes)}
          icon={ClipboardList}
          contexto={`${inteiro(dados.inspecoes_abertas)} em aberto hoje`}
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
                description={pendentes > 0 ? "Há medições aguardando avaliação técnica; a condição do parque ainda não está concluída." : "Consulte as medições e seus critérios para avaliar a condição de cada equipamento."}
              />
            ) : (
              <ul className="divide-y divide-border">
                {criticos.map((e) => (
                  <li
                    key={e.equipamento_id}
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
                description={`${inteiro(total)} medições registradas, incluindo ${inteiro(pendentes)} pendentes.`}
                dica="Classificações seguem o critério registrado ou a avaliação técnica. Sem critério aplicável, a leitura fica pendente."
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
                      { label: "Pendente", valor: pendentes, tom: "neutral" },
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
                  ["Inspeções no período", inteiro(dados.total_inspecoes)],
                  ["Inspeções em aberto (hoje)", inteiro(dados.inspecoes_abertas)],
                  ["Medições no período", inteiro(dados.total_medicoes)],
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

function Executivo({ periodo }: { periodo: Periodo }) {
  const { clienteAtivo } = useClienteAtivo();
  const { dados, falha, carregando, recarregar } = useRecurso<DashboardExecutivo>(
    `/dashboard/executivo/${qs({ cliente: clienteAtivo?.id, ...periodo })}`,
    "painel executivo"
  );

  if (carregando) return <LoadingState variante="indicadores" colunas={4} label="Carregando indicadores…" />;
  if (falha) return <ErrorCard falha={falha} onRetry={recarregar} />;
  if (!dados) return null;

  const k = dados.kpis;
  const custos = dados.custos;
  const semCusto = custos.real === null && custos.estimado === null;
  const maxEvolucao = Math.max(1, ...dados.evolucao.map((m) => Math.max(m.criticas, m.osps)));

  return (
    <>
      <MetricGrid colunas={4}>
        <MetricCard
          label="Ordens concluídas"
          value={percentual(k.taxa_conclusao, 0)}
          tone={k.taxa_conclusao === null ? "neutral" : k.taxa_conclusao >= 80 ? "success" : k.taxa_conclusao >= 50 ? "warning" : "danger"}
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
          contexto="intervalo médio entre ordens do mesmo equipamento"
          dica="MTBF (indicativo): média dos dias entre ordens consecutivas, não canceladas, do mesmo equipamento no período. Equipamento com uma só ordem não entra na conta."
        />
        <MetricCard
          label="Retorno da preditiva"
          value={moeda(custos.retorno_investimento, true)}
          tone={custos.retorno_investimento === null ? "neutral" : custos.retorno_investimento > 0 ? "success" : "warning"}
          icon={ScrollText}
          contexto={
            custos.osps_com_avaliacao > 0
              ? `em ${plural(custos.osps_com_avaliacao, "ordem", "ordens")} com Avaliação de Resultados`
              : "nenhuma Avaliação de Resultados lançada"
          }
          dica="Soma de (custo emergencial − custo da manutenção orientada pela preditiva), conforme a Avaliação de Resultados de cada ordem."
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
              description="Somente o que foi informado nas ordens; ordem sem valor fica fora da soma (não vale zero)."
            />
            {semCusto ? (
              <EmptyState compacto icon={ScrollText} title="Nenhum custo informado no período"
                description="Os valores aparecem quando as ordens recebem custo estimado ou real." />
            ) : (
              <BarMeter
                formatarValor={(v) => moeda(v, true)}
                total={Math.max(custos.estimado ?? 0, custos.real ?? 0, 1)}
                itens={[
                  { label: "Estimado", valor: custos.estimado ?? 0, tom: "neutral" },
                  { label: "Realizado", valor: custos.real ?? 0, tom: "primary" },
                ]}
              />
            )}
            <p className="mt-4 text-xs text-fg-muted">
              {inteiro(custos.osps_com_custo_real)} ordens com custo real · {inteiro(custos.osps_sem_custo_real)} sem
              valor informado.
            </p>
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
                const taxa = p.osps > 0 ? (p.finalizadas / p.osps) * 100 : null;
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
                          taxa === null ? "text-fg-muted" : taxa >= 80 ? "text-success-fg" : taxa >= 50 ? "text-warning-fg" : "text-danger-fg"
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
