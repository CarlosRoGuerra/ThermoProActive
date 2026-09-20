"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Clock, Plus, TriangleAlert, Wrench } from "lucide-react";
import {
  Alert,
  Badge,
  Button,
  DataTable,
  EmptyState,
  EstadoBadge,
  Field,
  MetricCard,
  MetricGrid,
  PageBody,
  PageHeader,
  PriorityBadge,
  SearchInput,
  SegmentedControl,
  Select,
  SemDado,
  StatusBadge,
  Toolbar,
  grauDe,
  useToast,
  type Coluna,
} from "@/components/ds";
import { Combobox } from "@/components/combobox";
import { api, qs } from "@/lib/api";
import { useLista, useMutacao } from "@/lib/recurso";
import { useClienteAtivo } from "@/lib/cliente-ativo";
import { useClientes } from "@/lib/hierarquia";
import { usePermissoes } from "@/lib/permissions";
import { data as fmtData, diasAte, plural, texto } from "@/lib/format";
import type { OrdemServico } from "@/lib/types";

/* ==========================================================================
   Ordens de Serviço Preditivas (visão interna)
   --------------------------------------------------------------------------
   O ciclo acordado com o cliente é Aberta → Planejada → Executada →
   Finalizada, com desvios possíveis (análise, execução, aprovação, cancelada).

   O filtro por cliente vai ao SERVIDOR (`?cliente=`), não à memória do
   navegador: com milhares de ordens, filtrar no cliente significa baixar tudo.
   ========================================================================== */

const FLUXO_STATUS = [
  "ABERTA",
  "PLANEJADA",
  "EXECUTADA",
  "EM_ANALISE",
  "EM_EXECUCAO",
  "AGUARDANDO_APROVACAO",
  "FINALIZADA",
  "CANCELADA",
] as const;

const ROTULO_STATUS: Record<string, string> = {
  ABERTA: "Aberta",
  PLANEJADA: "Planejada",
  EXECUTADA: "Executada",
  EM_ANALISE: "Em análise",
  EM_EXECUCAO: "Em execução",
  AGUARDANDO_APROVACAO: "Aguardando aprovação",
  FINALIZADA: "Finalizada",
  CANCELADA: "Cancelada",
};

const STATUS_ABERTOS = [
  "ABERTA",
  "PLANEJADA",
  "EM_ANALISE",
  "EM_EXECUCAO",
  "AGUARDANDO_APROVACAO",
  "EXECUTADA",
];

/** "OSP | Código": sequencial do cliente para as geradas do fluxo novo. */
function codigo(o: OrdemServico): string {
  return o.sequencial_cliente != null
    ? `${String(o.sequencial_cliente).padStart(4, "0")} | ${o.id}`
    : o.numero;
}

type Filtro = "abertas" | "vencidas" | "todas";

