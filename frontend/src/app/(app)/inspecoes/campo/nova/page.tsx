"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Save, Search } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useClienteAtivo } from "@/lib/cliente-ativo";
import type { Carregamento, CarregamentoLista, Paginated, Rota } from "@/lib/types";
import { Button, Card, Field, Input, Select, Spinner } from "@/components/ui";

type TecOpt = { id: number; nome: string };
type InstrumentoOpt = { id: number; tipo: string; marca: string; modelo: string };

export default function CarregarRotaPage() {
  const router = useRouter();
  const { user } = useAuth();
  const { clienteAtivo } = useClienteAtivo();

  const [tecnologia, setTecnologia] = useState("");
  const [rota, setRota] = useState("");
  const [instrumento, setInstrumento] = useState("");
  const [data, setData] = useState(() => new Date().toISOString().slice(0, 10));

  // Número do relatório: gerar novo (automático) ou utilizar outro (informado).
  const [modoNumero, setModoNumero] = useState<"novo" | "outro">("novo");
  const [sequencial, setSequencial] = useState("");
  const [buscando, setBuscando] = useState(false);
  const [buscaMsg, setBuscaMsg] = useState<string | null>(null);

  const [tecnologias, setTecnologias] = useState<TecOpt[]>([]);
  const [rotas, setRotas] = useState<Rota[]>([]);
  const [instrumentos, setInstrumentos] = useState<InstrumentoOpt[]>([]);
  const [salvando, setSalvando] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    api<Paginated<TecOpt>>("/tecnologias-analise/?page_size=1000")
      .then((d) => setTecnologias(d.results))
      .catch(() => setTecnologias([]));
    // Instrumentação: busca a tabela de Dados de sistema (todos os instrumentos).
    api<Paginated<InstrumentoOpt>>("/instrumentos/?page_size=1000")
      .then((d) => setInstrumentos(d.results))
      .catch(() => setInstrumentos([]));
  }, []);

  useEffect(() => {
    if (!clienteAtivo) return;
    api<Paginated<Rota>>(`/rotas/?cliente=${clienteAtivo.id}&page_size=1000`)
      .then((d) => setRotas(d.results))
      .catch(() => setRotas([]));
  }, [clienteAtivo]);

  // Rotas da tecnologia escolhida (ou sem tecnologia definida).
  const rotasFiltradas = useMemo(() => {
    if (!tecnologia) return rotas;
    const tid = Number(tecnologia);
    return rotas.filter((r) => r.tecnologia === null || r.tecnologia === tid);
  }, [rotas, tecnologia]);

  async function buscarNumero() {
    if (!clienteAtivo || sequencial.trim() === "") return;
    setBuscando(true);
    setBuscaMsg(null);
    try {
      const d = await api<Paginated<CarregamentoLista>>(
        `/carregamentos/?cliente=${clienteAtivo.id}&numero_relatorio=${encodeURIComponent(
          sequencial.trim()
        )}&page_size=1`
      );
      setBuscaMsg(
        d.count > 0
          ? `Relatório encontrado (${d.count} carregamento(s)). As análises serão somadas a ele.`
          : "Nenhum relatório com esse número — será criado um novo com este número."
      );
    } catch {
      setBuscaMsg("Não foi possível buscar agora.");
    } finally {
      setBuscando(false);
    }
  }

  async function salvar() {
    if (!clienteAtivo || !tecnologia) return;
    if (modoNumero === "outro" && sequencial.trim() === "") {
      setMsg("Informe o sequencial do relatório ou escolha “Gerar novo número”.");
      return;
    }
    setSalvando(true);
    setMsg(null);
    try {
      const novo = await api<Carregamento>("/carregamentos/", {
        method: "POST",
        body: {
          cliente: clienteAtivo.id,
          tecnologia: Number(tecnologia),
          rota: rota === "" ? null : Number(rota),
          instrumento: instrumento === "" ? null : Number(instrumento),
          numero_relatorio: modoNumero === "novo" ? "" : sequencial.trim(),
          data,
        },
      });
      router.push(`/inspecoes/campo/${novo.id}`);
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "Erro ao carregar a rota.");
      setSalvando(false);
    }
  }

  if (!clienteAtivo) {
    return (
      <Card>
        <p className="text-sm text-fg-muted">
          Ative um cliente no seletor do topo para carregar uma rota.
        </p>
      </Card>
    );
  }

  const podeSalvar = tecnologia !== "" && !salvando;

  return (
    <div className="space-y-5">
      <div>
        <Link
          href="/inspecoes/campo"
          className="inline-flex items-center gap-1.5 text-xs font-medium text-fg-muted transition-colors hover:text-fg"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Voltar para Análise de campo
        </Link>
        <h1 className="mt-2 text-xl font-semibold tracking-tight text-fg">Carregar rota</h1>
        <p className="mt-0.5 text-sm text-fg-muted">
          {clienteAtivo.nome_fantasia || clienteAtivo.nome}
        </p>
      </div>

      <Card>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Tecnologia *">
            <Select value={tecnologia} onChange={(e) => setTecnologia(e.target.value)}>
              <option value="">— selecione —</option>
              {tecnologias.map((t) => (
                <option key={t.id} value={t.id}>{t.nome}</option>
              ))}
            </Select>
          </Field>
          <Field label="Rota">
            <Select value={rota} onChange={(e) => setRota(e.target.value)} disabled={!tecnologia}>
              <option value="">{tecnologia ? "— selecione —" : "Escolha a tecnologia primeiro"}</option>
              {rotasFiltradas.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.nome} ({r.qtd_equipamentos} equip.)
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Instrumentação">
            <Select value={instrumento} onChange={(e) => setInstrumento(e.target.value)}>
              <option value="">— selecione —</option>
              {instrumentos.map((i) => (
                <option key={i.id} value={i.id}>
                  {[i.tipo, i.marca, i.modelo].filter(Boolean).join(" — ")}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Analista">
            <Input value={user?.nome ?? ""} disabled readOnly />
          </Field>
          <Field label="Data">
            <Input type="date" value={data} onChange={(e) => setData(e.target.value)} />
          </Field>
        </div>

        {/* Número do relatório */}
        <div className="mt-4 rounded-lg border border-border bg-surface-muted/30 p-4">
          <p className="mb-3 text-sm font-medium text-fg">Sequencial do relatório</p>
          <div className="flex flex-col gap-2 sm:flex-row sm:gap-6">
            <label className="flex cursor-pointer items-center gap-2 text-sm text-fg">
              <input
                type="radio"
                name="modoNumero"
                checked={modoNumero === "novo"}
                onChange={() => setModoNumero("novo")}
                className="h-4 w-4"
                style={{ accentColor: "var(--accent)" }}
              />
              Gerar novo número
            </label>
            <label className="flex cursor-pointer items-center gap-2 text-sm text-fg">
              <input
                type="radio"
                name="modoNumero"
                checked={modoNumero === "outro"}
                onChange={() => setModoNumero("outro")}
                className="h-4 w-4"
                style={{ accentColor: "var(--accent)" }}
              />
              Utilizar outro número (preencha abaixo)
            </label>
          </div>

          {modoNumero === "outro" && (
            <div className="mt-3">
              <div className="flex flex-col gap-2 sm:flex-row">
                <Input
                  value={sequencial}
                  maxLength={40}
                  placeholder="Sequencial do relatório"
                  onChange={(e) => setSequencial(e.target.value)}
                  className="sm:max-w-xs"
                />
                <Button variant="secondary" icon={Search} onClick={buscarNumero} loading={buscando}>
                  Buscar
                </Button>
              </div>
              {buscaMsg && <p className="mt-2 text-xs text-fg-muted">{buscaMsg}</p>}
            </div>
          )}
          {modoNumero === "novo" && (
            <p className="mt-2 text-xs text-fg-subtle">
              O sistema gera automaticamente o próximo número deste cliente ao carregar a rota.
            </p>
          )}
        </div>

        {msg && <p className="mt-3 text-sm text-danger-fg">{msg}</p>}
      </Card>

      <div className="flex items-center justify-end gap-3 pb-2">
        <span className="mr-auto text-xs text-fg-subtle">* campo obrigatório</span>
        <Button variant="secondary" onClick={() => router.push("/inspecoes/campo")}>
          Cancelar
        </Button>
        <Button onClick={salvar} loading={salvando} disabled={!podeSalvar} icon={Save}>
          Carregar rota
        </Button>
      </div>
    </div>
  );
}
