"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Building2, Pencil, Plus, Route as RouteIcon, Search, Trash2 } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useClienteAtivo } from "@/lib/cliente-ativo";
import type { Paginated, Rota } from "@/lib/types";
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

export default function RotasPage() {
  const { user } = useAuth();
  const router = useRouter();
  const podeEditar = !!user?.is_interno;
  const podeExcluir = !!user?.pode_excluir;
  const { clienteAtivo } = useClienteAtivo();

  const [rows, setRows] = useState<Rota[]>([]);
  const [loading, setLoading] = useState(true);
  const [busca, setBusca] = useState("");
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    if (!clienteAtivo) {
      setRows([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    api<Paginated<Rota>>(`/rotas/?cliente=${clienteAtivo.id}&page_size=1000`)
      .then((d) => setRows(d.results))
      .catch(() => setRows([]))
      .finally(() => setLoading(false));
  }, [clienteAtivo]);

  async function remover(r: Rota) {
    if (!confirm(`Remover a rota “${r.nome}”?`)) return;
    setMsg(null);
    try {
      await api(`/rotas/${r.id}/`, { method: "DELETE" });
      setRows((rs) => rs.filter((x) => x.id !== r.id));
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "Erro ao remover a rota.");
    }
  }

  const visibleRows = useMemo(() => {
    const q = busca.trim().toLowerCase();
    const filtrados = q
      ? rows.filter((r) =>
          [r.nome, r.tecnologia_nome, r.descricao]
            .map((v) => String(v ?? "").toLowerCase())
            .join(" ")
            .includes(q)
        )
      : rows;
    return [...filtrados].sort((a, b) =>
      String(a.nome ?? "").localeCompare(String(b.nome ?? ""), "pt-BR", { sensitivity: "base" })
    );
  }, [rows, busca]);

  return (
    <div className="space-y-6">
      <PageHeader
        icon={RouteIcon}
        title="Rotas de inspeção"
        description={
          clienteAtivo
            ? `Rotas de ${clienteAtivo.nome_fantasia || clienteAtivo.nome}.`
            : "Conjuntos de equipamentos percorridos numa inspeção."
        }
        actions={
          podeEditar && clienteAtivo ? (
            <Link href="/rotas/nova">
              <Button icon={Plus}>Nova rota</Button>
            </Link>
          ) : undefined
        }
      />

      {!clienteAtivo && (
        <Card>
          <EmptyState
            icon={Building2}
            title="Selecione um cliente"
            description="As rotas pertencem a um cliente. Ative um cliente no seletor do topo para criá-las."
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
            placeholder="Buscar rota por nome, tecnologia…"
            className="pl-9"
          />
        </div>
      )}

      {msg && (
        <Card>
          <p className="text-sm text-danger-fg">{msg}</p>
        </Card>
      )}

      {!clienteAtivo ? null : loading ? (
        <Card>
          <Spinner />
        </Card>
      ) : visibleRows.length === 0 ? (
        <Card>
          <EmptyState
            icon={busca ? Search : RouteIcon}
            title={busca ? "Nada encontrado" : "Nenhuma rota"}
            description={
              busca
                ? `Nenhuma rota corresponde a “${busca}”.`
                : "Crie a primeira rota deste cliente."
            }
            action={
              !busca && podeEditar ? (
                <Link href="/rotas/nova">
                  <Button icon={Plus}>Nova rota</Button>
                </Link>
              ) : undefined
            }
          />
        </Card>
      ) : (
        <Table>
          <THead>
            <TH>Rota</TH>
            <TH>Tecnologia</TH>
            <TH>Equipamentos</TH>
            <TH>Periodicidade</TH>
            {podeEditar && <TH />}
          </THead>
          <TBody>
            {visibleRows.map((r) => (
              <TR key={r.id} onClick={podeEditar ? () => router.push(`/rotas/${r.id}`) : undefined}>
                <TD className="font-medium text-fg">{r.nome}</TD>
                <TD>{r.tecnologia_nome ? <Badge tone="accent">{r.tecnologia_nome}</Badge> : "—"}</TD>
                <TD className="tabular-nums">{r.qtd_equipamentos}</TD>
                <TD>{r.periodicidade_dias ? `${r.periodicidade_dias} dias` : "—"}</TD>
                {podeEditar && (
                  <TD className="text-right">
                    <div className="flex items-center justify-end gap-1">
                      <Link
                        href={`/rotas/${r.id}`}
                        onClick={(e) => e.stopPropagation()}
                        className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-fg-muted transition-colors hover:bg-surface-muted hover:text-fg"
                      >
                        <Pencil className="h-3.5 w-3.5" /> Editar
                      </Link>
                      {podeExcluir && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            remover(r);
                          }}
                          className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-danger-fg transition-colors hover:bg-danger-subtle"
                        >
                          <Trash2 className="h-3.5 w-3.5" /> Remover
                        </button>
                      )}
                    </div>
                  </TD>
                )}
              </TR>
            ))}
          </TBody>
        </Table>
      )}
    </div>
  );
}
