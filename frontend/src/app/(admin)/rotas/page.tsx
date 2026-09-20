"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { CalendarDays, Map, Pencil, Plus, Trash2 } from "lucide-react";
import {
  Badge,
  Button,
  ConfirmDialog,
  DataTable,
  EmptyState,
  PageBody,
  PageHeader,
  SearchInput,
  SemDado,
  Toolbar,
  useConfirmacao,
  useToast,
  type Coluna,
  type ItemMenu,
} from "@/components/ds";
import { api } from "@/lib/api";
import { useLista, useMutacao } from "@/lib/recurso";
import { useClienteAtivo } from "@/lib/cliente-ativo";
import { usePermissoes } from "@/lib/permissions";
import { plural } from "@/lib/format";
import { ExigeClienteAtivo } from "@/features/clientes/exige-cliente-ativo";
import type { Rota } from "@/lib/types";

/**
 * Rotas de inspeção — o roteiro que o técnico carrega para o campo.
 *
 * Uma rota é "estes equipamentos, com esta tecnologia, nesta periodicidade".
 * Por isso as três informações aparecem juntas na linha: sem elas a rota não
 * diz nada.
 */
export default function RotasPage() {
  const router = useRouter();
  const toast = useToast();
  const { podeEditar, podeExcluir } = usePermissoes();
  const { clienteAtivo } = useClienteAtivo();
  const [busca, setBusca] = useState("");

  const lista = useLista<Rota>(
    clienteAtivo ? `/rotas/?cliente=${clienteAtivo.id}&page_size=500` : null,
    "rotas de inspeção"
  );
  const mutacao = useMutacao("remoção de rota");
  const remocao = useConfirmacao<Rota>();

  async function remover(r: Rota) {
    const res = await mutacao.executar(() => api(`/rotas/${r.id}/`, { method: "DELETE" }));
    if (res.ok) {
      toast.sucesso("Rota removida", { descricao: `“${r.nome}” saiu da lista.` });
      lista.removerItem((x) => x.id === r.id);
    } else {
      toast.erro(res.falha.titulo, { descricao: res.falha.descricao });
    }
  }

  const colunas: Coluna<Rota>[] = [
    {
      chave: "nome",
      header: "Rota",
      mobile: "titulo",
      valor: (r) => r.nome,
      celula: (r) => (
        <span>
          <span className="font-medium text-fg">{r.nome}</span>
          {r.descricao && <span className="block truncate text-xs text-fg-subtle">{r.descricao}</span>}
        </span>
      ),
    },
    {
      chave: "tecnologia",
      header: "Tecnologia",
      mobile: "subtitulo",
      valor: (r) => r.tecnologia_nome ?? "",
      celula: (r) =>
        r.tecnologia_nome ? <Badge tone="primary">{r.tecnologia_nome}</Badge> : <SemDado />,
    },
    {
      chave: "equipamentos",
      header: "Equipamentos",
      mobile: "meta",
      alinhamento: "direita",
      tecnico: true,
      valor: (r) => r.qtd_equipamentos,
      celula: (r) =>
        r.qtd_equipamentos > 0 ? (
          r.qtd_equipamentos
        ) : (
          <SemDado>Nenhum</SemDado>
        ),
    },
    {
      chave: "periodicidade",
      header: "Periodicidade",
      mobile: "meta",
      valor: (r) => r.periodicidade_dias ?? 0,
      celula: (r) =>
        r.periodicidade_dias ? (
          <span className="inline-flex items-center gap-1.5 text-fg-muted">
            <CalendarDays className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            a cada {r.periodicidade_dias} dias
          </span>
        ) : (
          <SemDado>Sob demanda</SemDado>
        ),
    },
  ];

  const acoes = (r: Rota): ItemMenu[] => {
    const itens: ItemMenu[] = [];
    if (podeEditar) itens.push({ label: "Editar rota", href: `/rotas/${r.id}`, icon: Pencil });
    if (podeExcluir)
      itens.push({
        label: "Remover rota",
        icon: Trash2,
        destrutivo: true,
        onClick: () => remocao.pedir(r),
      });
    return itens;
  };

  return (
    <PageBody>
      <PageHeader
        icon={Map}
        title="Rotas de inspeção"
        description={
          clienteAtivo
            ? `Roteiros de coleta de ${clienteAtivo.nome_fantasia || clienteAtivo.nome}: quais equipamentos, com qual tecnologia e em que periodicidade.`
            : "Roteiros de coleta em campo, por cliente."
        }
        trilha={[{ label: "Clientes", href: "/clientes" }, { label: "Rotas de inspeção" }]}
        actions={
          podeEditar && clienteAtivo ? (
            <Link href="/rotas/nova">
              <Button icon={Plus}>Nova rota</Button>
            </Link>
          ) : undefined
        }
      />

      {!clienteAtivo ? (
        <ExigeClienteAtivo oQue="As rotas de inspeção" />
      ) : (
        <>
          <Toolbar
            busca={
              <SearchInput
                value={busca}
                onChange={setBusca}
                label="Buscar rota"
                placeholder="Nome, tecnologia, descrição…"
              />
            }
            resumo={lista.itens.length > 0 ? plural(lista.itens.length, "rota") : undefined}
          />

          <DataTable<Rota>
            itens={lista.itens}
            colunas={colunas}
            getId={(r) => r.id}
            busca={busca}
            carregando={lista.carregando}
            falha={lista.falha}
            onRetry={lista.recarregar}
            onLinhaClick={podeEditar ? (r) => router.push(`/rotas/${r.id}`) : undefined}
            acoes={acoes}
            ordenacaoInicial={{ chave: "nome", direcao: "asc" }}
            legenda="Rotas de inspeção com tecnologia, número de equipamentos e periodicidade"
            vazio={
              <EmptyState
                icon={Map}
                title="Nenhuma rota cadastrada para este cliente"
                description="A rota agrupa os equipamentos que o técnico vai medir na mesma visita, com a tecnologia e a periodicidade definidas."
                action={
                  podeEditar ? (
                    <Link href="/rotas/nova">
                      <Button icon={Plus}>Criar a primeira rota</Button>
                    </Link>
                  ) : undefined
                }
                comoFunciona={[
                  "Escolha a tecnologia de análise (vibração, termografia…).",
                  "Selecione os equipamentos que entram na rota.",
                  "Defina de quantos em quantos dias ela se repete.",
                ]}
              />
            }
          />
        </>
      )}

      <ConfirmDialog
        aberto={!!remocao.alvo}
        onFechar={remocao.cancelar}
        onConfirmar={() => remocao.executar(remover)}
        enviando={mutacao.enviando}
        title="Remover esta rota?"
        confirmarLabel="Remover rota"
        mensagem={
          <>
            A rota <strong>{remocao.alvo?.nome}</strong> deixará de estar disponível para carregar em
            campo.
          </>
        }
        detalhe="As coletas já realizadas por esta rota continuam no histórico."
        irreversivel
      />
    </PageBody>
  );
}
