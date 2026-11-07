"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card, PageHeader } from "@/components/ds";

/** Rótulos das pendências do índice (o texto técnico fica no backend). */
const PENDENCIA: Record<string, string> = {
  sem_condicao_classificada: "sem condição classificada",
  sem_tendencia_avaliada: "tendência não avaliada (sem limite validado ou série curta)",
  criticidade_do_ativo_nao_informada: "criticidade A/B/C do ativo não informada",
};

const ESTADO: Record<string, string> = {
  ATINGIDO: "limite atingido",
  ESTIMADO: "estimativa de cruzamento",
  NAO_CONVERGE: "tendência não se aproxima do limite",
  FORA_DO_HORIZONTE: "cruzamento além do horizonte",
};

type Projecao = {
  nivel: string;
  limite: string;
  estado: string;
  data_estimada: string | null;
  intervalo_confianca: [string | null, string | null] | null;
};

type Serie = {
  modalidade: string;
  grandeza: string;
  ponto_medicao: string;
  criticidade: string | null;
  status_serie: string;
  motivo: string;
  limite_validado: boolean;
  limite_motivo: string;
  projecoes: Projecao[];
};

type Item = {
  equipamento: { id: number; tag: string; nome: string };
  indice: number | null;
  faixa: string | null;
  completo: boolean;
  pendencias: string[];
  componentes: {
    severidade: { valor: string | null };
    tendencia: { valor: string | null };
    consequencia: { criticidade: string | null };
  };
  series: Serie[];
  matriz: { nome: string; origem: string; validacao: string };
};

function data(iso: string | null) {
  return iso ? new Date(iso).toLocaleDateString("pt-BR") : "—";
}

export function RankingRisco() {
  const [itens, setItens] = useState<Item[] | null>(null);
  const [aviso, setAviso] = useState("");
  const [erro, setErro] = useState("");

  useEffect(() => {
    api<{ itens: Item[]; aviso: string }>("/preditiva/risco/ranking/")
      .then((r) => {
        setItens(r.itens);
        setAviso(r.aviso);
      })
      .catch(() => setErro("Não foi possível carregar o ranking de risco."));
  }, []);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Risco por equipamento"
        description="Priorização a partir da condição atual, da tendência e da criticidade do ativo."
      />
      {aviso && <p className="text-sm text-fg-muted">{aviso}</p>}
      {erro && <p className="text-sm text-danger-fg">{erro}</p>}
      {itens && itens.length === 0 && <p className="text-sm">Nenhum equipamento neste escopo.</p>}
      <div className="space-y-3">
        {itens?.map((item) => (
          <Card key={item.equipamento.id}>
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <div>
                <p className="font-semibold">
                  {item.equipamento.tag} — {item.equipamento.nome}
                </p>
                <p className="text-xs text-fg-muted">
                  Matriz: {item.matriz.nome} ({item.matriz.validacao === "PROVISORIA" ? "provisória, a confirmar" : "validada"})
                </p>
              </div>
              {item.completo ? (
                <p className="text-lg font-semibold">
                  {item.indice} <span className="text-sm font-normal">· {item.faixa}</span>
                </p>
              ) : (
                <p className="text-sm">Índice incompleto</p>
              )}
            </div>
            {!item.completo && (
              <ul className="mt-2 list-disc pl-5 text-sm">
                {item.pendencias.map((p) => (
                  <li key={p}>{PENDENCIA[p] ?? p}</li>
                ))}
              </ul>
            )}
            <p className="mt-2 text-xs text-fg-muted">
              Condição: {item.componentes.severidade.valor ?? "—"} · Tendência:{" "}
              {item.componentes.tendencia.valor ?? "—"} · Criticidade do ativo:{" "}
              {item.componentes.consequencia.criticidade ?? "—"}
            </p>
            <details className="mt-2 text-sm">
              <summary className="cursor-pointer">Séries e projeções ({item.series.length})</summary>
              <ul className="mt-2 space-y-2">
                {item.series.map((s) => (
                  <li key={`${s.modalidade}-${s.ponto_medicao}-${s.grandeza}`}>
                    <span className="font-medium">
                      {s.ponto_medicao} · {s.grandeza}
                    </span>{" "}
                    — {s.status_serie.toLowerCase().replace(/_/g, " ")}
                    {!s.limite_validado && ` (${s.limite_motivo || "sem limite validado"})`}
                    {s.projecoes.map((p) => (
                      <p key={p.nivel} className="pl-3 text-xs">
                        {p.nivel} ({p.limite}): {ESTADO[p.estado] ?? p.estado}
                        {p.data_estimada && ` em ${data(p.data_estimada)}`}
                        {p.intervalo_confianca && ` · IC 95%: ${data(p.intervalo_confianca[0])} a ${data(p.intervalo_confianca[1])}`}
                      </p>
                    ))}
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-xs text-fg-muted">
                Estimativa estatística da medição, não probabilidade de falha, vida útil remanescente ou diagnóstico.
              </p>
            </details>
          </Card>
        ))}
      </div>
    </div>
  );
}
