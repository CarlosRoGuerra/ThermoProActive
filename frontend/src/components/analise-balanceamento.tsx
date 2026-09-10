"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { ItemCorretivo, ServicoCampo } from "@/lib/types";
import { Button, Card, Field, Input, Select, Spinner, Textarea } from "@/components/ui";
import { PontosMedicao, QuantidadePlanos, SelecaoPontoFoco, TrialRun, TrimRun } from "@/components/balanceamento-medicoes";

type Opcao = { id: number; nome: string };
type Catalogos = { condicoes: Opcao[]; tipos_componente: Opcao[]; tipos_anomalia: Opcao[]; recomendacoes: Opcao[] };
type Tecnica = {
  id?: number; condicao: number | null; tipo_componente: number | null;
  componente_texto: string; detalhe: string; tipo_anomalia: number | null;
  recomendacao: number | null; anomalia_texto: string; recomendacao_texto: string; observacoes: string;
};
type Dados = { servico: ServicoCampo; tecnica: Tecnica | null };
type Form = { [K in Exclude<keyof Tecnica, "id">]: string };
const vazio: Form = { condicao: "", tipo_componente: "", componente_texto: "", detalhe: "", tipo_anomalia: "", recomendacao: "", anomalia_texto: "", recomendacao_texto: "", observacoes: "" };

function Opcoes({ itens, selecionado }: { itens: Opcao[]; selecionado: string }) {
  return <>
    <option value="">Selecione</option>
    {selecionado && !itens.some((i) => String(i.id) === selecionado) && <option value={selecionado} disabled>Seleção anterior indisponível — escolha outra</option>}
    {itens.map((i) => <option key={i.id} value={i.id}>{i.nome}</option>)}
  </>;
}

