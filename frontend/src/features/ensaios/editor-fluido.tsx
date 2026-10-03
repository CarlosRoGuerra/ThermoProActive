"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, FileText } from "lucide-react";
import { api } from "@/lib/api";
import type { Paginated } from "@/lib/types";
import { Alert, Badge, Card, LoadingState } from "@/components/ds";
import { CartaoEnsaio } from "./cartao-ensaio";
import { RegistroColetaFluido } from "./registro-fluido";
import type {
  ColetaFluidoApi,
  EnsaioCatalogo,
  FluidoInspecao,
  InstrumentoOpcao,
  Opcao,
  ProdutoFluido,
  ResultadoApi,
} from "./tipos";

/* ==========================================================================
   Lançamento da análise de fluido de um equipamento — o mesmo editor no campo
   (folha da rota, ?item=) e no escritório (Análise final → Ensaios de fluidos).

   No campo entra a coleta da amostra (fluido, ponto, condição, histórico e os
   ensaios solicitados); no escritório, os resultados do laboratório — FQ, EF e,
   quando pedida, CP —, a conclusão e a recomendação. Cada parte grava sozinha.
   ========================================================================== */

type Dados = {
  item: FluidoInspecao;
  ensaios: EnsaioCatalogo[];
  coleta: ColetaFluidoApi | null;
  resultados: Record<number, ResultadoApi>;
  instrumentos: InstrumentoOpcao[];
  pontos: Opcao[];
  produtos: ProdutoFluido[];
};

export function EditorFluido({
  itemId, podeEditar, voltar,
}: {
  itemId: number;
  podeEditar: boolean;
  voltar: { href: string; label: string };
}) {
  const [dados, setDados] = useState<Dados | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  const carregar = useCallback(async () => {
    try {
      const item = await api<FluidoInspecao>(`/fluidos-inspecao/${itemId}/`);
      const [ensaios, coletas, resultados, instrumentos, pontos, produtos] = await Promise.all([
        api<Paginated<EnsaioCatalogo>>("/ensaios/?modulo=FLUIDO_LUBRIFICANTE&page_size=50"),
        api<Paginated<ColetaFluidoApi>>(`/coletas-fluido/?item=${itemId}`),
        api<Paginated<ResultadoApi>>(`/resultados-ensaio/?item=${itemId}`),
        api<Paginated<InstrumentoOpcao>>(`/instrumentos/?tecnologias=${item.tecnologia}&page_size=500`),
        api<Paginated<Opcao & { modulo: string }>>("/pontos-coleta/?page_size=500"),
        api<Paginated<ProdutoFluido>>("/produtos-fluido/?page_size=500"),
      ]);
      setDados({
        item,
        ensaios: [...ensaios.results].sort((a, b) => a.ordem - b.ordem),
        coleta: coletas.results[0] ?? null,
        resultados: Object.fromEntries(resultados.results.map((r) => [r.ensaio, r])),
        instrumentos: instrumentos.results,
        // Pontos desta tecnologia e os que valem para todas.
        pontos: pontos.results.filter((p) => !p.modulo || p.modulo === "FLUIDO_LUBRIFICANTE"),
        produtos: produtos.results,
      });
    } catch {
      setErro("Não foi possível carregar a análise de fluido deste equipamento.");
    }
  }, [itemId]);

  useEffect(() => {
    void carregar();
  }, [carregar]);

  const voltarLink = (
    <Link href={voltar.href} className="inline-flex items-center gap-1.5 text-xs font-medium text-fg-muted transition-colors hover:text-fg">
      <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" /> {voltar.label}
    </Link>
  );

  if (erro) return <div className="space-y-4">{voltarLink}<Card><p className="text-sm text-danger-fg">{erro}</p></Card></div>;
  if (!dados) return <LoadingState variante="formulario" label="Carregando a análise de fluido…" />;

  const { item, ensaios, coleta } = dados;
  const solicitados = new Set(coleta?.ensaios ?? []);
  // Solicitados (ou já com resultado) primeiro; os demais ficam recolhidos.
  const ordenados = [...ensaios].sort(
    (a, b) => Number(solicitados.has(b.id) || !!dados.resultados[b.id]) - Number(solicitados.has(a.id) || !!dados.resultados[a.id])
  );

  return (
    <div className="space-y-5">
      {voltarLink}

      <Card>
        <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
          <div className="min-w-0">
            <p className="data text-lg font-semibold text-fg">{item.equipamento_tag}</p>
            <p className="text-sm text-fg-muted">{item.equipamento_nome}</p>
            <p className="mt-1 text-xs text-fg-subtle">
              {item.area_nome} <span aria-hidden="true">/</span> {item.setor_nome} · {item.cliente_nome}
              {item.tipo_equipamento_nome ? ` · ${item.tipo_equipamento_nome}` : ""}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="primary">{item.tecnologia_nome}</Badge>
            {item.numero && <Badge tone="neutral">{item.numero}</Badge>}
            <Badge tone={item.carregamento_status === "EM_CAMPO" ? "warning" : "success"}>
              {item.carregamento_status === "EM_CAMPO" ? "Em campo" : "No escritório"}
            </Badge>
          </div>
        </div>
        {item.relatorio && (
          <Link
            href={`/relatorios-inspecao/${item.relatorio}`}
            className="mt-3 inline-flex items-center gap-1.5 text-xs font-medium text-primary underline-offset-4 hover:underline"
          >
            <FileText className="h-3.5 w-3.5" aria-hidden="true" /> Ver o relatório técnico
          </Link>
        )}
      </Card>

      {!podeEditar && <Alert tone="info">Somente leitura.</Alert>}

      <RegistroColetaFluido
        itemId={itemId}
        dataPadrao={item.data_coleta}
        analistaPadrao={item.analista_nome}
        ensaios={ensaios}
        coleta={coleta}
        produtos={dados.produtos}
        pontos={dados.pontos}
        podeEditar={podeEditar}
        onSalvo={(c) => setDados((d) => (d ? { ...d, coleta: c } : d))}
      />

      <section className="space-y-4">
        <div>
          <h2 className="text-sm font-semibold text-fg">Resultados do laboratório</h2>
          <p className="text-xs text-fg-subtle">
            A referência de cada parâmetro é a cadastrada para este equipamento, fluido ou cliente (Dados de sistema →
            Referências dos parâmetros). Sem referência, o valor fica sem classificação.
          </p>
        </div>
        {ordenados.map((e) => (
          <CartaoEnsaio
            key={e.id}
            itemId={itemId}
            ensaio={e}
            resultado={dados.resultados[e.id] ?? null}
            solicitado={solicitados.has(e.id)}
            instrumentos={dados.instrumentos}
            podeEditar={podeEditar}
            onSalvo={(r) => setDados((d) => (d ? { ...d, resultados: { ...d.resultados, [r.ensaio]: r } } : d))}
          />
        ))}
      </section>
    </div>
  );
}
