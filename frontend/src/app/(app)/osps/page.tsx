"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, Wrench } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { OrdemServico, Paginated } from "@/lib/types";
import {
  Badge,
  EmptyState,
  PageHeader,
  PriorityBadge,
  Select,
  StatusBadge,
  Table,
  TableSkeleton,
  TBody,
  TD,
  TH,
  THead,
  TR,
  Card,
} from "@/components/ui";

const STATUS_FLOW = [
  "ABERTA",
  "EM_ANALISE",
  "EM_EXECUCAO",
  "AGUARDANDO_APROVACAO",
  "FINALIZADA",
  "CANCELADA",
];
const STATUS_LABEL: Record<string, string> = {
  ABERTA: "Aberta",
  EM_ANALISE: "Em análise",
  EM_EXECUCAO: "Em execução",
  AGUARDANDO_APROVACAO: "Aguardando aprovação",
  FINALIZADA: "Finalizada",
  CANCELADA: "Cancelada",
};

export default function OspsPage() {
  const { user } = useAuth();
  const [osps, setOsps] = useState<OrdemServico[]>([]);
  const [loading, setLoading] = useState(true);

  async function reload() {
    const data = await api<Paginated<OrdemServico>>("/osps/?ordering=-criado_em");
    setOsps(data.results);
  }

  useEffect(() => {
    reload().finally(() => setLoading(false));
  }, []);

  async function mudarStatus(id: number, status: string) {
    await api(`/osps/${id}/status/`, { method: "PATCH", body: { status } });
    await reload();
  }

  return (
    <div className="space-y-6">
      <PageHeader
        icon={Wrench}
        title="Ordens de Serviço Preditivas"
        description="Geradas automaticamente a partir de medições críticas (Anexo I 2.6)."
      />

      {loading ? (
        <TableSkeleton rows={5} cols={6} />
      ) : osps.length === 0 ? (
        <Card>
          <EmptyState
            icon={Wrench}
            title="Nenhuma OSP registrada"
            description="Ordens de serviço são abertas automaticamente quando uma medição é classificada como crítica."
          />
        </Card>
      ) : (
        <Table>
          <THead>
            <TH>Número</TH>
            <TH>Equipamento</TH>
            <TH>Prioridade</TH>
            <TH>SLA</TH>
            <TH>Origem</TH>
            <TH>Status</TH>
          </THead>
          <TBody>
            {osps.map((o) => (
              <TR key={o.id}>
                <TD>
                  <span className="font-mono font-medium text-fg">{o.numero}</span>
                  {o.gerada_automaticamente && (
                    <Badge tone="accent" className="ml-2 px-1.5 py-0 text-[10px]">
                      AUTO
                    </Badge>
                  )}
                </TD>
                <TD className="text-fg">{o.equipamento_tag}</TD>
                <TD>
                  <PriorityBadge value={o.prioridade} label={o.prioridade_display} />
                </TD>
                <TD>
                  {o.sla_vencido ? (
                    <span className="inline-flex items-center gap-1 font-medium text-danger-fg">
                      <AlertTriangle className="h-3.5 w-3.5" /> {o.sla_data}
                    </span>
                  ) : (
                    o.sla_data ?? "—"
                  )}
                </TD>
                <TD className="text-xs">{o.criticidade_origem || "—"}</TD>
                <TD>
                  {user?.is_interno ? (
                    <Select
                      value={o.status}
                      onChange={(e) => mudarStatus(o.id, e.target.value)}
                      className="h-8 w-auto py-0 text-xs"
                    >
                      {STATUS_FLOW.map((s) => (
                        <option key={s} value={s}>
                          {STATUS_LABEL[s]}
                        </option>
                      ))}
                    </Select>
                  ) : (
                    <StatusBadge value={o.status_display} />
                  )}
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      )}
    </div>
  );
}
