"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Building2, FileText, Search } from "lucide-react";
import { api } from "@/lib/api";
import { useClienteAtivo } from "@/lib/cliente-ativo";
import type { Paginated, Relatorio } from "@/lib/types";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  Input,
  PageHeader,
  Spinner,
  Table,
  TBody,
  TD,
  TH,
  THead,
  TR,
} from "@/components/ui";

const ddmmaaaa = (iso: string | null) => (iso ? iso.split("-").reverse().join("/") : "—");

export default function RelatoriosInspecaoPage() {
  const router = useRouter();
  const { clienteAtivo } = useClienteAtivo();
  const [rows, setRows] = useState<Relatorio[]>([]);
  const [loading, setLoading] = useState(true);
  const [busca, setBusca] = useState("");

  useEffect(() => {
    if (!clienteAtivo) {
      setRows([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    api<Paginated<Relatorio>>(`/relatorios-inspecao/?cliente=${clienteAtivo.id}&page_size=1000`)
      .then((d) => setRows(d.results))
      .catch(() => setRows([]))
      .finally(() => setLoading(false));
  }, [clienteAtivo]);

  const visibleRows = useMemo(() => {
    const q = busca.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter((r) =>
      [r.numero, r.tecnologia_nome].map((v) => String(v ?? "").toLowerCase()).join(" ").includes(q)
    );
  }, [rows, busca]);

  return (
    <div className="space-y-6">
      <PageHeader
        icon={FileText}
        title="Relatório técnico"
        description={
          clienteAtivo
            ? `Relatórios de ${clienteAtivo.nome_fantasia || clienteAtivo.nome}.`
            : "Selecione um cliente para ver os relatórios."
        }
      />

      {!clienteAtivo && (
        <Card>
          <EmptyState
            icon={Building2}
            title="Selecione um cliente"
            description="Ative um cliente no seletor do topo para ver os relatórios técnicos."
            action={
              <Link href="/clientes">
                <Button icon={Building2}>Ir para Clientes</Button>
              </Link>
            }
          />
        </Card>
      )}

      {clienteAtivo && (
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-fg-subtle" />
          <Input
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            placeholder="Buscar por número ou tecnologia…"
            className="pl-9"
          />
        </div>
      )}

      {!clienteAtivo ? null : loading ? (
        <Card>
          <Spinner />
        </Card>
      ) : visibleRows.length === 0 ? (
        <Card>
          <EmptyState
            icon={FileText}
            title="Nenhum relatório"
            description="Os relatórios são criados ao carregar rotas (cada número de relatório é um laudo)."
          />
        </Card>
      ) : (
        <Table>
          <THead>
            <TH>Número</TH>
            <TH>Tecnologia</TH>
            <TH>Início</TH>
            <TH>Término</TH>
            <TH>Rotas</TH>
          </THead>
          <TBody>
            {visibleRows.map((r) => (
              <TR key={r.id} onClick={() => router.push(`/relatorios-inspecao/${r.id}`)}>
                <TD className="font-mono font-medium text-fg">{r.numero}</TD>
                <TD><Badge tone="accent">{r.tecnologia_nome}</Badge></TD>
                <TD className="tabular-nums">{ddmmaaaa(r.data_inicio)}</TD>
                <TD className="tabular-nums">{ddmmaaaa(r.data_termino)}</TD>
                <TD className="tabular-nums">{r.qtd_rotas}</TD>
              </TR>
            ))}
          </TBody>
        </Table>
      )}
    </div>
  );
}
