"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { Building2, FileCheck2, Search, Trash2 } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useClienteAtivo } from "@/lib/cliente-ativo";
import type { Achado, Paginated } from "@/lib/types";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  Field,
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
const ddmmaaaa = (iso: string | null) => (iso ? iso.split("-").reverse().join("/") : "—");

function AnaliseFinalConteudo() {
  const { user } = useAuth();
  const router = useRouter();
  const params = useSearchParams();
  const podeEditar = !!user?.is_interno;
  const podeExcluir = !!user?.pode_excluir;
  const { clienteAtivo } = useClienteAtivo();

  const [rows, setRows] = useState<Achado[]>([]);
  const [tecnologias, setTecnologias] = useState<TecOpt[]>([]);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState<string | null>(null);

  const [busca, setBusca] = useState("");
  const [tecFiltro, setTecFiltro] = useState("");
  // Ao voltar de "Confirmar e publicar", cai na visão "Confirmadas".
  const situacaoInicial = params.get("situacao");
  const [situacao, setSituacao] = useState<"nao" | "sim" | "todas">(
    situacaoInicial === "sim" || situacaoInicial === "todas" ? situacaoInicial : "nao"
  );
  const [dataIni, setDataIni] = useState("");
  const [dataFim, setDataFim] = useState("");

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
    api<Paginated<Achado>>(
      `/achados/?item__carregamento__cliente=${clienteAtivo.id}&item__carregamento__status=TRANSFERIDA&page_size=1000`
    )
      .then((d) => setRows(d.results))
      .catch(() => setRows([]))
      .finally(() => setLoading(false));
  }, [clienteAtivo]);

  async function remover(a: Achado) {
    if (!confirm("Remover esta análise?")) return;
    setMsg(null);
    try {
      await api(`/achados/${a.id}/`, { method: "DELETE" });
      setRows((rs) => rs.filter((x) => x.id !== a.id));
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "Erro ao remover.");
    }
  }

  const visibleRows = useMemo(() => {
    const q = busca.trim().toLowerCase();
    return rows
      .filter((a) => {
        if (situacao === "nao" && a.confirmada) return false;
        if (situacao === "sim" && !a.confirmada) return false;
        if (tecFiltro && a.tecnologia_nome !== tecnologias.find((t) => String(t.id) === tecFiltro)?.nome) return false;
        if (dataIni && (a.data ?? "") < dataIni) return false;
        if (dataFim && (a.data ?? "") > dataFim) return false;
        if (!q) return true;
        return [a.numero_osp, a.equipamento_tag, a.equipamento_nome, a.tipo_componente_nome, a.componente_texto]
          .map((v) => String(v ?? "").toLowerCase())
          .join(" ")
          .includes(q);
      })
      .sort((a, b) => (b.data ?? "").localeCompare(a.data ?? ""));
  }, [rows, busca, situacao, tecFiltro, dataIni, dataFim, tecnologias]);

  return (
    <div className="space-y-6">
      <PageHeader
        icon={FileCheck2}
        title="Análise final"
        description={
          clienteAtivo
            ? `Refino e liberação de ${clienteAtivo.nome_fantasia || clienteAtivo.nome}.`
            : "Refinamento no escritório — selecione um cliente."
        }
      />

      {!clienteAtivo && (
        <Card>
          <EmptyState
            icon={Building2}
            title="Selecione um cliente"
            description="Ative um cliente no seletor do topo para ver as análises transferidas."
            action={
              <Link href="/clientes">
                <Button icon={Building2}>Ir para Clientes</Button>
              </Link>
            }
          />
        </Card>
      )}

      {clienteAtivo && (
        <Card>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
            <div className="relative lg:col-span-2">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-fg-subtle" />
              <Input
                value={busca}
                onChange={(e) => setBusca(e.target.value)}
                placeholder="Buscar OSP, equipamento, componente…"
                className="pl-9"
              />
            </div>
            <Field label="Tecnologia">
              <Select value={tecFiltro} onChange={(e) => setTecFiltro(e.target.value)}>
                <option value="">Todas</option>
                {tecnologias.map((t) => (
                  <option key={t.id} value={t.id}>{t.nome}</option>
                ))}
              </Select>
            </Field>
            <Field label="Situação">
              <Select value={situacao} onChange={(e) => setSituacao(e.target.value as "nao" | "sim" | "todas")}>
                <option value="nao">Não confirmadas</option>
                <option value="sim">Confirmadas</option>
                <option value="todas">Todas</option>
              </Select>
            </Field>
            <div className="grid grid-cols-2 gap-2">
              <Field label="De">
                <Input type="date" value={dataIni} onChange={(e) => setDataIni(e.target.value)} />
              </Field>
              <Field label="Até">
                <Input type="date" value={dataFim} onChange={(e) => setDataFim(e.target.value)} />
              </Field>
            </div>
          </div>
        </Card>
      )}

      {msg && <Card><p className="text-sm text-danger-fg">{msg}</p></Card>}

      {!clienteAtivo ? null : loading ? (
        <Card><Spinner /></Card>
      ) : visibleRows.length === 0 ? (
        <Card>
          <EmptyState
            icon={FileCheck2}
            title="Nada para mostrar"
            description="Nenhuma análise transferida corresponde aos filtros."
          />
        </Card>
      ) : (
        <Table>
          <THead>
            <TH>Código</TH>
            <TH>OSP</TH>
            <TH>Data</TH>
            <TH>Equipamento</TH>
            <TH>Componente</TH>
            <TH>Condição</TH>
            <TH>Tecnologia</TH>
            <TH>Situação</TH>
            {podeEditar && <TH />}
          </THead>
          <TBody>
            {visibleRows.map((a) => (
              <TR key={a.id} onClick={() => router.push(`/inspecoes/final/${a.id}`)}>
                <TD className="font-mono text-xs text-fg-subtle">#{a.id}</TD>
                <TD className="font-medium text-fg">{a.numero_osp || "—"}</TD>
                <TD className="tabular-nums">{ddmmaaaa(a.data)}</TD>
                <TD>
                  <span className="font-mono text-xs font-semibold text-fg">{a.equipamento_tag}</span>{" "}
                  <span className="text-fg-muted">{a.equipamento_nome}</span>
                </TD>
                <TD>{a.tipo_componente_nome || a.componente_texto || "—"}</TD>
                <TD>
                  {a.condicao_sigla || a.condicao_nome ? (
                    <Badge tone="warning">{a.condicao_sigla || a.condicao_nome}</Badge>
                  ) : (
                    "—"
                  )}
                </TD>
                <TD>{a.tecnologia_nome}</TD>
                <TD>
                  {a.confirmada ? (
                    <Badge tone="success">Confirmada</Badge>
                  ) : (
                    <Badge tone="warning">Não confirmada</Badge>
                  )}
                </TD>
                {podeEditar && (
                  <TD className="text-right">
                    <div className="flex items-center justify-end gap-1">
                      <Link
                        href={`/inspecoes/final/${a.id}`}
                        onClick={(e) => e.stopPropagation()}
                        className="rounded-md px-2 py-1 text-xs font-medium text-fg-muted transition-colors hover:bg-surface-muted hover:text-fg"
                      >
                        Editar
                      </Link>
                      {podeExcluir && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            remover(a);
                          }}
                          className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-danger-fg transition-colors hover:bg-danger-subtle"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
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

export default function AnaliseFinalPage() {
  return (
    <Suspense fallback={<Card><Spinner /></Card>}>
      <AnaliseFinalConteudo />
    </Suspense>
  );
}
