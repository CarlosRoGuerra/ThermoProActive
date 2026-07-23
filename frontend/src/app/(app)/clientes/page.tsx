"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Building2, Pencil, Plus, Search, Trash2 } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Cliente, Paginated } from "@/lib/types";
import {
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
  cn,
} from "@/components/ui";

const PAGE_SIZE = 10;

function pageWindow(current: number, total: number): (number | "…")[] {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
  const out: (number | "…")[] = [1];
  const start = Math.max(2, current - 1);
  const end = Math.min(total - 1, current + 1);
  if (start > 2) out.push("…");
  for (let i = start; i <= end; i++) out.push(i);
  if (end < total - 1) out.push("…");
  out.push(total);
  return out;
}

export default function ClientesPage() {
  const { user } = useAuth();
  const router = useRouter();
  const podeEditar = !!user?.is_interno;
  const podeExcluir = !!user?.pode_excluir;

  const [rows, setRows] = useState<Cliente[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [msg, setMsg] = useState<string | null>(null);

  async function reload() {
    setLoading(true);
    try {
      const data = await api<Paginated<Cliente>>("/clientes/?page_size=1000");
      setRows(data.results);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    reload();
  }, []);

  async function remover(c: Cliente) {
    if (!confirm(`Remover o cliente “${c.nome}”?`)) return;
    setMsg(null);
    try {
      await api(`/clientes/${c.id}/`, { method: "DELETE" });
      await reload();
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "Erro ao remover o cliente.");
    }
  }

  const visibleRows = useMemo(() => {
    const q = query.trim().toLowerCase();
    const filtrados = q
      ? rows.filter((c) =>
          [c.nome, c.nome_fantasia, c.cnpj, c.unidade_negocio, c.cidade, c.uf, c.contato_gestor]
            .map((v) => String(v ?? "").toLowerCase())
            .join(" ")
            .includes(q)
        )
      : rows;
    return [...filtrados].sort((a, b) =>
      String(a.nome ?? "").localeCompare(String(b.nome ?? ""), "pt-BR", { sensitivity: "base" })
    );
  }, [rows, query]);

  const totalPages = Math.max(1, Math.ceil(visibleRows.length / PAGE_SIZE));
  const pageRows = visibleRows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  useEffect(() => {
    if (page > totalPages) setPage(totalPages);
  }, [page, totalPages]);

  return (
    <div className="space-y-6">
      <PageHeader
        icon={Building2}
        title="Clientes"
        description="Tomadores de serviço cadastrados no sistema."
        actions={
          podeEditar ? (
            <Link href="/clientes/novo">
              <Button icon={Plus}>Novo cliente</Button>
            </Link>
          ) : undefined
        }
      />

      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-fg-subtle" />
        <Input
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setPage(1);
          }}
          placeholder="Buscar por razão social, CNPJ, cidade…"
          className="pl-9"
        />
      </div>

      {msg && (
        <Card>
          <p className="text-sm text-danger-fg">{msg}</p>
        </Card>
      )}

      {loading ? (
        <Card>
          <Spinner />
        </Card>
      ) : visibleRows.length === 0 ? (
        <Card>
          <EmptyState
            icon={query ? Search : Building2}
            title={query ? "Nada encontrado" : "Nenhum cliente cadastrado"}
            description={
              query
                ? `Nenhum cliente corresponde a “${query}”.`
                : "Cadastre o primeiro tomador de serviço para começar."
            }
            action={
              !query && podeEditar ? (
                <Link href="/clientes/novo">
                  <Button icon={Plus}>Novo cliente</Button>
                </Link>
              ) : undefined
            }
          />
        </Card>
      ) : (
        <>
          <Table>
            <THead>
              <TH>Razão social</TH>
              <TH>CNPJ</TH>
              <TH>Unidade</TH>
              <TH>Cidade/UF</TH>
              <TH>Contato</TH>
              {podeEditar && <TH />}
            </THead>
            <TBody>
              {pageRows.map((c) => (
                <TR key={c.id} onClick={podeEditar ? () => router.push(`/clientes/${c.id}`) : undefined}>
                  <TD className="font-medium text-fg">
                    {c.nome}
                    {c.nome_fantasia && (
                      <span className="block text-xs font-normal text-fg-subtle">
                        {c.nome_fantasia}
                      </span>
                    )}
                  </TD>
                  <TD className="font-mono text-xs">{c.cnpj || "—"}</TD>
                  <TD>{c.unidade_negocio || "—"}</TD>
                  <TD>{c.cidade_uf || "—"}</TD>
                  <TD>{c.contato_gestor || "—"}</TD>
                  {podeEditar && (
                    <TD className="text-right">
                      <div className="flex items-center justify-end gap-1">
                        <Link
                          href={`/clientes/${c.id}`}
                          onClick={(e) => e.stopPropagation()}
                          aria-label="Editar"
                          className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-fg-muted transition-colors hover:bg-surface-muted hover:text-fg"
                        >
                          <Pencil className="h-3.5 w-3.5" /> Editar
                        </Link>
                        {podeExcluir && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              remover(c);
                            }}
                            aria-label="Remover"
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

          {totalPages > 1 && (
            <div className="flex flex-wrap items-center justify-between gap-3 px-1">
              <p className="text-xs text-fg-subtle">
                Mostrando {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, visibleRows.length)} de{" "}
                {visibleRows.length}
              </p>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="rounded-md px-2 py-1 text-xs font-medium text-fg-muted transition-colors hover:bg-surface-muted hover:text-fg disabled:pointer-events-none disabled:opacity-40"
                >
                  ‹ Anterior
                </button>
                {pageWindow(page, totalPages).map((n, i) =>
                  n === "…" ? (
                    <span key={`e${i}`} className="px-1.5 text-xs text-fg-subtle">
                      …
                    </span>
                  ) : (
                    <button
                      key={n}
                      onClick={() => setPage(n)}
                      aria-current={n === page ? "page" : undefined}
                      className={cn(
                        "min-w-[2rem] rounded-md px-2 py-1 text-xs font-medium transition-colors",
                        n === page
                          ? "bg-accent text-accent-fg"
                          : "text-fg-muted hover:bg-surface-muted hover:text-fg"
                      )}
                    >
                      {n}
                    </button>
                  )
                )}
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                  className="rounded-md px-2 py-1 text-xs font-medium text-fg-muted transition-colors hover:bg-surface-muted hover:text-fg disabled:pointer-events-none disabled:opacity-40"
                >
                  Próxima ›
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
