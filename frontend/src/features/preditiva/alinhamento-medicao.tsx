"use client";

import { useState } from "react";
import { api } from "@/lib/api";

/**
 * Antes e depois de um alinhamento a laser (Anexo I 2.3.2.8.1.1–2). Consulta sob demanda.
 * A condição só existe com tolerância cadastrada e validada; o sistema não calcula calços.
 */

type Trio = { angular_mm_100mm: string | null; paralelo_mm: string | null; rpm: string | null } | null;

type Resposta = {
  antes: Trio;
  depois: Trio;
  reducao_angular_pct: string | null;
  reducao_paralelo_pct: string | null;
  condicao: string;
  aviso: string;
};

const CONDICAO: Record<string, string> = {
  NORMAL: "Dentro da tolerância",
  ALERTA: "Alerta",
  CRITICO: "Crítico",
  PENDENTE: "Pendente (sem tolerância cadastrada e validada)",
};

const valor = (v: string | null | undefined) =>
  v == null ? "—" : Number(v).toLocaleString("pt-BR", { maximumFractionDigits: 3 });

export function AlinhamentoMedicao({ medicaoId }: { medicaoId: number }) {
  const [dados, setDados] = useState<Resposta | null>(null);
  const [erro, setErro] = useState("");

  return (
    <details
      className="mt-2 text-xs text-fg-muted"
      onToggle={(e) => {
        if ((e.target as HTMLDetailsElement).open && !dados && !erro) {
          api<Resposta>(`/preditiva/alinhamento/${medicaoId}/`).then(setDados).catch(() => setErro("Não foi possível obter o alinhamento."));
        }
      }}
    >
      <summary className="cursor-pointer py-1">Antes e depois do alinhamento</summary>
      <div className="mt-2 space-y-1">
        {erro && <p className="text-danger-fg">{erro}</p>}
        {!dados && !erro && <p>Consultando…</p>}
        {dados && (
          <>
            <p>
              Antes: angular {valor(dados.antes?.angular_mm_100mm)} mm/100 mm · paralelo {valor(dados.antes?.paralelo_mm)} mm
              {dados.antes?.rpm && ` · ${dados.antes.rpm} rpm`}
            </p>
            <p>
              Depois: angular {valor(dados.depois?.angular_mm_100mm)} mm/100 mm · paralelo {valor(dados.depois?.paralelo_mm)} mm
            </p>
            <p>
              Redução: angular {dados.reducao_angular_pct ?? "—"} % · paralelo {dados.reducao_paralelo_pct ?? "—"} %
            </p>
            <p>Condição: {CONDICAO[dados.condicao] ?? dados.condicao}</p>
            <p className="italic">{dados.aviso}</p>
          </>
        )}
      </div>
    </details>
  );
}
