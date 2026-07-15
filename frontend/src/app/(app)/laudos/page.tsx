"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, FileText } from "lucide-react";
import { api } from "@/lib/api";
import type { Laudo, Paginated } from "@/lib/types";
import {
  Card,
  CriticidadeBadge,
  EmptyState,
  PageHeader,
  StatusBadge,
  Table,
  TableSkeleton,
  TBody,
  TD,
  TH,
  THead,
  TR,
} from "@/components/ui";

export default function LaudosPage() {
  const [laudos, setLaudos] = useState<Laudo[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api<Paginated<Laudo>>("/laudos/")
      .then((d) => setLaudos(d.results))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-6">
      <PageHeader
        icon={FileText}
        title="Laudos Técnicos"
        description="Relatórios sequenciais (Anexo I 2.5 / 3.1.19)."
      />

      {loading ? (
        <TableSkeleton rows={5} cols={5} />
      ) : laudos.length === 0 ? (
        <Card>
          <EmptyState
            icon={FileText}
            title="Nenhum laudo emitido"
            description="Os laudos gerados a partir das inspeções aparecerão aqui."
          />
        </Card>
      ) : (
        <Table>
          <THead>
            <TH>Número</TH>
            <TH>Título</TH>
            <TH>Cliente</TH>
            <TH>Criticidade</TH>
            <TH>Status</TH>
            <TH />
          </THead>
          <TBody>
            {laudos.map((l) => (
              <TR key={l.id}>
                <TD className="font-mono font-medium text-fg">{l.numero}</TD>
                <TD>{l.titulo}</TD>
                <TD>{l.cliente_nome}</TD>
                <TD>{l.criticidade_geral ? <CriticidadeBadge value={l.criticidade_geral} /> : "—"}</TD>
                <TD>
                  <StatusBadge value={l.status_display} />
                </TD>
                <TD className="text-right">
                  <Link
                    href={`/laudos/${l.id}`}
                    className="inline-flex items-center gap-1 text-sm font-medium text-accent transition-colors hover:text-accent-hover"
                  >
                    Abrir <ArrowRight className="h-3.5 w-3.5" />
                  </Link>
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      )}
    </div>
  );
}
