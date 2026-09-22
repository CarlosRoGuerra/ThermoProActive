"use client";

import { useParams } from "next/navigation";
import { Activity, ClipboardCheck, Flame, Gauge, Waves } from "lucide-react";
import {
  Badge,
  Card,
  CardHeader,
  DescriptionList,
  EmptyState,
  ErrorCard,
  EstadoBadge,
  LegendaEstados,
  LoadingState,
  MetricCard,
  MetricGrid,
  PageBody,
  PageHeader,
  SemDado,
  Table,
  TBody,
  TD,
  TH,
  THead,
  TR,
  grauDe,
} from "@/components/ds";
import { useRecurso } from "@/lib/recurso";
import { data as fmtData, numero, numeroUnidade, texto } from "@/lib/format";
import type { Inspecao } from "@/lib/types";

/**
 * Portal do Cliente — uma inspeção, ponto a ponto.
 *
 * Somente leitura e sem jargão de processo: o cliente vê o que foi medido, com
 * que valor, contra qual limite e qual foi o resultado. As três tecnologias
 * (vibração, termografia e demais ensaios) vêm aninhadas no próprio recurso, em
 * tabelas separadas porque as grandezas são diferentes — misturar mm/s com °C na
 * mesma tabela não ajuda ninguém.
 */
