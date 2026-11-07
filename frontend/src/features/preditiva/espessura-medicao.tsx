"use client";

import { useState } from "react";
import { api } from "@/lib/api";

/**
 * Perda, taxa de corrosão e classificação de uma medição de espessura (Anexo I 2.3.2.7).
 * Consulta sob demanda. Sem limite cadastrado e validado, a condição fica PENDENTE.
 */

type Resposta = {
  valor: string;
  espessura_nominal_mm: string | null;
  perda_percentual: string | null;
  anterior: { valor: string; data_hora: string } | null;
  dias_entre_medicoes: number | null;
  taxa_corrosao_mm_ano: string | null;
  classificacao: string;
  limite: { validado: boolean; motivo: string; valores: { nivel: string; valor: string }[] };
  aviso: string;
};

const CLASSE: Record<string, string> = {
  NORMAL: "Normal",
  ALERTA: "Alerta",
  CRITICO: "Crítico",
  PENDENTE: "Pendente — sem limite cadastrado e validado",
};

const MOTIVO: Record<string, string> = {
  sem_limite_cadastrado: "não há limite de espessura cadastrado para esta peça",
  limite_nao_validado: "o limite cadastrado ainda não foi validado",
};

export function EspessuraMedicao({ medicaoId }: { medicaoId: number }) {
  const [dados, setDados] = useState<Resposta | null>(null);
  const [erro, setErro] = useState("");

  return (
    <details
      className="mt-2 text-xs text-fg-muted"
      onToggle={(e) => {
        if ((e.target as HTMLDetailsElement).open && !dados && !erro) {
          api<Resposta>(`/preditiva/espessura/${medicaoId}/`).then(setDados).catch(() => setErro("Não foi possível calcular."));
        }
      }}
    >
      <summary className="cursor-pointer py-1">Perda e taxa de corrosão</summary>
      <div className="mt-2 space-y-1">
        {erro && <p className="text-danger-fg">{erro}</p>}
        {!dados && !erro && <p>Calculando…</p>}
        {dados && (
          <>
            <p>
              Nominal: {dados.espessura_nominal_mm ?? "—"} mm · medida: {dados.valor} mm · perda:{" "}
              {dados.perda_percentual ?? "—"} %
            </p>
            <p>
              {dados.anterior
                ? `Taxa desde a campanha anterior (${dados.dias_entre_medicoes?.toFixed(0)} dias): ${dados.taxa_corrosao_mm_ano ?? "—"} mm/ano`
                : "Sem campanha anterior comparável (mesmo ponto, instrumento e ficha) para a taxa de corrosão."}
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
