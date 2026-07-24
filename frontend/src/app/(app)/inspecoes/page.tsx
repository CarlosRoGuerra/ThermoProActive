"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, ClipboardList, Plus } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Cliente, Inspecao, Paginated } from "@/lib/types";
import { Combobox } from "@/components/combobox";
import { useClienteAtivo } from "@/lib/cliente-ativo";
import {
  Button,
  Card,
  CriticidadeBadge,
  EmptyState,
  Field,
  Input,
  PageHeader,
  Select,
  StatusBadge,
  Table,
  TableSkeleton,
  TBody,
  TD,
  TH,
  THead,
  TR,
} from "@/components/ui";

export default function InspecoesPage() {
  const { user } = useAuth();
  const { clienteAtivo } = useClienteAtivo();
  const [inspecoes, setInspecoes] = useState<Inspecao[]>([]);
  const [clientes, setClientes] = useState<Cliente[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  // Nova inspeção já começa no cliente ativo (o ambiente escolhido).
  const [novoCliente, setNovoCliente] = useState<number | "">(clienteAtivo?.id ?? "");
  const [novoTipo, setNovoTipo] = useState("VIBRACAO");
  const [novaData, setNovaData] = useState(() => new Date().toISOString().slice(0, 10));

  useEffect(() => {
    if (clienteAtivo) setNovoCliente(clienteAtivo.id);
  }, [clienteAtivo]);

  async function reload() {
    const data = await api<Paginated<Inspecao>>("/inspecoes/");
    setInspecoes(data.results);
  }

  useEffect(() => {
    Promise.all([
      reload(),
      user?.is_interno
        ? api<Paginated<Cliente>>("/clientes/").then((d) => setClientes(d.results))
        : Promise.resolve(),
    ]).finally(() => setLoading(false));
  }, [user]);

  async function criar() {
    if (!novoCliente) return;
    setCreating(true);
    try {
      await api("/inspecoes/", {
        method: "POST",
        body: { cliente: novoCliente, data: novaData, tipo_analise: novoTipo },
      });
      await reload();
      setNovoCliente("");
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        icon={ClipboardList}
        title="Inspeções"
        description="Coleta de dados — Vibração e Termografia (Anexo I 2.3)."
      />

      {user?.is_interno && (
        <Card>
          <h2 className="mb-3 text-sm font-semibold text-fg">Nova inspeção</h2>
          <div className="flex flex-wrap items-end gap-3">
            <Field label="Cliente" className="min-w-[260px] flex-1">
              <Combobox
                value={novoCliente}
                onChange={setNovoCliente}
                options={clientes.map((c) => ({
                  id: c.id,
                  label: c.nome_fantasia || c.nome,
                  hint: [c.cnpj, c.cidade_uf].filter(Boolean).join(" · "),
                }))}
                placeholder="Buscar cliente…"
                permiteLimpar={false}
              />
            </Field>
            <Field label="Tipo de análise">
              <Select value={novoTipo} onChange={(e) => setNovoTipo(e.target.value)}>
                <option value="VIBRACAO">Análise de Vibração</option>
                <option value="TERMOGRAFIA">Termografia</option>
                <option value="ENSAIO_ELETRICO">Ensaios Elétricos</option>
                <option value="FLUIDOS">Análise de Fluidos</option>
                <option value="ULTRASSOM">Ultrassom</option>
                <option value="ESPESSURA">Medição de Espessura</option>
                <option value="QUALIDADE_ENERGIA">Qualidade de Energia</option>
                <option value="CORRETIVA">Manutenção Corretiva</option>
                <option value="SENSITIVA">Inspeção Sensitiva</option>
              </Select>
            </Field>
            <Field label="Data">
              <Input type="date" value={novaData} onChange={(e) => setNovaData(e.target.value)} />
            </Field>
            <Button onClick={criar} loading={creating} disabled={!novoCliente} icon={Plus}>
              Criar inspeção
            </Button>
          </div>
        </Card>
      )}

      {loading ? (
        <TableSkeleton rows={5} cols={6} />
      ) : inspecoes.length === 0 ? (
        <Card>
          <EmptyState
            icon={ClipboardList}
            title="Nenhuma inspeção registrada"
            description="As inspeções de campo aparecerão aqui assim que forem criadas."
          />
        </Card>
      ) : (
        <Table>
          <THead>
            <TH>#</TH>
            <TH>Cliente</TH>
            <TH>Tipo</TH>
            <TH>Data</TH>
            <TH>Medições</TH>
            <TH>Criticidade</TH>
            <TH>Status</TH>
            <TH />
          </THead>
          <TBody>
            {inspecoes.map((i) => (
              <TR key={i.id}>
                <TD className="font-medium text-fg">{i.id}</TD>
                <TD className="text-fg">{i.cliente_nome}</TD>
                <TD>{i.tipo_analise_display}</TD>
                <TD>{i.data}</TD>
                <TD>{i.qtd_medicoes}</TD>
                <TD>
                  <CriticidadeBadge value={i.criticidade_maxima} />
                </TD>
                <TD>
                  <StatusBadge value={i.status_display} />
                </TD>
                <TD className="text-right">
                  <Link
                    href={`/inspecoes/${i.id}`}
                    className="inline-flex items-center gap-1 text-sm font-medium text-accent transition-colors hover:text-accent-hover"
                  >
                    Abrir <ArrowRight className="h-3.5 w-3.5" />
                  </Link>
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      )}
    </div>
  );
}
