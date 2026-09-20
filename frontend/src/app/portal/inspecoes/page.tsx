"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ClipboardCheck, Eye, Pencil, Plus, Trash2 } from "lucide-react";
import {
  Badge,
  Button,
  ConfirmDialog,
  DataTable,
  EmptyState,
  EstadoBadge,
  PageBody,
  PageHeader,
  SearchInput,
  Toolbar,
  grauDe,
  pesoGravidade,
  useConfirmacao,
  useToast,
  type Coluna,
  type ItemMenu,
} from "@/components/ds";
import { api } from "@/lib/api";
import { useLista, useMutacao } from "@/lib/recurso";
import { useClienteAtivo } from "@/lib/cliente-ativo";
import { usePermissoes } from "@/lib/permissions";
import { data as fmtData, plural } from "@/lib/format";
import { ModalNovaInspecao } from "@/features/inspecoes/modal-nova-inspecao";
import type { Inspecao } from "@/lib/types";

/**
 * Portal do Cliente — Inspeções.
 *
 * Para o cliente existe UMA inspeção; a divisão interna entre "análise de campo"
 * e "análise final" é processo da contratada e não aparece aqui. O que ele quer
 * saber é: o que foi medido, quando, quantos pontos e qual o pior resultado.
 *
 * Criar/editar/excluir: só o Master da empresa (decisão de 2026-09-19) —
 * reaproveita a MESMA modal e a MESMA tela de lançar medições do admin.
 */
export default function PortalInspecoesPage() {
  const router = useRouter();
  const toast = useToast();
  const { pode } = usePermissoes();
  const podeGerenciar = pode("parque:gerenciar");
  const { clienteAtivo } = useClienteAtivo();
  const [busca, setBusca] = useState("");
  const [criando, setCriando] = useState(false);
  const { itens, carregando, falha, recarregar } = useLista<Inspecao>(
    "/inspecoes/?ordering=-data&page_size=200",
    "inspeções do portal"
  );
  const mutacao = useMutacao("remoção de inspeção");
  const remocao = useConfirmacao<Inspecao>();

  async function remover(insp: Inspecao) {
    const r = await mutacao.executar(() => api(`/inspecoes/${insp.id}/`, { method: "DELETE" }));
    if (r.ok) {
      toast.sucesso("Inspeção removida");
      recarregar();
    } else {
      toast.erro(r.falha.titulo, { descricao: r.falha.descricao });
    }
  }

  const colunas: Coluna<Inspecao>[] = [
    {
      chave: "data",
      header: "Data",
      mobile: "titulo",
      tecnico: true,
      valor: (i) => i.data,
      celula: (i) => <span className="font-semibold text-fg">{fmtData(i.data)}</span>,
    },
    {
      chave: "tipo",
      header: "Tecnologia aplicada",
      mobile: "subtitulo",
      valor: (i) => i.tipo_analise_display,
      celula: (i) => <span className="text-fg">{i.tipo_analise_display}</span>,
    },
    {
      chave: "medicoes",
      header: "Pontos medidos",
      mobile: "meta",
      alinhamento: "direita",
      tecnico: true,
      valor: (i) => i.qtd_medicoes,
      celula: (i) => i.qtd_medicoes,
    },
    {
      chave: "resultado",
      header: "Pior resultado",
      mobile: "meta",
      valor: (i) => pesoGravidade(grauDe(i.criticidade_maxima)),
      celula: (i) => <EstadoBadge grau={grauDe(i.criticidade_maxima)} mostrarSignificado />,
    },
    {
      chave: "status",
      header: "Situação",
      mobile: "meta",
      valor: (i) => i.status_display,
      celula: (i) => <Badge tone="neutral">{i.status_display}</Badge>,
    },
  ];

  return (
    <PageBody>
      <PageHeader
        icon={ClipboardCheck}
        title="Inspeções"
        description="Todas as coletas realizadas no seu parque, da mais recente para a mais antiga. Abra uma inspeção para ver os pontos medidos e o resultado de cada um."
        trilha={[{ label: "Inspeções" }]}
        actions={
          podeGerenciar ? (
            <Button icon={Plus} onClick={() => setCriando(true)}>
              Nova inspeção
            </Button>
          ) : undefined
        }
      />

      <Toolbar
        busca={
          <SearchInput
            value={busca}
            onChange={setBusca}
            label="Buscar inspeção"
            placeholder="Tecnologia, data, situação…"
          />
        }
        resumo={itens.length > 0 ? plural(itens.length, "inspeção", "inspeções") : undefined}
      />

      <DataTable<Inspecao>
        itens={itens}
        colunas={colunas}
        getId={(i) => i.id}
        busca={busca}
        camposBusca={(i) => [i.observacoes, i.status_display]}
        carregando={carregando}
        falha={falha}
        onRetry={recarregar}
        onLinhaClick={(i) => router.push(`/portal/inspecoes/${i.id}`)}
        acoes={(i): ItemMenu[] => [
          { label: "Ver medições", href: `/portal/inspecoes/${i.id}`, icon: Eye },
          ...(podeGerenciar
            ? [
                { label: "Editar", href: `/portal/inspecoes/editar/${i.id}`, icon: Pencil },
                {
                  label: "Remover",
                  icon: Trash2,
                  destrutivo: true,
                  onClick: () => remocao.pedir(i),
                } as ItemMenu,
              ]
            : []),
        ]}
        ordenacaoInicial={{ chave: "data", direcao: "desc" }}
        tomDaLinha={(i) => (i.criticidade_maxima === "CRITICO" ? "danger" : undefined)}
        legenda="Inspeções realizadas, com data, tecnologia, pontos medidos e pior resultado"
        vazio={
          <EmptyState
            icon={ClipboardCheck}
            title="Nenhuma inspeção registrada ainda"
            description="Assim que a primeira rota for executada na sua planta, ela aparece aqui com todos os pontos medidos."
            action={
              podeGerenciar ? (
                <Button icon={Plus} onClick={() => setCriando(true)}>
                  Nova inspeção
                </Button>
              ) : undefined
            }
            comoFunciona={[
              "A rota de inspeção é definida a partir do seu parque cadastrado.",
              "O técnico coleta as medições em campo com os instrumentos calibrados.",
              "A análise compara cada ponto com o limite da norma e classifica o resultado.",
            ]}
          />
        }
      />

      {podeGerenciar && (
        <ModalNovaInspecao
          aberto={criando}
          clienteSugerido={clienteAtivo?.id ?? ""}
          onFechar={() => setCriando(false)}
          onCriada={(id) => {
            setCriando(false);
            toast.sucesso("Inspeção criada", { descricao: "Agora lance as medições coletadas." });
            router.push(`/portal/inspecoes/editar/${id}`);
          }}
        />
      )}

      <ConfirmDialog
        aberto={!!remocao.alvo}
        onFechar={remocao.cancelar}
        onConfirmar={() => remocao.executar(remover)}
        enviando={remocao.enviando}
        title="Remover esta inspeção?"
        confirmarLabel="Remover"
        mensagem="As medições lançadas nesta inspeção são removidas junto."
        irreversivel
      />
    </PageBody>
  );
}
