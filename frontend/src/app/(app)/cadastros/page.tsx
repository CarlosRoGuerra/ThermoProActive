"use client";

import { useEffect, useMemo, useState } from "react";
import { Database, Pencil, Plus, Search, Trash2, X } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Paginated } from "@/lib/types";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  Field,
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

type FieldType = "text" | "number" | "color" | "multiref" | "date";
type FieldDef = {
  key: string;
  label: string;
  type?: FieldType;
  required?: boolean;
  optionsEndpoint?: string; // para type "multiref"
  maxLength?: number; // limite espelhando o max_length do modelo
};
type CatalogDef = { key: string; label: string; endpoint: string; fields: FieldDef[]; columns: string[] };

// Quantidade de itens por página na listagem.
const PAGE_SIZE = 10;

// Rótulos amigáveis para os cabeçalhos das colunas (evita "tecnologias_display").
const COL_LABELS: Record<string, string> = {
  codigo: "Código",
  nome: "Nome",
  orgao: "Órgão",
  descricao: "Descrição",
  sigla: "Sigla",
  nivel: "Nível",
  cor: "Cor",
  tecnologias_display: "Tecnologias",
  tipo: "Tipo",
  marca: "Marca",
  modelo: "Modelo",
  numero_serie: "Nº de série",
  data_ultima_calibracao: "Última calibração",
  entidade_calibracao: "Entidade de calibração",
};

const CATALOGOS: CatalogDef[] = [
  {
    key: "normas",
    label: "Normas (NBRs)",
    endpoint: "normas",
    fields: [
      { key: "codigo", label: "Código", required: true, maxLength: 40 },
      { key: "nome", label: "Título", required: true, maxLength: 250 },
      { key: "orgao", label: "Órgão", maxLength: 40 },
      {
        key: "tecnologias",
        label: "Tecnologias aplicáveis",
        type: "multiref",
        optionsEndpoint: "tecnologias-analise",
      },
    ],
    columns: ["codigo", "nome", "orgao", "tecnologias_display"],
  },
  {
    key: "tecnologias",
    label: "Tecnologias de análise",
    endpoint: "tecnologias-analise",
    fields: [
      { key: "nome", label: "Nome", required: true },
      { key: "sigla", label: "Sigla" },
    ],
    columns: ["nome", "sigla"],
  },
  {
    key: "instrumentos",
    label: "Instrumentação",
    endpoint: "instrumentos",
    fields: [
      { key: "tipo", label: "Tipo de instrumento", required: true },
      { key: "marca", label: "Marca" },
      { key: "modelo", label: "Modelo" },
      { key: "numero_serie", label: "Nº de série" },
      { key: "data_ultima_calibracao", label: "Última calibração", type: "date" },
      { key: "entidade_calibracao", label: "Entidade de calibração" },
    ],
    columns: ["tipo", "marca", "modelo", "numero_serie", "data_ultima_calibracao"],
  },
  catSimples("tipos-equipamento", "Tipos de equipamento"),
  catComTecnologias("tipos-componente", "Tipos de componente"),
  catComTecnologias("tipos-anomalia", "Tipos de anomalia"),
  catComTecnologias("tipos-recomendacao", "Tipos de recomendação"),
  {
    key: "criticidades",
    label: "Tipos de criticidade",
    endpoint: "tipos-criticidade",
    fields: [
      { key: "nome", label: "Nome", required: true },
      { key: "nivel", label: "Nível", type: "number" },
      { key: "cor", label: "Cor", type: "color" },
    ],
    columns: ["nome", "nivel", "cor"],
  },
  catSimples("classificacoes-inspecao", "Classificações de inspeção"),
  catSimples("tipos-inspecao", "Tipos de inspeção"),
  catSimples("falhas-recorrentes", "Falhas recorrentes"),
  catSimples("grupos-acesso", "Grupos de acesso"),
];

function catSimples(endpoint: string, label: string): CatalogDef {
  return {
    key: endpoint,
    label,
    endpoint,
    fields: [
      { key: "nome", label: "Nome", required: true },
      { key: "descricao", label: "Descrição" },
    ],
    columns: ["nome", "descricao"],
  };
}

