"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Printer } from "lucide-react";
import { api } from "@/lib/api";
import { Button, Card, Spinner } from "@/components/ui";

const ddmmaaaa = (iso: string | null) => (iso ? iso.split("-").reverse().join("/") : "—");

/* ------------------------------- Tipos ------------------------------------ */
type Instrumento = { tipo: string; marca: string; modelo: string; numero_serie: string; entidade_calibracao: string; software_analise: string };
type Norma = { codigo: string; nome: string; orgao: string };
type Cabecalho = {
  empresa: string; cnpj: string; endereco: string; cidade_uf: string; contato: string;
  logomarca: string | null; numero: string; tecnologia: string; analistas: string[];
  data_inicio: string | null; data_termino: string | null;
  instrumentos: Instrumento[]; normas: Norma[];
};
type Dist = { rotulo: string; total: number };
type SecaoB = { condicoes: Dist[]; componentes: Dist[]; anomalias: Dist[]; equip_monitorados: number; anomalias_diagnosticadas: number };
type LinhaC = { tag: string; equipamento: string; condicao: string };
type GrupoC = { area: string; setor: string; linhas: LinhaC[] };
type OspD = {
  osp: string; area: string; setor: string; tag: string; equipamento: string; componente: string;
  anomalia: string; recomendacao: string; observacao: string; grau_risco: string; grau_risco_descricao: string;
  amplitude_velocidade: string | null; amplitude_aceleracao: string | null; analista: string;
  imagens: { tipo: string; arquivo: string; legenda: string }[];
};
type Dossie = { cabecalho: Cabecalho; secao_b: SecaoB; secao_c: { total: number; grupos: GrupoC[] }; secao_d: OspD[] };

/* ------------------------------- Cores GR --------------------------------- */
const CORES: Record<string, { bg: string; fg: string }> = {
  GR0: { bg: "#16a34a", fg: "#fff" }, GR1: { bg: "#dc2626", fg: "#fff" },
  GR2: { bg: "#b91c1c", fg: "#fff" }, GR3: { bg: "#ea580c", fg: "#fff" },
  GR4: { bg: "#facc15", fg: "#1f2937" }, GR5: { bg: "#fde047", fg: "#1f2937" },
  OK: { bg: "#16a34a", fg: "#fff" },
};
function corCondicao(c: string): { bg: string; fg: string } {
  return CORES[c.replace(/[^A-Za-z0-9]/g, "").toUpperCase()] ?? { bg: "#94a3b8", fg: "#fff" };
}

