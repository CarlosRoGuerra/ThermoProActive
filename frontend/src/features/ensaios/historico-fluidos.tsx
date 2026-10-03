"use client";

import { useState } from "react";
import { Droplets } from "lucide-react";
import {
  Badge,
  Card,
  CardHeader,
  DataTable,
  EmptyState,
  LoadingState,
  SearchInput,
  Toolbar,
  type Coluna,
  type Tom,
} from "@/components/ds";
import { useRecurso } from "@/lib/recurso";
import { data as fmtData, plural } from "@/lib/format";
import type { LinhaFluido } from "@/features/relatorio-inspecao/tipos";
import { numero } from "@/features/relatorio-inspecao/modulos/transformador/formato";
import { CodigosIso, Tendencias } from "@/features/relatorio-inspecao/modulos/fluidos/graficos";
import type { AvaliacaoFluido } from "./tipos";

/* ==========================================================================
   Histórico da análise de fluidos — equipamento → ensaio → parâmetro → data.
   O mesmo cálculo do relatório (referência, estado, tendência, código ISO),
   lido de /fluidos-historico/. No portal só aparecem resultados de relatórios
   finalizados; a equipe interna vê também o que está em análise.
   ========================================================================== */

type EquipamentoComFluido = {
  equipamento: number; tag: string; nome: string; area: string; setor: string;
  ultima_coleta: string; fluido: string; aplicacao: string; coletas: number;
};
type EnsaioHistorico = AvaliacaoFluido & { sigla: string; nome: string };
type Historico = {
  equipamento: { id: number; tag: string; nome: string; area: string; setor: string };
  ensaios: EnsaioHistorico[];
};

const TOM: Record<string, Tom> = { ROTINA: "success", ALERTA: "warning", CRITICA: "danger" };
const ROTULO: Record<string, string> = { ROTINA: "Rotina", ALERTA: "Alerta", CRITICA: "Crítica" };
const APLICACAO: Record<string, string> = { LUBRIFICANTE: "Lubrificante", HIDRAULICO: "Hidráulico" };

function valor(l: LinhaFluido, i: number) {
  const c = l.valores[i];
  if (!c) return "";
  if (c.valor != null) return numero(c.valor, l.casas);
  return c.texto || "";
}