// Catálogo simples + vínculo com tecnologias de análise (facilita filtrar por atividade).
function catComTecnologias(endpoint: string, label: string): CatalogDef {
  return {
    key: endpoint,
    label,
    endpoint,
    fields: [
      { key: "nome", label: "Nome", required: true },
      { key: "descricao", label: "Descrição" },
      {
        key: "tecnologias",
        label: "Tecnologias aplicáveis",
        type: "multiref",
        optionsEndpoint: "tecnologias-analise",
      },
    ],
    columns: ["nome", "descricao", "tecnologias_display"],
  };
}

// Janela de números de página (com reticências quando há muitas páginas).
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

type TecOption = { id: number; nome: string; sigla?: string };
type Row = Record<string, unknown> & { id: number };
type FormValue = string | number[];

function optionLabel(o: TecOption) {
  return o.sigla?.trim() ? o.sigla : o.nome;
}

function colLabel(c: string) {
  return COL_LABELS[c] ?? c.charAt(0).toUpperCase() + c.slice(1);
}

// Texto pesquisável de uma linha (junta as colunas visíveis + nomes de tecnologias).
function haystack(r: Row, def: CatalogDef) {
  const parts: string[] = [];
  for (const c of def.columns) {
    const v = r[c];
    if (Array.isArray(v)) {
      parts.push((v as TecOption[]).map((t) => `${t.sigla ?? ""} ${t.nome ?? ""}`).join(" "));
    } else {
      parts.push(String(v ?? ""));
    }
  }
  return parts.join(" ").toLowerCase();
}

