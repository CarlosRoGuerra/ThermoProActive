"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

/**
 * Tendência e projeção de UMA medição (Anexo I 2.4.1.3). Só descreve a série e,
 * quando há limite cadastrado e validado, a data em que a reta cruza o limite.
 */

export const AVISO_TENDENCIA =
  "Estimativa estatística da medição, não probabilidade de falha, vida útil remanescente ou diagnóstico.";

type Projecao = {
  nivel: string;
  limite: string;
  sentido: string;
  estado: string;
  data_estimada: string | null;
  data_observada?: string | null;
  intervalo_confianca: [string | null, string | null] | null;
  dias_ate_limite: number | null;
};

type Analise = {
  serie: {
    status: string;
    motivo: string;
    n: number;
    modelo: string | null;
    sentido?: string;
    estatisticas: { r2_ajustado?: number | null; inclinacao_por_dia?: number | null; unidade_inclinacao?: string };
    projecoes: Projecao[];
    pontos: { data_hora: string; valor: string; atipico: boolean; medicao_id: number }[];
  };
  limite: { validado: boolean; motivo: string; fonte: string; valores: { nivel: string; valor: string }[] };
  grandeza: string;
  configuracao: { pontos_minimos: number; janela: number; origem: string };
};

const STATUS: Record<string, string> = {
  INSUFICIENTE: "Série insuficiente",
  SERIE_CONSTANTE: "Valores iguais, sem tendência",
  SEM_TENDENCIA: "Sem tendência estatisticamente significativa",
  TENDENCIA: "Tendência significativa",
};

const MOTIVO_LIMITE: Record<string, string> = {
  sem_limite_cadastrado: "sem critério cadastrado para esta grandeza — nenhuma data estimada",
  limite_nao_validado: "limite cadastrado mas não validado — nenhuma data estimada",
  criterio_ou_base_nao_confirmados: "critério normativo ou base do equipamento não confirmados — nenhuma data estimada",
};

const ESTADO: Record<string, string> = {
  ATINGIDO: "já atingido",
  ESTIMADO: "cruzamento estimado",
  NAO_CONVERGE: "a tendência não se aproxima do limite",
  FORA_DO_HORIZONTE: "cruzamento além do horizonte configurado",
};

function data(iso: string | null | undefined) {
  return iso ? new Date(iso).toLocaleDateString("pt-BR") : "—";
}

export function TendenciaMedicao({
  modalidade,
  medicaoId,
}: {
  modalidade: "vibracao" | "termografia" | "tecnica";
  medicaoId: number;
}) {
  const [analise, setAnalise] = useState<Analise | null>(null);
  const [erro, setErro] = useState("");

  useEffect(() => {
    setAnalise(null);
    setErro("");
    api<Analise>(`/preditiva/tendencias/${modalidade}/${medicaoId}/`)
      .then(setAnalise)
      .catch(() => setErro("Não foi possível calcular a tendência desta medição."));
  }, [modalidade, medicaoId]);

  if (erro) return <p className="text-sm text-danger-fg">{erro}</p>;
  if (!analise) return <p className="text-sm text-fg-muted">Calculando tendência…</p>;

  const s = analise.serie;
  const semLimite = analise.limite.valores.length === 0;

  return (
    <div className="space-y-3">
      <p className="text-sm font-medium text-fg">
        {STATUS[s.status] ?? s.status}
        {s.status === "TENDENCIA" && s.sentido && ` (${s.sentido === "SOBE" ? "subindo" : "descendo"})`}
      </p>
      <p className="text-xs text-fg-muted">
        {s.n} leitura(s) comparável(is), janela de {analise.configuracao.janela}; mínimo de{" "}
        {analise.configuracao.pontos_minimos}.
        {s.estatisticas.r2_ajustado != null && ` R² ajustado: ${s.estatisticas.r2_ajustado.toFixed(2)}.`}
      </p>
      {semLimite && (
        <p className="text-xs text-fg-muted">
          Limite de alarme: {MOTIVO_LIMITE[analise.limite.motivo] ?? "não aplicável"}.
        </p>
      )}
      {!semLimite && analise.limite.valores.length > 0 && (
        <p className="text-xs text-fg-muted">
          Limites: {analise.limite.valores.map((v) => `${v.nivel} ${v.valor}`).join(" · ")}
          {analise.limite.fonte && ` (fonte: ${analise.limite.fonte})`}
        </p>
      )}
      {s.projecoes.length > 0 && (
        <ul className="space-y-1 text-sm">
          {s.projecoes.map((p) => (
            <li key={p.nivel}>
              {p.nivel} ({p.limite}): {ESTADO[p.estado] ?? p.estado}
              {p.estado === "ESTIMADO" && ` em ${data(p.data_estimada)}`}
              {p.estado === "ESTIMADO" && p.intervalo_confianca &&
                ` · intervalo de 95%: ${data(p.intervalo_confianca[0])} a ${data(p.intervalo_confianca[1]) === "—" ? "além do horizonte" : data(p.intervalo_confianca[1])}`}
            </li>
          ))}
        </ul>
      )}
      <p className="text-xs italic text-fg-muted">{AVISO_TENDENCIA}</p>
    </div>
  );
}
