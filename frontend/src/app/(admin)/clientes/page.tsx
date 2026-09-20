"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Building2, CircleCheck, Pencil, Plus, Power, Trash2 } from "lucide-react";
import {
  Avatar,
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
import { cnpj as fmtCnpj, plural, telefone, texto } from "@/lib/format";
import type { Cliente } from "@/lib/types";

/**
 * Clientes — os tomadores de serviço.
 *
 * "Ativar" um cliente coloca o sistema dentro do ambiente dele: as telas de
 * estrutura (áreas, setores, equipamentos, rotas) passam a mostrar só os dados
 * daquela empresa. É a ação mais usada desta tela, por isso ela aparece na
 * própria linha, e não escondida no menu.
 */
export default function ClientesPage() {
  const router = useRouter();
  const toast = useToast();
  const { podeEditar, podeExcluir } = usePermissoes();
  const { clienteAtivo, ativar } = useClienteAtivo();
  const [busca, setBusca] = useState("");

  const lista = useLista<Cliente>("/clientes/?page_size=500", "clientes");
  const mutacao = useMutacao("remoção de cliente");
  const remocao = useConfirmacao<Cliente>();

  async function remover(c: Cliente) {
    const r = await mutacao.executar(() => api(`/clientes/${c.id}/`, { method: "DELETE" }));
    if (r.ok) {
      toast.sucesso("Cliente removido", { descricao: `“${c.nome}” saiu da lista.` });
      lista.removerItem((x) => x.id === c.id);
    } else {
      toast.erro(r.falha.titulo, { descricao: r.falha.descricao });
    }
  }

  const colunas: Coluna<Cliente>[] = [
    {
      chave: "nome",
      header: "Cliente",
      mobile: "titulo",
      valor: (c) => c.nome_fantasia || c.nome,
      celula: (c) => (
        <span className="flex items-center gap-2.5">
          <Avatar nome={c.nome_fantasia || c.nome} src={c.logomarca} tamanho="xs" />
          <span className="min-w-0">
            <span className="flex items-center gap-1.5">
              {clienteAtivo?.id === c.id && (
                <span
                  className="h-1.5 w-1.5 shrink-0 rounded-full bg-primary"
                  title="Cliente em atendimento"
                  aria-label="Cliente em atendimento"
                />
              )}
              <span className="truncate font-medium text-fg">{c.nome_fantasia || c.nome}</span>
            </span>
            {c.nome_fantasia && c.nome !== c.nome_fantasia && (
              <span className="block truncate text-xs text-fg-subtle">{c.nome}</span>
            )}
          </span>
        </span>
      ),
    },
    {
      chave: "cnpj",
      header: "CNPJ",
      mobile: "meta",
      tecnico: true,
      valor: (c) => c.cnpj,
      celula: (c) => (c.cnpj ? fmtCnpj(c.cnpj) : <SemDado />),
    },
    {
      chave: "unidade",
      header: "Unidade",
      mobile: "meta",
      valor: (c) => c.unidade_negocio,
      celula: (c) => (c.unidade_negocio ? <Badge tone="neutral">{c.unidade_negocio}</Badge> : <SemDado />),
    },
    {
      chave: "local",
      header: "Cidade/UF",
      mobile: "meta",
      valor: (c) => c.cidade_uf,
      celula: (c) => (c.cidade_uf ? texto(c.cidade_uf) : <SemDado />),
    },
    {
      chave: "contato",
      header: "Contato",
      mobile: "meta",
      valor: (c) => c.contato_gestor,
      celula: (c) =>
        c.contato_gestor ? (
          <span>
            {c.contato_gestor}
            {c.telefone && (
              <span className="block text-xs text-fg-subtle">{telefone(c.telefone)}</span>
            )}
          </span>
        ) : (
          <SemDado />
        ),
    },
  ];

  const acoes = (c: Cliente): ItemMenu[] => {
    const ehAtivo = clienteAtivo?.id === c.id;
    const itens: ItemMenu[] = [
      {
        label: ehAtivo ? "Já é o cliente em atendimento" : "Atender este cliente",
        icon: ehAtivo ? CircleCheck : Power,
        disabled: ehAtivo,
        motivoDesabilitado: "Você já está trabalhando no ambiente deste cliente.",
        onClick: () =>
          ativar({
            id: c.id,
            nome: c.nome,
            nome_fantasia: c.nome_fantasia,
            logomarca: c.logomarca,
          }),
      },
    ];
    if (podeEditar) itens.push({ label: "Editar cadastro", href: `/clientes/${c.id}`, icon: Pencil });
    if (podeExcluir)
      itens.push({
        label: "Remover cliente",
        icon: Trash2,
        destrutivo: true,
        onClick: () => remocao.pedir(c),
      });
    return itens;
  };

  return (
    <PageBody>
      <PageHeader
        icon={Building2}
        title="Clientes"
        description="As empresas atendidas. Ative um cliente para trabalhar dentro do ambiente dele — a estrutura, os equipamentos e as rotas passam a aparecer filtrados."
        trilha={[{ label: "Clientes" }]}
        actions={
          podeEditar ? (
            <Link href="/clientes/novo">
              <Button icon={Plus}>Novo cliente</Button>
            </Link>
          ) : undefined
        }
      />

      <Toolbar
        busca={
          <SearchInput
            value={busca}
            onChange={setBusca}
            label="Buscar cliente"
            placeholder="Razão social, CNPJ, cidade, contato…"
          />
        }
        resumo={lista.itens.length > 0 ? plural(lista.itens.length, "cliente") : undefined}
      />

      <DataTable<Cliente>
        itens={lista.itens}
        colunas={colunas}
        getId={(c) => c.id}
        busca={busca}
        camposBusca={(c) => [c.email, c.departamento, c.uf, c.cidade]}
        carregando={lista.carregando}
        falha={lista.falha}
        onRetry={lista.recarregar}
        onLinhaClick={podeEditar ? (c) => router.push(`/clientes/${c.id}`) : undefined}
        acoes={acoes}
        ordenacaoInicial={{ chave: "nome", direcao: "asc" }}
        legenda="Clientes cadastrados com CNPJ, unidade, cidade e contato"
        vazio={
          <EmptyState
            icon={Building2}
            title="Nenhum cliente cadastrado"
            description="O cliente é o topo da hierarquia: dele saem as áreas, os setores, os equipamentos e as rotas de inspeção."
            action={
              podeEditar ? (
                <Link href="/clientes/novo">
                  <Button icon={Plus}>Cadastrar o primeiro cliente</Button>
                </Link>
              ) : undefined
            }
            comoFunciona={[
              "Cadastre a empresa com CNPJ, endereço e contato do gestor.",
              "Crie as áreas e os setores da planta dela.",
              "Cadastre os equipamentos e monte as rotas de inspeção.",
            ]}
          />
        }
      />

      <ConfirmDialog
        aberto={!!remocao.alvo}
        onFechar={remocao.cancelar}
        onConfirmar={() => remocao.executar(remover)}
        enviando={mutacao.enviando}
        title="Remover este cliente?"
        confirmarLabel="Remover cliente"
        mensagem={
          <>
            O cliente <strong>{remocao.alvo?.nome}</strong> sairá das listagens do sistema.
          </>
        }
        detalhe="As áreas, setores, equipamentos e o histórico técnico vinculados a ele deixam de aparecer junto. Se houver dados em uso, o sistema recusa a remoção."
        irreversivel
      />
    </PageBody>
  );
}
