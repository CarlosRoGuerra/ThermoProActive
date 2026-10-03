"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Droplets } from "lucide-react";
import {
  Badge,
  DataTable,
  EmptyState,
  LoadingState,
  SearchInput,
  SegmentedControl,
  SemDado,
  Toolbar,
  type Coluna,
  type Tom,
} from "@/components/ds";
import { useLista } from "@/lib/recurso";
import { data as fmtData, plural, texto } from "@/lib/format";
import type { EnsaioNaFila, FluidoInspecao } from "./tipos";

/* ==========================================================================
   Análise final → Ensaios de fluidos: os equipamentos das rotas de fluidos
   lubrificantes e hidráulicos já transferidas, com o que falta lançar (coleta e
   resultados do laboratório dos ensaios solicitados).
   ========================================================================== */

type Recorte = "pendentes" | "todos";

const pendente = (t: FluidoInspecao) => !t.registro || t.pendentes > 0;

function tomDoEnsaio(e: EnsaioNaFila): Tom {
  if (e.situacao === "REALIZADO") return "success";
  if (e.situacao === "NAO_COLETADO" || e.situacao === "NAO_REALIZADO") return "warning";
  return "neutral";
}

const APLICACAO: Record<string, string> = { LUBRIFICANTE: "Lubrificante", HIDRAULICO: "Hidráulico" };

export function FilaEnsaiosFluido({ clienteId }: { clienteId: number }) {
  const router = useRouter();
  const [recorte, setRecorte] = useState<Recorte>("pendentes");
  const [busca, setBusca] = useState("");
  const lista = useLista<FluidoInspecao>(
    `/fluidos-inspecao/?carregamento__cliente=${clienteId}&carregamento__status=TRANSFERIDA&page_size=500`,
    "ensaios de fluidos"
  );
  const filtrados = recorte === "pendentes" ? lista.itens.filter(pendente) : lista.itens;
  const abrir = (t: FluidoInspecao) => router.push(`/inspecoes/final/fluido/${t.id}`);

  const colunas: Coluna<FluidoInspecao>[] = [
    {
      chave: "equipamento",
      header: "Equipamento",
      mobile: "titulo",
      valor: (t) => `${t.equipamento_tag} ${t.equipamento_nome}`,
      celula: (t) => (
        <span>
          <span className="data font-medium text-fg">{t.equipamento_tag}</span>
          <span className="block truncate text-xs text-fg-muted">{texto(t.equipamento_nome)}</span>
        </span>
      ),
    },
    {
      chave: "fluido",
      header: "Fluido",
      mobile: "subtitulo",
      valor: (t) => t.fluido ?? "",
      celula: (t) =>
        t.aplicacao ? (
          <span>
            <span className="text-fg">{APLICACAO[t.aplicacao]}</span>
            {t.fluido && <span className="block truncate text-xs text-fg-muted">{t.fluido}</span>}
          </span>
        ) : (
          <SemDado />
        ),
    },
    {
      chave: "relatorio",
      header: "Relatório",
      mobile: "meta",
      tecnico: true,
      valor: (t) => t.numero ?? "",
      celula: (t) => (t.numero ? <span className="text-fg">{t.numero}</span> : <SemDado />),
    },
    {
      chave: "coleta",
      header: "Coleta",
      mobile: "meta",
      tecnico: true,
      valor: (t) => t.registro?.data ?? t.data_coleta,
      celula: (t) => fmtData(t.registro?.data ?? t.data_coleta),
    },
    {
      chave: "ensaios",
      header: "Ensaios",
      mobile: "meta",
      valor: (t) => t.ensaios.filter((e) => e.solicitado).length,
      celula: (t) => {
        const visiveis = t.ensaios.filter((e) => e.solicitado || e.situacao);
        return visiveis.length ? (
          <span className="flex flex-wrap gap-1">
            {visiveis.map((e) => <Badge key={e.sigla} tone={tomDoEnsaio(e)} title={e.nome}>{e.sigla}</Badge>)}
          </span>
        ) : (
          <SemDado>Nenhum solicitado</SemDado>
        );
      },
    },
    {
      chave: "situacao",
      header: "Situação",
      mobile: "meta",
      valor: (t) => (!t.registro ? 2 : t.pendentes ? 1 : 0),
      celula: (t) =>
        !t.registro ? (
          <Badge tone="warning">Sem coleta registrada</Badge>
        ) : t.pendentes ? (
          <Badge tone="warning">{plural(t.pendentes, "resultado pendente", "resultados pendentes")}</Badge>
        ) : (
          <Badge tone="success">Em dia</Badge>
        ),
    },
  ];

  return (
    <div className="space-y-4">
      <Toolbar
        busca={<SearchInput value={busca} onChange={setBusca} label="Buscar equipamento" placeholder="TAG, relatório…" />}
        filtros={
          <SegmentedControl
            label="Recorte dos equipamentos"
            tamanho="sm"
            valor={recorte}
            onMudar={setRecorte}
            opcoes={[
              { valor: "pendentes", label: "Com pendência" },
              { valor: "todos", label: "Todos" },
            ]}
          />
        }
        resumo={
          lista.itens.length > 0
            ? `${filtrados.length} de ${plural(lista.itens.length, "equipamento", "equipamentos")}`
            : undefined
        }
      />
      {lista.carregando ? (
        <LoadingState variante="tabela" linhas={6} colunas={6} label="Carregando equipamentos…" />
      ) : (
        <DataTable<FluidoInspecao>
          itens={filtrados}
          colunas={colunas}
          getId={(t) => t.id}
          busca={busca}
          camposBusca={(t) => [t.tecnologia_nome, t.area_nome, t.setor_nome, t.fluido ?? ""]}
          falha={lista.falha}
          onRetry={lista.recarregar}
          onLinhaClick={abrir}
          ordenacaoInicial={{ chave: "coleta", direcao: "desc" }}
          porPagina={15}
          legenda="Equipamentos das rotas de fluidos lubrificantes e hidráulicos, com os ensaios e o que falta lançar"
          vazio={
            recorte === "pendentes" && lista.itens.length > 0 ? (
              <EmptyState compacto icon={Droplets} title="Nenhum resultado pendente"
                description="Todos os equipamentos transferidos têm coleta e os resultados dos ensaios solicitados." />
            ) : (
              <EmptyState
                icon={Droplets}
                title="Nenhum equipamento de fluidos transferido deste cliente"
                description="Os equipamentos aparecem aqui quando uma rota de fluidos lubrificantes e hidráulicos é transferida do campo."
                comoFunciona={[
                  "Carregue a rota em Análise de campo com a tecnologia de fluidos lubrificantes e hidráulicos.",
                  "Em cada equipamento, dê a condição e registre a coleta da amostra.",
                  "Transfira a rota e lance aqui os resultados do laboratório (FQ, EF e, nos hidráulicos, CP).",
                ]}
              />
            )
          }
        />
      )}
    </div>
  );
}
