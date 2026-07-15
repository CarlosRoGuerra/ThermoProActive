"use client";

import { useEffect, useMemo, useState } from "react";
import { Database, Plus, Trash2 } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { Paginated } from "@/lib/types";
import {
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
} from "@/components/ui";

type FieldDef = { key: string; label: string; type?: "text" | "number" | "color"; required?: boolean };
type CatalogDef = { key: string; label: string; endpoint: string; fields: FieldDef[]; columns: string[] };

const CATALOGOS: CatalogDef[] = [
  {
    key: "normas",
    label: "Normas (NBRs)",
    endpoint: "normas",
    fields: [
      { key: "codigo", label: "Código", required: true },
      { key: "nome", label: "Título", required: true },
      { key: "orgao", label: "Órgão" },
    ],
    columns: ["codigo", "nome", "orgao"],
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
  catSimples("tipos-equipamento", "Tipos de equipamento"),
  catSimples("tipos-componente", "Tipos de componente"),
  catSimples("tipos-anomalia", "Tipos de anomalia"),
  catSimples("tipos-recomendacao", "Tipos de recomendação"),
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

type Row = Record<string, unknown> & { id: number };

export default function CadastrosPage() {
  const [sel, setSel] = useState<CatalogDef>(CATALOGOS[0]);
  const [rows, setRows] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const emptyForm = useMemo(
    () => Object.fromEntries(sel.fields.map((f) => [f.key, f.type === "color" ? "#64748b" : ""])),
    [sel]
  );

  async function reload(def: CatalogDef) {
    setLoading(true);
    try {
      const data = await api<Paginated<Row>>(`/${def.endpoint}/`);
      setRows(data.results);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    setForm(emptyForm);
    reload(sel);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sel]);

  async function criar() {
    setSaving(true);
    setMsg(null);
    try {
      const body: Record<string, unknown> = {};
      for (const f of sel.fields) {
        const v = form[f.key];
        if (v !== "" && v !== undefined) body[f.key] = f.type === "number" ? Number(v) : v;
      }
      await api(`/${sel.endpoint}/`, { method: "POST", body });
      setForm(emptyForm);
      await reload(sel);
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "Erro ao salvar.");
    } finally {
      setSaving(false);
    }
  }

  async function remover(id: number) {
    await api(`/${sel.endpoint}/${id}/`, { method: "DELETE" });
    await reload(sel);
  }

  const podeSalvar = sel.fields.filter((f) => f.required).every((f) => (form[f.key] ?? "") !== "");

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
                className={`block w-full rounded-lg px-3 py-2 text-left text-sm font-medium transition-colors duration-150 ${
                  sel.key === c.key
                    ? "bg-accent-subtle text-accent-subtle-fg"
                    : "text-fg-muted hover:bg-surface-muted hover:text-fg"
                }`}
              >
                {c.label}
              </button>
            ))}
          </nav>
        </Card>

        <div className="space-y-4">
          <Card>
            <h2 className="mb-3 text-sm font-semibold text-fg">Novo: {sel.label}</h2>
            <div className="flex flex-wrap items-end gap-3">
              {sel.fields.map((f) => (
                <Field key={f.key} label={f.required ? `${f.label} *` : f.label}>
                  {f.type === "color" ? (
                    <input
                      type="color"
                      value={form[f.key] ?? "#64748b"}
                      onChange={(e) => setForm({ ...form, [f.key]: e.target.value })}
                      className="h-10 w-16 cursor-pointer rounded-lg border border-border bg-surface p-1"
                    />
                  ) : (
                    <Input
                      type={f.type === "number" ? "number" : "text"}
                      value={form[f.key] ?? ""}
                      onChange={(e) => setForm({ ...form, [f.key]: e.target.value })}
                    />
                  )}
                </Field>
              ))}
              <Button onClick={criar} loading={saving} disabled={!podeSalvar} icon={Plus}>
                Adicionar
              </Button>
            </div>
            {msg && <p className="mt-2 text-sm text-danger-fg">{msg}</p>}
          </Card>

          {loading ? (
            <Card>
              <Spinner />
            </Card>
          ) : rows.length === 0 ? (
            <Card>
              <EmptyState icon={Database} title="Nenhum registro" description={`Adicione o primeiro item em “${sel.label}”.`} />
            </Card>
          ) : (
            <Table>
              <THead>
                {sel.columns.map((c) => (
                  <TH key={c} className="capitalize">
                    {c}
                  </TH>
                ))}
                <TH />
              </THead>
              <TBody>
                {rows.map((r) => (
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
                        ) : (
                          String(r[c] ?? "—")
                        )}
                      </TD>
                    ))}
                    <TD className="text-right">
                      <button
                        onClick={() => remover(r.id)}
                        aria-label="Remover"
                        className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-danger-fg transition-colors hover:bg-danger-subtle"
                      >
                        <Trash2 className="h-3.5 w-3.5" /> Remover
                      </button>
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          )}
        </div>
      </div>
    </div>
  );
}
