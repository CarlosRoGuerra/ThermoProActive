"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useClienteAtivo } from "@/lib/cliente-ativo";
import type { AtividadeCorretiva, Paginated, Rota, TecnologiaCorretiva } from "@/lib/types";
import { Button, Card, Field, Input, PageHeader, Select } from "@/components/ui";

type Instrumento = { id: number; tipo: string; marca: string; modelo: string; numero_serie: string };
const hoje = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

export default function NovaAtividadePage() {
  const router = useRouter();
  const { user } = useAuth();
  const { clienteAtivo } = useClienteAtivo();
  const [tecnologias, setTecnologias] = useState<TecnologiaCorretiva[]>([]);
  const [rotas, setRotas] = useState<Rota[]>([]);
  const [instrumentos, setInstrumentos] = useState<Instrumento[]>([]);
  const [tecnologia, setTecnologia] = useState("");
  const [rota, setRota] = useState("");
  const [instrumento, setInstrumento] = useState("");
  const [data, setData] = useState(hoje);
  const [salvando, setSalvando] = useState(false);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    let ativo = true;
    setRota(""); setRotas([]); setCarregando(true);
    Promise.all([
      api<Paginated<TecnologiaCorretiva>>("/tecnologias-analise/?page_size=1000"),
      clienteAtivo ? api<Paginated<Rota>>(`/rotas/?cliente=${clienteAtivo.id}&page_size=1000`) : Promise.resolve({ results: [] }),
    ]).then(([t, r]) => {
      if (ativo) { setTecnologias(t.results.filter((x) => x.tipo_corretiva)); setRotas(r.results); }
    }).catch(() => { if (ativo) setErro("Não foi possível carregar as tecnologias e rotas."); })
      .finally(() => { if (ativo) setCarregando(false); });
    return () => { ativo = false; };
  }, [clienteAtivo?.id]);

  useEffect(() => {
    let ativo = true;
    setInstrumentos([]); setInstrumento("");
    if (tecnologia) api<Paginated<Instrumento>>(`/instrumentos/?tecnologias=${tecnologia}&page_size=1000`)
      .then((d) => { if (ativo) setInstrumentos(d.results); })
      .catch(() => { if (ativo) setErro("Não foi possível carregar os instrumentos."); });
    return () => { ativo = false; };
  }, [tecnologia]);

  async function carregar() {
    setSalvando(true); setErro(null);
    try {
      const atividade = await api<AtividadeCorretiva>("/atividades-corretivas/", {
        method: "POST", body: {
          tecnologia: Number(tecnologia), rota: Number(rota), instrumento: Number(instrumento),
          data_termino_novo: data,
        },
      });
      router.push(`/servicos/atividades/${atividade.id}`);
    } catch (e) {
      setErro(e instanceof ApiError ? JSON.stringify(e.data) : "Não foi possível carregar a rota.");
      setSalvando(false);
    }
  }

  if (!user?.is_interno) return <Card>Seu perfil permite consultar as atividades de manutenção corretiva.</Card>;
  if (!clienteAtivo) return <Card>Ative um cliente no seletor do topo para carregar uma rota.</Card>;
  const disponiveis = rotas.filter((r) => r.tecnologia === null || r.tecnologia === Number(tecnologia));
  const valida = disponiveis.some((r) => r.id === Number(rota) && r.qtd_equipamentos > 0);

  return <div className="space-y-5">
    <Link href="/servicos" className="text-sm text-accent">Voltar para Manutenção corretiva</Link>
    <PageHeader title="Nova atividade / Carregar rota" description={clienteAtivo.nome_fantasia || clienteAtivo.nome} />
    <Card>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Tecnologia *"><Select value={tecnologia} disabled={salvando || carregando} onChange={(e) => { setTecnologia(e.target.value); setRota(""); }}>
          <option value="">Selecione a tecnologia</option>
          {tecnologias.map((t) => <option key={t.id} value={t.id}>{t.nome}</option>)}
        </Select></Field>
        <Field label="Rota *"><Select value={rota} disabled={!tecnologia || salvando || carregando} onChange={(e) => setRota(e.target.value)}>
          <option value="">Selecione a rota</option>
          {disponiveis.map((r) => <option key={r.id} value={r.id}>{r.nome} ({r.qtd_equipamentos} equipamentos)</option>)}
        </Select></Field>
        <Field label="Instrumento *"><Select value={instrumento} disabled={!tecnologia || salvando} onChange={(e) => setInstrumento(e.target.value)}>
          <option value="">{tecnologia && !instrumentos.length ? "Nenhum instrumento compatível cadastrado" : "Selecione o instrumento"}</option>
          {instrumentos.map((i) => <option key={i.id} value={i.id}>{[i.tipo, i.marca, i.modelo, i.numero_serie].filter(Boolean).join(" — ")}</option>)}
        </Select></Field>
        <Field label="Analista"><Input value={user.nome} readOnly disabled /></Field>
        <Field label="Número do relatório"><Input value="Gerar novo número ao carregar a rota" readOnly disabled /></Field>
        <Field label="Data de término/ensaio *"><Input type="date" value={data} max={hoje()} disabled={salvando} onChange={(e) => setData(e.target.value)} /></Field>
      </div>
      {!carregando && !tecnologias.length && <p className="mt-4 text-sm text-fg-muted">Nenhuma tecnologia corretiva configurada. Em Dados de sistema → Tecnologias de análise, associe a tecnologia a Balanceamento ou Alinhamento a laser.</p>}
      <p className="mt-4 text-sm text-fg-muted">Informe a data real de execução. Todos os equipamentos da rota serão incluídos na atividade.</p>
      {erro && <p role="alert" className="mt-4 text-sm text-danger-fg">{erro}</p>}
    </Card>
    <Button onClick={carregar} loading={salvando} disabled={carregando || salvando || !tecnologia || !valida || !instrumento || !data || data > hoje()}>Carregar rota</Button>
  </div>;
}
