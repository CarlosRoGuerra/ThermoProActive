"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Printer, Save } from "lucide-react";
import { api } from "@/lib/api";
import { tecnologiaTipo, type TecnologiaTipo } from "@/lib/inspecoes";
import { Button, Card, Field, Input, Spinner, Textarea } from "@/components/ui";

const ddmmaaaa = (iso: string | null) => (iso ? iso.split("-").reverse().join("/") : "—");

/* ------------------------------- Tipos ------------------------------------ */
type Instrumento = {
  tipo: string; marca: string; modelo: string; numero_serie: string;
  data_ultima_calibracao: string | null; proxima_calibracao: string | null;
  periodicidade: string; entidade_calibracao: string; software_analise: string;
};
type Norma = { codigo: string; nome: string; orgao: string };
type GlossTerm = { sigla: string; termo: string; descricao: string };
type Cabecalho = {
  empresa: string; nome_fantasia: string; cnpj: string; endereco: string; cidade_uf: string; contato: string; departamento: string;
  logomarca: string | null; numero: string; tecnologia: string; analistas: string[];
  data_inicio: string | null; data_termino: string | null; data_finalizacao: string | null;
  instrumentos: Instrumento[]; normas: Norma[]; glossario: GlossTerm[]; consideracoes_finais: string;
};
type Dist = { rotulo: string; total: number };
type SecaoB = { condicoes: Dist[]; componentes: Dist[]; anomalias: Dist[]; equip_monitorados: number; anomalias_diagnosticadas: number };
type LinhaC = { tag: string; equipamento: string; condicao: string };
type GrupoC = { area: string; setor: string; linhas: LinhaC[] };
type AvalLinha = { rotulo: string; pred_q: string | null; pred_v: string | null; emerg_q: string | null; emerg_v: string | null };
type Avaliacao = { linhas: AvalLinha[]; total_preditiva: string; total_emergencial: string; retorno: string };
type OspD = {
  osp: string; area: string; setor: string; tag: string; equipamento: string; componente: string;
  anomalia: string; recomendacao: string; observacao: string; grau_risco: string; grau_risco_descricao: string;
  amplitude_velocidade: string | null; amplitude_aceleracao: string | null;
  temperatura_medida: string | null; temperatura_referencia: string | null; delta_t: string | null; carga_percentual: string | null;
  corrente: (string | null)[]; tensao: (string | null)[]; analista: string;
  imagens: { tipo: string; arquivo: string; legenda: string }[];
  avaliacao: Avaliacao | null;
};

const num = (v: string | null) => (v == null || v === "" ? 0 : Number(v));
const moeda = (v: string | number | null) => (v == null || v === "" ? "—" : num(String(v)).toLocaleString("pt-BR", { style: "currency", currency: "BRL" }));
const qtd = (v: string | null) => (v == null || v === "" ? "—" : String(num(v)));
type Dossie = { cabecalho: Cabecalho; secao_b: SecaoB; secao_c: { total: number; grupos: GrupoC[] }; secao_d: OspD[] };

/* ------------------------------- Cores GR --------------------------------- */
const CORES: Record<string, { bg: string; fg: string }> = {
  GR0: { bg: "#16a34a", fg: "#fff" }, GR1: { bg: "#dc2626", fg: "#fff" },
  GR2: { bg: "#b91c1c", fg: "#fff" }, GR3: { bg: "#ea580c", fg: "#fff" },
  GR4: { bg: "#facc15", fg: "#1f2937" }, GR5: { bg: "#fde047", fg: "#1f2937" },
  OK: { bg: "#16a34a", fg: "#fff" },
};
function corCondicao(c: string) {
  return CORES[c.replace(/[^A-Za-z0-9]/g, "").toUpperCase()] ?? { bg: "#94a3b8", fg: "#fff" };
}

// 6.1 — abreviações fixas do glossário (não vêm de dado).
const ABREVIACOES: [string, string][] = [
  ["O.S.P.", "Ordem de Serviço Preditivo gerada para correção de cada anomalia detectada."],
  ["G.R.", "Grau de Risco — determina o prazo de correção das anomalias detectadas."],
  ["LA", "Lado Acoplado."],
  ["LOA", "Lado Oposto ao Acoplado."],
];

