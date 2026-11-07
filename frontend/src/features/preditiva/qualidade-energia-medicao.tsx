"use client";

import { useState } from "react";
import { api } from "@/lib/api";

/**
 * Condição de uma leitura de qualidade de energia (Anexo I 2.3.2.10). Consulta sob demanda.
 * Não há limiar universal de THD ou de desequilíbrio: sem critério cadastrado e validado, PENDENTE.
 */

type Resposta = {
  grandeza: string;
  valor: string;
  unidade: string;
  janela_agregacao: string | null;
  classificacao: string;
  limite: { validado: boolean; motivo: string; fonte: string; valores: { nivel: string; valor: string }[] };
  aviso: string;
};

const CLASSE: Record<string, string> = {
  NORMAL: "Normal",
  ALERTA: "Alerta",
  CRITICO: "Crítico",
  PENDENTE: "Pendente (sem critério validado)",
};

const MOTIVO: Record<string, string> = {
  sem_limite_cadastrado: "não há critério cadastrado para esta grandeza",
  limite_nao_validado: "o critério cadastrado ainda não foi validado",
};

export function QualidadeEnergiaMedicao({ medicaoId }: { medicaoId: number }) {
  const [dados, setDados] = useState<Resposta | null>(null);
  const [erro, setErro] = useState("");

  return (
    <details
      className="mt-2 text-xs text-fg-muted"
      onToggle={(e) => {
        if ((e.target as HTMLDetailsElement).open && !dados && !erro) {
          api<Resposta>(`/preditiva/qualidade-energia/${medicaoId}/`).then(setDados).catch(() => setErro("Não foi possível obter a condição."));
        }
      }}
    >
      <summary className="cursor-pointer py-1">Condição da qualidade de energia</summary>
      <div className="mt-2 space-y-1">
        {erro && <p className="text-danger-fg">{erro}</p>}
        {!dados && !erro && <p>Consultando…</p>}
        {dados && (
          <>
            <p>
              {dados.grandeza}: {dados.valor} {dados.unidade} · janela: {dados.janela_agregacao ?? "—"}
            </p>
            <p>
              Condição: {CLASSE[dados.classificacao] ?? dados.classificacao}
              {!dados.limite.validado && dados.limite.motivo && ` — ${MOTIVO[dados.limite.motivo] ?? dados.limite.motivo}`}
            </p>
            <p className="italic">{dados.aviso}</p>
          </>
        )}
      </div>
    </details>
  );
}
