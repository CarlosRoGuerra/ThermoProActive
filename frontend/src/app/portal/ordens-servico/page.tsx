"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { Clock, Pencil, Plus, TriangleAlert, Trash2, Wrench } from "lucide-react";
import {
  Alert,
  Button,
  ConfirmDialog,
  DataTable,
  EmptyState,
  EstadoBadge,
  MetricCard,
  MetricGrid,
  PageBody,
  PageHeader,
  PriorityBadge,
  SearchInput,
  SegmentedControl,
  SemDado,
  StatusBadge,
  Toolbar,
  grauDe,
  useConfirmacao,
  useToast,
  type Coluna,
  type ItemMenu,
} from "@/components/ds";
import { api } from "@/lib/api";
import { useLista, useMutacao } from "@/lib/recurso";
import { usePermissoes } from "@/lib/permissions";
import { data as fmtData, diasAte, plural, texto } from "@/lib/format";
import type { OrdemServico } from "@/lib/types";

/* ==========================================================================
   Portal do Cliente — Ordens de serviço
   --------------------------------------------------------------------------
   O que o cliente precisa daqui: o que foi recomendado, para qual equipamento,
   com que urgência e até quando. O prazo (SLA) é a informação central, então
   ganha coluna própria com a contagem em dias — "vence em 3 dias" comunica, uma
   data solta não.

   Criar/editar/excluir: só o Master da empresa (decisão de 2026-09-18 — antes
   era tudo em leitura, mudar status era só ação da contratada). Os demais
   perfis do cliente continuam só acompanhando.
   ========================================================================== */

const STATUS_ABERTOS = [
  "ABERTA",
  "PLANEJADA",
  "EM_ANALISE",
  "EM_EXECUCAO",
  "AGUARDANDO_APROVACAO",
  "EXECUTADA",
];

type Filtro = "abertas" | "todas" | "concluidas";

/** Prazo em linguagem de calendário, não em data crua. */
function Prazo({ osp }: { osp: OrdemServico }) {
  if (!osp.sla_data) return <SemDado>Sem prazo definido</SemDado>;
  const dias = diasAte(osp.sla_data);
  const vencido = osp.sla_vencido || (dias !== null && dias < 0);
  const finalizada = osp.status === "FINALIZADA" || osp.status === "CANCELADA";

  if (finalizada) return <span className="data text-xs text-fg-muted">{fmtData(osp.sla_data)}</span>;

  return (
    <span
      className={
        vencido
          ? "inline-flex items-center gap-1.5 font-medium text-danger-fg"
          : dias !== null && dias <= 7
          ? "inline-flex items-center gap-1.5 font-medium text-warning-fg"
          : "inline-flex items-center gap-1.5 text-fg-muted"
      }
    >
      {vencido ? (
        <TriangleAlert className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
      ) : (
        <Clock className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
      )}
      <span>
        {vencido
          ? `Prazo vencido em ${fmtData(osp.sla_data)}`
          : dias === 0
          ? "Vence hoje"
          : dias === 1
          ? "Vence amanhã"
          : `Vence em ${dias} dias`}
      </span>
    </span>
  );
}

