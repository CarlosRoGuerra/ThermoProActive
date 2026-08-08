"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Printer } from "lucide-react";
import { api } from "@/lib/api";
import { Button, Card, Spinner } from "@/components/ui";

const ddmmaaaa = (iso: string | null) => (iso ? iso.split("-").reverse().join("/") : "—");

type LinhaC = { tag: string; equipamento: string; condicao: string };
type GrupoC = { area: string; setor: string; linhas: LinhaC[] };
type SecaoC = {
  empresa: string;
  numero: string;
  data_inicio: string | null;
  data_termino: string | null;
  total: number;
  grupos: GrupoC[];
};

// Cores dos graus de risco / condições (paleta da carta do relatório).
const CORES: Record<string, { bg: string; fg: string }> = {
  GR0: { bg: "#16a34a", fg: "#fff" },
  GR1: { bg: "#dc2626", fg: "#fff" },
  GR2: { bg: "#b91c1c", fg: "#fff" },
  GR3: { bg: "#ea580c", fg: "#fff" },
  GR4: { bg: "#facc15", fg: "#1f2937" },
  GR5: { bg: "#fde047", fg: "#1f2937" },
  OK: { bg: "#16a34a", fg: "#fff" },
};
function corCondicao(c: string): { bg: string; fg: string } {
  const chave = c.replace(/[^A-Za-z0-9]/g, "").toUpperCase();
  return CORES[chave] ?? { bg: "#94a3b8", fg: "#fff" };
}

export function RelatorioDossie({ relatorioId }: { relatorioId: number }) {
  const [secao, setSecao] = useState<SecaoC | null>(null);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  const carregar = useCallback(async () => {
    setLoading(true);
    try {
      const d = await api<SecaoC>(`/relatorios-inspecao/${relatorioId}/secao-c/`);
      setSecao(d);
    } catch {
      setErro("Não foi possível carregar o relatório.");
    } finally {
      setLoading(false);
    }
  }, [relatorioId]);

  useEffect(() => {
    carregar();
  }, [carregar]);

  if (loading) return <Card><Spinner label="Montando relatório…" /></Card>;
  if (!secao) return <Card><p className="text-sm text-danger-fg">{erro ?? "Relatório não encontrado."}</p></Card>;

  return (
    <div className="space-y-4">
      {/* Estilo de impressão: imprime só a área do relatório. */}
      <style>{`
        @media print {
          body * { visibility: hidden; }
          .print-area, .print-area * { visibility: visible; }
          .print-area { position: absolute; left: 0; top: 0; width: 100%; }
          .no-print { display: none !important; }
        }
      `}</style>

      <div className="no-print flex items-center justify-between gap-3">
        <Link
          href="/relatorios-inspecao"
          className="inline-flex items-center gap-1.5 text-xs font-medium text-fg-muted transition-colors hover:text-fg"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Voltar para Relatórios
        </Link>
        <Button icon={Printer} onClick={() => window.print()}>Imprimir / PDF</Button>
      </div>

      <div className="print-area rounded-xl border border-border bg-white p-6 text-slate-800 shadow-sm">
        {/* Cabeçalho da Seção C */}
        <div className="mb-4 border-b-2 border-slate-300 pb-3">
          <p className="text-right text-sm font-semibold text-rose-700">
            Seção C — Equipamentos Inspecionados
          </p>
          <div className="mt-2 flex flex-wrap items-end justify-between gap-2">
            <div>
              <p className="text-xs text-slate-500">Empresa</p>
              <p className="text-base font-semibold text-slate-900">{secao.empresa}</p>
            </div>
            <div className="text-right text-xs text-slate-600">
              <p className="font-mono font-semibold text-slate-900">{secao.numero}</p>
              <p>
                {ddmmaaaa(secao.data_inicio)} a {ddmmaaaa(secao.data_termino)} · {secao.total} análise(s)
              </p>
            </div>
          </div>
        </div>

        {secao.grupos.length === 0 ? (
          <p className="py-8 text-center text-sm text-slate-500">
            Nenhum equipamento inspecionado neste relatório ainda.
          </p>
        ) : (
          <div className="space-y-5">
            {secao.grupos.map((g, gi) => (
              <div key={gi}>
                <p className="text-sm font-semibold text-slate-800">
                  Área: {g.area} · Setor: {g.setor}
                </p>
                <table className="mt-1 w-full border-collapse text-sm">
                  <thead>
                    <tr className="border-b border-slate-300 text-left text-xs uppercase tracking-wide text-slate-500">
                      <th className="w-28 py-1.5 pr-2 font-semibold">Tag</th>
                      <th className="py-1.5 pr-2 font-semibold">Equipamento</th>
                      <th className="w-24 py-1.5 text-right font-semibold">
                        {ddmmaaaa(secao.data_termino)}
                      </th>
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
                            <span
                              className="inline-block rounded px-2 py-0.5 text-xs font-semibold"
                              style={{ background: cor.bg, color: cor.fg }}
                            >
                              {l.condicao}
                            </span>
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
      </div>
    </div>
  );
}
