"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { AnaliseBalanceamento } from "@/components/analise-balanceamento";
import type { AtividadeCorretiva, Condicao, ItemCorretivo, Paginated } from "@/lib/types";
import { Badge, Button, Card, Field, PageHeader, Select, Spinner, Table, TBody, TD, Textarea, TH, THead, TR } from "@/components/ui";

export default function AtividadePage() {
  const { id } = useParams<{ id: string }>();
  const params = useSearchParams();
  const router = useRouter();
  const { user } = useAuth();
  const [atividade, setAtividade] = useState<AtividadeCorretiva | null>(null);
  const [condicoes, setCondicoes] = useState<Condicao[]>([]);
  const [loading, setLoading] = useState(true);
  const [ocupado, setOcupado] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [observacoes, setObservacoes] = useState("");
  const base = `/atividades-corretivas/${id}`;
  const href = `/servicos/atividades/${id}`;
  const itemId = params.get("item");
  const item = atividade?.itens.find((i) => String(i.id) === itemId);
  const podeEditar = !!user?.is_interno && atividade?.status === "EM_CAMPO";
  const recarregar = useCallback(async () => {
    setAtividade(await api<AtividadeCorretiva>(`${base}/`));
  }, [base]);

  useEffect(() => {
    let ativo = true;
    setLoading(true);
    Promise.all([api<AtividadeCorretiva>(`${base}/`), api<Paginated<Condicao>>("/condicoes/?page_size=1000")])
      .then(([a, c]) => { if (ativo) { setAtividade(a); setCondicoes(c.results); } })
      .catch(() => { if (ativo) setErro("Não foi possível carregar esta atividade."); })
      .finally(() => { if (ativo) setLoading(false); });
    return () => { ativo = false; };
  }, [base]);

  useEffect(() => { setObservacoes(item?.observacoes_analise ?? ""); }, [item?.id, item?.observacoes_analise]);

  async function executar(acao: () => Promise<void>) {
    setOcupado(true); setErro(null);
    try { await acao(); }
    catch (e) { setErro(e instanceof ApiError ? JSON.stringify(e.data) : "Não foi possível salvar. Tente novamente."); }
    finally { setOcupado(false); }
  }

  function analisar(i: ItemCorretivo) {
    if (i.analise) { router.push(`${href}?item=${i.id}`); return; }
    void executar(async () => {
      await api(`${base}/itens/${i.id}/analise/`, { method: "POST" });
      await recarregar();
      router.push(`${href}?item=${i.id}`);
    });
  }

  if (loading) return <Spinner />;
  if (!atividade) return <Card>{erro || "Atividade não encontrada."}</Card>;

  return <div className="space-y-5">
    <Link href={itemId ? href : "/servicos"} className="text-sm text-accent">{itemId ? "Voltar para equipamentos da rota" : "Voltar para Manutenção corretiva"}</Link>
    <PageHeader title={itemId ? "Análise corretiva" : atividade.rota_nome || "Atividade corretiva"} description={`${atividade.cliente_nome} · ${atividade.tecnologia_nome}`} />
    <Card>
      <dl className="grid gap-3 text-sm sm:grid-cols-2">
        <div><dt className="text-fg-muted">Relatório</dt><dd>{atividade.numero}</dd></div>
        <div><dt className="text-fg-muted">Rota</dt><dd>{atividade.rota_nome}</dd></div>
        <div><dt className="text-fg-muted">Instrumento</dt><dd>{atividade.instrumento_nome} · #{atividade.instrumento}</dd></div>
        <div><dt className="text-fg-muted">Analista</dt><dd>{atividade.analista_nome}</dd></div>
        <div><dt className="text-fg-muted">Data de término/ensaio</dt><dd>{atividade.data_coleta.split("-").reverse().join("/")}</dd></div>
      </dl>
    </Card>
    {erro && <p role="alert" className="text-sm text-danger-fg">{erro}</p>}
    {itemId ? (
      !item?.analise ? <Card>Análise não encontrada nesta atividade.</Card>
      : atividade.tipo_corretiva === "BALANCEAMENTO" ? <AnaliseBalanceamento key={item.id} atividadeId={id} item={item} podeEditar={podeEditar} onSaved={recarregar} />
      : <Card className="space-y-4">
        <h2 className="font-semibold text-fg">{item.equipamento_tag} — {item.equipamento_nome}</h2>
        <p className="text-sm text-fg-muted">Condição: {item.condicao_nome || "Não informada"} · Análise iniciada</p>
        <p className="text-sm text-fg-muted">A análise está vinculada a este equipamento e à rota atual. O formulário técnico de alinhamento a laser estará disponível na próxima fase.</p>
        <Field label="Observações da atividade neste equipamento"><Textarea value={observacoes} onChange={(e) => setObservacoes(e.target.value)} disabled={!podeEditar || ocupado} rows={4} /></Field>
        {podeEditar && <Button disabled={ocupado} onClick={() => executar(async () => {
          await api(`${base}/itens/${item.id}/analise/`, { method: "PATCH", body: { observacoes } });
          await recarregar();
          router.push(href);
        })}>Salvar e voltar para a rota</Button>}
      </Card>
    ) : <Card padding={false}>
      <Table><THead><TR><TH>Equipamento</TH><TH>Condição</TH><TH>Estado da análise</TH><TH>Ação</TH></TR></THead>
        <TBody>{atividade.itens.map((i) => <TR key={i.id}>
          <TD><span className="font-medium">{i.equipamento_tag}</span><span className="block text-xs text-fg-muted">{i.equipamento_nome}</span></TD>
          <TD><Select aria-label={`Condição de ${i.equipamento_tag}`} value={i.condicao ?? ""} disabled={!podeEditar || ocupado} onChange={(e) => {
            const condicao = Number(e.target.value);
            void executar(async () => { await api(`${base}/itens/${i.id}/condicao/`, { method: "PATCH", body: { condicao } }); await recarregar(); });
          }}>
            <option value="" disabled>Selecione a condição</option>
            {i.condicao && !condicoes.some((c) => c.id === i.condicao) && <option value={i.condicao}>{i.condicao_nome}</option>}
            {condicoes.map((c) => <option key={c.id} value={c.id}>{c.nome}</option>)}
          </Select></TD>
          <TD><Badge tone="neutral">{i.analise_tecnica ? "Análise salva" : i.analise ? "Análise iniciada" : "Não iniciada"}</Badge></TD>
          <TD><Button disabled={ocupado || (!i.analise && (!podeEditar || !i.condicao))} onClick={() => analisar(i)}>{i.analise ? (podeEditar ? (i.analise_tecnica ? "Editar análise" : "Continuar análise") : "Visualizar análise") : "Analisar"}</Button></TD>
        </TR>)}</TBody>
      </Table>
    </Card>}
  </div>;
}
