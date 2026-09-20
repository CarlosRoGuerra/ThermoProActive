"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Activity,
  ChartColumn,
  CircleDollarSign,
  Download,
  FileChartColumn,
  FileSpreadsheet,
  FileText,
  History,
  TriangleAlert,
  Users,
  type LucideIcon,
} from "lucide-react";
import {
  Button,
  Card,
  CardHeader,
  EmptyState,
  ErrorCard,
  Field,
  Input,
  LoadingState,
  PageBody,
  PageHeader,
  SectionHeader,
  Table,
  TBody,
  TD,
  TH,
  THead,
  TR,
  cn,
  useToast,
} from "@/components/ds";
import { Combobox } from "@/components/combobox";
import { api, downloadFile, qs as montarQuery } from "@/lib/api";
import { useRecurso } from "@/lib/recurso";
import { interpretarFalha, type Falha } from "@/lib/erros";
import { useClientes } from "@/lib/hierarquia";
import { inteiro } from "@/lib/format";
import type { ReportData, ReportDef } from "@/lib/types";

/* ==========================================================================
   Relatórios — compartilhado pelos dois portais.
   --------------------------------------------------------------------------
   O backend já filtra o catálogo (`interno_only`) e o conteúdo por cliente, de
   modo que a mesma tela serve às duas áreas. Diferenças:
     • o filtro por cliente só existe para a equipe interna (o cliente é ele mesmo);
     • os textos explicam o que cada relatório serve para responder.

   Fluxo: escolher → pré-visualizar na tela → exportar PDF/Excel/CSV. A
   pré-visualização evita o vai-e-vem de baixar arquivo errado.
   ========================================================================== */

const ICONE_CATEGORIA: Record<string, LucideIcon> = {
  Técnico: FileText,
  Gerencial: ChartColumn,
  Equipamento: Activity,
  Falhas: TriangleAlert,
  Financeiro: CircleDollarSign,
  Produtividade: Users,
  Histórico: History,
};

