"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Factory, Pencil, Plus, Trash2 } from "lucide-react";
import {
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
import { usePermissoes } from "@/lib/permissions";
import { cnpj as fmtCnpj, plural, telefone, texto } from "@/lib/format";
import type { Empresa } from "@/lib/types";

/**
 * Prestadores — as empresas contratadas que executam o serviço.
 *
 * Os dados daqui saem no cabeçalho dos laudos e relatórios técnicos (é a
 * CONTRATADA do documento), então razão social e CNPJ são as colunas de frente.
 */
export default function PrestadoresPage() {
  const router = useRouter();
  const toast = useToast();
  const { podeEditar, podeExcluir } = usePermissoes();
  const [busca, setBusca] = useState("");

  const lista = useLista<Empresa>("/empresas/?page_size=500", "prestadores");
  const mutacao = useMutacao("remoção de prestador");
  const remocao = useConfirmacao<Empresa>();

  async function remover(e: Empresa) {
    const r = await mutacao.executar(() => api(`/empresas/${e.id}/`, { method: "DELETE" }));
    if (r.ok) {
      toast.sucesso("Prestador removido", { descricao: `“${e.nome}” saiu da lista.` });
      lista.removerItem((x) => x.id === e.id);
    } else {
      toast.erro(r.falha.titulo, { descricao: r.falha.descricao });
    }
  }

  const colunas: Coluna<Empresa>[] = [
    {
      chave: "nome",
      header: "Razão social",
      mobile: "titulo",
      valor: (e) => e.nome,
      celula: (e) => <span className="font-medium text-fg">{e.nome}</span>,
    },
    {
      chave: "cnpj",
      header: "CNPJ",
      mobile: "meta",
      tecnico: true,
      valor: (e) => e.cnpj,
      celula: (e) => (e.cnpj ? fmtCnpj(e.cnpj) : <SemDado />),
    },
    {
      chave: "local",
      header: "Cidade/UF",
      mobile: "meta",
      valor: (e) => e.cidade_uf,
      celula: (e) => (e.cidade_uf ? texto(e.cidade_uf) : <SemDado />),
    },
    {
      chave: "contato",
      header: "Contato",
      mobile: "meta",
      valor: (e) => e.contato_gestor,
      celula: (e) =>
        e.contato_gestor ? (
          <span>
            {e.contato_gestor}
            {e.departamento && (
              <span className="block text-xs text-fg-subtle">{e.departamento}</span>
            )}
          </span>
        ) : (
          <SemDado />
        ),
    },
    {
      chave: "telefone",
      header: "Telefone",
      mobile: "meta",
      tecnico: true,
      valor: (e) => e.telefone,
      celula: (e) => (e.telefone ? telefone(e.telefone) : <SemDado />),
    },
  ];

  const acoes = (e: Empresa): ItemMenu[] => {
    const itens: ItemMenu[] = [];
    if (podeEditar) itens.push({ label: "Editar cadastro", href: `/prestadores/${e.id}`, icon: Pencil });
    if (podeExcluir)
      itens.push({
        label: "Remover prestador",
        icon: Trash2,
        destrutivo: true,
        onClick: () => remocao.pedir(e),
      });
    return itens;
  };

  return (
    <PageBody>
      <PageHeader
        icon={Factory}
        title="Prestadores"
        description="As empresas contratadas que executam os serviços. Estes dados saem no cabeçalho dos laudos e relatórios técnicos."
        trilha={[{ label: "Prestadores" }]}
        actions={
          podeEditar ? (
            <Link href="/prestadores/novo">
              <Button icon={Plus}>Novo prestador</Button>
            </Link>
          ) : undefined
        }
      />

      <Toolbar
        busca={
          <SearchInput
            value={busca}
            onChange={setBusca}
            label="Buscar prestador"
            placeholder="Razão social, CNPJ, cidade…"
          />
        }
        resumo={lista.itens.length > 0 ? plural(lista.itens.length, "prestador", "prestadores") : undefined}
      />

      <DataTable<Empresa>
        itens={lista.itens}
        colunas={colunas}
        getId={(e) => e.id}
        busca={busca}
        camposBusca={(e) => [e.email, e.inscricao_estadual, e.uf, e.cidade]}
        carregando={lista.carregando}
        falha={lista.falha}
        onRetry={lista.recarregar}
        onLinhaClick={podeEditar ? (e) => router.push(`/prestadores/${e.id}`) : undefined}
        acoes={acoes}
        ordenacaoInicial={{ chave: "nome", direcao: "asc" }}
        legenda="Prestadores com razão social, CNPJ, cidade e contato"
        vazio={
          <EmptyState
            icon={Factory}
            title="Nenhum prestador cadastrado"
            description="Cadastre a empresa que executa os serviços: os dados dela identificam a CONTRATADA nos documentos técnicos."
            action={
              podeEditar ? (
                <Link href="/prestadores/novo">
                  <Button icon={Plus}>Novo prestador</Button>
                </Link>
              ) : undefined
            }
          />
        }
      />

      <ConfirmDialog
        aberto={!!remocao.alvo}
        onFechar={remocao.cancelar}
        onConfirmar={() => remocao.executar(remover)}
        enviando={mutacao.enviando}
        title="Remover este prestador?"
        confirmarLabel="Remover prestador"
        mensagem={
          <>
            O prestador <strong>{remocao.alvo?.nome}</strong> sairá das listagens.
          </>
        }
        detalhe="Documentos já emitidos com estes dados no cabeçalho não mudam."
        irreversivel
      />
    </PageBody>
  );
}