export default function PortalOrdensServicoPage() {
  const { pode } = usePermissoes();
  const podeGerenciar = pode("parque:gerenciar");
  const toast = useToast();
  const [busca, setBusca] = useState("");
  const [filtro, setFiltro] = useState<Filtro>("abertas");
  const { itens, carregando, falha, recarregar } = useLista<OrdemServico>(
    "/osps/?ordering=-criado_em&page_size=300",
    "ordens de serviço do portal"
  );
  const mutacao = useMutacao("remoção de ordem de serviço");
  const remocao = useConfirmacao<OrdemServico>();

  async function remover(osp: OrdemServico) {
    const r = await mutacao.executar(() => api(`/osps/${osp.id}/`, { method: "DELETE" }));
    if (r.ok) {
      toast.sucesso(`OSP ${osp.numero} removida`);
      recarregar();
    } else {
      toast.erro(r.falha.titulo, { descricao: r.falha.descricao });
    }
  }

  const abertas = useMemo(() => itens.filter((o) => STATUS_ABERTOS.includes(o.status)), [itens]);
  const vencidas = useMemo(() => abertas.filter((o) => o.sla_vencido), [abertas]);
  const concluidas = useMemo(() => itens.filter((o) => o.status === "FINALIZADA"), [itens]);

  const visiveis =
    filtro === "abertas" ? abertas : filtro === "concluidas" ? concluidas : itens;

  const colunas: Coluna<OrdemServico>[] = [
    {
      chave: "numero",
      header: "Ordem",
      mobile: "titulo",
      tecnico: true,
      valor: (o) => o.sequencial_cliente ?? o.numero,
      celula: (o) => (
        <span className="font-semibold text-fg">
          {o.sequencial_cliente != null
            ? String(o.sequencial_cliente).padStart(4, "0")
            : o.numero}
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
          <span className="block text-xs text-fg-muted">{texto(o.titulo)}</span>
        </span>
      ),
    },
    {
      chave: "origem",
      header: "Origem",
      mobile: "meta",
      valor: (o) => o.criticidade_origem,
      celula: (o) =>
        o.criticidade_origem ? (
          <EstadoBadge grau={grauDe(o.criticidade_origem)} tamanho="sm" mostrarSignificado />
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
      header: "Prazo",
      mobile: "meta",
      valor: (o) => o.sla_data ?? "",
      celula: (o) => <Prazo osp={o} />,
    },
    {
      chave: "status",
      header: "Situação",
      mobile: "meta",
      valor: (o) => o.status_display,
      celula: (o) => <StatusBadge value={o.status} label={o.status_display} />,
    },
  ];

  return (
    <PageBody>
      <PageHeader
        icon={Wrench}
        title="Ordens de serviço"
        description="As intervenções recomendadas a partir das medições do seu parque, com a urgência e o prazo de cada uma. A execução é acompanhada pela equipe técnica."
        trilha={[{ label: "Ordens de serviço" }]}
        actions={
          podeGerenciar ? (
            <Link href="/portal/ordens-servico/novo">
              <Button icon={Plus}>Nova ordem de serviço</Button>
            </Link>
          ) : undefined
        }
      />

      {vencidas.length > 0 && (
        <Alert
          tone="danger"
          title={`${plural(vencidas.length, "ordem", "ordens")} com prazo vencido`}
        >
          O prazo recomendado para a intervenção já passou. Quanto mais tempo o equipamento opera
          nessa condição, maior o risco de falha e de dano secundário.
        </Alert>
      )}

      <MetricGrid colunas={3}>
        <MetricCard
          label="Em aberto"
          value={abertas.length}
          tone={abertas.length > 0 ? "warning" : "success"}
          icon={Wrench}
          contexto={abertas.length > 0 ? "aguardando execução" : "nada pendente"}
        />
        <MetricCard
          label="Com prazo vencido"
          value={vencidas.length}
          tone={vencidas.length > 0 ? "danger" : "success"}
          icon={TriangleAlert}
          contexto={vencidas.length > 0 ? "exigem decisão imediata" : "nenhuma"}
        />
        <MetricCard
          label="Concluídas"
          value={concluidas.length}
          tone="success"
          contexto={`de ${plural(itens.length, "ordem", "ordens")} no histórico`}
        />
      </MetricGrid>

      <Toolbar
        busca={
          <SearchInput
            value={busca}
            onChange={setBusca}
            label="Buscar ordem de serviço"
            placeholder="Número, TAG do equipamento, descrição…"
          />
        }
        filtros={
          <SegmentedControl
            label="Filtrar ordens"
            tamanho="sm"
            valor={filtro}
            onMudar={setFiltro}
            opcoes={[
              { valor: "abertas", label: `Em aberto (${abertas.length})` },
              { valor: "concluidas", label: `Concluídas (${concluidas.length})` },
              { valor: "todas", label: "Todas" },
            ]}
          />
        }
      />

      <DataTable<OrdemServico>
        itens={visiveis}
        colunas={colunas}
        getId={(o) => o.id}
        busca={busca}
        camposBusca={(o) => [o.descricao, o.numero_relatorio, o.numero]}
        carregando={carregando}
        falha={falha}
        onRetry={recarregar}
        tomDaLinha={(o) =>
          o.sla_vencido && STATUS_ABERTOS.includes(o.status)
            ? "danger"
            : o.status === "CANCELADA"
            ? "muted"
            : undefined
        }
        ordenacaoInicial={{ chave: "prazo", direcao: "asc" }}
        legenda="Ordens de serviço com número, equipamento, urgência, prazo e situação"
        acoes={
          podeGerenciar
            ? (o): ItemMenu[] => [
                { label: "Editar", icon: Pencil, href: `/portal/ordens-servico/editar/${o.id}` },
                {
                  label: "Remover",
                  icon: Trash2,
                  destrutivo: true,
                  onClick: () => remocao.pedir(o),
                },
              ]
            : undefined
        }
        vazio={
          filtro === "abertas" && itens.length > 0 ? (
            <EmptyState
              compacto
              icon={Wrench}
              title="Nenhuma ordem em aberto"
              description="Todas as intervenções recomendadas já foram concluídas."
            />
          ) : (
            <EmptyState
              icon={Wrench}
              title="Nenhuma ordem de serviço"
              description={
                podeGerenciar
                  ? "As ordens costumam abrir automaticamente numa medição crítica — mas você também pode abrir uma manualmente."
                  : "As ordens são abertas automaticamente quando uma medição aponta condição crítica em um equipamento seu."
              }
              action={
                podeGerenciar ? (
                  <Link href="/portal/ordens-servico/novo">
                    <Button icon={Plus}>Nova ordem de serviço</Button>
                  </Link>
                ) : undefined
              }
              comoFunciona={[
                "Uma medição fora do limite da norma é classificada como crítica.",
                "O sistema abre a ordem com a recomendação técnica e o prazo (SLA).",
                "Você é avisado por e-mail e acompanha a execução aqui.",
              ]}
            />
          )
        }
      />

      <ConfirmDialog
        aberto={!!remocao.alvo}
        onFechar={remocao.cancelar}
        onConfirmar={() => remocao.executar(remover)}
        enviando={remocao.enviando}
        title="Remover esta ordem de serviço?"
        confirmarLabel="Remover"
        mensagem={
          <>
            A OSP <strong>{remocao.alvo?.numero}</strong> ({texto(remocao.alvo?.equipamento_tag)})
            é removida.
          </>
        }
        irreversivel
      />
    </PageBody>
  );
}
