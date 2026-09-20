"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Activity, CornerDownRight, Pencil, Plus, Trash2 } from "lucide-react";
import {
  Badge,
  Button,
  ClasseAtivoBadge,
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
import { plural, texto } from "@/lib/format";
import { ExigeClienteAtivo } from "@/features/clientes/exige-cliente-ativo";
import type { Equipamento } from "@/lib/types";

/**
 * Equipamentos do cliente em atendimento.
 *
 * A ordenação padrão preserva a ÁRVORE (Caldeira → Exaustor): sub-item aparece
 * logo abaixo do equipamento principal, indentado. Isso só faz sentido sem
 * busca ativa — ao buscar, a lista vira uma lista plana ordenada por TAG, porque
 * aí o que importa é achar, não navegar a hierarquia.
 */
export default function EquipamentosPage() {
  const router = useRouter();
  const toast = useToast();
  const { podeEditar, podeExcluir } = usePermissoes();
  const { clienteAtivo } = useClienteAtivo();
  const [busca, setBusca] = useState("");

  const lista = useLista<Equipamento>(
    clienteAtivo
      ? `/equipamentos/?page_size=500&setor__area__cliente=${clienteAtivo.id}`
      : null,
    "equipamentos do cliente"
  );
  const mutacao = useMutacao("remoção de equipamento");
  const remocao = useConfirmacao<Equipamento>();

  const emArvore = useMemo(() => {
    if (busca.trim()) return lista.itens;
    const porTag = (a: Equipamento, b: Equipamento) =>
      String(a.tag ?? "").localeCompare(String(b.tag ?? ""), "pt-BR", { numeric: true });

    const ordenados: Equipamento[] = [];
    const empilhar = (paiId: number | null, profundidade: number) => {
      for (const e of lista.itens.filter((x) => x.equipamento_pai === paiId).sort(porTag)) {
        ordenados.push(e);
        if (profundidade < 5) empilhar(e.id, profundidade + 1);
      }
    };
    empilhar(null, 0);
    // Sub-item cujo pai não veio na página não pode desaparecer da lista.
    for (const e of lista.itens) if (!ordenados.includes(e)) ordenados.push(e);
    return ordenados;
  }, [lista.itens, busca]);

  async function remover(e: Equipamento) {
    const r = await mutacao.executar(() => api(`/equipamentos/${e.id}/`, { method: "DELETE" }));
    if (r.ok) {
      toast.sucesso("Equipamento removido", { descricao: `A TAG ${e.tag} saiu da lista.` });
      lista.removerItem((x) => x.id === e.id);
    } else {
      toast.erro(r.falha.titulo, { descricao: r.falha.descricao });
    }
  }

  const colunas: Coluna<Equipamento>[] = [
    {
      chave: "tag",
      header: "TAG",
      mobile: "titulo",
      tecnico: true,
      // Sem busca, a ordenação da árvore é a da tela; a coluna não reordena.
      ordenavel: !!busca.trim(),
      valor: (e) => e.tag,
      celula: (e) => (
        <span
          className="inline-flex items-center gap-1.5 font-semibold text-fg"
          style={{ paddingLeft: busca.trim() ? 0 : `${e.nivel * 12}px` }}
        >
          {e.is_subitem && !busca.trim() && (
            <CornerDownRight className="h-3 w-3 shrink-0 text-fg-subtle" aria-hidden="true" />
          )}
          {e.tag}
        </span>
      ),
    },
    {
      chave: "nome",
      header: "Equipamento",
      mobile: "subtitulo",
      valor: (e) => e.nome,
      celula: (e) => (
        <span>
          <span className="text-fg">{e.nome}</span>
          {e.qtd_subitens > 0 && (
            <Badge tone="neutral" className="ml-2">
              {plural(e.qtd_subitens, "sub-item", "sub-itens")}
            </Badge>
          )}
          {e.componentes?.length > 0 && (
            <span className="block truncate text-xs text-fg-subtle">
              {e.componentes.map((c) => c.nome).join(" · ")}
            </span>
          )}
        </span>
      ),
    },
    {
      chave: "local",
      header: "Área / Setor",
      mobile: "meta",
      valor: (e) => `${e.area_nome} ${e.setor_nome}`,
      celula: (e) =>
        e.setor_nome ? (
          <span className="text-fg-muted">
            {e.area_nome}
            <span className="text-fg-subtle"> · </span>
            {e.setor_nome}
          </span>
        ) : (
          <SemDado />
        ),
    },
    {
      chave: "tipo",
      header: "Tipo",
      mobile: "meta",
      valor: (e) => e.tipo_equipamento_nome ?? e.tipo,
      celula: (e) => texto(e.tipo_equipamento_nome || e.tipo),
    },
    {
      chave: "fabricante",
      header: "Fabricante",
      mobile: "oculta",
      valor: (e) => e.fabricante,
      celula: (e) => (e.fabricante ? texto(e.fabricante) : <SemDado />),
    },
    {
      chave: "iso",
      header: "Classe ISO",
      mobile: "meta",
      alinhamento: "centro",
      valor: (e) => e.classe_iso,
      celula: (e) =>
        e.classe_iso ? (
          <Badge tone="primary" title={e.classe_iso_display}>
            {e.classe_iso}
          </Badge>
        ) : (
          <SemDado />
        ),
    },
    {
      chave: "criticidade",
      header: "Classe do ativo",
      mobile: "oculta",
      alinhamento: "centro",
      valor: (e) => e.criticidade,
      celula: (e) => <ClasseAtivoBadge value={e.criticidade} label={e.criticidade_display} />,
    },
  ];

  const acoes = (e: Equipamento): ItemMenu[] => {
    const itens: ItemMenu[] = [];
    if (podeEditar)
      itens.push({ label: "Editar equipamento", href: `/equipamentos/${e.id}`, icon: Pencil });
    if (podeExcluir)
      itens.push({
        label: "Remover equipamento",
        icon: Trash2,
        destrutivo: true,
        onClick: () => remocao.pedir(e),
      });
    return itens;
  };

  return (
    <PageBody>
      <PageHeader
        icon={Activity}
        title="Equipamentos"
        description={
          clienteAtivo
            ? `Parque de ${clienteAtivo.nome_fantasia || clienteAtivo.nome}, organizado por área e setor. Sub-itens aparecem indentados sob o equipamento principal.`
            : "Máquinas monitoradas, organizadas por Cliente → Área → Setor."
        }
        trilha={[{ label: "Clientes", href: "/clientes" }, { label: "Equipamentos" }]}
        actions={
          podeEditar && clienteAtivo ? (
            <Link href="/equipamentos/novo">
              <Button icon={Plus}>Novo equipamento</Button>
            </Link>
          ) : undefined
        }
      />

      {!clienteAtivo ? (
        <ExigeClienteAtivo oQue="Os equipamentos" />
      ) : (
        <>
          <Toolbar
            busca={
              <SearchInput
                value={busca}
                onChange={setBusca}
                label="Buscar equipamento"
                placeholder="TAG, nome, nº de série, fabricante…"
              />
            }
            resumo={
              lista.itens.length > 0
                ? busca.trim()
                  ? "Buscando em toda a lista — a hierarquia volta ao limpar a busca."
                  : plural(lista.itens.length, "equipamento")
                : undefined
            }
          />

          <DataTable<Equipamento>
            itens={emArvore}
            colunas={colunas}
            getId={(e) => e.id}
            busca={busca}
            camposBusca={(e) => [e.numero_serie, e.modelo, e.caminho]}
            carregando={lista.carregando}
            falha={lista.falha}
            onRetry={lista.recarregar}
            onLinhaClick={podeEditar ? (e) => router.push(`/equipamentos/${e.id}`) : undefined}
            acoes={acoes}
            porPagina={20}
            legenda="Equipamentos com TAG, nome, área, setor, tipo, fabricante e classe"
            vazio={
              <EmptyState
                icon={Activity}
                title="Este cliente ainda não tem equipamentos"
                description="Cadastre as máquinas do parque para poder montar as rotas de inspeção e registrar medições."
                action={
                  podeEditar ? (
                    <Link href="/equipamentos/novo">
                      <Button icon={Plus}>Novo equipamento</Button>
                    </Link>
                  ) : undefined
                }
                comoFunciona={[
                  "Crie as áreas e os setores da planta em Dados do cliente.",
                  "Cadastre cada equipamento com TAG, tipo e dados de placa.",
                  "Agrupe os equipamentos em rotas de inspeção por periodicidade.",
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
        title="Remover este equipamento?"
        confirmarLabel="Remover equipamento"
        mensagem={
          <>
            O equipamento <strong>{remocao.alvo?.tag}</strong> — {remocao.alvo?.nome} — sairá do
            parque monitorado.
          </>
        }
        detalhe={
          remocao.alvo?.qtd_subitens
            ? `Ele tem ${plural(remocao.alvo.qtd_subitens, "sub-item", "sub-itens")} vinculado(s), que também deixam de aparecer.`
            : "As medições já registradas continuam no histórico técnico."
        }
        irreversivel
      />
    </PageBody>
  );
}
