"use client";

import { useState } from "react";
import { TendenciaMedicao } from "./tendencia-medicao";

/** Tendência sob demanda: só consulta o backend quando o analista abre o bloco. */
export function TendenciaExpansivel({
  modalidade,
  medicaoId,
}: {
  modalidade: "vibracao" | "termografia" | "tecnica";
  medicaoId: number;
}) {
  const [aberto, setAberto] = useState(false);
  return (
    <details className="mt-2 text-xs text-fg-muted" onToggle={(e) => setAberto((e.target as HTMLDetailsElement).open)}>
      <summary className="cursor-pointer py-1">Tendência e projeção</summary>
      <div className="mt-2">{aberto && <TendenciaMedicao modalidade={modalidade} medicaoId={medicaoId} />}</div>
    </details>
  );
}