export default function OspsPage() {
  const toast = useToast();
  const { pode, podeEditar } = usePermissoes();
  const router = useRouter();
  const { clienteAtivo } = useClienteAtivo();
  const { opcoes: opcoesClientes } = useClientes();
  const [cliente, setCliente] = useState<number | "">(clienteAtivo?.id ?? "");
  const [busca, setBusca] = useState("");
  const [filtro, setFiltro] = useState<Filtro>("abertas");

  // Trocar o cliente em atendimento re-filtra esta tela automaticamente.
  useEffect(() => {
    if (clienteAtivo) setCliente(clienteAtivo.id);
  }, [clienteAtivo]);

  const lista = useLista<OrdemServico>(
    `/osps/${qs({ ordering: "-criado_em", page_size: 300, cliente })}`,
    "ordens de serviço"
  );
  const mutacao = useMutacao("mudança de status da OSP");

  const abertas = useMemo(() => lista.itens.filter((o) => STATUS_ABERTOS.includes(o.status)), [lista.itens]);
  const vencidas = useMemo(() => abertas.filter((o) => o.sla_vencido), [abertas]);
  const automaticas = useMemo(() => lista.itens.filter((o) => o.gerada_automaticamente), [lista.itens]);

  const visiveis = filtro === "abertas" ? abertas : filtro === "vencidas" ? vencidas : lista.itens;

  async function mudarStatus(o: OrdemServico, status: string) {
    const r = await mutacao.executar(() =>
      api(`/osps/${o.id}/status/`, { method: "PATCH", body: { status } })
    );
    if (r.ok) {
      toast.sucesso(`Ordem ${codigo(o)} agora está ${ROTULO_STATUS[status]?.toLowerCase()}`, {
        descricao:
          status === "AGUARDANDO_APROVACAO"
            ? "Os aprovadores do cliente foram notificados."
            : undefined,
      });
      lista.recarregar();
    } else {
      toast.erro(r.falha.titulo, { descricao: r.falha.descricao });
    }
  }

  const colunas: Coluna<OrdemServico>[] = [
    {
      chave: "codigo",
      header: "OSP | Código",
      mobile: "titulo",
      tecnico: true,
      valor: (o) => o.sequencial_cliente ?? o.numero,
      celula: (o) => (
        <span className="inline-flex items-center gap-1.5">
          <span className="font-semibold text-fg">{codigo(o)}</span>
          {o.gerada_automaticamente && (
            <Badge tone="primary" className="px-1.5 py-0 text-2xs" title="Gerada pela análise final">
              AUTO
            </Badge>
          )}
        </span>
      ),
    },
    {
      chave: "equipamento",
      header: "Equipamento",
      mobile: "subtitulo",
      valor: (o) => `${o.equipamento_tag} ${o.titulo}`,
      celula: (o) => (
        <span>
          <span className="data font-medium text-fg">{o.equipamento_tag}</span>
          <span className="block truncate text-xs text-fg-muted">{texto(o.titulo)}</span>
        </span>
      ),
    },
    {
      chave: "cliente",
      header: "Cliente",
      mobile: "meta",
      valor: (o) => o.cliente_nome,
      celula: (o) => texto(o.cliente_nome),
    },
    {
      chave: "gr",
      header: "Grau de risco",
      mobile: "meta",
      alinhamento: "centro",
      valor: (o) => o.grau_risco,
      celula: (o) =>
        o.grau_risco ? (
          <Badge tone="warning" title={o.grau_risco_display}>
            {o.grau_risco}
          </Badge>
        ) : o.criticidade_origem ? (
          <EstadoBadge grau={grauDe(o.criticidade_origem)} tamanho="sm" />
        ) : (
          <SemDado />
        ),
    },
    {
      chave: "prioridade",
      header: "Urgência",
      mobile: "meta",
      valor: (o) => ({ URGENTE: 4, ALTA: 3, MEDIA: 2, BAIXA: 1 })[o.prioridade] ?? 0,
      celula: (o) => <PriorityBadge value={o.prioridade} label={o.prioridade_display} />,
    },
    {
      chave: "prazo",
      header: "Prazo (SLA)",
      mobile: "meta",
      valor: (o) => o.sla_data ?? "",
      celula: (o) => {
        if (!o.sla_data) return <SemDado />;
        const dias = diasAte(o.sla_data);
        const encerrada = o.status === "FINALIZADA" || o.status === "CANCELADA";
        if (encerrada) return <span className="data text-xs text-fg-muted">{fmtData(o.sla_data)}</span>;
        if (o.sla_vencido || (dias !== null && dias < 0))
          return (
            <span className="inline-flex items-center gap-1.5 font-medium text-danger-fg">
              <TriangleAlert className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
              venceu {fmtData(o.sla_data)}
            </span>
          );
        return (
          <span
            className={
              dias !== null && dias <= 7
                ? "inline-flex items-center gap-1.5 font-medium text-warning-fg"
                : "inline-flex items-center gap-1.5 text-fg-muted"
            }
          >
            <Clock className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            {dias === 0 ? "hoje" : dias === 1 ? "amanhã" : `em ${dias} dias`}
          </span>
        );
      },
    },
    {
      chave: "status",
      header: "Situação",
      mobile: "meta",
      valor: (o) => o.status_display,
      celula: (o) =>
        pode("osp:mudar-status") ? (
          // O select fica na linha porque avançar o status é a ação mais
          // frequente da tela; o clique não propaga para a linha.
          <span onClick={(e) => e.stopPropagation()} className="inline-flex">
            <Select
              value={o.status}
              aria-label={`Situação da ordem ${codigo(o)}`}
              onChange={(e) => mudarStatus(o, e.target.value)}
              className="h-8 w-auto min-w-40 py-0 text-xs"
            >
              {FLUXO_STATUS.map((s) => (
                <option key={s} value={s}>
                  {ROTULO_STATUS[s]}
                </option>
              ))}
            </Select>
          </span>
        ) : (
          <StatusBadge value={o.status} label={o.status_display} />
        ),
    },
  ];

  return (
    <PageBody>
      <PageHeader
        icon={Wrench}
        title="Ordens de serviço"
        description="A corretiva orientada pela preditiva: cada ordem nasce de uma análise e carrega o prazo recomendado para a intervenção."
        trilha={[{ label: "Ordens de serviço" }]}
        actions={
          pode("osp:criar") ? (
            <Link href="/osps/nova">
              <Button icon={Plus}>Nova ordem</Button>
            </Link>
          ) : undefined
        }
      />

      {vencidas.length > 0 && (
        <Alert tone="danger" title={`${plural(vencidas.length, "ordem", "ordens")} com SLA vencido`}>
          O prazo recomendado passou e o equipamento continua operando na condição detectada.
          Priorize estas ordens ou registre a justificativa com o cliente.
        </Alert>
      )}

      <MetricGrid colunas={3}>
        <MetricCard
          label="Em aberto"
          value={abertas.length}
          tone={abertas.length > 0 ? "warning" : "success"}
          icon={Wrench}
          contexto={`de ${plural(lista.itens.length, "ordem", "ordens")} no período`}
        />
        <MetricCard
          label="SLA vencido"
          value={vencidas.length}
          tone={vencidas.length > 0 ? "danger" : "success"}
          icon={TriangleAlert}
          contexto={vencidas.length > 0 ? "exigem priorização" : "nenhuma atrasada"}
        />
        <MetricCard
          label="Geradas pela análise"
          value={automaticas.length}
          contexto="sem digitação manual"
          dica="Ordens criadas automaticamente ao confirmar uma análise final com achado crítico."
        />
      </MetricGrid>

      <Toolbar
        busca={
          <SearchInput
            value={busca}
            onChange={setBusca}
            label="Buscar ordem de serviço"
            placeholder="Número, TAG, título, relatório…"
          />
        }
        filtros={
          <>
            <div className="w-56">
              <Field label="Cliente">
                <Combobox
                  value={cliente}
                  onChange={setCliente}
                  options={opcoesClientes}
                  placeholder="Todos os clientes"
                  limparLabel="Todos os clientes"
                />
              </Field>
            </div>
            <SegmentedControl
              label="Filtrar ordens"
              tamanho="sm"
              valor={filtro}
              onMudar={setFiltro}
              opcoes={[
                { valor: "abertas", label: `Em aberto (${abertas.length})` },
                { valor: "vencidas", label: `Vencidas (${vencidas.length})` },
                { valor: "todas", label: "Todas" },
              ]}
            />
          </>
        }
      />

      <DataTable<OrdemServico>
        itens={visiveis}
        colunas={colunas}
        getId={(o) => o.id}
        busca={busca}
        camposBusca={(o) => [o.descricao, o.numero_relatorio, o.numero, o.responsavel_nome]}
        onLinhaClick={podeEditar ? (o) => router.push(`/osps/${o.id}`) : undefined}
        carregando={lista.carregando}
        falha={lista.falha}
        onRetry={lista.recarregar}
        tomDaLinha={(o) =>
          o.sla_vencido && STATUS_ABERTOS.includes(o.status)
            ? "danger"
            : o.status === "CANCELADA"
            ? "muted"
            : undefined
        }
        ordenacaoInicial={{ chave: "prazo", direcao: "asc" }}
        porPagina={15}
        legenda="Ordens de serviço com código, equipamento, cliente, grau de risco, urgência, prazo e situação"
        vazio={
          filtro !== "todas" && lista.itens.length > 0 ? (
            <EmptyState
              compacto
              icon={Wrench}
              title={filtro === "vencidas" ? "Nenhuma ordem com SLA vencido" : "Nenhuma ordem em aberto"}
              description="Tudo dentro do prazo no recorte atual."
            />
          ) : (
            <EmptyState
              icon={Wrench}
              title="Nenhuma ordem de serviço registrada"
              description="As ordens são geradas ao confirmar uma análise na Análise final — uma por achado."
              action={
                <Link href="/inspecoes/final">
                  <Button variant="secondary">Ir para Análise final</Button>
                </Link>
              }
            />
          )
        }
      />
    </PageBody>
  );
}