/* ------------------------------- Barras ----------------------------------- */
function Barras({ dados, corFn, hue = "#3b6ea5" }: { dados: Dist[]; corFn?: (r: string) => string; hue?: string }) {
  if (dados.length === 0) return <p className="text-xs text-slate-400">Sem dados.</p>;
  const max = Math.max(1, ...dados.map((d) => d.total));
  return (
    <div className="space-y-1.5">
      {dados.map((d) => (
        <div key={d.rotulo} className="flex items-center gap-2 text-xs">
          <span className="w-40 shrink-0 truncate text-slate-600" title={d.rotulo}>{d.rotulo}</span>
          <div className="h-4 flex-1 overflow-hidden rounded bg-slate-100">
            <div className="h-4 rounded" style={{ width: `${(d.total / max) * 100}%`, background: corFn?.(d.rotulo) ?? hue }} />
          </div>
          <span className="w-6 shrink-0 text-right tabular-nums font-medium text-slate-700">{d.total}</span>
        </div>
      ))}
    </div>
  );
}

/* Bloco de medição específico por tecnologia (base do template dinâmico). */
function BlocoMedicao({ o, tipo }: { o: OspD; tipo: TecnologiaTipo }) {
  if (tipo === "vibracao") {
    return (
      <div className="flex flex-wrap gap-x-8 gap-y-1 pt-1">
        <p><span className="font-semibold text-slate-700">Amplitude Velocidade Global [mm/s]:</span> {o.amplitude_velocidade ?? "—"}</p>
        <p><span className="font-semibold text-slate-700">Amplitude Aceleração Global [g]:</span> {o.amplitude_aceleracao ?? "—"}</p>
      </div>
    );
  }
  if (tipo === "termografia") {
    return (
      <div className="flex flex-wrap gap-x-8 gap-y-1 pt-1">
        <p><span className="font-semibold text-slate-700">Temp. medida [°C]:</span> {o.temperatura_medida ?? "—"}</p>
        <p><span className="font-semibold text-slate-700">Temp. referência [°C]:</span> {o.temperatura_referencia ?? "—"}</p>
        <p><span className="font-semibold text-slate-700">ΔT [°C]:</span> {o.delta_t ?? "—"}</p>
        <p><span className="font-semibold text-slate-700">Carga [%]:</span> {o.carga_percentual ?? "—"}</p>
      </div>
    );
  }
  return null;
}

