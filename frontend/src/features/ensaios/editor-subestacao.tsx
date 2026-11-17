"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, FileText } from "lucide-react";
import { api } from "@/lib/api";
import type { Paginated } from "@/lib/types";
import { Alert, Badge, Card, LoadingState } from "@/components/ds";
import { CartaoEnsaio } from "./cartao-ensaio";
import { DadosPlacaSubestacao, RegistroSubestacao } from "./registro-subestacao";
import type {
  DadosPlacaApi,
  EnsaioCatalogo,
  InstrumentoOpcao,
  ItemEnsaio,
  ModuloSubestacao,
  RegistroSubestacaoApi,
  ResultadoApi,
} from "./tipos";

/* ==========================================================================
   Lançamento dos ensaios de um equipamento de subestação (TC, TP, DJ, CS, RP) —
   o mesmo editor no campo (folha da rota, ?item=) e no escritório (Análise final).
   Registro e placa, depois as medições de cada ensaio por série. Cada parte grava
   sozinha; o relatório técnico lê o que houver.
   ========================================================================== */

type Dados = {
  equipamento: ItemEnsaio;
  ensaios: EnsaioCatalogo[];
  registro: RegistroSubestacaoApi | null;
  placa: DadosPlacaApi | null;
  resultados: Record<number, ResultadoApi>;
  instrumentos: InstrumentoOpcao[];
};

const ROTULO_EQUIPAMENTO: Record<ModuloSubestacao, string> = {
  ENSAIO_ELETRICO_TC: "Transformador de corrente",
  ENSAIO_ELETRICO_TP: "Transformador de potencial",
  ENSAIO_ELETRICO_DJ: "Disjuntor",
  ENSAIO_ELETRICO_CS: "Chave seccionadora",
  ENSAIO_ELETRICO_RP: "Relé de proteção",
};

export function EditorSubestacao({
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
      const equipamento = await api<ItemEnsaio>(`/subestacao-inspecao/${itemId}/`);
      const modulo = equipamento.modulo as ModuloSubestacao;
      const [ensaios, registros, placas, resultados, instrumentos] = await Promise.all([
        api<Paginated<EnsaioCatalogo>>(`/ensaios/?modulo=${modulo}&page_size=50`),
        api<Paginated<RegistroSubestacaoApi>>(`/registros-ensaio-subestacao/?item=${itemId}`),
        api<Paginated<DadosPlacaApi>>(`/dados-placa-subestacao/?equipamento=${equipamento.equipamento}`),
        api<Paginated<ResultadoApi>>(`/resultados-ensaio/?item=${itemId}`),
        api<Paginated<InstrumentoOpcao>>(`/instrumentos/?tecnologias=${equipamento.tecnologia}&page_size=500`),
      ]);
      setDados({
        equipamento,
        ensaios: [...ensaios.results].sort((a, b) => a.ordem - b.ordem),
        registro: registros.results[0] ?? null,
        placa: placas.results[0] ?? null,
        resultados: Object.fromEntries(resultados.results.map((r) => [r.ensaio, r])),
        instrumentos: instrumentos.results,
      });
    } catch {
      setErro("Não foi possível carregar os ensaios deste equipamento.");
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
  if (!dados) return <LoadingState variante="formulario" label="Carregando os ensaios do equipamento…" />;

  const { equipamento, ensaios, registro, placa } = dados;
  const modulo = equipamento.modulo as ModuloSubestacao;
  const solicitados = new Set(registro?.ensaios ?? []);
  // Solicitados primeiro: é o que o registro pediu; os demais ficam recolhidos.
  const ordenados = [...ensaios].sort(
    (a, b) => Number(solicitados.has(b.id) || !!dados.resultados[b.id]) - Number(solicitados.has(a.id) || !!dados.resultados[a.id])
  );

  return (
    <div className="space-y-5">
      {voltarLink}

      <Card>
        <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
          <div className="min-w-0">
            <p className="data text-lg font-semibold text-fg">{equipamento.equipamento_tag}</p>
            <p className="text-sm text-fg-muted">
              {ROTULO_EQUIPAMENTO[modulo]} · {equipamento.equipamento_nome}
            </p>
            <p className="mt-1 text-xs text-fg-subtle">
              {equipamento.area_nome} <span aria-hidden="true">/</span> {equipamento.setor_nome} · {equipamento.cliente_nome}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="primary">{equipamento.tecnologia_nome}</Badge>
            {equipamento.numero && <Badge tone="neutral">{equipamento.numero}</Badge>}
            <Badge tone={equipamento.carregamento_status === "EM_CAMPO" ? "warning" : "success"}>
              {equipamento.carregamento_status === "EM_CAMPO" ? "Em campo" : "No escritório"}
            </Badge>
          </div>
        </div>
        {equipamento.relatorio && (
          <Link
            href={`/relatorios-inspecao/${equipamento.relatorio}`}
            className="mt-3 inline-flex items-center gap-1.5 text-xs font-medium text-primary underline-offset-4 hover:underline"
          >
            <FileText className="h-3.5 w-3.5" aria-hidden="true" /> Ver o relatório técnico
          </Link>
        )}
      </Card>

      {!podeEditar && <Alert tone="info">Somente leitura.</Alert>}

      <RegistroSubestacao
        itemId={itemId}
        dataPadrao={equipamento.data_coleta}
        analistaPadrao={equipamento.analista_nome}
        ensaios={ensaios}
        registro={registro}
        podeEditar={podeEditar}
        onSalvo={(r) => setDados((d) => (d ? { ...d, registro: r } : d))}
      />

      <DadosPlacaSubestacao
        equipamentoId={equipamento.equipamento}
        modulo={modulo}
        placa={placa}
        podeEditar={podeEditar}
        onSalvo={(p) => setDados((d) => (d ? { ...d, placa: p } : d))}
      />

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