export default function CadastrosPage() {
  const { user } = useAuth();
  const isAdmin = user?.perfil === "ADMIN";

  const [sel, setSel] = useState<CatalogDef>(CATALOGOS[0]);
  const [rows, setRows] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState<Record<string, FormValue>>({});
  const [editingId, setEditingId] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [options, setOptions] = useState<Record<string, TecOption[]>>({});

  const emptyForm = useMemo(
    () =>
      Object.fromEntries(
        sel.fields.map((f) => [
          f.key,
          f.type === "color" ? "#64748b" : f.type === "multiref" ? [] : "",
        ])
      ) as Record<string, FormValue>,
    [sel]
  );

  async function reload(def: CatalogDef) {
    setLoading(true);
    try {
      // Catálogos são pequenos: traz a lista completa para ordenar/buscar no cliente.
      const data = await api<Paginated<Row>>(`/${def.endpoint}/?page_size=1000`);
      setRows(data.results);
    } finally {
      setLoading(false);
    }
  }

  // Ao trocar de catálogo: reseta form/edição/busca, recarrega e busca opções de multiref.
  useEffect(() => {
    setForm(emptyForm);
    setEditingId(null);
    setMsg(null);
    setQuery("");
    setPage(1);
    reload(sel);
    for (const f of sel.fields) {
      if (f.type === "multiref" && f.optionsEndpoint && !options[f.optionsEndpoint]) {
        const ep = f.optionsEndpoint;
        api<Paginated<TecOption>>(`/${ep}/?page_size=1000`)
          .then((d) => setOptions((o) => ({ ...o, [ep]: d.results })))
          .catch(() => {});
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sel]);

  function toggleTec(key: string, id: number) {
    setForm((prev) => {
      const cur = Array.isArray(prev[key]) ? (prev[key] as number[]) : [];
      const next = cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id];
      return { ...prev, [key]: next };
    });
  }

  function iniciarEdicao(r: Row) {
    const f: Record<string, FormValue> = {};
    for (const fd of sel.fields) {
      if (fd.type === "multiref") {
        f[fd.key] = Array.isArray(r[fd.key]) ? (r[fd.key] as number[]) : [];
      } else if (fd.type === "color") {
        f[fd.key] = String(r[fd.key] ?? "#64748b");
      } else {
        f[fd.key] = r[fd.key] == null ? "" : String(r[fd.key]);
      }
    }
    setForm(f);
    setEditingId(r.id);
    setMsg(null);
    if (typeof window !== "undefined") window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function cancelarEdicao() {
    setForm(emptyForm);
    setEditingId(null);
    setMsg(null);
  }

  async function salvar() {
    setSaving(true);
    setMsg(null);
    try {
      const body: Record<string, unknown> = {};
      for (const f of sel.fields) {
        const v = form[f.key];
        if (f.type === "multiref") {
          body[f.key] = Array.isArray(v) ? v : [];
        } else if (f.type === "number") {
          if (v !== "" && v !== undefined) body[f.key] = Number(v);
        } else if (f.type === "date") {
          // data vazia: omite na criação; envia null na edição (permite limpar)
          if (v !== "" && v !== undefined) body[f.key] = v;
          else if (editingId !== null) body[f.key] = null;
        } else {
          // text / color — na edição enviamos mesmo vazio (permite limpar campos opcionais)
          if (editingId !== null || (v !== "" && v !== undefined)) body[f.key] = v ?? "";
        }
      }
      if (editingId !== null) {
        await api(`/${sel.endpoint}/${editingId}/`, { method: "PATCH", body });
      } else {
        await api(`/${sel.endpoint}/`, { method: "POST", body });
      }
      cancelarEdicao();
      await reload(sel);
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "Erro ao salvar.");
    } finally {
      setSaving(false);
    }
  }

  async function remover(id: number) {
    if (editingId === id) cancelarEdicao();
    await api(`/${sel.endpoint}/${id}/`, { method: "DELETE" });
    await reload(sel);
  }

  const podeSalvar = sel.fields
    .filter((f) => f.required)
    .every((f) => {
      const v = form[f.key];
      return typeof v === "string" ? v.trim() !== "" : Array.isArray(v) ? v.length > 0 : v != null;
    });

  // Busca (cliente) + ordem alfabética pela coluna principal (código p/ normas, nome p/ demais).
  const visibleRows = useMemo(() => {
    const q = query.trim().toLowerCase();
    const primary = sel.columns[0];
    const filtered = q ? rows.filter((r) => haystack(r, sel).includes(q)) : rows;
    return [...filtered].sort((a, b) =>
      String(a[primary] ?? "").localeCompare(String(b[primary] ?? ""), "pt-BR", {
        numeric: true,
        sensitivity: "base",
      })
    );
  }, [rows, query, sel]);

  const totalPages = Math.max(1, Math.ceil(visibleRows.length / PAGE_SIZE));
  const pageRows = visibleRows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  // Se a página atual ficou além do total (após excluir/filtrar), recua.
  useEffect(() => {
    if (page > totalPages) setPage(totalPages);
  }, [page, totalPages]);

  return (
    <div className="space-y-6">
      <PageHeader
        icon={Database}
        title="Cadastros"
        description="Tabelas de referência do sistema (Anexo I 2.2). Rotas e vínculos relacionais via painel administrativo."
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[230px_1fr]">
        <Card padding={false} className="h-fit p-2">
          <nav className="space-y-0.5">
            {CATALOGOS.map((c) => (
              <button
                key={c.key}
                onClick={() => setSel(c)}
                className={cn(
                  "block w-full rounded-lg px-3 py-2 text-left text-sm font-medium transition-colors duration-150",
                  sel.key === c.key
                    ? "bg-accent-subtle text-accent-subtle-fg"
                    : "text-fg-muted hover:bg-surface-muted hover:text-fg"
                )}
              >
                {c.label}
              </button>
            ))}
          </nav>
        </Card>

        <div className="space-y-4">
          {/* Formulário de criar/editar — somente Admin (curadoria centralizada). */}
          {isAdmin ? (
            <Card>
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-sm font-semibold text-fg">
                  {editingId !== null ? "Editar" : "Novo"}: {sel.label}
                </h2>
                {editingId !== null && (
                  <button
                    onClick={cancelarEdicao}
                    className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-fg-muted transition-colors hover:bg-surface-muted hover:text-fg"
                  >
                    <X className="h-3.5 w-3.5" /> Cancelar
                  </button>
                )}
              </div>
              <div className="flex flex-wrap items-end gap-3">
                {sel.fields.map((f) => (
                  <Field key={f.key} label={f.required ? `${f.label} *` : f.label}>
                    {f.type === "color" ? (
                      <input
                        type="color"
                        value={(form[f.key] as string) ?? "#64748b"}
                        onChange={(e) => setForm({ ...form, [f.key]: e.target.value })}
                        className="h-10 w-16 cursor-pointer rounded-lg border border-border bg-surface p-1"
                      />
                    ) : f.type === "multiref" ? (
                      <div className="flex max-w-xl flex-wrap gap-1.5">
                        {(options[f.optionsEndpoint ?? ""] ?? []).length === 0 ? (
                          <span className="text-xs text-fg-subtle">
                            Nenhuma tecnologia cadastrada ainda.
                          </span>
                        ) : (
                          (options[f.optionsEndpoint ?? ""] ?? []).map((o) => {
                            const selected =
                              Array.isArray(form[f.key]) && (form[f.key] as number[]).includes(o.id);
                            return (
                              <button
                                key={o.id}
                                type="button"
                                onClick={() => toggleTec(f.key, o.id)}
                                className={cn(
                                  "rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset transition-colors",
                                  selected
                                    ? "bg-accent-subtle text-accent-subtle-fg ring-accent/20"
                                    : "bg-surface-muted text-fg-muted ring-border hover:text-fg"
                                )}
                                title={o.nome}
                              >
                                {optionLabel(o)}
                              </button>
                            );
                          })
                        )}
                      </div>
                    ) : (
                      <Input
                        type={f.type === "number" ? "number" : f.type === "date" ? "date" : "text"}
                        value={(form[f.key] as string) ?? ""}
                        maxLength={f.maxLength}
                        onChange={(e) => setForm({ ...form, [f.key]: e.target.value })}
                      />
                    )}
                  </Field>
                ))}
                <Button
                  onClick={salvar}
                  loading={saving}
                  disabled={!podeSalvar}
                  icon={editingId !== null ? Pencil : Plus}
                >
                  {editingId !== null ? "Salvar" : "Adicionar"}
                </Button>
              </div>
              {msg && <p className="mt-2 text-sm text-danger-fg">{msg}</p>}
            </Card>
          ) : (
            <Card>
              <p className="text-sm text-fg-muted">
                Você pode consultar e buscar os cadastros. A criação e edição são restritas ao
                perfil <span className="font-medium text-fg">Administrador</span>.
              </p>
            </Card>
          )}

          {/* Busca */}
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-fg-subtle" />
            <Input
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setPage(1);
              }}
              placeholder={`Buscar em ${sel.label.toLowerCase()}…`}
              className="pl-9"
            />
          </div>

          {loading ? (
            <Card>
              <Spinner />
            </Card>
          ) : visibleRows.length === 0 ? (
            <Card>
              <EmptyState
                icon={query ? Search : Database}
                title={query ? "Nada encontrado" : "Nenhum registro"}
                description={
                  query
                    ? `Nenhum item corresponde a “${query}”.`
                    : `Adicione o primeiro item em “${sel.label}”.`
                }
              />
            </Card>
          ) : (
            <>
            <Table>
              <THead>
                {sel.columns.map((c) => (
                  <TH key={c}>{colLabel(c)}</TH>
                ))}
                {isAdmin && <TH />}
              </THead>
              <TBody>
                {pageRows.map((r) => (
                  <TR key={r.id}>
                    {sel.columns.map((c) => (
                      <TD key={c} className={c === "nome" || c === "codigo" ? "font-medium text-fg" : ""}>
                        {c === "cor" ? (
                          <span className="inline-flex items-center gap-2">
                            <span
                              className="h-4 w-4 rounded-full ring-1 ring-border"
                              style={{ background: String(r[c] ?? "") }}
                            />
                            {String(r[c] ?? "")}
                          </span>
                        ) : Array.isArray(r[c]) ? (
                          (r[c] as TecOption[]).length ? (
                            <span className="flex flex-wrap gap-1">
                              {(r[c] as TecOption[]).map((t) => (
                                <Badge key={t.id} tone="accent">
                                  {optionLabel(t)}
                                </Badge>
                              ))}
                            </span>
                          ) : (
                            "—"
                          )
                        ) : (
                          String(r[c] ?? "—")
                        )}
                      </TD>
                    ))}
                    {isAdmin && (
                      <TD className="text-right">
                        <div className="flex items-center justify-end gap-1">
                          <button
                            onClick={() => iniciarEdicao(r)}
                            aria-label="Editar"
                            className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-fg-muted transition-colors hover:bg-surface-muted hover:text-fg"
                          >
                            <Pencil className="h-3.5 w-3.5" /> Editar
                          </button>
                          <button
                            onClick={() => remover(r.id)}
                            aria-label="Remover"
                            className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-danger-fg transition-colors hover:bg-danger-subtle"
                          >
                            <Trash2 className="h-3.5 w-3.5" /> Remover
                          </button>
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
      </div>
    </div>
  );
}