/* Avaliação de Resultados (ROI) — preditiva × emergencial. */
function TabelaAvaliacao({ aval }: { aval: Avaliacao }) {
  return (
    <div className="mt-4 overflow-x-auto">
      <p className="rounded-t bg-emerald-600 px-2 py-1 text-center text-xs font-bold text-white">Avaliação de Resultados</p>
      <table className="w-full border-collapse text-xs">
        <thead className="text-slate-500">
          <tr className="border-b border-slate-300">
            <th className="py-1 text-left" />
            <th colSpan={2} className="py-1 text-center">Manut. Orientada Preditiva</th>
            <th colSpan={2} className="py-1 text-center">Manut. Emergencial</th>
            <th className="py-1 text-center">Retorno</th>
          </tr>
          <tr className="border-b border-slate-200 text-[10px]">
            <th />
            <th className="py-0.5 text-right">Qtde</th><th className="py-0.5 text-right">Valor</th>
            <th className="py-0.5 text-right">Qtde</th><th className="py-0.5 text-right">Valor</th>
            <th className="py-0.5 text-right">Resultado</th>
          </tr>
        </thead>
        <tbody className="text-slate-700">
          {aval.linhas.map((l) => {
            const ret = num(l.emerg_v) - num(l.pred_v);
            return (
              <tr key={l.rotulo} className="border-b border-slate-100">
                <td className="py-1 font-medium">{l.rotulo}</td>
                <td className="py-1 text-right">{qtd(l.pred_q)}</td>
                <td className="py-1 text-right">{moeda(l.pred_v)}</td>
                <td className="py-1 text-right">{qtd(l.emerg_q)}</td>
                <td className="py-1 text-right">{moeda(l.emerg_v)}</td>
                <td className="py-1 text-right">{ret ? moeda(ret) : "—"}</td>
              </tr>
            );
          })}
          <tr className="border-t border-slate-300 font-semibold">
            <td className="py-1">Total</td>
            <td />
            <td className="py-1 text-right">{moeda(aval.total_preditiva)}</td>
            <td />
            <td className="py-1 text-right">{moeda(aval.total_emergencial)}</td>
            <td className="py-1 text-right text-emerald-700">{moeda(aval.retorno)}</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

/* Bloco de cliente reutilizado na Capa e na Carta (redundância obrigatória). */
function BlocoCliente({ cab }: { cab: Cabecalho }) {
  return (
    <div className="text-sm font-semibold text-slate-700">
      <p className="font-mono text-[#1d4ed8]">{cab.numero}</p>
      <p className="mt-1">{cab.empresa}</p>
      {cab.cnpj && <p className="font-normal">CNPJ {cab.cnpj}</p>}
      {cab.endereco && <p className="font-normal">{cab.endereco}</p>}
      {(cab.contato || cab.departamento) && (
        <p className="mt-1">A/C.: {[cab.contato, cab.departamento].filter(Boolean).join(" — ")}</p>
      )}
    </div>
  );
}

/* ------------------------------- Página ----------------------------------- */
export function RelatorioDossie({ relatorioId }: { relatorioId: number }) {
  const [d, setD] = useState<Dossie | null>(null);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  // Painel de finalização (edição).
  const [dataFim, setDataFim] = useState("");
  const [consideracoes, setConsideracoes] = useState("");
  const [salvando, setSalvando] = useState(false);

  const carregar = useCallback(async () => {
    setLoading(true);
    try {
      const dossie = await api<Dossie>(`/relatorios-inspecao/${relatorioId}/dossie/`);
      setD(dossie);
      setDataFim(dossie.cabecalho.data_finalizacao ?? "");
      setConsideracoes(dossie.cabecalho.consideracoes_finais ?? "");
    } catch {
      setErro("Não foi possível carregar o relatório.");
    } finally {
      setLoading(false);
    }
  }, [relatorioId]);

  useEffect(() => { carregar(); }, [carregar]);

  async function salvarFinalizacao() {
    setSalvando(true);
    try {
      await api(`/relatorios-inspecao/${relatorioId}/`, {
        method: "PATCH",
        body: { data_finalizacao: dataFim || null, consideracoes_finais: consideracoes },
      });
      await carregar();
    } finally {
      setSalvando(false);
    }
  }

  if (loading) return <Card><Spinner label="Montando relatório…" /></Card>;
  if (!d) return <Card><p className="text-sm text-danger-fg">{erro ?? "Relatório não encontrado."}</p></Card>;

  const { cabecalho: cab, secao_b: b, secao_c: c, secao_d: osps } = d;
  const tipoTec = tecnologiaTipo(cab.tecnologia);

  // Nome do PDF = número + razão social + nome fantasia (o navegador usa o title).
  function imprimir() {
    const nome = [cab.numero, cab.empresa, cab.nome_fantasia]
      .filter(Boolean)
      .join("_")
      .replace(/[\\/:*?"<>|]/g, "-");
    const original = document.title;
    document.title = nome;
    const restaurar = () => {
      document.title = original;
      window.removeEventListener("afterprint", restaurar);
    };
    window.addEventListener("afterprint", restaurar);
    window.print();
  }

  return (
    <div className="space-y-4">
      <style>{`
        @media print {
          body * { visibility: hidden; }
          .print-area, .print-area * { visibility: visible; }
          .print-area { position: absolute; left: 0; top: 0; width: 100%; }
          .no-print { display: none !important; }
          .pagina { break-before: page; }
        }
      `}</style>

      <div className="no-print flex items-center justify-between gap-3">
        <Link href="/relatorios-inspecao" className="inline-flex items-center gap-1.5 text-xs font-medium text-fg-muted transition-colors hover:text-fg">
          <ArrowLeft className="h-3.5 w-3.5" /> Voltar para Relatórios
        </Link>
        <Button icon={Printer} onClick={imprimir}>Imprimir / PDF</Button>
      </div>

      {/* Painel de finalização (não sai na impressão) */}
      <Card className="no-print">
        <h2 className="mb-3 text-sm font-semibold text-fg">Finalização do relatório</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <Field label="Data de finalização do relatório">
            <Input type="date" value={dataFim} onChange={(e) => setDataFim(e.target.value)} />
          </Field>
          <Field label="Considerações finais / conclusões" className="sm:col-span-2">
            <Textarea rows={3} value={consideracoes} onChange={(e) => setConsideracoes(e.target.value)} placeholder="Conclusões da análise que saem no fim do relatório…" />
          </Field>
        </div>
        <div className="mt-3 flex justify-end">
          <Button icon={Save} loading={salvando} onClick={salvarFinalizacao}>Salvar</Button>
        </div>
      </Card>

      <div className="print-area space-y-4 text-slate-800">
        {/* ============================= CAPA ============================= */}
        <section className="flex min-h-[55vh] flex-col justify-between rounded-xl border border-border bg-white p-8">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-3xl font-black tracking-tight text-[#1d4ed8]">Thermo<span className="text-[#ea580c]">proactive</span></p>
              <p className="text-sm text-slate-500">Manutenção Preditiva</p>
            </div>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            {cab.logomarca && <img src={cab.logomarca} alt="Logo do cliente" className="max-h-20 max-w-[160px] object-contain" />}
          </div>
          <div className="flex flex-col items-end text-right">
            <p className="text-2xl font-bold text-slate-700">RELATÓRIO TÉCNICO</p>
            <div className="mt-6"><BlocoCliente cab={cab} /></div>
          </div>
        </section>

        {/* ========================= SEÇÃO A — CARTA ========================= */}
        <section className="pagina rounded-xl border border-border bg-white p-6">
          <div className="mb-4 flex items-start justify-between gap-4 border-b border-slate-200 pb-3">
            <p className="text-sm font-semibold text-rose-700">Seção A — Carta ao Cliente</p>
            {/* Redundância: número + cliente também aqui. */}
            <BlocoCliente cab={cab} />
          </div>

          <h3 className="text-sm font-bold text-slate-800">1. Objetivo do Relatório</h3>
          <p className="mb-3 text-sm text-slate-600">Apresentar os resultados das análises técnicas de: <em>{cab.tecnologia}</em>.</p>

          <h3 className="text-sm font-bold text-slate-800">2. Datas da Execução</h3>
          <ul className="mb-3 ml-4 list-disc text-sm text-slate-600">
            <li>Data de execução (medições em campo): {ddmmaaaa(cab.data_inicio)}{cab.data_inicio !== cab.data_termino ? ` a ${ddmmaaaa(cab.data_termino)}` : ""}</li>
            <li>Data de finalização do relatório: {ddmmaaaa(cab.data_finalizacao)}</li>
          </ul>

          <h3 className="text-sm font-bold text-slate-800">3. Conteúdo do Relatório</h3>
          <ul className="mb-3 ml-4 list-disc text-sm text-slate-600">
            <li>Seção A — Carta ao Cliente</li><li>Seção B — KPI’s Dashboard</li>
            <li>Seção C — Relação de Equipamentos Contemplados</li><li>Seção D — Ordens de Serviços Preditivos</li>
          </ul>

          <h3 className="text-sm font-bold text-slate-800">4. Instrumentação Utilizada</h3>
          {cab.instrumentos.length ? (
            <ul className="mb-3 ml-4 list-disc text-sm text-slate-600">
              {cab.instrumentos.map((i, k) => (
                <li key={k}>
                  {[i.tipo, i.marca, i.modelo].filter(Boolean).join(" · ")}
                  {i.numero_serie && ` · Serial ${i.numero_serie}`}
                  {i.software_analise && ` · Software ${i.software_analise}`}
                  <br />
                  <span className="text-xs text-slate-500">
                    Calibração: {ddmmaaaa(i.data_ultima_calibracao)}
                    {i.proxima_calibracao && ` · válida até ${ddmmaaaa(i.proxima_calibracao)}`}
                    {i.periodicidade && ` · ${i.periodicidade}`}
                    {i.entidade_calibracao && ` · Entidade: ${i.entidade_calibracao}`}
                  </span>
                </li>
              ))}
            </ul>
          ) : <p className="mb-3 text-sm text-slate-400">Não informada.</p>}

          <h3 className="text-sm font-bold text-slate-800">5. Normatização</h3>
          {cab.normas.length ? (
            <ul className="mb-3 ml-4 list-disc text-sm text-slate-600">
              {cab.normas.map((n, k) => <li key={k}>{[n.codigo, n.nome].filter(Boolean).join(" — ")}</li>)}
            </ul>
          ) : <p className="mb-3 text-sm text-slate-400">Não informada.</p>}

          <h3 className="text-sm font-bold text-slate-800">6. Glossário Técnico</h3>

          <p className="mt-1 text-sm font-semibold text-slate-700">6.1. Das abreviações</p>
          <dl className="mb-2 ml-2 text-sm text-slate-600">
            {ABREVIACOES.map(([sigla, desc], k) => (
              <div key={k} className="flex gap-2 py-0.5">
                <dt className="w-20 shrink-0 font-semibold text-slate-700">{sigla}</dt>
                <dd>{desc}</dd>
              </div>
            ))}
          </dl>

          <p className="mt-1 text-sm font-semibold text-slate-700">6.2. Das condições apropriadas</p>
          {cab.glossario.length ? (
            <dl className="mb-3 ml-2 text-sm text-slate-600">
              {cab.glossario.map((g, k) => (
                <div key={k} className="flex gap-2 py-0.5">
                  <dt className="w-20 shrink-0 font-semibold text-slate-700">{g.sigla}</dt>
                  <dd>{g.descricao}</dd>
                </div>
              ))}
            </dl>
          ) : <p className="mb-3 ml-2 text-sm text-slate-400">Sem condições no escopo deste relatório.</p>}

          <h3 className="text-sm font-bold text-slate-800">7. Considerações Importantes</h3>
          <p className="text-sm text-slate-600">
            Os critérios das análises são técnicos, associados à experiência do analista. Cada equipamento tem
            seu nível de criticidade para a planta, que deve ser considerado pelo planejamento da manutenção.
            Toda anomalia detectada deve ser corrigida o mais rápido possível; o prazo sugerido serve como referência.
          </p>
          {cab.consideracoes_finais.trim() && (
            <p className="mt-2 whitespace-pre-line text-sm text-slate-700">{cab.consideracoes_finais}</p>
          )}
          <div className="mt-8 text-center">
            <p className="mx-auto w-56 border-t border-slate-400 pt-1 text-sm font-semibold text-slate-800">{cab.analistas.join(", ") || "Analista"}</p>
            <p className="text-xs text-slate-500">Analista em Manutenção Preditiva</p>
          </div>
        </section>

        {/* ========================= SEÇÃO B — KPIs ========================= */}
        <section className="pagina rounded-xl border border-border bg-white p-6">
          <p className="mb-4 text-right text-sm font-semibold text-rose-700">Seção B — KPI’s Dashboard</p>
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
            <div>
              <h3 className="mb-2 text-sm font-bold text-slate-800">Status das Condições</h3>
              <Barras dados={b.condicoes} corFn={(r) => corCondicao(r).bg} />
            </div>
            <div>
              <h3 className="mb-2 text-sm font-bold text-slate-800">Equipamentos × Anomalias</h3>
              <div className="flex gap-4">
                <div className="flex-1 rounded-lg bg-slate-50 p-4 text-center">
                  <p className="text-3xl font-bold text-slate-800">{b.equip_monitorados}</p>
                  <p className="text-xs text-slate-500">Equipamentos monitorados</p>
                </div>
                <div className="flex-1 rounded-lg bg-slate-50 p-4 text-center">
                  <p className="text-3xl font-bold text-rose-700">{b.anomalias_diagnosticadas}</p>
                  <p className="text-xs text-slate-500">Anomalias diagnosticadas</p>
                </div>
              </div>
            </div>
            <div>
              <h3 className="mb-2 text-sm font-bold text-slate-800">Status dos Componentes</h3>
              <Barras dados={b.componentes} hue="#3b6ea5" />
            </div>
            <div>
              <h3 className="mb-2 text-sm font-bold text-slate-800">Status das Anomalias</h3>
              <Barras dados={b.anomalias} hue="#7c5cbf" />
            </div>
          </div>
        </section>

        {/* ========================= SEÇÃO C ========================= */}
        <section className="pagina rounded-xl border border-border bg-white p-6">
          <p className="mb-3 text-right text-sm font-semibold text-rose-700">Seção C — Equipamentos Inspecionados</p>
          <div className="mb-3 flex items-end justify-between border-b border-slate-200 pb-2">
            <p className="text-base font-semibold text-slate-900">{cab.empresa}</p>
            <p className="text-xs text-slate-600">Total de análises: {c.total}</p>
          </div>
          {c.grupos.length === 0 ? (
            <p className="py-6 text-center text-sm text-slate-500">Nenhum equipamento inspecionado.</p>
          ) : (
            <div className="space-y-4">
              {c.grupos.map((g, gi) => (
                <div key={gi}>
                  <p className="text-sm font-semibold text-slate-800">Área: {g.area} · Setor: {g.setor}</p>
                  <table className="mt-1 w-full border-collapse text-sm">
                    <thead>
                      <tr className="border-b border-slate-300 text-left text-xs uppercase tracking-wide text-slate-500">
                        <th className="w-24 py-1.5 pr-2 font-semibold">Tag</th>
                        <th className="py-1.5 pr-2 font-semibold">Equipamento</th>
                        <th className="w-24 py-1.5 text-right font-semibold">{ddmmaaaa(cab.data_termino)}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {g.linhas.map((l, li) => {
                        const cor = corCondicao(l.condicao);
                        return (
                          <tr key={li} className={li % 2 ? "bg-slate-50" : ""}>
                            <td className="py-1.5 pr-2 font-mono text-xs text-slate-600">{l.tag || "—"}</td>
                            <td className="py-1.5 pr-2 text-slate-800">{l.equipamento}</td>
                            <td className="py-1.5 text-right">
                              <span className="inline-block rounded px-2 py-0.5 text-xs font-semibold" style={{ background: cor.bg, color: cor.fg }}>{l.condicao}</span>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* ========================= SEÇÃO D — OSPs ========================= */}
        {osps.map((o, i) => {
          const cor = corCondicao(o.grau_risco);
          return (
            <section key={i} className="pagina rounded-xl border border-border bg-white p-6">
              <p className="mb-3 text-right text-sm font-semibold text-rose-700">Seção D — Ordem de Serviço</p>
              <div className="flex justify-between gap-4">
                <dl className="grid grid-cols-[auto,1fr] gap-x-3 gap-y-0.5 text-sm">
                  {[
                    ["Empresa", cab.empresa], ["Data", ddmmaaaa(cab.data_termino)], ["Analista", o.analista],
                    ["Área", o.area], ["Setor", o.setor], ["Tag", o.tag],
                    ["Equipamento", o.equipamento], ["Componente", o.componente], ["Anomalia", o.anomalia],
                  ].map(([k, v]) => (
                    <div key={k} className="contents">
                      <dt className="font-semibold text-slate-700">{k}:</dt>
                      <dd className="text-slate-600">{v || "—"}</dd>
                    </div>
                  ))}
                </dl>
                <div className="shrink-0 text-center">
                  <p className="font-mono text-sm text-slate-500">O.S.P nº: {o.osp}</p>
                  <p className="mt-1 text-xs text-slate-500">Grau de risco</p>
                  <div className="mx-auto mt-1 rounded-lg px-4 py-1.5 text-3xl font-black" style={{ background: cor.bg, color: cor.fg }}>{o.grau_risco || "—"}</div>
                  <p className="mt-1 text-xs font-medium text-slate-600">{o.grau_risco_descricao}</p>
                </div>
              </div>

              {o.imagens.length > 0 && (
                <div className="mt-4 grid grid-cols-2 gap-3">
                  {o.imagens.map((img, k) => (
                    <figure key={k} className="overflow-hidden rounded-lg border border-slate-200">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img src={img.arquivo} alt={img.tipo} className="mx-auto max-h-40 w-full object-contain" />
                      <figcaption className="px-2 py-1 text-center text-xs text-slate-500">{img.legenda || img.tipo}</figcaption>
                    </figure>
                  ))}
                </div>
              )}

              <div className="mt-4 space-y-1 text-sm">
                <p><span className="font-semibold text-slate-700">Recomendação:</span> <span className="text-slate-600">{o.recomendacao || "—"}</span></p>
                <p><span className="font-semibold text-slate-700">Observação:</span> <span className="text-slate-600">{o.observacao || "—"}</span></p>
                <BlocoMedicao o={o} tipo={tipoTec} />
              </div>

              {o.avaliacao && <TabelaAvaliacao aval={o.avaliacao} />}

              <table className="mt-4 w-full border-collapse text-xs text-slate-600">
                <thead>
                  <tr className="border-b border-slate-300 text-left">
                    <th className="py-1 font-semibold" /><th className="py-1 font-semibold">Data</th><th className="py-1 font-semibold">Responsável</th>
                  </tr>
                </thead>
                <tbody>
                  {["Planejamento", "Corretiva", "Finalização"].map((e) => (
                    <tr key={e} className="border-b border-slate-100">
                      <td className="py-2 font-medium text-slate-700">{e}</td><td className="py-2" /><td className="py-2" />
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          );
        })}

      </div>
    </div>
  );
}
