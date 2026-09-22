"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ClipboardCheck, Eye } from "lucide-react";
import {
  Badge,
  DataTable,
  EmptyState,
  EstadoBadge,
  PageBody,
  PageHeader,
  SearchInput,
  Toolbar,
  grauDe,
  pesoGravidade,
  type Coluna,
  type ItemMenu,
} from "@/components/ds";
import { useLista } from "@/lib/recurso";
import { data as fmtData, plural } from "@/lib/format";
import type { Inspecao } from "@/lib/types";

/**
 * Portal do Cliente — Inspeções.
 *
 * Para o cliente existe UMA inspeção; a divisão interna entre "análise de campo"
 * e "análise final" é processo da contratada e não aparece aqui. O que ele quer
 * saber é: o que foi medido, quando, quantos pontos e qual o pior resultado.
 *
 * Tela de consulta: as inspeções são lançadas pela equipe da ThermoProActive
 * (decisão de 2026-09-21). O cliente abre uma inspeção para ver os pontos
 * medidos e o resultado de cada um.
 */
export default function PortalInspecoesPage() {
  const router = useRouter();
  const [busca, setBusca] = useState("");
  const { itens, carregando, falha, recarregar } = useLista<Inspecao>(
    "/inspecoes/?ordering=-data&page_size=200",
    "inspeções do portal"
  );

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
        ]}
        ordenacaoInicial={{ chave: "data", direcao: "desc" }}
        tomDaLinha={(i) => (i.criticidade_maxima === "CRITICO" ? "danger" : undefined)}
        legenda="Inspeções realizadas, com data, tecnologia, pontos medidos e pior resultado"
        vazio={
          <EmptyState
            icon={ClipboardCheck}
            title="Nenhuma inspeção registrada ainda"
            description="Assim que a primeira rota for executada na sua planta, ela aparece aqui com todos os pontos medidos."
            comoFunciona={[
              "A rota de inspeção é definida a partir do seu parque cadastrado.",
              "O técnico coleta as medições em campo com os instrumentos calibrados.",
              "A análise compara cada ponto com o limite da norma e classifica o resultado.",
            ]}
          />
        }
      />

    </PageBody>
  );
}