export default function PortalInspecaoPage() {
  const { id } = useParams<{ id: string }>();
  const { dados: insp, falha, carregando, recarregar } = useRecurso<Inspecao>(
    `/inspecoes/${id}/`,
    "inspeção"
  );

  if (carregando) return <LoadingState variante="texto" linhas={8} label="Carregando a inspeção…" />;
  if (falha) return <ErrorCard falha={falha} onRetry={recarregar} />;
  if (!insp) return null;

  const vib = insp.medicoes_vibracao ?? [];
  const termo = insp.medicoes_termografia ?? [];
  const tec = insp.medicoes_tecnicas ?? [];
  const total = vib.length + termo.length + tec.length;
  const criticas = [...vib, ...termo, ...tec].filter((m) => m.criticidade === "CRITICO").length;
  const alertas = [...vib, ...termo, ...tec].filter((m) => m.criticidade === "ALERTA").length;

  return (
    <PageBody>
      <PageHeader
        icon={ClipboardCheck}
        title={`Inspeção de ${fmtData(insp.data)}`}
        description={insp.tipo_analise_display}
        trilha={[{ label: "Inspeções", href: "/portal/inspecoes" }, { label: fmtData(insp.data) }]}
        selo={<Badge tone="neutral">{insp.status_display}</Badge>}
      />

      <MetricGrid colunas={3}>
        <MetricCard label="Pontos medidos" value={total} icon={Gauge} contexto="nesta inspeção" />
        <MetricCard
          label="Pontos críticos"
          value={criticas}
          tone={criticas > 0 ? "danger" : "success"}
          contexto={criticas > 0 ? "exigem intervenção imediata" : "nenhum"}
        />
        <MetricCard
          label="Pontos em alerta"
          value={alertas}
          tone={alertas > 0 ? "warning" : "neutral"}
          contexto={alertas > 0 ? "acima do aceitável" : "nenhum"}
        />
      </MetricGrid>

      <Card>
        <CardHeader title="Dados da inspeção" />
        <DescriptionList
          colunas={3}
          items={[
            { label: "Data da coleta", value: fmtData(insp.data), tecnico: true },
            { label: "Tecnologia", value: insp.tipo_analise_display },
            { label: "Responsável em campo", value: texto(insp.tecnico_nome) },
            { label: "Situação", value: insp.status_display },
            {
              label: "Pior resultado",
              value: <EstadoBadge grau={grauDe(insp.criticidade_maxima)} mostrarSignificado />,
            },
            {
              label: "Observações do técnico",
              value: insp.observacoes || <SemDado>Sem observações</SemDado>,
              largo: true,
            },
          ]}
        />
      </Card>

      {total === 0 ? (
        <Card padding={false}>
          <EmptyState
            icon={Activity}
            title="Esta inspeção ainda não tem medições publicadas"
            description="A coleta foi registrada, mas as medições ainda estão em análise. Elas aparecem aqui quando a análise técnica é concluída."
          />
        </Card>
      ) : (
        <div className="space-y-5">
          <LegendaEstados graus={["NORMAL", "ALERTA", "CRITICO"]} />

          {vib.length > 0 && (
            <section>
              <CardHeader
                title="Análise de vibração"
                icon={Waves}
                description="Velocidade global comparada ao limite da classe ISO 10816 do equipamento."
              />
              <Table>
                <THead>
                  <TH>Equipamento</TH>
                  <TH>Ponto</TH>
                  <TH>Direção</TH>
                  <TH className="text-right">Velocidade</TH>
                  <TH className="text-right">Temperatura</TH>
                  <TH>Zona ISO</TH>
                  <TH>Resultado</TH>
                </THead>
                <TBody>
                  {vib.map((m) => (
                    <TR key={m.id} tom={m.criticidade === "CRITICO" ? "danger" : undefined}>
                      <TD className="font-medium text-fg" tecnico>
                        {m.equipamento_tag}
                      </TD>
                      <TD>
                        {texto(m.ponto_medicao)}
                        {m.componente_nome && (
                          <span className="block text-xs text-fg-subtle">{m.componente_nome}</span>
                        )}
                      </TD>
                      <TD>{m.direcao_display}</TD>
                      <TD className="text-right" tecnico>
                        {numeroUnidade(m.velocidade_rms, "mm/s")}
                      </TD>
                      <TD className="text-right" tecnico>
                        {m.temperatura ? numeroUnidade(m.temperatura, "°C", 1) : <SemDado />}
                      </TD>
                      <TD>{m.zona_iso ? <Badge tone="neutral">{m.zona_iso}</Badge> : <SemDado />}</TD>
                      <TD>
                        <EstadoBadge grau={grauDe(m.criticidade)} tamanho="sm" />
                      </TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
            </section>
          )}

          {termo.length > 0 && (
            <section>
              <CardHeader
                title="Termografia"
                icon={Flame}
                description="Diferença de temperatura (ΔT) entre o ponto medido e a referência do mesmo sistema."
              />
              <Table>
                <THead>
                  <TH>Equipamento</TH>
                  <TH>Ponto</TH>
                  <TH>Sistema</TH>
                  <TH className="text-right">Medido</TH>
                  <TH className="text-right">Referência</TH>
                  <TH className="text-right">ΔT</TH>
                  <TH>Resultado</TH>
                </THead>
                <TBody>
                  {termo.map((m) => (
                    <TR key={m.id} tom={m.criticidade === "CRITICO" ? "danger" : undefined}>
                      <TD className="font-medium text-fg" tecnico>
                        {m.equipamento_tag}
                      </TD>
                      <TD>
                        {texto(m.ponto_medicao)}
                        {m.componente_nome && (
                          <span className="block text-xs text-fg-subtle">{m.componente_nome}</span>
                        )}
                      </TD>
                      <TD>{m.sistema_display}</TD>
                      <TD className="text-right" tecnico>
                        {numeroUnidade(m.temperatura_ponto, "°C", 1)}
                      </TD>
                      <TD className="text-right" tecnico>
                        {numeroUnidade(m.temperatura_referencia, "°C", 1)}
                      </TD>
                      <TD className="text-right font-semibold" tecnico>
                        {numeroUnidade(m.delta_t, "°C", 1)}
                      </TD>
                      <TD>
                        <EstadoBadge grau={grauDe(m.criticidade)} tamanho="sm" />
                      </TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
            </section>
          )}

          {tec.length > 0 && (
            <section>
              <CardHeader
                title="Outros ensaios"
                icon={Gauge}
                description="Ensaios elétricos, fluidos, ultrassom, espessura e qualidade de energia."
              />
              <Table>
                <THead>
                  <TH>Equipamento</TH>
                  <TH>Ensaio</TH>
                  <TH>Grandeza</TH>
                  <TH className="text-right">Valor</TH>
                  <TH className="text-right">Referência</TH>
                  <TH>Resultado</TH>
                </THead>
                <TBody>
                  {tec.map((m) => (
                    <TR key={m.id} tom={m.criticidade === "CRITICO" ? "danger" : undefined}>
                      <TD className="font-medium text-fg" tecnico>
                        {m.equipamento_tag}
                      </TD>
                      <TD>{m.tipo_display}</TD>
                      <TD>{texto(m.grandeza)}</TD>
                      <TD className="text-right" tecnico>
                        {numero(m.valor)} {m.unidade}
                      </TD>
                      <TD className="text-right" tecnico>
                        {m.valor_referencia ? `${numero(m.valor_referencia)} ${m.unidade}` : <SemDado />}
                      </TD>
                      <TD>
                        <EstadoBadge grau={grauDe(m.criticidade)} tamanho="sm" />
                      </TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
            </section>
          )}
        </div>
      )}
    </PageBody>
  );
}
