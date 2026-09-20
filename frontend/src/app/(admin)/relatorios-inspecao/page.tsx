"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Eye, ScrollText } from "lucide-react";
import {
  Badge,
  DataTable,
  EmptyState,
  PageBody,
  PageHeader,
  SearchInput,
  SemDado,
  Toolbar,
  type Coluna,
} from "@/components/ds";
import { useLista } from "@/lib/recurso";
import { useClienteAtivo } from "@/lib/cliente-ativo";
import { data as fmtData, plural } from "@/lib/format";
import { ExigeClienteAtivo } from "@/features/clientes/exige-cliente-ativo";
import type { Relatorio } from "@/lib/types";

/**
 * Relatório técnico — o dossiê entregue ao cliente.
 *
 * Um número de relatório agrupa as rotas transferidas de uma mesma campanha de
 * inspeção; é a unidade de entrega. Por isso a coluna "Rotas" fica visível: ela
 * diz o tamanho do documento que está sendo montado.
 */
export default function RelatoriosInspecaoPage() {
  const router = useRouter();
  const { clienteAtivo } = useClienteAtivo();
  const [busca, setBusca] = useState("");

  const lista = useLista<Relatorio>(
    clienteAtivo ? `/relatorios-inspecao/?cliente=${clienteAtivo.id}&page_size=300` : null,
    "relatórios técnicos"
  );

  const colunas: Coluna<Relatorio>[] = [
    {
      chave: "numero",
      header: "Número",
      mobile: "titulo",
      tecnico: true,
      valor: (r) => r.numero,
      celula: (r) => <span className="font-semibold text-fg">{r.numero}</span>,
    },
    {
      chave: "tecnologia",
      header: "Tecnologia",
      mobile: "subtitulo",
      valor: (r) => r.tecnologia_nome,
      celula: (r) => <Badge tone="primary">{r.tecnologia_nome}</Badge>,
    },
    {
      chave: "inicio",
      header: "Início da campanha",
      mobile: "meta",
      tecnico: true,
      valor: (r) => r.data_inicio ?? "",
      celula: (r) => (r.data_inicio ? fmtData(r.data_inicio) : <SemDado />),
    },
    {
      chave: "termino",
      header: "Término",
      mobile: "meta",
      tecnico: true,
      valor: (r) => r.data_termino ?? "",
      celula: (r) => (r.data_termino ? fmtData(r.data_termino) : <SemDado>Em andamento</SemDado>),
    },
    {
      chave: "rotas",
      header: "Rotas",
      mobile: "meta",
      alinhamento: "direita",
      tecnico: true,
      valor: (r) => r.qtd_rotas,
      celula: (r) => r.qtd_rotas,
    },
  ];

  return (
    <PageBody>
      <PageHeader
        icon={ScrollText}
        title="Relatório técnico"
        description={
          clienteAtivo
            ? `Dossiês de ${clienteAtivo.nome_fantasia || clienteAtivo.nome}. Cada número agrupa as rotas de uma campanha de inspeção e vira um documento entregável.`
            : "Os dossiês técnicos são organizados por cliente."
        }
        trilha={[{ label: "Inspeções", href: "/inspecoes/campo" }, { label: "Relatório técnico" }]}
      />

      {!clienteAtivo ? (
        <ExigeClienteAtivo oQue="Os relatórios técnicos" />
      ) : (
        <>
          <Toolbar
            busca={
              <SearchInput
                value={busca}
                onChange={setBusca}
                label="Buscar relatório"
                placeholder="Número ou tecnologia…"
              />
            }
            resumo={lista.itens.length > 0 ? plural(lista.itens.length, "relatório") : undefined}
          />

          <DataTable<Relatorio>
            itens={lista.itens}
            colunas={colunas}
            getId={(r) => r.id}
            busca={busca}
            carregando={lista.carregando}
            falha={lista.falha}
            onRetry={lista.recarregar}
            onLinhaClick={(r) => router.push(`/relatorios-inspecao/${r.id}`)}
            acoes={(r) => [
              { label: "Abrir dossiê", href: `/relatorios-inspecao/${r.id}`, icon: Eye },
            ]}
            ordenacaoInicial={{ chave: "termino", direcao: "desc" }}
            legenda="Relatórios técnicos com número, tecnologia, período e quantidade de rotas"
            vazio={
              <EmptyState
                icon={ScrollText}
                title="Nenhum relatório técnico deste cliente"
                description="O número do relatório é atribuído quando uma rota é carregada para o campo — ele é o que amarra a campanha de inspeção ao documento final."
                comoFunciona={[
                  "Carregue as rotas da campanha em Análise de campo.",
                  "Refine os achados em Análise final e confirme o que vira ordem de serviço.",
                  "Abra o relatório para montar o dossiê e gerar o PDF do cliente.",
                ]}
              />
            }
          />
        </>
      )}
    </PageBody>
  );
}
