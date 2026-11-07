"use client";

/**
 * Sensores instalados no equipamento (Anexo I 3.1.11). Somente leitura aqui:
 * o cadastro e a edição ficam no catálogo "Sensores" (/cadastros), com o mesmo
 * escopo de cliente do servidor. Sem ingestão automática (coleta IoT é futura).
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import { Gauge } from "lucide-react";
import { api } from "@/lib/api";
import type { Paginated } from "@/lib/types";
import { Badge, Card } from "@/components/ds";

interface SensorLinha {
  id: number;
  ponto_instalacao: string;
  tipo_display: string;
  fabricante: string;
  modelo: string;
  grandeza: string;
  unidade: string;
  faixa_minima: string | null;
  faixa_maxima: string | null;
  data_ultima_calibracao: string | null;
  status: string;
  status_display: string;
}

const TOM_STATUS: Record<string, "success" | "warning" | "neutral" | "danger"> = {
  ATIVO: "success",
  EM_MANUTENCAO: "warning",
  INATIVO: "neutral",
  DESINSTALADO: "danger",
};

export function SensoresDoEquipamento({ equipamentoId }: { equipamentoId: number }) {
  const [sensores, setSensores] = useState<SensorLinha[] | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    api<Paginated<SensorLinha>>(`/sensores/?equipamento=${equipamentoId}&page_size=200`, { signal: ctrl.signal })
      .then((r) => setSensores(r.results))
      .catch((e) => {
        if (ctrl.signal.aborted) return;
        setErro(e instanceof Error ? e.message : "Não foi possível carregar os sensores.");
        setSensores([]);
      });
    return () => ctrl.abort();
  }, [equipamentoId]);

  return (
    <Card as="section" className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 font-semibold text-fg">
          <Gauge className="h-4 w-4" aria-hidden /> Sensores instalados
        </h2>
        <Link href="/cadastros" className="text-sm text-primary hover:underline">
          Gerenciar sensores
        </Link>
      </div>
      {erro && <p role="alert" className="text-sm text-danger-fg">{erro}</p>}
      {sensores === null ? (
        <p className="text-sm text-fg-muted">Carregando…</p>
      ) : sensores.length === 0 ? (
        <p className="text-sm text-fg-muted">Nenhum sensor cadastrado para este equipamento.</p>
      ) : (
        <ul className="divide-y divide-border">
          {sensores.map((s) => (
            <li key={s.id} className="flex flex-wrap items-center gap-2 py-2 text-sm">
              <div className="min-w-0 flex-1">
                <p className="text-fg">
                  {s.ponto_instalacao} · {s.tipo_display}
                  {s.fabricante || s.modelo ? ` · ${[s.fabricante, s.modelo].filter(Boolean).join(" ")}` : ""}
                </p>
                <p className="text-xs text-fg-muted">
                  {s.grandeza ? `${s.grandeza}` : "Grandeza não informada"}
                  {s.unidade ? ` (${s.unidade})` : ""}
                  {s.faixa_minima !== null && s.faixa_maxima !== null
                    ? ` · faixa ${s.faixa_minima} a ${s.faixa_maxima}`
                    : ""}
                  {s.data_ultima_calibracao ? ` · calibrado em ${s.data_ultima_calibracao}` : ""}
                </p>
              </div>
              <Badge tone={TOM_STATUS[s.status] ?? "neutral"}>{s.status_display}</Badge>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
