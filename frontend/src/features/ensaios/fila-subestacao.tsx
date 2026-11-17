"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { FlaskConical } from "lucide-react";
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
import { rotuloEnsaio } from "./cartao-ensaio";
import type { EnsaioNaFila, ItemEnsaio } from "./tipos";

/* ==========================================================================
   Análise final → Ensaios de subestação: os equipamentos (TC, TP, DJ, CS e RP) das
   rotas já transferidas, com o que ainda falta lançar (registro de campo, placa e
   medições dos ensaios solicitados). Mesma tela da fila do transformador.
   ========================================================================== */

type Recorte = "pendentes" | "todos";

const pendente = (t: ItemEnsaio) => !t.registro || t.pendentes > 0;

function tomDoEnsaio(e: EnsaioNaFila): Tom {
  if (e.situacao === "REALIZADO") return "success";
  if (e.situacao === "NAO_COLETADO" || e.situacao === "NAO_REALIZADO") return "warning";
  return "neutral";
}

function textoDoEnsaio(e: EnsaioNaFila): string {
  const situacao = {
    REALIZADO: "realizado", NAO_COLETADO: "não coletado", NAO_REALIZADO: "não realizado",
    SEM_RESULTADO: "aguardando resultado",
  }[e.situacao ?? "SEM_RESULTADO"];
  return `${rotuloEnsaio(e.sigla)}: ${e.solicitado ? "solicitado" : "não solicitado"}, ${situacao}`;
}

export function FilaEnsaiosSubestacao({ clienteId }: { clienteId: number }) {
  const router = useRouter();
  const [recorte, setRecorte] = useState<Recorte>("pendentes");
  const [busca, setBusca] = useState("");
  const lista = useLista<ItemEnsaio>(
    `/subestacao-inspecao/?carregamento__cliente=${clienteId}&carregamento__status=TRANSFERIDA&page_size=500`,
    "ensaios de subestação"
  );
  const filtrados = recorte === "pendentes" ? lista.itens.filter(pendente) : lista.itens;
  const abrir = (t: ItemEnsaio) => router.push(`/inspecoes/final/subestacao/${t.id}`);

  const colunas: Coluna<ItemEnsaio>[] = [
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
      chave: "relatorio",
      header: "Relatório",
      mobile: "subtitulo",
      tecnico: true,
      valor: (t) => t.numero ?? "",
      celula: (t) => (t.numero ? <span className="text-fg">{t.numero}</span> : <SemDado />),
    },
    {
      chave: "coleta",
      header: "Ensaio",
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
            {visiveis.map((e) => (
              <Badge key={e.sigla} tone={tomDoEnsaio(e)} title={textoDoEnsaio(e)}>
                {rotuloEnsaio(e.sigla)}
              </Badge>
            ))}
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
          <Badge tone="warning">Sem registro de campo</Badge>
        ) : t.pendentes ? (
          <Badge tone="warning">{plural(t.pendentes, "medição pendente", "medições pendentes")}</Badge>
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
        <LoadingState variante="tabela" linhas={6} colunas={5} label="Carregando equipamentos…" />
      ) : (
        <DataTable<ItemEnsaio>
          itens={filtrados}
          colunas={colunas}
          getId={(t) => t.id}
          busca={busca}
          camposBusca={(t) => [t.tecnologia_nome, t.area_nome, t.setor_nome]}
          falha={lista.falha}
          onRetry={lista.recarregar}
          onLinhaClick={abrir}
          ordenacaoInicial={{ chave: "coleta", direcao: "desc" }}
          porPagina={15}
          legenda="Equipamentos das rotas de ensaios elétricos de subestação, com os ensaios e o que falta lançar"
          vazio={
            recorte === "pendentes" && lista.itens.length > 0 ? (
              <EmptyState compacto icon={FlaskConical} title="Nenhuma medição pendente"
                description="Todos os equipamentos transferidos têm registro e medições dos ensaios solicitados." />
            ) : (
              <EmptyState
                icon={FlaskConical}
                title="Nenhum equipamento de subestação transferido deste cliente"
                description="Os equipamentos aparecem aqui quando uma rota de TC, TP, disjuntor, chave seccionadora ou relé é transferida do campo."
                comoFunciona={[
                  "Carregue a rota em Análise de campo com uma tecnologia de ensaios elétricos de subestação.",
                  "Em cada equipamento, dê a condição, registre os ensaios solicitados e os dados de placa.",
                  "Transfira a rota e lance aqui as medições e os laudos.",
                ]}
              />
            )
          }
        />
      )}
    </div>
  );
}