function TabelaHistorico({ e }: { e: EnsaioHistorico }) {
  const linhas = e.linhas.filter((l) => l.valores.some((c) => c.valor != null || c.texto));
  if (!linhas.length) return <p className="text-sm text-fg-muted">Sem valores registrados.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[36rem] text-sm">
        <thead>
          <tr className="text-left text-xs text-fg-muted">
            <th className="py-1.5 pr-3 font-medium">Parâmetro</th>
            <th className="py-1.5 pr-3 font-medium">Referência</th>
            {e.campanhas.map((c, i) => (
              <th key={i} className="py-1.5 pr-3 text-right font-medium">{fmtData(c.data)}</th>
            ))}
            <th className="py-1.5 font-medium">Estado</th>
          </tr>
        </thead>
        <tbody>
          {linhas.map((l) => (
            <tr key={l.codigo} className="border-t border-border">
              <td className="py-1.5 pr-3 text-fg">
                {l.nome}{l.simbolo ? ` (${l.simbolo})` : ""} {l.unidade && <span className="text-xs text-fg-subtle">[{l.unidade}]</span>}
              </td>
              <td className="py-1.5 pr-3 text-xs text-fg-muted">{l.referencia?.texto ?? "—"}</td>
              {e.campanhas.map((c, i) => (
                <td key={i} className={`data py-1.5 pr-3 text-right ${c.atual ? "font-semibold text-fg" : "text-fg-muted"}`}>{valor(l, i)}</td>
              ))}
              <td className="py-1.5">{l.status ? <Badge tone={TOM[l.status]}>{ROTULO[l.status]}</Badge> : <span className="text-xs text-fg-subtle">—</span>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function DetalheEquipamento({ equipamentoId }: { equipamentoId: number }) {
  const h = useRecurso<Historico>(`/fluidos-historico/?equipamento=${equipamentoId}`, "histórico de fluidos");
  if (h.carregando) return <LoadingState variante="formulario" label="Carregando o histórico…" />;
  if (!h.dados) return <p className="text-sm text-danger-fg">Não foi possível carregar o histórico deste equipamento.</p>;
  return (
    <div className="space-y-4">
      {h.dados.ensaios.map((e) => {
        const meta = e.meta?.referencia_texto ? e.meta.referencia_texto.split("/").map((p) => (p === ">28" ? 29 : Number(p))) : null;
        return (
          <Card key={e.sigla}>
            <CardHeader
              title={`${e.sigla} — ${e.nome}`}
              description={plural(e.campanhas.length, "coleta", "coletas")}
              actions={
                e.status === "ROTINA" || e.status === "ALERTA" || e.status === "CRITICA"
                  ? <Badge tone={TOM[e.status]}>{e.status_rotulo}</Badge>
                  : <Badge tone="neutral">{e.status_rotulo}</Badge>
              }
            />
            <div className="space-y-4">
              <TabelaHistorico e={e} />
              {e.tipo === "CP" ? (
                <CodigosIso codigos={e.codigos ?? []} meta={meta} />
              ) : (
                <Tendencias linhas={e.linhas} campanhas={e.campanhas} maximo={4} />
              )}
            </div>
          </Card>
        );
      })}
    </div>
  );
}

export function HistoricoFluidos() {
  const [busca, setBusca] = useState("");
  const [selecionado, setSelecionado] = useState<number | null>(null);
  // Lista simples (não paginada): um item por equipamento com resultado de fluido.
  const lista = useRecurso<EquipamentoComFluido[]>("/fluidos-historico/", "equipamentos com análise de fluidos");
  const colunas: Coluna<EquipamentoComFluido>[] = [
    { chave: "tag", header: "TAG", mobile: "titulo", tecnico: true, valor: (e) => e.tag, celula: (e) => <span className="font-semibold text-fg">{e.tag}</span> },
    { chave: "nome", header: "Equipamento", mobile: "subtitulo", valor: (e) => e.nome, celula: (e) => e.nome },
    { chave: "local", header: "Local", mobile: "oculta", valor: (e) => `${e.area} / ${e.setor}`, celula: (e) => `${e.area} / ${e.setor}` },
    {
      chave: "fluido", header: "Fluido", mobile: "meta", valor: (e) => e.fluido,
      celula: (e) => <span>{APLICACAO[e.aplicacao] ?? ""}{e.fluido ? ` · ${e.fluido}` : ""}</span>,
    },
    { chave: "coletas", header: "Coletas", mobile: "meta", alinhamento: "direita", valor: (e) => e.coletas, celula: (e) => e.coletas },
    { chave: "ultima", header: "Última coleta", mobile: "meta", tecnico: true, valor: (e) => e.ultima_coleta, celula: (e) => fmtData(e.ultima_coleta) },
  ];
  return (
    <div className="space-y-5">
      <Toolbar busca={<SearchInput value={busca} onChange={setBusca} label="Buscar equipamento" placeholder="TAG ou nome…" />} />
      {lista.carregando ? (
        <LoadingState variante="tabela" linhas={5} colunas={6} label="Carregando equipamentos…" />
      ) : (
        <DataTable<EquipamentoComFluido>
          itens={lista.dados ?? []}
          colunas={colunas}
          getId={(e) => e.equipamento}
          busca={busca}
          camposBusca={(e) => [e.tag, e.nome, e.fluido]}
          falha={lista.falha}
          onRetry={lista.recarregar}
          onLinhaClick={(e) => setSelecionado(e.equipamento)}
          porPagina={10}
          legenda="Equipamentos com análise de fluidos — escolha um para ver a tendência"
          vazio={
            <EmptyState
              icon={Droplets}
              title="Nenhuma análise de fluido disponível ainda"
              description="Os resultados aparecem aqui depois que o relatório de análise de fluidos é finalizado."
            />
          }
        />
      )}
      {selecionado != null && <DetalheEquipamento key={selecionado} equipamentoId={selecionado} />}
    </div>
  );
}
