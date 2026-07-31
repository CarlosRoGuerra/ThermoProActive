"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Activity, Building2, CornerDownRight, Pencil, Plus, Search, Trash2 } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useClienteAtivo } from "@/lib/cliente-ativo";
import type { Equipamento, Paginated } from "@/lib/types";
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

export default function EquipamentosPage() {
  const { user } = useAuth();
  const router = useRouter();
  const podeEditar = !!user?.is_interno;
  const podeExcluir = !!user?.pode_excluir;

  const { clienteAtivo } = useClienteAtivo();
  const [rows, setRows] = useState<Equipamento[]>([]);
  const [loading, setLoading] = useState(true);
  const [busca, setBusca] = useState("");
  const [page, setPage] = useState(1);
  const [msg, setMsg] = useState<string | null>(null);

  // A tela mostra sempre os equipamentos do CLIENTE ATIVO. Trocar o cliente no
  // topo re-filtra aqui automaticamente (mesma lógica das Áreas/Setores).
  useEffect(() => {
    if (!clienteAtivo) {
      setRows([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    setPage(1);
    api<Paginated<Equipamento>>(
      `/equipamentos/?page_size=1000&setor__area__cliente=${clienteAtivo.id}`
    )
      .then((d) => setRows(d.results))
      .catch(() => setRows([]))
      .finally(() => setLoading(false));
  }, [clienteAtivo]);

  async function remover(e: Equipamento) {
    if (!confirm(`Remover o equipamento “${e.tag}”?`)) return;
    setMsg(null);
    try {
      await api(`/equipamentos/${e.id}/`, { method: "DELETE" });
      setRows((r) => r.filter((x) => x.id !== e.id));
    } catch (err) {
      setMsg(err instanceof ApiError ? err.message : "Erro ao remover o equipamento.");
    }
  }

  const visibleRows = useMemo(() => {
    const q = busca.trim().toLowerCase();
    const filtrados = q
      ? rows.filter((e) =>
          [e.tag, e.nome, e.fabricante, e.modelo, e.numero_serie, e.setor_nome]
            .map((v) => String(v ?? "").toLowerCase())
            .join(" ")
            .includes(q)
        )
      : rows;

    // Sem busca, mostra a árvore: cada sub-item logo abaixo do seu equipamento
    // principal (Caldeira → Exaustor), como na hierarquia acordada com o cliente.
    if (q) {
      return [...filtrados].sort((a, b) =>
        String(a.tag ?? "").localeCompare(String(b.tag ?? ""), "pt-BR", { numeric: true })
      );
    }
    const porTag = (a: Equipamento, b: Equipamento) =>
      String(a.tag ?? "").localeCompare(String(b.tag ?? ""), "pt-BR", { numeric: true });
    const filhosDe = (paiId: number | null) =>
      filtrados.filter((e) => e.equipamento_pai === paiId).sort(porTag);

    const ordenados: Equipamento[] = [];
    const empilhar = (paiId: number | null, profundidade: number) => {
      for (const e of filhosDe(paiId)) {
        ordenados.push(e);
        if (profundidade < 5) empilhar(e.id, profundidade + 1);
      }
    };
    empilhar(null, 0);
    // Sub-itens cujo pai foi filtrado fora entram no fim, para não sumirem.
    for (const e of filtrados) if (!ordenados.includes(e)) ordenados.push(e);
    return ordenados;
  }, [rows, busca]);

  const totalPages = Math.max(1, Math.ceil(visibleRows.length / PAGE_SIZE));
  const pageRows = visibleRows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  useEffect(() => {
    if (page > totalPages) setPage(totalPages);
  }, [page, totalPages]);

  return (
    <div className="space-y-6">
      <PageHeader
        icon={Activity}
        title="Equipamentos"
        description={
          clienteAtivo
            ? `Equipamentos de ${clienteAtivo.nome_fantasia || clienteAtivo.nome}, por Área → Setor.`
            : "Máquinas monitoradas, organizadas por Cliente → Área → Setor."
        }
        actions={
          podeEditar && clienteAtivo ? (
            <Link href="/equipamentos/novo">
              <Button icon={Plus}>Novo equipamento</Button>
            </Link>
          ) : undefined
        }
      />

      {/* Sem cliente ativo não há o que mostrar — os equipamentos são dele. */}
      {!clienteAtivo && (
        <Card>
          <EmptyState
            icon={Building2}
            title="Selecione um cliente"
            description="Os equipamentos pertencem a um cliente. Ative um cliente no seletor do topo para vê-los e cadastrá-los."
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
            onChange={(e) => {
              setBusca(e.target.value);
              setPage(1);
            }}
            placeholder="Buscar por TAG, nº de série, fabricante…"
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
            icon={busca ? Search : Activity}
            title={busca ? "Nada encontrado" : "Nenhum equipamento"}
            description={
              busca
                ? `Nenhum equipamento corresponde a “${busca}”.`
                : "Este cliente ainda não tem equipamentos cadastrados."
            }
            action={
              !busca && podeEditar ? (
                <Link href="/equipamentos/novo">
                  <Button icon={Plus}>Novo equipamento</Button>
                </Link>
              ) : undefined
            }
          />
        </Card>
      ) : (
        <>
          <Table>
            <THead>
              <TH>TAG</TH>
              <TH>Equipamento</TH>
              <TH>Setor</TH>
              <TH>Fabricante</TH>
              <TH>Classe</TH>
              {podeEditar && <TH />}
            </THead>
            <TBody>
              {pageRows.map((e) => (
                <TR
                  key={e.id}
                  onClick={podeEditar ? () => router.push(`/equipamentos/${e.id}`) : undefined}
                >
                  <TD className="font-mono text-xs font-semibold text-fg">
                    {/* Indenta o sub-item para deixar a hierarquia visível. */}
                    <span style={{ paddingLeft: `${e.nivel * 14}px` }} className="inline-flex items-center gap-1.5">
                      {e.is_subitem && <CornerDownRight className="h-3 w-3 shrink-0 text-fg-subtle" />}
                      {e.tag}
                    </span>
                  </TD>
                  <TD className="text-fg">
                    {e.nome}
                    {e.qtd_subitens > 0 && (
                      <Badge tone="neutral" className="ml-2">
                        {e.qtd_subitens} sub-{e.qtd_subitens > 1 ? "itens" : "item"}
                      </Badge>
                    )}
                    {e.componentes?.length > 0 && (
                      <span className="block text-xs text-fg-subtle">
                        {e.componentes.map((c) => c.nome).join(" · ")}
                      </span>
                    )}
                  </TD>
                  <TD>{e.setor_nome || "—"}</TD>
                  <TD>{e.fabricante || "—"}</TD>
                  <TD>
                    <Badge tone="accent">{e.classe_iso}</Badge>
                  </TD>
                  {podeEditar && (
                    <TD className="text-right">
                      <div className="flex items-center justify-end gap-1">
                        <Link
                          href={`/equipamentos/${e.id}`}
                          onClick={(ev) => ev.stopPropagation()}
                          className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-fg-muted transition-colors hover:bg-surface-muted hover:text-fg"
                        >
                          <Pencil className="h-3.5 w-3.5" /> Editar
                        </Link>
                        {podeExcluir && (
                          <button
                            onClick={(ev) => {
                              ev.stopPropagation();
                              remover(e);
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
