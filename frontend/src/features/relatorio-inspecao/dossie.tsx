"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Printer, Save } from "lucide-react";
import { api } from "@/lib/api";
import { Button, Card, Field, Input, Spinner, Textarea } from "@/components/ui";
import { RelatorioCorpo } from "./shell/documento";
import type { DossieShell } from "./tipos";

/* ============================================================================
   Tela do relatório técnico (equipe interna): impressão + finalização.

   O documento em si é o shell comum (`shell/documento.tsx`) com o módulo da
   tecnologia (`modulos/`); o contrato do payload está em `tipos.ts`.
   Arquitetura completa: docs/10-ARQUITETURA-RELATORIO-MODULAR.md.
   ========================================================================== */

export function RelatorioDossie({ relatorioId }: { relatorioId: number }) {
  const [d, setD] = useState<DossieShell | null>(null);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const [dataFim, setDataFim] = useState("");
  const [consideracoes, setConsideracoes] = useState("");
  const [salvando, setSalvando] = useState(false);

  const carregar = useCallback(async () => {
    setLoading(true);
    try {
      const dossie = await api<DossieShell>(`/relatorios-inspecao/${relatorioId}/dossie/`);
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

  const cab = d.cabecalho;

  function imprimir() {
    const nome = [cab.numero, cab.empresa, cab.nome_fantasia].filter(Boolean).join("_").replace(/[\\/:*?"<>|]/g, "-");
    const original = document.title;
    document.title = nome;
    const restaurar = () => { document.title = original; window.removeEventListener("afterprint", restaurar); };
    window.addEventListener("afterprint", restaurar);
    window.print();
  }

  return (
    <div className="space-y-4">
      <style>{`
        @media print {
          /* Margem 0: cada seção é uma folha A4 FÍSICA (210×297mm) com suas
             próprias margens internas (10/5/10/15mm) e o timbrado em fluxo. */
          @page { size: A4; margin: 0; }

          html, body { margin: 0 !important; padding: 0 !important; background: #fff !important; }

          body * { visibility: hidden; }
          .print-area, .print-area * { visibility: visible; }

          .print-area { position: absolute; inset: 0 auto auto 0; width: 100%; }
          .print-area > * { margin-top: 0 !important; }
          .no-print { display: none !important; }

          /* A Carta ao Cliente (shell/carta.tsx) embrulha suas 5 folhas num
             <div className="carta-doc">, então NÃO são filhas diretas do
             .print-area — precisam do seletor à parte para quebrar página aqui
             também (a versão paged.js, "Imprimir / PDF", casa por classe .pagina
             independente da profundidade, então não precisa deste ajuste). */
          .print-area > section, .print-area .carta-doc > section { break-after: page; page-break-after: always; }
          .print-area > section:last-child, .print-area .carta-doc > section:last-child { break-after: auto; page-break-after: auto; }
          .evitar-quebra { break-inside: avoid; page-break-inside: avoid; }

          /* Capa/contracapas ocupam a folha inteira. */
          .pagina-capa { box-sizing: border-box; width: 210mm; min-height: 297mm; background: #fff !important; }
        }
      `}</style>

      <div className="no-print flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Link href="/relatorios-inspecao" className="inline-flex items-center gap-1.5 text-xs font-medium text-fg-muted transition-colors hover:text-fg">
            <ArrowLeft className="h-3.5 w-3.5" /> Voltar para Relatórios
          </Link>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" size="sm" icon={Printer} onClick={imprimir}>Impressão simples</Button>
          <Link
            href={`/imprimir/${relatorioId}`}
            className="inline-flex h-10 items-center gap-2 rounded-lg bg-accent px-4 text-sm font-medium text-accent-fg shadow-xs transition-colors hover:bg-accent-hover"
          >
            <Printer className="h-4 w-4" /> Imprimir / PDF (com nº de página)
          </Link>
        </div>
      </div>

      {/* Painel de finalização */}
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

      <RelatorioCorpo d={d} />
    </div>
  );
}
