"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { AlertTriangle, Plus, Wrench } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useClienteAtivo } from "@/lib/cliente-ativo";
import { useClientes } from "@/lib/hierarquia";
import type { OrdemServico, Paginated } from "@/lib/types";
import {
  Badge,
  Button,
  EmptyState,
  Field,
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
import { Combobox } from "@/components/combobox";

// Ciclo acordado com o cliente: Aberta → Planejada → Executada → Finalizada.
const STATUS_FLOW = [
  "ABERTA",
  "PLANEJADA",
  "EXECUTADA",
  "EM_ANALISE",
  "EM_EXECUCAO",
  "AGUARDANDO_APROVACAO",
  "FINALIZADA",
  "CANCELADA",
];
const STATUS_LABEL: Record<string, string> = {
  ABERTA: "Aberta",
  PLANEJADA: "Planejada",
  EXECUTADA: "Executada",
  EM_ANALISE: "Em análise",
  EM_EXECUCAO: "Em execução",
  AGUARDANDO_APROVACAO: "Aguardando aprovação",
  FINALIZADA: "Finalizada",
  CANCELADA: "Cancelada",
};

export default function OspsPage() {
  const { user } = useAuth();
  const router = useRouter();
  const podeEditar = !!user?.is_interno;
  const { opcoes: opcoesClientes } = useClientes();
  const { clienteAtivo } = useClienteAtivo();
  const [cliente, setCliente] = useState<number | "">(clienteAtivo?.id ?? "");
  const [osps, setOsps] = useState<OrdemServico[]>([]);
  const [loading, setLoading] = useState(true);

  async function reload(clienteId: number | "" = cliente) {
    // Filtro por cliente no servidor — essencial quando houver milhares de OSPs.
    const filtro = clienteId ? `&cliente=${clienteId}` : "";
    const data = await api<Paginated<OrdemServico>>(
      `/osps/?ordering=-criado_em&page_size=1000${filtro}`
    );
    setOsps(data.results);
  }

  // Ativar um cliente (ou recuperá-lo do localStorage) já filtra as OSPs aqui.
  useEffect(() => {
    if (clienteAtivo) setCliente(clienteAtivo.id);
  }, [clienteAtivo]);

  useEffect(() => {
    setLoading(true);
    reload(cliente).finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cliente]);

  async function mudarStatus(id: number, status: string) {
    await api(`/osps/${id}/status/`, { method: "PATCH", body: { status } });
    await reload();
  }

  return (
    <div className="space-y-6">
      <PageHeader
        icon={Wrench}
        title="Ordens de Serviço Preditivas"
        description="Corretiva orientada pela preditiva (Anexo I 2.6)."
        actions={
          podeEditar ? (
            <Link href="/osps/nova">
              <Button icon={Plus}>Nova OSP</Button>
            </Link>
          ) : undefined
        }
      />

      <Card>
        <Field label="Filtrar por cliente">
          <div className="max-w-md">
            <Combobox
              value={cliente}
              onChange={setCliente}
              options={opcoesClientes}
              placeholder="Todos os clientes"
              limparLabel="Todos os clientes"
            />
          </div>
        </Field>
      </Card>

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
