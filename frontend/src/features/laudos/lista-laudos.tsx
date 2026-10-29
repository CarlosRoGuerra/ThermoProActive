"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Eye, FileText, Printer, ScrollText } from "lucide-react";
import {
  Badge,
  CriticidadeBadge,
  DataTable,
  EmptyState,
  PageBody,
  PageHeader,
  SearchInput,
  SemDado,
  Toolbar,
  type Coluna,
  type ItemMenu,
} from "@/components/ds";
import { useLista } from "@/lib/recurso";
import { data as fmtData, plural, texto } from "@/lib/format";
import type { Laudo } from "@/lib/types";

/**
 * Listagem de laudos — compartilhada pelos dois portais.
 *
 * O backend já entrega ao cliente somente os laudos EMITIDOS da própria empresa
 * (LaudoViewSet.get_queryset), então a mesma consulta serve às duas áreas: o que
 * muda é o texto e para onde os links apontam.
 */
export function ListaLaudos({
  baseHref,
  ehCliente,
}: {
  /** Prefixo das rotas de detalhe nesta área. */
  baseHref: "/laudos" | "/portal/laudos";
  ehCliente: boolean;
}) {
  const router = useRouter();
  const [busca, setBusca] = useState("");
  const { itens, carregando, falha, recarregar } = useLista<Laudo>(
    "/laudos/?ordering=-criado_em&page_size=200",
    "laudos"
  );

  const colunas: Coluna<Laudo>[] = [
    {
      chave: "numero",
      header: "Número",
      mobile: "titulo",
      tecnico: true,
      valor: (l) => l.numero,
      celula: (l) => (
        <span className="font-semibold text-fg">
          {l.numero}
          {l.versao > 1 && <span className="ml-1 text-xs font-normal text-fg-subtle">v{l.versao}</span>}
        </span>
      ),
    },
    {
      chave: "titulo",
      header: "Assunto",
      mobile: "subtitulo",
      valor: (l) => l.titulo,
      celula: (l) => <span className="text-fg">{texto(l.titulo)}</span>,
    },
    ...(ehCliente
      ? []
      : ([
          {
            chave: "cliente",
            header: "Cliente",
            mobile: "meta",
            valor: (l: Laudo) => l.cliente_nome,
            celula: (l: Laudo) => texto(l.cliente_nome),
          },
        ] as Coluna<Laudo>[])),
    {
      chave: "criticidade",
      header: "Criticidade",
      mobile: "meta",
      valor: (l) => l.criticidade_geral,
      celula: (l) =>
        l.criticidade_geral ? <CriticidadeBadge value={l.criticidade_geral} /> : <SemDado />,
    },
    {
      chave: "emissao",
      header: "Emissão",
      mobile: "meta",
      tecnico: true,
      valor: (l) => l.data_emissao ?? "",
      celula: (l) =>
        l.data_emissao ? fmtData(l.data_emissao) : <SemDado>Não emitido</SemDado>,
    },
    {
      chave: "status",
      header: "Situação",
      mobile: "meta",
      valor: (l) => l.status_display,
      celula: (l) => (
        <Badge tone={l.status === "EMITIDO" ? "success" : "warning"}>{l.status_display}</Badge>
      ),
    },
  ];

  const acoes = (l: Laudo): ItemMenu[] => [
    { label: "Abrir laudo", href: `${baseHref}/${l.id}`, icon: Eye },
    // O Relatório Técnico completo só existe na área interna: a rota do portal
    // foi revertida junto com o documento (ver docs/08-FRONTEND-REDESIGN.md).
    ...(ehCliente
      ? []
      : l.status === "RASCUNHO" ? [
          {
            label: "Consultar fonte do rascunho",
            href: l.relatorio_origem ? `/relatorios-inspecao/${l.relatorio_origem}` : `${baseHref}/${l.id}/relatorio`,
            icon: FileText,
          } as ItemMenu,
        ] : []),
    { label: l.pdf_disponivel ? "Abrir documento e baixar PDF" : "Consultar prévia", href: `${baseHref}/${l.id}`, icon: Printer },
  ];

  return (
    <PageBody>
      <PageHeader
        icon={ScrollText}
        title="Laudos técnicos"
        description={
          ehCliente
            ? "Consulte o conteúdo emitido, a aprovação registrada e o PDF disponibilizado pela equipe técnica."
            : "Laudos gerados a partir das inspeções, em ordem de criação (Anexo I 2.5)."
        }
        trilha={[{ label: "Laudos técnicos" }]}
      />

      <Toolbar
        busca={
          <SearchInput
            value={busca}
            onChange={setBusca}
            label="Buscar laudo"
            placeholder="Número, assunto…"
          />
        }
        resumo={itens.length > 0 ? plural(itens.length, "laudo") : undefined}
      />

      <DataTable<Laudo>
        itens={itens}
        colunas={colunas}
        getId={(l) => l.id}
        busca={busca}
        carregando={carregando}
        falha={falha}
        onRetry={recarregar}
        onLinhaClick={(l) => router.push(`${baseHref}/${l.id}`)}
        acoes={acoes}
        ordenacaoInicial={{ chave: "emissao", direcao: "desc" }}
        legenda="Laudos técnicos com número, assunto, criticidade, data de emissão e situação"
        vazio={
          ehCliente ? (
            <EmptyState
              icon={ScrollText}
              title="Nenhum laudo disponível ainda"
              description="Os laudos aparecem aqui depois que a equipe conclui a análise e emite o documento."
              comoFunciona={[
                "A equipe executa a rota de inspeção na sua planta.",
                "A equipe analisa as medições pelos critérios aplicáveis.",
                "O responsável aprova a emissão e o documento é disponibilizado neste portal.",
              ]}
            />
          ) : (
            <EmptyState
              icon={ScrollText}
              title="Nenhum laudo emitido"
              description="Os laudos são gerados a partir de uma inspeção concluída, em Inspeções → Análise final."
            />
          )
        }
      />
    </PageBody>
  );
}