export function PainelRelatorios({ ehCliente }: { ehCliente: boolean }) {
  const toast = useToast();
  const catalogo = useRecurso<ReportDef[]>("/relatorios/", "catálogo de relatórios");
  const { opcoes: opcoesClientes } = useClientes(!ehCliente);

  const [selecionado, setSelecionado] = useState<ReportDef | null>(null);
  const [filtros, setFiltros] = useState<{ cliente: number | ""; data_inicio: string; data_fim: string }>({
    cliente: "",
    data_inicio: "",
    data_fim: "",
  });
  const [previa, setPrevia] = useState<ReportData | null>(null);
  const [carregandoPrevia, setCarregandoPrevia] = useState(false);
  const [falhaPrevia, setFalhaPrevia] = useState<Falha | null>(null);
  const [baixando, setBaixando] = useState<string | null>(null);

  const query = useCallback(
    () =>
      montarQuery({
        cliente: filtros.cliente,
        data_inicio: filtros.data_inicio,
        data_fim: filtros.data_fim,
      }).replace(/^\?/, ""),
    [filtros]
  );

  const gerarPrevia = useCallback(
    async (def: ReportDef) => {
      setCarregandoPrevia(true);
      setFalhaPrevia(null);
      try {
        const extra = query();
        const dados = await api<ReportData>(
          `/relatorios/${def.key}/?formato=json${extra ? `&${extra}` : ""}`
        );
        setPrevia(dados);
      } catch (e) {
        setFalhaPrevia(interpretarFalha(e));
        setPrevia(null);
      } finally {
        setCarregandoPrevia(false);
      }
    },
    [query]
  );

  // Trocar de relatório já mostra o resultado, sem exigir "aplicar".
  useEffect(() => {
    if (selecionado) void gerarPrevia(selecionado);
    // `gerarPrevia` muda com os filtros; aqui queremos disparar só na troca.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selecionado]);

  async function exportar(formato: "csv" | "xlsx" | "pdf") {
    if (!selecionado) return;
    setBaixando(formato);
    try {
      const extra = query();
      await downloadFile(
        `/relatorios/${selecionado.key}/?formato=${formato}${extra ? `&${extra}` : ""}`,
        `relatorio_${selecionado.key}.${formato}`
      );
      toast.sucesso("Arquivo gerado", { descricao: `O download do ${formato.toUpperCase()} começou.` });
    } catch (e) {
      toast.falha(e, "Não foi possível gerar o arquivo agora.");
    } finally {
      setBaixando(null);
    }
  }

  return (
    <PageBody>
      <PageHeader
        icon={FileChartColumn}
        title="Relatórios"
        description={
          ehCliente
            ? "Consolidados da sua operação para levar à reunião: escolha o relatório, confira na tela e exporte em PDF, Excel ou CSV."
            : "Relatórios técnicos e gerenciais com exportação PDF, Excel e CSV (Anexo I 2.9)."
        }
        trilha={[{ label: "Relatórios" }]}
      />

      {catalogo.carregando ? (
        <LoadingState variante="cartoes" linhas={6} label="Carregando relatórios disponíveis…" />
      ) : catalogo.falha ? (
        <ErrorCard falha={catalogo.falha} onRetry={catalogo.recarregar} />
      ) : (
        <>
          <section>
            <SectionHeader
              title="Escolha o relatório"
              description="Cada um responde a uma pergunta diferente sobre a operação."
            />
            <div
              role="radiogroup"
              aria-label="Relatórios disponíveis"
              className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3"
            >
              {(catalogo.dados ?? []).map((d) => {
                const Icone = ICONE_CATEGORIA[d.categoria] ?? FileText;
                const ativo = selecionado?.key === d.key;
                return (
                  <button
                    key={d.key}
                    type="button"
                    role="radio"
                    aria-checked={ativo}
                    onClick={() => setSelecionado(d)}
                    className="block h-full w-full text-left"
                  >
                    <Card
                      className={cn(
                        "h-full transition-[border-color,box-shadow] duration-normal",
                        ativo
                          ? "border-primary ring-1 ring-primary"
                          : "hover:border-border-strong hover:shadow-md"
                      )}
                    >
                      <div className="flex items-start gap-3">
                        <span
                          className={cn(
                            "flex h-9 w-9 shrink-0 items-center justify-center rounded-lg",
                            ativo ? "bg-primary text-primary-fg" : "bg-primary-subtle text-primary"
                          )}
                          aria-hidden="true"
                        >
                          <Icone className="h-[1.125rem] w-[1.125rem]" />
                        </span>
                        <span className="min-w-0">
                          <span className="block text-sm font-semibold text-fg">{d.nome}</span>
                          <span className="mt-0.5 block text-xs text-fg-muted">{d.descricao}</span>
                        </span>
                      </div>
                    </Card>
                  </button>
                );
              })}
            </div>
          </section>

          {!selecionado ? (
            <Card padding={false}>
              <EmptyState
                icon={FileChartColumn}
                title="Escolha um relatório acima"
                description="Você vê o resultado aqui antes de exportar — assim não baixa arquivo errado."
              />
            </Card>
          ) : (
            <section className="space-y-4">
              <Card>
                <CardHeader
                  title={selecionado.nome}
                  description={selecionado.descricao}
                  actions={
                    <div className="flex items-center gap-1.5">
                      <Button
                        variant="secondary"
                        size="sm"
                        icon={FileText}
                        onClick={() => exportar("pdf")}
                        loading={baixando === "pdf"}
                      >
                        PDF
                      </Button>
                      <Button
                        variant="secondary"
                        size="sm"
                        icon={FileSpreadsheet}
                        onClick={() => exportar("xlsx")}
                        loading={baixando === "xlsx"}
                      >
                        Excel
                      </Button>
                      <Button
                        variant="secondary"
                        size="sm"
                        icon={Download}
                        onClick={() => exportar("csv")}
                        loading={baixando === "csv"}
                      >
                        CSV
                      </Button>
                    </div>
                  }
                />

                <div className="grid grid-cols-1 items-end gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  {!ehCliente && (
                    <Field label="Cliente">
                      <Combobox
                        value={filtros.cliente}
                        onChange={(v) => setFiltros((f) => ({ ...f, cliente: v }))}
                        options={opcoesClientes}
                        placeholder="Todos os clientes"
                        limparLabel="Todos os clientes"
                      />
                    </Field>
                  )}
                  <Field label="De" hint="Deixe em branco para todo o período">
                    <Input
                      type="date"
                      value={filtros.data_inicio}
                      onChange={(e) => setFiltros((f) => ({ ...f, data_inicio: e.target.value }))}
                    />
                  </Field>
                  <Field label="Até">
                    <Input
                      type="date"
                      value={filtros.data_fim}
                      onChange={(e) => setFiltros((f) => ({ ...f, data_fim: e.target.value }))}
                    />
                  </Field>
                  <Button
                    variant="secondary"
                    onClick={() => gerarPrevia(selecionado)}
                    loading={carregandoPrevia}
                  >
                    Aplicar período
                  </Button>
                </div>
              </Card>

              {carregandoPrevia ? (
                <LoadingState variante="tabela" linhas={6} colunas={5} label="Gerando o relatório…" />
              ) : falhaPrevia ? (
                <ErrorCard falha={falhaPrevia} onRetry={() => gerarPrevia(selecionado)} />
              ) : !previa ? null : previa.linhas.length === 0 ? (
                <Card padding={false}>
                  <EmptyState
                    icon={FileChartColumn}
                    title="Nenhum registro no período"
                    description="Não há dados para os filtros escolhidos. Amplie o período ou remova o filtro de cliente."
                    action={
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => setFiltros({ cliente: "", data_inicio: "", data_fim: "" })}
                      >
                        Limpar filtros
                      </Button>
                    }
                  />
                </Card>
              ) : (
                <div className="space-y-2">
                  <p className="text-sm font-medium text-fg">
                    {previa.titulo}{" "}
                    <span className="font-normal text-fg-subtle">
                      · {inteiro(previa.total_linhas)} linha{previa.total_linhas === 1 ? "" : "s"}
                    </span>
                  </p>
                  <Table>
                    <THead>
                      {previa.colunas.map((c) => (
                        <TH key={c}>{c}</TH>
                      ))}
                    </THead>
                    <TBody>
                      {previa.linhas.map((linha, i) => (
                        <TR key={i}>
                          {linha.map((celula, j) => (
                            <TD key={j} className={j === 0 ? "font-medium text-fg" : undefined}>
                              {String(celula ?? "—")}
                            </TD>
                          ))}
                        </TR>
                      ))}
                    </TBody>
                  </Table>
                </div>
              )}
            </section>
          )}
        </>
      )}
    </PageBody>
  );
}