export function AnaliseBalanceamento({ atividadeId, item, podeEditar, onSaved }: {
  atividadeId: string; item: ItemCorretivo; podeEditar: boolean; onSaved: () => Promise<void>;
}) {
  const url = `/atividades-corretivas/${atividadeId}/itens/${item.id}/balanceamento/`;
  const [dados, setDados] = useState<Dados | null>(null);
  const [catalogos, setCatalogos] = useState<Catalogos | null>(null);
  const [recomendacoes, setRecomendacoes] = useState<Opcao[]>([]);
  const [form, setForm] = useState<Form>(vazio);
  const [rotacao, setRotacao] = useState("");
  const [loading, setLoading] = useState(true);
  const [buscandoRecomendacoes, setBuscandoRecomendacoes] = useState(false);
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [salvo, setSalvo] = useState(false);

  useEffect(() => {
    let ativo = true;
    Promise.all([api<Dados>(url), api<Catalogos>(`${url}catalogos/`)])
      .then(([d, c]) => {
        if (!ativo) return;
        setDados(d); setCatalogos(c); setRotacao(d.servico.rotacao_hz ?? "");
        const f = { ...vazio, condicao: String(item.condicao ?? "") };
        if (d.tecnica) for (const chave of Object.keys(f) as (keyof Form)[]) f[chave] = String(d.tecnica[chave] ?? "");
        setForm(f);
      }).catch(() => { if (ativo) setErro("Não foi possível carregar a análise e seus catálogos."); })
      .finally(() => { if (ativo) setLoading(false); });
    return () => { ativo = false; };
  }, [url]);

  useEffect(() => {
    let ativo = true;
    setRecomendacoes([]);
    if (!form.tipo_anomalia) { setBuscandoRecomendacoes(false); return; }
    setBuscandoRecomendacoes(true);
    api<Catalogos>(`${url}catalogos/?anomalia=${form.tipo_anomalia}`)
      .then((c) => { if (ativo) setRecomendacoes(c.recomendacoes); })
      .catch(() => { if (ativo) setErro("Não foi possível carregar recomendações válidas para esta anomalia."); })
      .finally(() => { if (ativo) setBuscandoRecomendacoes(false); });
    return () => { ativo = false; };
  }, [url, form.tipo_anomalia]);

  const recarregarMedicoes = useCallback(async () => { setDados(await api<Dados>(url)); }, [url]);
  function alterar(campo: keyof Form, valor: string) {
    setSalvo(false);
    setForm((f) => ({ ...f, [campo]: valor, ...(campo === "tipo_anomalia" ? { recomendacao: "" } : {}) }));
  }
  async function salvar() {
    setSalvando(true); setErro(null); setSalvo(false);
    try {
      const d = await api<Dados>(url, { method: "PATCH", body: {
        rotacao_hz: rotacao || null,
        tecnica: { ...form, condicao: Number(form.condicao), tipo_componente: Number(form.tipo_componente), tipo_anomalia: Number(form.tipo_anomalia), recomendacao: Number(form.recomendacao) },
      } });
      setDados(d); setSalvo(true); await onSaved();
    } catch (e) { setErro(e instanceof ApiError ? JSON.stringify(e.data) : "Não foi possível salvar a análise."); }
    finally { setSalvando(false); }
  }

  if (loading) return <Spinner />;
  if (!dados || !catalogos) return <Card><p role="alert">{erro}</p></Card>;
  const habilitado = podeEditar && !salvando;
  const completo = form.condicao && form.tipo_componente && form.tipo_anomalia && recomendacoes.some((r) => String(r.id) === form.recomendacao);
  return <div className="space-y-5">
    <Card className="space-y-4">
      <h2 className="font-semibold text-fg">Balanceamento — {item.equipamento_tag} · {item.equipamento_nome}</h2>
      <fieldset disabled={!habilitado} className="grid gap-4 sm:grid-cols-2">
        <Field label="Grau de risco / Condição"><Select value={form.condicao} onChange={(e) => alterar("condicao", e.target.value)}><Opcoes itens={catalogos.condicoes} selecionado={form.condicao} /></Select></Field>
        <Field label="Tipo de componente"><Select value={form.tipo_componente} onChange={(e) => alterar("tipo_componente", e.target.value)}><Opcoes itens={catalogos.tipos_componente} selecionado={form.tipo_componente} /></Select></Field>
        <Field label="Componente"><Input value={form.componente_texto} maxLength={120} onChange={(e) => alterar("componente_texto", e.target.value)} /></Field>
        <Field label="Detalhe do componente"><Input value={form.detalhe} maxLength={200} onChange={(e) => alterar("detalhe", e.target.value)} /></Field>
        <Field label="Tipo de anomalia"><Select value={form.tipo_anomalia} onChange={(e) => alterar("tipo_anomalia", e.target.value)}><Opcoes itens={catalogos.tipos_anomalia} selecionado={form.tipo_anomalia} /></Select></Field>
        <Field label="Recomendação"><Select value={form.recomendacao} disabled={!form.tipo_anomalia || buscandoRecomendacoes} onChange={(e) => alterar("recomendacao", e.target.value)}><Opcoes itens={recomendacoes} selecionado={form.recomendacao} /></Select></Field>
        <Field label="Anomalia — complemento"><Textarea value={form.anomalia_texto} onChange={(e) => alterar("anomalia_texto", e.target.value)} /></Field>
        <Field label="Recomendação — complemento"><Textarea value={form.recomendacao_texto} onChange={(e) => alterar("recomendacao_texto", e.target.value)} /></Field>
        <Field label="Rotação (Hz)"><Input type="number" min="0" step="0.01" value={rotacao} onChange={(e) => { setRotacao(e.target.value); setSalvo(false); }} /></Field>
        <Field label="Observações"><Textarea value={form.observacoes} onChange={(e) => alterar("observacoes", e.target.value)} /></Field>
      </fieldset>
      {(!catalogos.tipos_componente.length || !catalogos.tipos_anomalia.length) && <p className="text-sm text-fg-muted">Os catálogos de componentes e anomalias precisam estar vinculados à tecnologia desta atividade no cadastro de dados de sistema.</p>}
      {form.tipo_anomalia && !buscandoRecomendacoes && !recomendacoes.length && <p className="text-sm text-fg-muted">Nenhuma recomendação compatível cadastrada para esta tecnologia e anomalia.</p>}
      {podeEditar && <Button onClick={salvar} loading={salvando} disabled={!completo || buscandoRecomendacoes || salvando}>Salvar análise</Button>}
      {salvo && <p role="status" className="text-sm text-fg-muted">Análise salva nesta atividade e equipamento.</p>}
    </Card>
    {erro && <p role="alert" className="text-sm text-danger-fg">{erro}</p>}
    <QuantidadePlanos servico={dados.servico} podeEditar={habilitado} onMudou={recarregarMedicoes} />
    <PontosMedicao servico={dados.servico} podeEditar={habilitado} onMudou={recarregarMedicoes} onErro={setErro} />
    <SelecaoPontoFoco servico={dados.servico} podeEditar={habilitado} onMudou={recarregarMedicoes} onErro={setErro} />
    <TrialRun servico={dados.servico} podeEditar={habilitado} onMudou={recarregarMedicoes} onErro={setErro} />
    <TrimRun servico={dados.servico} podeEditar={habilitado} onMudou={recarregarMedicoes} onErro={setErro} />
  </div>;
}