/* Glossário (conteúdo padrão da carta do relatório) */
const GLOSSARIO: [string, string][] = [
  ["O.S.P.", "Ordem de Serviço Preditivo gerada para correção de cada anomalia detectada."],
  ["G.R.", "Grau de Risco — determina o prazo de correção das anomalias detectadas."],
  ["GR-1", "Risco eminente — intervenção imediata, prazo máximo de 03 dias."],
  ["GR-2", "Risco elevado — intervenção em prazo máximo de 10 dias."],
  ["GR-3", "Risco moderado — intervenção em prazo máximo de 20 dias."],
  ["GR-4", "Risco baixo — intervenção em parada programada, prazo máximo de 30 dias."],
  ["MP", "Monitoramento Prejudicado — obstrução parcial ao equipamento monitorado."],
  ["NM", "Não Monitorado — obstrução total e/ou risco à integridade dos trabalhadores."],
  ["OK", "Normalidade Operacional — sem anomalias."],
  ["PDM", "Parado Devido Manutenção."],
  ["PDP", "Parado Devido Processo."],
  ["LA / LOA", "Lado Acoplado / Lado Oposto ao Acoplamento."],
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

/* ------------------------------- Página ----------------------------------- */
export function RelatorioDossie({ relatorioId }: { relatorioId: number }) {
  const [d, setD] = useState<Dossie | null>(null);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  const carregar = useCallback(async () => {
    setLoading(true);
    try {
      setD(await api<Dossie>(`/relatorios-inspecao/${relatorioId}/dossie/`));
    } catch {
      setErro("Não foi possível carregar o relatório.");
    } finally {
      setLoading(false);
    }
  }, [relatorioId]);

  useEffect(() => { carregar(); }, [carregar]);

  if (loading) return <Card><Spinner label="Montando relatório…" /></Card>;
  if (!d) return <Card><p className="text-sm text-danger-fg">{erro ?? "Relatório não encontrado."}</p></Card>;

  const { cabecalho: cab, secao_b: b, secao_c: c, secao_d: osps } = d;

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
        <Button icon={Printer} onClick={() => window.print()}>Imprimir / PDF</Button>
      </div>

      <div className="print-area space-y-4 text-slate-800">
        {/* ============================= CAPA ============================= */}
        <section className="flex min-h-[60vh] flex-col justify-between rounded-xl border border-border bg-white p-8">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-3xl font-black tracking-tight text-[#1d4ed8]">Thermo<span className="text-[#ea580c]">proactive</span></p>
              <p className="text-sm text-slate-500">Manutenção Preditiva</p>
            </div>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            {cab.logomarca && <img src={cab.logomarca} alt="Logo do cliente" className="max-h-24 max-w-[180px] object-contain" />}
          </div>
          <div className="text-right">
            <p className="text-2xl font-bold text-slate-700">RELATÓRIO TÉCNICO</p>
            <p className="mt-1 font-mono text-xl font-bold text-[#1d4ed8]">{cab.numero}</p>
            <div className="mt-6 text-sm font-semibold text-slate-700">
              <p>{cab.empresa}</p>
              {cab.cnpj && <p>CNPJ {cab.cnpj}</p>}
              {cab.endereco && <p className="font-normal">{cab.endereco}</p>}
              {cab.contato && <p className="mt-2">A/C.: {cab.contato}</p>}
            </div>
          </div>
        </section>

        {/* ========================= SEÇÃO A — CARTA ========================= */}
        <section className="pagina rounded-xl border border-border bg-white p-6">
          <p className="mb-4 text-right text-sm font-semibold text-rose-700">Seção A — Carta ao Cliente</p>

          <h3 className="text-sm font-bold text-slate-800">1. Objetivo do Relatório</h3>
          <p className="mb-3 text-sm text-slate-600">
            Apresentar os resultados das análises técnicas de: <em>{cab.tecnologia}</em>.
          </p>

          <h3 className="text-sm font-bold text-slate-800">2. Datas da Execução</h3>
          <p className="mb-3 text-sm text-slate-600">
            Medições em campo — {ddmmaaaa(cab.data_inicio)}{cab.data_inicio !== cab.data_termino ? ` a ${ddmmaaaa(cab.data_termino)}` : ""}.
          </p>

          <h3 className="text-sm font-bold text-slate-800">3. Conteúdo do Relatório</h3>
          <ul className="mb-3 ml-4 list-disc text-sm text-slate-600">
            <li>Seção A — Carta ao Cliente</li>
            <li>Seção B — KPI’s Dashboard</li>
            <li>Seção C — Relação de Equipamentos Contemplados</li>
            <li>Seção D — Ordens de Serviços Preditivos</li>
          </ul>

          <h3 className="text-sm font-bold text-slate-800">4. Instrumentação Utilizada</h3>
          {cab.instrumentos.length ? (
            <ul className="mb-3 ml-4 list-disc text-sm text-slate-600">
              {cab.instrumentos.map((i, k) => (
                <li key={k}>
                  {[i.tipo, i.marca, i.modelo].filter(Boolean).join(" · ")}
                  {i.numero_serie && ` · Serial ${i.numero_serie}`}
                  {i.software_analise && ` · Software ${i.software_analise}`}
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
          <dl className="mb-3 text-sm text-slate-600">
            {GLOSSARIO.map(([sigla, desc]) => (
              <div key={sigla} className="flex gap-2 py-0.5">
                <dt className="w-20 shrink-0 font-semibold text-slate-700">{sigla}</dt>
                <dd>{desc}</dd>
              </div>
            ))}
          </dl>

          <h3 className="text-sm font-bold text-slate-800">7. Considerações Importantes</h3>
          <p className="text-sm text-slate-600">
            Os critérios das análises são técnicos, associados à experiência do analista. Cada equipamento tem
            seu nível de criticidade para a planta, que deve ser considerado pelo planejamento da manutenção.
            Toda anomalia detectada deve ser corrigida o mais rápido possível; o prazo sugerido serve como
            referência.
          </p>
          <div className="mt-8 text-center">
            <p className="mx-auto w-56 border-t border-slate-400 pt-1 text-sm font-semibold text-slate-800">
              {cab.analistas.join(", ") || "Analista"}
            </p>
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
                  <div className="mx-auto mt-1 rounded-lg px-4 py-2 text-4xl font-black" style={{ background: cor.bg, color: cor.fg }}>
                    {o.grau_risco || "—"}
                  </div>
                  <p className="mt-1 text-xs font-medium text-slate-600">{o.grau_risco_descricao}</p>
                </div>
              </div>

              {o.imagens.length > 0 && (
                <div className="mt-4 grid grid-cols-2 gap-3">
                  {o.imagens.map((img, k) => (
                    <figure key={k} className="overflow-hidden rounded-lg border border-slate-200">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img src={img.arquivo} alt={img.tipo} className="w-full object-contain" />
                      <figcaption className="px-2 py-1 text-center text-xs text-slate-500">{img.legenda || img.tipo}</figcaption>
                    </figure>
                  ))}
                </div>
              )}

              <div className="mt-4 space-y-1 text-sm">
                <p><span className="font-semibold text-slate-700">Recomendação:</span> <span className="text-slate-600">{o.recomendacao || "—"}</span></p>
                <p><span className="font-semibold text-slate-700">Observação:</span> <span className="text-slate-600">{o.observacao || "—"}</span></p>
                <div className="flex gap-8 pt-1">
                  <p><span className="font-semibold text-slate-700">Amplitude Velocidade Global [mm/s]:</span> {o.amplitude_velocidade ?? "—"}</p>
                  <p><span className="font-semibold text-slate-700">Amplitude Aceleração Global [mm/s²]:</span> {o.amplitude_aceleracao ?? "—"}</p>
                </div>
              </div>

              {/* Etapas alimentadas pelo cliente */}
              <table className="mt-4 w-full border-collapse text-xs text-slate-600">
                <thead>
                  <tr className="border-b border-slate-300 text-left">
                    <th className="py-1 font-semibold" />
                    <th className="py-1 font-semibold">Data</th>
                    <th className="py-1 font-semibold">Responsável</th>
                  </tr>
                </thead>
                <tbody>
                  {["Planejamento", "Corretiva", "Finalização"].map((e) => (
                    <tr key={e} className="border-b border-slate-100">
                      <td className="py-2 font-medium text-slate-700">{e}</td>
                      <td className="py-2" />
                      <td className="py-2" />
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
