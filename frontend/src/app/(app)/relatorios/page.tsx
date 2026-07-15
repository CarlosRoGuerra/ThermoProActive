"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  DollarSign,
  Download,
  FileBarChart,
  FileSpreadsheet,
  FileText,
  History,
  Users,
} from "lucide-react";
import { api, downloadFile } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Cliente, Paginated, ReportData, ReportDef } from "@/lib/types";
import {
  Button,
  Card,
  EmptyState,
  Field,
  Input,
  PageHeader,
  Select,
  Spinner,
  Table,
  TableSkeleton,
  TBody,
  TD,
  TH,
  THead,
  TR,
  cn,
} from "@/components/ui";
import { Stagger, StaggerItem } from "@/components/motion";

const CAT_ICON: Record<string, typeof FileText> = {
  Técnico: FileText,
  Gerencial: BarChart3,
  Equipamento: Activity,
  Falhas: AlertTriangle,
  Financeiro: DollarSign,
  Produtividade: Users,
  Histórico: History,
};

export default function RelatoriosPage() {
  const { user } = useAuth();
  const [defs, setDefs] = useState<ReportDef[]>([]);
  const [clientes, setClientes] = useState<Cliente[]>([]);
  const [sel, setSel] = useState<ReportDef | null>(null);
  const [filtros, setFiltros] = useState({ cliente: "", data_inicio: "", data_fim: "" });
  const [preview, setPreview] = useState<ReportData | null>(null);
  const [loadingDefs, setLoadingDefs] = useState(true);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [baixando, setBaixando] = useState<string | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      api<ReportDef[]>("/relatorios/").then(setDefs),
      user?.is_interno
        ? api<Paginated<Cliente>>("/clientes/").then((d) => setClientes(d.results))
        : Promise.resolve(),
    ]).finally(() => setLoadingDefs(false));
  }, [user]);

  const queryString = useCallback(() => {
    const p = new URLSearchParams();
    if (filtros.cliente) p.set("cliente", filtros.cliente);
    if (filtros.data_inicio) p.set("data_inicio", filtros.data_inicio);
    if (filtros.data_fim) p.set("data_fim", filtros.data_fim);
    return p.toString();
  }, [filtros]);

  const gerarPreview = useCallback(
    async (def: ReportDef) => {
      setLoadingPreview(true);
      setErro(null);
      try {
        const qs = queryString();
        const data = await api<ReportData>(`/relatorios/${def.key}/?formato=json${qs ? `&${qs}` : ""}`);
        setPreview(data);
      } catch {
        setErro("Não foi possível gerar o relatório.");
        setPreview(null);
      } finally {
        setLoadingPreview(false);
      }
    },
    [queryString]
  );

  function selecionar(def: ReportDef) {
    setSel(def);
    setPreview(null);
    gerarPreview(def);
  }

  async function exportar(formato: "csv" | "xlsx" | "pdf") {
    if (!sel) return;
    setBaixando(formato);
    setErro(null);
    try {
      const qs = queryString();
      await downloadFile(
        `/relatorios/${sel.key}/?formato=${formato}${qs ? `&${qs}` : ""}`,
        `relatorio_${sel.key}.${formato}`
      );
    } catch {
      setErro("Falha ao baixar o arquivo.");
    } finally {
      setBaixando(null);
    }
  }

  if (loadingDefs) return <Spinner />;

  return (
    <div className="space-y-6">
      <PageHeader
        icon={FileBarChart}
        title="Relatórios"
        description="Relatórios técnicos e gerenciais com exportação PDF, Excel e CSV (Anexo I 2.9)."
      />

      {/* Catálogo de relatórios */}
      <Stagger className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {defs.map((d) => {
          const Icon = CAT_ICON[d.categoria] ?? FileText;
          const active = sel?.key === d.key;
          return (
            <StaggerItem key={d.key}>
              <button onClick={() => selecionar(d)} className="block w-full text-left">
                <Card
                  className={cn(
                    "h-full transition duration-200 ease-out-soft hover:-translate-y-0.5 hover:shadow-md",
                    active ? "border-accent ring-1 ring-accent" : "hover:border-border-strong"
                  )}
                >
                  <div className="flex items-start gap-3">
                    <div
                      className={cn(
                        "flex h-9 w-9 shrink-0 items-center justify-center rounded-lg",
                        active ? "bg-accent text-accent-fg" : "bg-accent-subtle text-accent"
                      )}
                    >
                      <Icon className="h-5 w-5" />
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-fg">{d.nome}</p>
                      <p className="mt-0.5 text-xs text-fg-muted">{d.descricao}</p>
                    </div>
                  </div>
                </Card>
              </button>
            </StaggerItem>
          );
        })}
      </Stagger>

      {!sel ? (
        <Card>
          <EmptyState
            icon={FileBarChart}
            title="Selecione um relatório"
            description="Escolha um dos relatórios acima para visualizar e exportar."
          />
        </Card>
      ) : (
        <div className="space-y-4">
          {/* Filtros + exportação */}
          <Card>
            <div className="flex flex-wrap items-end gap-3">
              {user?.is_interno && (
                <Field label="Cliente">
                  <Select
                    value={filtros.cliente}
                    onChange={(e) => setFiltros({ ...filtros, cliente: e.target.value })}
                  >
                    <option value="">Todos</option>
                    {clientes.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.nome}
                      </option>
                    ))}
                  </Select>
                </Field>
              )}
              <Field label="Data início">
                <Input
                  type="date"
                  value={filtros.data_inicio}
                  onChange={(e) => setFiltros({ ...filtros, data_inicio: e.target.value })}
                />
              </Field>
              <Field label="Data fim">
                <Input
                  type="date"
                  value={filtros.data_fim}
                  onChange={(e) => setFiltros({ ...filtros, data_fim: e.target.value })}
                />
              </Field>
              <Button variant="secondary" onClick={() => gerarPreview(sel)} loading={loadingPreview}>
                Aplicar filtros
              </Button>
              <div className="ml-auto flex items-end gap-2">
                <Button variant="secondary" icon={FileText} onClick={() => exportar("pdf")} loading={baixando === "pdf"}>
                  PDF
                </Button>
                <Button variant="secondary" icon={FileSpreadsheet} onClick={() => exportar("xlsx")} loading={baixando === "xlsx"}>
                  Excel
                </Button>
                <Button variant="secondary" icon={Download} onClick={() => exportar("csv")} loading={baixando === "csv"}>
                  CSV
                </Button>
              </div>
            </div>
            {erro && <p className="mt-3 text-sm text-danger-fg">{erro}</p>}
          </Card>

          {/* Preview */}
          {loadingPreview ? (
            <TableSkeleton rows={6} cols={5} />
          ) : !preview ? null : preview.linhas.length === 0 ? (
            <Card>
              <EmptyState icon={FileBarChart} title="Sem dados" description="Nenhum registro para os filtros selecionados." />
            </Card>
          ) : (
            <div className="space-y-2">
              <p className="text-sm font-medium text-fg">
                {preview.titulo}{" "}
                <span className="text-fg-subtle">· {preview.total_linhas} linha(s)</span>
              </p>
              <Table>
                <THead>
                  {preview.colunas.map((c) => (
                    <TH key={c}>{c}</TH>
                  ))}
                </THead>
                <TBody>
                  {preview.linhas.map((linha, i) => (
                    <TR key={i}>
                      {linha.map((cel, j) => (
                        <TD key={j} className={j === 0 ? "font-medium text-fg" : ""}>
                          {String(cel)}
                        </TD>
                      ))}
                    </TR>
                  ))}
                </TBody>
              </Table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
