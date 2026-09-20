"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ClipboardList, Eye, Plus } from "lucide-react";
import {
  Badge,
  Button,
  DataTable,
  EmptyState,
  EstadoBadge,
  PageBody,
  PageHeader,
  SearchInput,
  Toolbar,
  grauDe,
  pesoGravidade,
  useToast,
  type Coluna,
} from "@/components/ds";
import { useLista } from "@/lib/recurso";
import { useClienteAtivo } from "@/lib/cliente-ativo";
import { usePermissoes } from "@/lib/permissions";
import { data as fmtData, plural, texto } from "@/lib/format";
import { ModalNovaInspecao } from "@/features/inspecoes/modal-nova-inspecao";
import type { Inspecao } from "@/lib/types";

/* ==========================================================================
   Inspeções (coleta direta)
   --------------------------------------------------------------------------
   Caminho direto de coleta, sem carregar rota: usado para medição pontual e
   para as tecnologias que não têm rota montada. O fluxo completo campo →
   escritório fica em Inspeções → Análise de campo.

   A criação foi para um modal. Antes ela era um bloco fixo no topo da página,
   ocupando espaço permanente para uma ação ocasional e empurrando a lista —
   que é o motivo real de alguém abrir esta tela — para fora da primeira dobra.
   ========================================================================== */

export default function InspecoesPage() {
  const router = useRouter();
  const toast = useToast();
  const { podeEditar } = usePermissoes();
  const { clienteAtivo } = useClienteAtivo();
  const [busca, setBusca] = useState("");
  const [criando, setCriando] = useState(false);

  const lista = useLista<Inspecao>("/inspecoes/?ordering=-data&page_size=300", "inspeções");

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
      chave: "cliente",
      header: "Cliente",
      mobile: "subtitulo",
      valor: (i) => i.cliente_nome,
      celula: (i) => texto(i.cliente_nome),
    },
    {
      chave: "tipo",
      header: "Tecnologia",
      mobile: "meta",
      valor: (i) => i.tipo_analise_display,
      celula: (i) => <Badge tone="primary">{i.tipo_analise_display}</Badge>,
    },
    {
      chave: "tecnico",
      header: "Responsável",
      mobile: "oculta",
      valor: (i) => i.tecnico_nome,
      celula: (i) => texto(i.tecnico_nome),
    },
    {
      chave: "medicoes",
      header: "Medições",
      mobile: "meta",
      alinhamento: "direita",
      tecnico: true,
      valor: (i) => i.qtd_medicoes,
      celula: (i) => i.qtd_medicoes,
    },
    {
      chave: "criticidade",
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
        icon={ClipboardList}
        title="Inspeções"
        description="Coleta direta de medições, sem carregar rota. Para o fluxo completo de campo, use Inspeções → Análise de campo."
        trilha={[{ label: "Inspeções" }]}
        actions={
          podeEditar ? (
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
            placeholder="Cliente, tecnologia, responsável…"
          />
        }
        resumo={lista.itens.length > 0 ? plural(lista.itens.length, "inspeção", "inspeções") : undefined}
      />

      <DataTable<Inspecao>
        itens={lista.itens}
        colunas={colunas}
        getId={(i) => i.id}
        busca={busca}
        camposBusca={(i) => [i.observacoes, i.status_display]}
        carregando={lista.carregando}
        falha={lista.falha}
        onRetry={lista.recarregar}
        onLinhaClick={(i) => router.push(`/inspecoes/${i.id}`)}
        acoes={(i) => [{ label: "Abrir inspeção", href: `/inspecoes/${i.id}`, icon: Eye }]}
        ordenacaoInicial={{ chave: "data", direcao: "desc" }}
        tomDaLinha={(i) => (i.criticidade_maxima === "CRITICO" ? "danger" : undefined)}
        legenda="Inspeções com data, cliente, tecnologia, medições e pior resultado"
        vazio={
          <EmptyState
            icon={ClipboardList}
            title="Nenhuma inspeção registrada"
            description="Crie uma inspeção para lançar medições pontuais, ou use a Análise de campo para coletar uma rota inteira."
            action={
              podeEditar ? (
                <Button icon={Plus} onClick={() => setCriando(true)}>
                  Nova inspeção
                </Button>
              ) : undefined
            }
            secundaria={
              <Button variant="secondary" onClick={() => router.push("/inspecoes/campo")}>
                Ir para Análise de campo
              </Button>
            }
          />
        }
      />

      <ModalNovaInspecao
        aberto={criando}
        clienteSugerido={clienteAtivo?.id ?? ""}
        onFechar={() => setCriando(false)}
        onCriada={(id) => {
          setCriando(false);
          toast.sucesso("Inspeção criada", { descricao: "Agora lance as medições coletadas." });
          router.push(`/inspecoes/${id}`);
        }}
      />
    </PageBody>
  );
}
