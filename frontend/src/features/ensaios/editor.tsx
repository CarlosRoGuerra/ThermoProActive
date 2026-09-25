"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, FileText } from "lucide-react";
import { api } from "@/lib/api";
import type { Paginated } from "@/lib/types";
import { Alert, Badge, Card, LoadingState } from "@/components/ds";
import { CartaoEnsaio } from "./cartao-ensaio";
import { RegistroColeta, RegistroEletrico } from "./registro";
import type {
  ColetaOleoApi,
  EnsaioCatalogo,
  InstrumentoOpcao,
  ItemChecklist,
  Opcao,
  RegistroEletricoApi,
  ResultadoApi,
  TransformadorInspecao,
} from "./tipos";

/* ==========================================================================
   Lançamento dos ensaios de um transformador — o mesmo editor no campo (folha
   da rota, ?item=) e no escritório (Análise final → Ensaios de transformador).

   No campo entram o registro (coleta e inspeção visual, ou TAP e temperaturas)
   e as medições dos elétricos; no escritório, os laudos do laboratório, a
   conclusão e a recomendação. Nada é obrigatório em uma etapa só: cada parte
   grava sozinha e o relatório técnico lê o que houver.
   ========================================================================== */

type Dados = {
  trafo: TransformadorInspecao;
  ensaios: EnsaioCatalogo[];
  registro: ColetaOleoApi | RegistroEletricoApi | null;
  resultados: Record<number, ResultadoApi>;
  instrumentos: InstrumentoOpcao[];
  pontos: Opcao[];
  fluidos: Opcao[];
  checklist: ItemChecklist[];
};

const vazio = <T,>(): Promise<Paginated<T>> => Promise.resolve({ count: 0, next: null, previous: null, results: [] });

export function EditorTransformador({
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
      const trafo = await api<TransformadorInspecao>(`/transformadores-inspecao/${itemId}/`);
      const oleo = trafo.modulo === "OLEO_ISOLANTE";
      const [ensaios, registros, resultados, instrumentos, pontos, fluidos, checklist] = await Promise.all([
        api<Paginated<EnsaioCatalogo>>(`/ensaios/?modulo=${trafo.modulo}&page_size=50`),
        api<Paginated<ColetaOleoApi | RegistroEletricoApi>>(
          oleo ? `/coletas-oleo/?item=${itemId}` : `/registros-ensaio-eletrico/?item=${itemId}`
        ),
        api<Paginated<ResultadoApi>>(`/resultados-ensaio/?item=${itemId}`),
        api<Paginated<InstrumentoOpcao>>(`/instrumentos/?tecnologias=${trafo.tecnologia}&page_size=500`),
        oleo ? api<Paginated<Opcao>>("/pontos-coleta/?page_size=500") : vazio<Opcao>(),
        oleo ? api<Paginated<Opcao>>("/tipos-fluido/?page_size=500") : vazio<Opcao>(),
        oleo ? api<Paginated<ItemChecklist>>("/itens-checklist-visual/?page_size=500") : vazio<ItemChecklist>(),
      ]);
      setDados({
        trafo,
        ensaios: [...ensaios.results].sort((a, b) => a.ordem - b.ordem),
        registro: registros.results[0] ?? null,
        resultados: Object.fromEntries(resultados.results.map((r) => [r.ensaio, r])),
        instrumentos: instrumentos.results,
        pontos: pontos.results,
        fluidos: fluidos.results,
        checklist: [...checklist.results].sort((a, b) => a.grupo.localeCompare(b.grupo) || a.ordem - b.ordem),
      });
    } catch {
      setErro("Não foi possível carregar os ensaios deste transformador.");
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
  if (!dados) return <LoadingState variante="formulario" label="Carregando os ensaios do transformador…" />;

  const { trafo, ensaios, registro } = dados;
  const solicitados = new Set(registro?.ensaios ?? []);
  // Solicitados primeiro: é o que a coleta/o registro pediu; os demais ficam recolhidos.
  const ordenados = [...ensaios].sort(
    (a, b) => Number(solicitados.has(b.id) || !!dados.resultados[b.id]) - Number(solicitados.has(a.id) || !!dados.resultados[a.id])
  );

  return (
    <div className="space-y-5">
      {voltarLink}

      <Card>
        <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
          <div className="min-w-0">
            <p className="data text-lg font-semibold text-fg">{trafo.equipamento_tag}</p>
            <p className="text-sm text-fg-muted">{trafo.equipamento_nome}</p>
            <p className="mt-1 text-xs text-fg-subtle">
              {trafo.area_nome} <span aria-hidden="true">/</span> {trafo.setor_nome} · {trafo.cliente_nome}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="primary">{trafo.tecnologia_nome}</Badge>
            {trafo.numero && <Badge tone="neutral">{trafo.numero}</Badge>}
            <Badge tone={trafo.carregamento_status === "EM_CAMPO" ? "warning" : "success"}>
              {trafo.carregamento_status === "EM_CAMPO" ? "Em campo" : "No escritório"}
            </Badge>
          </div>
        </div>
        {trafo.relatorio && (
          <Link
            href={`/relatorios-inspecao/${trafo.relatorio}`}
            className="mt-3 inline-flex items-center gap-1.5 text-xs font-medium text-primary underline-offset-4 hover:underline"
          >
            <FileText className="h-3.5 w-3.5" aria-hidden="true" /> Ver o relatório técnico
          </Link>
        )}
      </Card>

      {!podeEditar && <Alert tone="info">Somente leitura.</Alert>}

      {trafo.modulo === "OLEO_ISOLANTE" ? (
        <RegistroColeta
          itemId={itemId}
          dataPadrao={trafo.data_coleta}
          ensaios={ensaios}
          coleta={registro as ColetaOleoApi | null}
          pontos={dados.pontos}
          fluidos={dados.fluidos}
          checklist={dados.checklist}
          possuiTanque={trafo.possui_tanque_expansao}
          podeEditar={podeEditar}
          onSalvo={(r) => setDados((d) => (d ? { ...d, registro: r } : d))}
        />
      ) : (
        <RegistroEletrico
          itemId={itemId}
          dataPadrao={trafo.data_coleta}
          analistaPadrao={trafo.analista_nome}
          ensaios={ensaios}
          registro={registro as RegistroEletricoApi | null}
          podeEditar={podeEditar}
          onSalvo={(r) => setDados((d) => (d ? { ...d, registro: r } : d))}
        />
      )}

      <section className="space-y-4">
        <h2 className="text-sm font-semibold text-fg">Ensaios</h2>
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
