"use client";

import { useMemo, useState } from "react";
import { Check, ClipboardList, Mail, Phone, UserCheck, X } from "lucide-react";
import {
  Badge,
  Button,
  ConfirmDialog,
  DataTable,
  EmptyState,
  MetricCard,
  MetricGrid,
  PageBody,
  PageHeader,
  PermissionDenied,
  SearchInput,
  SegmentedControl,
  SemDado,
  Toolbar,
  useConfirmacao,
  useToast,
  type Coluna,
  type ItemMenu,
} from "@/components/ds";
import { api } from "@/lib/api";
import { useLista, useMutacao } from "@/lib/recurso";
import { usePermissoes } from "@/lib/permissions";
import { cnpj as fmtCnpj, dataHora, telefone as fmtTelefone, texto } from "@/lib/format";
import type { SolicitacaoAcesso } from "@/lib/types";

/* ==========================================================================
   Solicitações de acesso — fila do formulário público /portal/cadastro.
   --------------------------------------------------------------------------
   Antes desta tela, um pedido comercial caía no banco e ficava invisível: só
   dava pra ver pelo admin do Django. Esta página fecha essa lacuna, do mesmo
   jeito que Usuários e acessos fechou a de conceder login.

   Aprovar/recusar aqui é só a DECISÃO comercial — nunca cria Cliente nem User
   sozinho (regra do backend). O passo seguinte continua manual e deliberado:
   Clientes → Novo cliente, e o convite ao usuário pelo fluxo que já existe.
   Juntar os dois num clique só criaria uma segunda porta de entrada de dados
   de cliente, correndo por fora do cadastro em Clientes.
   ========================================================================== */

type Visao = "pendentes" | "aprovadas" | "recusadas" | "todas";

const VISAO_STATUS: Record<Visao, string | null> = {
  pendentes: "PENDING",
  aprovadas: "APPROVED",
  recusadas: "REJECTED",
  todas: null,
};

