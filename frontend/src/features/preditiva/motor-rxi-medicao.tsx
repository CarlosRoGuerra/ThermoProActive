"use client";

import { useState } from "react";
import { api } from "@/lib/api";

/**
 * Índices DAR e IP do grupo de leituras de isolação de um motor (Anexo I 2.3.2.5.1.1).
 * Consulta sob demanda. Sem critério validado para o índice, a condição fica PENDENTE.
 */

type Resposta = {
  tensao_ensaio_v: string;
  temperatura_c: string;
  leituras: { "30": string | null; "60": string | null; "600": string | null };
  DAR: string | null;
  IP: string | null;
  condicao_DAR: string;
  condicao_IP: string;
  condicao: string;
  aviso: string;
};

const CONDICAO: Record<string, string> = {
  NORMAL: "Normal",
  ALERTA: "Alerta",
  CRITICO: "Crítico",
  PENDENTE: "Pendente (sem critério validado)",
};

const valor = (v: string | null) => (v == null ? "—" : Number(v).toLocaleString("pt-BR", { maximumFractionDigits: 2 }));

export function MotorRxiMedicao({ medicaoId }: { medicaoId: number }) {
  const [dados, setDados] = useState<Resposta | null>(null);
  const [erro, setErro] = useState("");

  return (
    <details
      className="mt-2 text-xs text-fg-muted"
      onToggle={(e) => {
        if ((e.target as HTMLDetailsElement).open && !dados && !erro) {
          api<Resposta>(`/preditiva/motor-rxi/${medicaoId}/`).then(setDados).catch(() => setErro("Não foi possível calcular os índices."));
        }
      }}
    >
      <summary className="cursor-pointer py-1">Índices DAR e IP do motor</summary>
      <div className="mt-2 space-y-1">
        {erro && <p className="text-danger-fg">{erro}</p>}
        {!dados && !erro && <p>Calculando…</p>}
        {dados && (
          <>
            <p>
              Tensão: {dados.tensao_ensaio_v} V · temperatura: {dados.temperatura_c} °C · R30: {valor(dados.leituras["30"])} ·
              R60: {valor(dados.leituras["60"])} · R600: {valor(dados.leituras["600"])} MΩ
            </p>
            <p>DAR (R60/R30): {valor(dados.DAR)} — {CONDICAO[dados.condicao_DAR] ?? dados.condicao_DAR}</p>
            <p>IP (R600/R60): {valor(dados.IP)} — {CONDICAO[dados.condicao_IP] ?? dados.condicao_IP}</p>
            <p className="italic">{dados.aviso}</p>
          </>
        )}
      </div>
    </details>
  );
}
