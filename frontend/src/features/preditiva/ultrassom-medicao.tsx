"use client";

import { useState } from "react";
import { api } from "@/lib/api";

/**
 * Condição de uma leitura de ultrassom elétrico ou mecânico (Anexo I 2.3.2.6). Consulta sob demanda.
 * Sem critério cadastrado e validado, a condição fica PENDENTE; não há limite universal em dB.
 */

type Resposta = {
  valor: string;
  unidade: string;
  grandeza: string;
  ganho_db: string | null;
  distancia_cm: string | null;
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
  sem_limite_cadastrado: "não há critério cadastrado para esta modalidade e aplicação",
  limite_nao_validado: "o critério cadastrado ainda não foi validado",
};

export function UltrassomMedicao({ medicaoId }: { medicaoId: number }) {
  const [dados, setDados] = useState<Resposta | null>(null);
  const [erro, setErro] = useState("");

  return (
    <details
      className="mt-2 text-xs text-fg-muted"
      onToggle={(e) => {
        if ((e.target as HTMLDetailsElement).open && !dados && !erro) {
          api<Resposta>(`/preditiva/ultrassom/${medicaoId}/`).then(setDados).catch(() => setErro("Não foi possível obter a condição."));
        }
      }}
    >
      <summary className="cursor-pointer py-1">Condição do ultrassom</summary>
      <div className="mt-2 space-y-1">
        {erro && <p className="text-danger-fg">{erro}</p>}
        {!dados && !erro && <p>Consultando…</p>}
        {dados && (
          <>
            <p>
              {dados.grandeza}: {dados.valor} {dados.unidade} · ganho: {dados.ganho_db ?? "—"} dB · distância:{" "}
              {dados.distancia_cm ?? "—"} cm
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
