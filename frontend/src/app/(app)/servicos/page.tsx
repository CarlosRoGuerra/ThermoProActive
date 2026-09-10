"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Gauge, Plus } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useClienteAtivo } from "@/lib/cliente-ativo";
import { useClientes } from "@/lib/hierarquia";
import type { AtividadeCorretiva, Paginated, ServicoCampoLista } from "@/lib/types";
import {
  Badge,
  Button,
  Card,
  CriticidadeBadge,
  EmptyState,
  Field,
  PageHeader,
  Table,
  TableSkeleton,
  TBody,
  TD,
  TH,
  THead,
  TR,
} from "@/components/ui";
import { Combobox } from "@/components/combobox";

const ddmmaaaa = (iso: string | null) => (iso ? iso.split("-").reverse().join("/") : "—");
const pct = (v: string | null) =>
  v == null ? "—" : `${Number(v).toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%`;

export default function ServicosPage() {
  const { user } = useAuth();
  const router = useRouter();
  const podeEditar = !!user?.is_interno;
  const { opcoes: opcoesClientes } = useClientes();
  const { clienteAtivo } = useClienteAtivo();
  const [cliente, setCliente] = useState<number | "">(clienteAtivo?.id ?? "");
  const [servicos, setServicos] = useState<ServicoCampoLista[]>([]);
  const [atividades, setAtividades] = useState<AtividadeCorretiva[]>([]);
  const [erro, setErro] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (clienteAtivo) setCliente(clienteAtivo.id);
  }, [clienteAtivo]);

  useEffect(() => {
    setLoading(true);
    const filtro = cliente ? `&cliente=${cliente}` : "";
    let ativo = true;
    setErro(null);
    Promise.all([
      api<Paginated<ServicoCampoLista>>(`/servicos/?ordering=-data_execucao&page_size=1000${filtro}`),
      api<Paginated<AtividadeCorretiva>>(`/atividades-corretivas/?ordering=-data_coleta&page_size=1000${filtro}`),
    ])
      .then(([s, a]) => { if (ativo) { setServicos(s.results); setAtividades(a.results); } })
      .catch(() => { if (ativo) setErro("Não foi possível carregar as atividades. Atualize a página para tentar novamente."); })
      .finally(() => { if (ativo) setLoading(false); });
    return () => { ativo = false; };
  }, [cliente]);

  return (
    <div className="space-y-5">
      <PageHeader
        title="Manutenção corretiva"
        description="Balanceamento, alinhamento a laser e outros trabalhos corretivos."
        icon={Gauge}
        actions={
          podeEditar && (
            <Button onClick={() => router.push("/servicos/novo")}>
              <Plus className="h-4 w-4" />
              Nova atividade / Carregar rota
            </Button>
          )
        }
      />

      <section aria-label="Tecnologias corretivas" className="grid gap-4 md:grid-cols-3">
        <Card className="space-y-2">
          <h2 id="balanceamento" className="scroll-mt-6 font-semibold text-fg">Balanceamento</h2>
          <p className="text-sm text-fg-muted">Os serviços já registrados estão na listagem abaixo.</p>
        </Card>
        <Card className="space-y-2">
          <h2 id="alinhamento" className="scroll-mt-6 font-semibold text-fg">Alinhamento a laser</h2>
          <ul className="list-disc space-y-1 pl-5 text-sm text-fg-muted">
            <li>Entre polias — em breve</li>
            <li>Entre eixos — em breve</li>
          </ul>
          <p className="text-sm text-fg-muted">Os registros atuais continuam agrupados como alinhamento a laser.</p>
        </Card>
        <Card className="space-y-2">
          <h2 id="outros" className="scroll-mt-6 font-semibold text-fg">Outros trabalhos corretivos</h2>
          <p className="text-sm text-fg-muted">Outros serviços corretivos — em breve.</p>
        </Card>
      </section>

      <Card>
        <Field label="Cliente" className="max-w-sm">
          <Combobox value={cliente} onChange={setCliente} options={opcoesClientes} />
        </Field>
      </Card>

      {erro && <p role="alert" className="text-sm text-danger-fg">{erro}</p>}
      {!loading && atividades.length > 0 && <section className="space-y-3" aria-label="Atividades por rota">
        <h2 className="font-semibold text-fg">Atividades por rota</h2>
        <Card padding={false}><Table>
          <THead><TR><TH>Relatório / Cliente</TH><TH>Rota</TH><TH>Tecnologia</TH><TH>Data do ensaio</TH><TH>Equipamentos</TH><TH>Ação</TH></TR></THead>
          <TBody>{atividades.map((a) => <TR key={a.id}>
            <TD>{a.numero}<span className="block text-xs text-fg-muted">{a.cliente_nome}</span></TD>
            <TD>{a.rota_nome}</TD><TD>{a.tecnologia_nome}</TD><TD>{ddmmaaaa(a.data_coleta)}</TD><TD>{a.qtd_itens}</TD>
            <TD><Button onClick={() => router.push(`/servicos/atividades/${a.id}`)}>Abrir atividade</Button></TD>
          </TR>)}</TBody>
        </Table></Card>
      </section>}
      {!loading && servicos.length > 0 && <h2 className="font-semibold text-fg">Serviços registrados</h2>}
      {loading ? (
        <TableSkeleton rows={5} cols={7} />
      ) : servicos.length === 0 && atividades.length === 0 && !erro ? (
        <EmptyState
          icon={Gauge}
          title="Nenhuma manutenção corretiva registrada"
          description="Balanceamentos e alinhamentos executados em campo aparecem aqui."
        />
      ) : servicos.length > 0 ? (
        <Card padding={false}>
          <Table>
            <THead>
              <TR>
                <TH>Equipamento</TH>
                <TH>Tipo</TH>
                <TH>Data</TH>
                <TH>Rotação</TH>
                <TH>Planos</TH>
                <TH>Redução média</TH>
                <TH>Condição final</TH>
              </TR>
            </THead>
            <TBody>
              {servicos.map((s) => (
                <TR key={s.id} onClick={() => router.push(s.atividade ? `/servicos/atividades/${s.atividade}?item=${s.item}` : `/servicos/${s.id}`)}>
                  <TD>
                    <span className="font-medium text-fg">{s.equipamento_tag}</span>
                    <span className="block text-xs text-fg-muted">{s.cliente_nome}</span>
                  </TD>
                  <TD>
                    <Badge tone="neutral">{s.tipo_display}</Badge>
                  </TD>
                  <TD>{ddmmaaaa(s.data_execucao)}</TD>
                  <TD>{s.rotacao_rpm ? `${s.rotacao_rpm} RPM` : "—"}</TD>
                  <TD>{s.numero_planos || "—"}</TD>
                  <TD className="tabular-nums">{pct(s.reducao_media_pct)}</TD>
                  <TD>
                    <CriticidadeBadge value={s.criticidade_final} />
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        </Card>
      ) : null}
    </div>
  );
}
