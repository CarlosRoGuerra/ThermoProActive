"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Building2, ClipboardList, Plus, Search } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useClienteAtivo } from "@/lib/cliente-ativo";
import type { CarregamentoLista, Paginated } from "@/lib/types";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  Input,
  PageHeader,
  Select,
  Spinner,
  Table,
  TBody,
  TD,
  TH,
  THead,
  TR,
} from "@/components/ui";

type TecOpt = { id: number; nome: string };

export default function AnaliseCampoPage() {
  const { user } = useAuth();
  const router = useRouter();
  const podeEditar = !!user?.is_interno;
  const { clienteAtivo } = useClienteAtivo();

  const [rows, setRows] = useState<CarregamentoLista[]>([]);
  const [tecnologias, setTecnologias] = useState<TecOpt[]>([]);
  const [loading, setLoading] = useState(true);
  const [busca, setBusca] = useState("");
  const [tecFiltro, setTecFiltro] = useState("");

  useEffect(() => {
    api<Paginated<TecOpt>>("/tecnologias-analise/?page_size=1000")
      .then((d) => setTecnologias(d.results))
      .catch(() => setTecnologias([]));
  }, []);

  useEffect(() => {
    if (!clienteAtivo) {
      setRows([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    api<Paginated<CarregamentoLista>>(
      `/carregamentos/?cliente=${clienteAtivo.id}&status=EM_CAMPO&page_size=1000`
    )
      .then((d) => setRows(d.results))
      .catch(() => setRows([]))
      .finally(() => setLoading(false));
  }, [clienteAtivo]);

  const visibleRows = useMemo(() => {
    const q = busca.trim().toLowerCase();
    return rows.filter((r) => {
      if (tecFiltro && String(r.tecnologia) !== tecFiltro) return false;
      if (!q) return true;
      return [r.numero_relatorio, r.rota_nome, r.tecnologia_nome, r.analista_nome]
        .map((v) => String(v ?? "").toLowerCase())
        .join(" ")
        .includes(q);
    });
  }, [rows, busca, tecFiltro]);

  return (
    <div className="space-y-6">
      <PageHeader
        icon={ClipboardList}
        title="Análise de campo"
        description={
          clienteAtivo
            ? `Rotas em coleta de ${clienteAtivo.nome_fantasia || clienteAtivo.nome}.`
            : "Coleta em campo — carregue uma rota para começar."
        }
        actions={
          podeEditar && clienteAtivo ? (
            <Link href="/inspecoes/campo/nova">
              <Button icon={Plus}>Carregar rota</Button>
            </Link>
          ) : undefined
        }
      />

      {!clienteAtivo && (
        <Card>
          <EmptyState
            icon={Building2}
            title="Selecione um cliente"
            description="A inspeção pertence a um cliente. Ative um cliente no seletor do topo."
            action={
              <Link href="/clientes">
                <Button icon={Building2}>Ir para Clientes</Button>
              </Link>
            }
          />
        </Card>
      )}

      {clienteAtivo && (
        <div className="flex flex-col gap-3 sm:flex-row">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-fg-subtle" />
            <Input
              value={busca}
              onChange={(e) => setBusca(e.target.value)}
              placeholder="Buscar por relatório, rota, analista…"
              className="pl-9"
            />
          </div>
          <div className="sm:w-64">
            <Select value={tecFiltro} onChange={(e) => setTecFiltro(e.target.value)}>
              <option value="">Todas as tecnologias</option>
              {tecnologias.map((t) => (
                <option key={t.id} value={t.id}>{t.nome}</option>
              ))}
            </Select>
          </div>
        </div>
      )}

      {!clienteAtivo ? null : loading ? (
        <Card>
          <Spinner />
        </Card>
      ) : visibleRows.length === 0 ? (
        <Card>
          <EmptyState
            icon={ClipboardList}
            title="Nenhuma rota em campo"
            description="Carregue uma rota para iniciar a coleta."
            action={
              podeEditar ? (
                <Link href="/inspecoes/campo/nova">
                  <Button icon={Plus}>Carregar rota</Button>
                </Link>
              ) : undefined
            }
          />
        </Card>
      ) : (
        <Table>
          <THead>
            <TH>Relatório</TH>
            <TH>Tecnologia</TH>
            <TH>Rota</TH>
            <TH>Analista</TH>
            <TH>Data</TH>
            <TH>Itens</TH>
            <TH>Situação</TH>
          </THead>
          <TBody>
            {visibleRows.map((r) => (
              <TR key={r.id} onClick={() => router.push(`/inspecoes/campo/${r.id}`)}>
                <TD className="font-medium text-fg">{r.numero_relatorio || `#${r.id}`}</TD>
                <TD><Badge tone="accent">{r.tecnologia_nome}</Badge></TD>
                <TD>{r.rota_nome || "—"}</TD>
                <TD>{r.analista_nome}</TD>
                <TD className="tabular-nums">{r.data?.split("-").reverse().join("/")}</TD>
                <TD className="tabular-nums">{r.qtd_itens}</TD>
                <TD>
                  {r.pode_transferir ? (
                    <Badge tone="success">Pronta p/ transferir</Badge>
                  ) : (
                    <Badge tone="warning">Em coleta</Badge>
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
