"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Check, Save, Search, X } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useClienteAtivo } from "@/lib/cliente-ativo";
import type { Carregamento, Paginated, Relatorio, Rota } from "@/lib/types";
import { Button, Card, Field, Input, Select, Spinner } from "@/components/ui";

type TecOpt = { id: number; nome: string };
type InstrumentoOpt = { id: number; tipo: string; marca: string; modelo: string };
const ddmmaaaa = (iso: string | null) => (iso ? iso.split("-").reverse().join("/") : "—");

export default function CarregarRotaPage() {
  const router = useRouter();
  const { user } = useAuth();
  const { clienteAtivo } = useClienteAtivo();

  const [tecnologia, setTecnologia] = useState("");
  const [rota, setRota] = useState("");
  const [instrumento, setInstrumento] = useState("");
  const [dataTermino, setDataTermino] = useState(() => new Date().toISOString().slice(0, 10));

  // Número do relatório: gerar novo ou reaproveitar um relatório existente.
  const [modoNumero, setModoNumero] = useState<"novo" | "outro">("novo");
  const [relatorioSel, setRelatorioSel] = useState<Relatorio | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [pickerAberto, setPickerAberto] = useState(false);
  const [carregandoPicker, setCarregandoPicker] = useState(false);
  const [relatorios, setRelatorios] = useState<Relatorio[]>([]);

  const [tecnologias, setTecnologias] = useState<TecOpt[]>([]);
  const [rotas, setRotas] = useState<Rota[]>([]);
  const [instrumentos, setInstrumentos] = useState<InstrumentoOpt[]>([]);
  const [salvando, setSalvando] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    api<Paginated<TecOpt>>("/tecnologias-analise/?page_size=1000")
      .then((d) => setTecnologias(d.results))
      .catch(() => setTecnologias([]));
  }, []);

  useEffect(() => {
    if (!clienteAtivo) return;
    api<Paginated<Rota>>(`/rotas/?cliente=${clienteAtivo.id}&page_size=1000`)
      .then((d) => setRotas(d.results))
      .catch(() => setRotas([]));
  }, [clienteAtivo]);

  // Instrumentação filtrada pela tecnologia (vínculo feito no cadastro de
  // Instrumentação). Trocar a tecnologia zera instrumento e o relatório escolhido.
  useEffect(() => {
    setRelatorioSel(null);
    setInstrumento("");
    if (!tecnologia) {
      setInstrumentos([]);
      return;
    }
    api<Paginated<InstrumentoOpt>>(`/instrumentos/?tecnologias=${tecnologia}&page_size=1000`)
      .then((d) => setInstrumentos(d.results))
      .catch(() => setInstrumentos([]));
  }, [tecnologia]);

  const rotasFiltradas = useMemo(() => {
    if (!tecnologia) return rotas;
    const tid = Number(tecnologia);
    return rotas.filter((r) => r.tecnologia === null || r.tecnologia === tid);
  }, [rotas, tecnologia]);

  async function abrirPicker() {
    if (!clienteAtivo) return;
    if (!tecnologia) {
      setAviso("Selecione a tecnologia primeiro.");
      return;
    }
    setAviso(null);
    setCarregandoPicker(true);
    setPickerAberto(true);
    try {
      const d = await api<Paginated<Relatorio>>(
        `/relatorios/?cliente=${clienteAtivo.id}&tecnologia=${tecnologia}&page_size=1000`
      );
      setRelatorios(d.results);
    } catch {
      setRelatorios([]);
    } finally {
      setCarregandoPicker(false);
    }
  }

  function escolherRelatorio(r: Relatorio) {
    setRelatorioSel(r);
    setPickerAberto(false);
  }

  async function salvar() {
    if (!clienteAtivo || !tecnologia) return;
    if (modoNumero === "outro" && !relatorioSel) {
      setMsg("Escolha um relatório em “Buscar” ou selecione “Gerar novo número”.");
      return;
    }
    setSalvando(true);
    setMsg(null);
    try {
      const body =
        modoNumero === "novo"
          ? {
              cliente: clienteAtivo.id,
              tecnologia: Number(tecnologia),
              rota: rota === "" ? null : Number(rota),
              instrumento: instrumento === "" ? null : Number(instrumento),
              data_termino_novo: dataTermino,
            }
          : {
              relatorio: relatorioSel!.id,
              rota: rota === "" ? null : Number(rota),
              instrumento: instrumento === "" ? null : Number(instrumento),
            };
      const novo = await api<Carregamento>("/carregamentos/", { method: "POST", body });
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

  const podeSalvar =
    tecnologia !== "" && !salvando && (modoNumero === "novo" || relatorioSel !== null);

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
            <Select
              value={instrumento}
              onChange={(e) => setInstrumento(e.target.value)}
              disabled={!tecnologia}
            >
              <option value="">
                {!tecnologia
                  ? "Escolha a tecnologia primeiro"
                  : instrumentos.length
                    ? "— selecione —"
                    : "Nenhum instrumento vinculado a esta tecnologia"}
              </option>
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
        </div>

        {/* Número do relatório */}
        <div className="mt-4 rounded-lg border border-border bg-surface-muted/30 p-4">
          <p className="mb-3 text-sm font-medium text-fg">Número do relatório</p>
          <div className="flex flex-col gap-2 sm:flex-row sm:gap-6">
            <label className="flex cursor-pointer items-center gap-2 text-sm text-fg">
              <input
                type="radio"
                name="modoNumero"
                checked={modoNumero === "novo"}
                onChange={() => {
                  setModoNumero("novo");
                  setAviso(null);
                }}
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
              Utilizar outro número
            </label>
          </div>

          {modoNumero === "novo" ? (
            <div className="mt-3 max-w-xs">
              <Field label="Data de término (auditoria)">
                <Input type="date" value={dataTermino} onChange={(e) => setDataTermino(e.target.value)} />
              </Field>
              <p className="mt-2 text-xs text-fg-subtle">
                Número = <span className="font-mono">RT-SIGLA-AAAA.MM.DD.seq</span> (a sigla vem da
                tecnologia). Use o último dia da inspeção (pode ser futuro).
              </p>
            </div>
          ) : (
            <div className="mt-3">
              {relatorioSel ? (
                <div className="flex flex-wrap items-center gap-3 rounded-lg border border-accent/40 bg-accent-subtle px-3 py-2">
                  <Check className="h-4 w-4 text-accent" />
                  <span className="font-mono text-sm font-semibold text-fg">{relatorioSel.numero}</span>
                  <span className="text-xs text-fg-muted">
                    início {ddmmaaaa(relatorioSel.data_inicio)} · término {ddmmaaaa(relatorioSel.data_termino)}
                  </span>
                  <button
                    onClick={abrirPicker}
                    className="ml-auto text-xs font-medium text-accent hover:underline"
                  >
                    trocar
                  </button>
                </div>
              ) : (
                <Button variant="secondary" icon={Search} onClick={abrirPicker}>
                  Buscar relatório
                </Button>
              )}
              {aviso && <p className="mt-2 text-xs text-fg-muted">{aviso}</p>}
            </div>
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

      {/* Janela: relatórios já gerados para o cliente + tecnologia */}
      {pickerAberto && (
        <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/50 p-4">
          <div className="my-8 w-full max-w-lg rounded-xl border border-border bg-surface p-5 shadow-xl">
            <div className="mb-1 flex items-center justify-between">
              <h2 className="text-base font-semibold text-fg">Relatórios do cliente</h2>
              <button
                onClick={() => setPickerAberto(false)}
                className="rounded p-1 text-fg-subtle transition-colors hover:bg-surface-muted hover:text-fg"
                aria-label="Fechar"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <p className="mb-3 text-xs text-fg-subtle">
              {tecnologias.find((t) => String(t.id) === tecnologia)?.nome} · escolha o número para reaproveitar.
            </p>
            {carregandoPicker ? (
              <Spinner />
            ) : relatorios.length === 0 ? (
              <p className="py-6 text-center text-sm text-fg-muted">
                Nenhum relatório gerado para este cliente nesta tecnologia.
              </p>
            ) : (
              <ul className="max-h-80 space-y-1.5 overflow-y-auto">
                {relatorios.map((r) => (
                  <li key={r.id}>
                    <button
                      onClick={() => escolherRelatorio(r)}
                      className="flex w-full items-center justify-between gap-3 rounded-lg border border-border px-3 py-2 text-left transition-colors hover:border-accent hover:bg-accent-subtle"
                    >
                      <span className="font-mono text-sm font-semibold text-fg">{r.numero}</span>
                      <span className="text-xs text-fg-subtle">
                        término {ddmmaaaa(r.data_termino)} · {r.qtd_rotas} rota(s)
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