export default function SolicitacoesAcessoPage() {
  const toast = useToast();
  const { pode } = usePermissoes();
  const [busca, setBusca] = useState("");
  const [visao, setVisao] = useState<Visao>("pendentes");

  // Mesmo gate do UserViewSet no backend (IsMaster): só quem concede acesso
  // decide quais empresas entram na fila de cadastro.
  const podeVer = pode("usuarios:ver");
  const lista = useLista<SolicitacaoAcesso>(
    podeVer ? "/solicitacoes-acesso/?page_size=300" : null,
    "solicitações de acesso"
  );
  const mutacao = useMutacao("decisão sobre a solicitação");
  const recusa = useConfirmacao<SolicitacaoAcesso>();

  if (!podeVer) {
    return (
      <PageBody>
        <PermissionDenied
          destino="/usuarios"
          destinoLabel="Ir para Usuários e acessos"
          motivo="A decisão sobre pedidos de acesso é exclusiva do nível Master, a mesma regra de quem concede login no sistema."
        />
      </PageBody>
    );
  }

  const todas = lista.itens;
  const pendentes = todas.filter((s) => s.status === "PENDING").length;

  const visiveis = useMemo(() => {
    const alvo = VISAO_STATUS[visao];
    return todas.filter((s) => alvo === null || s.status === alvo);
  }, [todas, visao]);

  async function aprovar(s: SolicitacaoAcesso) {
    const r = await mutacao.executar(() => api(`/solicitacoes-acesso/${s.id}/aprovar/`, { method: "POST" }));
    if (r.ok) {
      toast.sucesso(`Solicitação de ${s.razao_social} aprovada`, {
        descricao: "Agora é criar a empresa em Clientes → Novo cliente e convidar o usuário.",
      });
      lista.recarregar();
    } else {
      toast.erro(r.falha.titulo, { descricao: r.falha.descricao });
    }
  }

  async function recusar(s: SolicitacaoAcesso) {
    const r = await mutacao.executar(() => api(`/solicitacoes-acesso/${s.id}/recusar/`, { method: "POST" }));
    if (r.ok) {
      toast.sucesso(`Solicitação de ${s.razao_social} recusada`);
      lista.recarregar();
    } else {
      toast.erro(r.falha.titulo, { descricao: r.falha.descricao });
    }
  }

  const colunas: Coluna<SolicitacaoAcesso>[] = [
    {
      chave: "razao_social",
      header: "Empresa",
      mobile: "titulo",
      valor: (s) => s.razao_social,
      celula: (s) => (
        <span>
          <span className="font-semibold text-fg">{s.razao_social}</span>
          {s.nome_fantasia && s.nome_fantasia !== s.razao_social && (
            <span className="block truncate text-xs text-fg-muted">{s.nome_fantasia}</span>
          )}
        </span>
      ),
    },
    {
      chave: "cnpj",
      header: "CNPJ",
      mobile: "meta",
      tecnico: true,
      valor: (s) => s.cnpj,
      celula: (s) => fmtCnpj(s.cnpj),
    },
    {
      chave: "contato",
      header: "Contato",
      mobile: "subtitulo",
      valor: (s) => s.nome,
      celula: (s) => (
        <span>
          <span className="text-fg">{s.nome}</span>
          {s.cargo && <span className="text-fg-muted"> — {s.cargo}</span>}
        </span>
      ),
    },
    {
      chave: "email",
      header: "E-mail / Telefone",
      mobile: "meta",
      celula: (s) => (
        <span className="space-y-0.5 text-xs">
          <span className="flex items-center gap-1.5 text-fg-muted">
            <Mail className="h-3 w-3 shrink-0" aria-hidden="true" />
            {s.email}
          </span>
          {s.telefone && (
            <span className="flex items-center gap-1.5 text-fg-subtle">
              <Phone className="h-3 w-3 shrink-0" aria-hidden="true" />
              {fmtTelefone(s.telefone)}
            </span>
          )}
        </span>
      ),
    },
    {
      chave: "equipamentos",
      header: "Equipamentos",
      mobile: "meta",
      alinhamento: "direita",
      tecnico: true,
      valor: (s) => s.quantidade_equipamentos ?? -1,
      celula: (s) => s.quantidade_equipamentos ?? <SemDado />,
    },
    {
      chave: "data",
      header: "Recebida em",
      mobile: "meta",
      tecnico: true,
      valor: (s) => s.criado_em,
      celula: (s) => dataHora(s.criado_em),
    },
    {
      chave: "status",
      header: "Situação",
      mobile: "meta",
      valor: (s) => s.status_display,
      celula: (s) => (
        <Badge
          tone={s.status === "PENDING" ? "warning" : s.status === "APPROVED" ? "success" : "neutral"}
        >
          {s.status_display}
        </Badge>
      ),
    },
  ];

  return (
    <PageBody>
      <PageHeader
        icon={ClipboardList}
        title="Solicitações de acesso"
        description="Pedidos comerciais recebidos pelo formulário público de cadastro. Aprovar aqui é só a decisão — o cadastro da empresa e o convite do usuário continuam feitos à mão."
        trilha={[
          { label: "Usuários e acessos", href: "/usuarios" },
          { label: "Solicitações de acesso" },
        ]}
      />

      <MetricGrid colunas={3}>
        <MetricCard
          label="Aguardando decisão"
          value={pendentes}
          icon={ClipboardList}
          tone={pendentes > 0 ? "warning" : "success"}
          contexto={pendentes > 0 ? "precisam de aprovar ou recusar" : "fila em dia"}
        />
        <MetricCard
          label="Aprovadas"
          value={todas.filter((s) => s.status === "APPROVED").length}
          icon={UserCheck}
          contexto="prontas para virar cliente"
        />
        <MetricCard
          label="Recusadas"
          value={todas.filter((s) => s.status === "REJECTED").length}
          contexto="não seguiram para cadastro"
        />
      </MetricGrid>

      <Toolbar
        busca={
          <SearchInput
            value={busca}
            onChange={setBusca}
            label="Buscar solicitação"
            placeholder="Empresa, contato, CNPJ…"
          />
        }
        filtros={
          <SegmentedControl
            label="Situação"
            tamanho="sm"
            valor={visao}
            onMudar={setVisao}
            opcoes={[
              { valor: "pendentes", label: `Pendentes (${pendentes})` },
              { valor: "aprovadas", label: "Aprovadas" },
              { valor: "recusadas", label: "Recusadas" },
              { valor: "todas", label: "Todas" },
            ]}
          />
        }
      />

      <DataTable<SolicitacaoAcesso>
        itens={visiveis}
        colunas={colunas}
        getId={(s) => s.id}
        busca={busca}
        camposBusca={(s) => [s.razao_social, s.nome_fantasia, s.nome, s.email, s.cnpj]}
        carregando={lista.carregando}
        falha={lista.falha}
        onRetry={lista.recarregar}
        tomDaLinha={(s) => (s.status === "REJECTED" ? "muted" : undefined)}
        acoes={(s) =>
          s.status === "PENDING"
            ? ([
                { label: "Aprovar", icon: Check, onClick: () => aprovar(s) },
                { label: "Recusar", icon: X, onClick: () => recusa.pedir(s), destrutivo: true },
              ] as ItemMenu[])
            : []
        }
        ordenacaoInicial={{ chave: "data", direcao: "desc" }}
        legenda="Solicitações de acesso recebidas pelo formulário público, com empresa, contato e situação"
        vazio={
          <EmptyState
            icon={ClipboardList}
            title={visao === "pendentes" ? "Nenhuma solicitação pendente" : "Nenhuma solicitação aqui"}
            description={
              visao === "pendentes"
                ? "Quando alguém preencher o formulário público de cadastro, o pedido aparece aqui para aprovar ou recusar."
                : "Troque o filtro de situação para ver outras solicitações."
            }
          />
        }
      />

      <ConfirmDialog
        aberto={!!recusa.alvo}
        onFechar={recusa.cancelar}
        onConfirmar={() => recusa.executar(recusar)}
        enviando={recusa.enviando}
        title="Recusar esta solicitação?"
        confirmarLabel="Recusar"
        mensagem={
          <>
            O pedido de <strong>{recusa.alvo?.razao_social}</strong> ({texto(recusa.alvo?.nome)})
            fica marcado como recusado.
          </>
        }
        detalhe="Não impede a pessoa de preencher o formulário de novo mais tarde."
      />
    </PageBody>
  );
}
