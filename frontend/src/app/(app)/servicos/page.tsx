"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Gauge, Plus } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useClienteAtivo } from "@/lib/cliente-ativo";
import { useClientes } from "@/lib/hierarquia";
import type { Paginated, ServicoCampoLista } from "@/lib/types";
import {
  Badge,
  Button,
  Card,
  CriticidadeBadge,
  EmptyState,
  Field,
  PageHeader,
  Table,
  TableSkeleton,
  TBody,
  TD,
  TH,
  THead,
  TR,
} from "@/components/ui";
import { Combobox } from "@/components/combobox";

const ddmmaaaa = (iso: string | null) => (iso ? iso.split("-").reverse().join("/") : "—");
const pct = (v: string | null) =>
  v == null ? "—" : `${Number(v).toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%`;

export default function ServicosPage() {
  const { user } = useAuth();
  const router = useRouter();
  const podeEditar = !!user?.is_interno;
  const { opcoes: opcoesClientes } = useClientes();
  const { clienteAtivo } = useClienteAtivo();
  const [cliente, setCliente] = useState<number | "">(clienteAtivo?.id ?? "");
  const [servicos, setServicos] = useState<ServicoCampoLista[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (clienteAtivo) setCliente(clienteAtivo.id);
  }, [clienteAtivo]);

  useEffect(() => {
    setLoading(true);
    const filtro = cliente ? `&cliente=${cliente}` : "";
    api<Paginated<ServicoCampoLista>>(`/servicos/?ordering=-data_execucao&page_size=1000${filtro}`)
      .then((d) => setServicos(d.results))
      .finally(() => setLoading(false));
  }, [cliente]);

  return (
    <div className="space-y-5">
      <PageHeader
        title="Serviços de campo"
        description="Balanceamento dinâmico e alinhamento a laser — a execução que fecha a OSP."
        icon={Gauge}
        actions={
          podeEditar && (
            <Button onClick={() => router.push("/servicos/novo")}>
              <Plus className="h-4 w-4" />
              Novo serviço
            </Button>
          )
        }
      />

      <Card>
        <Field label="Cliente" className="max-w-sm">
          <Combobox value={cliente} onChange={setCliente} options={opcoesClientes} />
        </Field>
      </Card>

      {loading ? (
        <TableSkeleton rows={5} cols={7} />
      ) : servicos.length === 0 ? (
        <EmptyState
          icon={Gauge}
          title="Nenhum serviço registrado"
          description="Balanceamentos e alinhamentos executados em campo aparecem aqui."
        />
      ) : (
        <Card padding={false}>
          <Table>
            <THead>
              <TR>
                <TH>Equipamento</TH>
                <TH>Tipo</TH>
                <TH>Data</TH>
                <TH>Rotação</TH>
                <TH>Planos</TH>
                <TH>Redução média</TH>
                <TH>Condição final</TH>
              </TR>
            </THead>
            <TBody>
              {servicos.map((s) => (
                <TR key={s.id} onClick={() => router.push(`/servicos/${s.id}`)}>
                  <TD>
                    <span className="font-medium text-fg">{s.equipamento_tag}</span>
                    <span className="block text-xs text-fg-muted">{s.cliente_nome}</span>
                  </TD>
                  <TD>
                    <Badge tone="neutral">{s.tipo_display}</Badge>
                  </TD>
                  <TD>{ddmmaaaa(s.data_execucao)}</TD>
                  <TD>{s.rotacao_rpm ? `${s.rotacao_rpm} RPM` : "—"}</TD>
                  <TD>{s.numero_planos || "—"}</TD>
                  <TD className="tabular-nums">{pct(s.reducao_media_pct)}</TD>
                  <TD>
                    <CriticidadeBadge value={s.criticidade_final} />
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        </Card>
      )}
    </div>
  );
}
