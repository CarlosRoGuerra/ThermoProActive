"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Printer } from "lucide-react";
import { api } from "@/lib/api";
import type { Dossie } from "@/app/(app)/relatorios-inspecao/[id]/dossie";
import { CartaCorpo } from "./carta";

/* Regras que o paged.js processa: cada folha da carta é uma A4 física (margens
   internas próprias, timbrado em fluxo). */
const PAGED_RULES = `
  @page { size: A4; margin: 0; }
  .pagina { break-before: page; }
`;

const CHROME_CSS = `
  .paged-source { display: none; }
  @media screen {
    body { background: #e2e8f0; }
    .pagedjs_pages { padding: 1.5rem 0; }
    .pagedjs_page { background: #fff; margin: 0 auto 1rem; box-shadow: 0 1px 8px rgba(0,0,0,.18); }
  }
  @media print {
    body { background: #fff; }
    .no-print { display: none !important; }
    .pagedjs_page { margin: 0; box-shadow: none; }
  }
`;

export default function CartaClient({ relatorioId }: { relatorioId: number }) {
  const [d, setD] = useState<Dossie | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [status, setStatus] = useState("Carregando dados…");
  const [mostrarFonte, setMostrarFonte] = useState(false);
  const fonteRef = useRef<HTMLDivElement>(null);
  const alvoRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api<Dossie>(`/relatorios-inspecao/${relatorioId}/dossie/`)
      .then(setD)
      .catch(() => setErro("Não foi possível carregar os dados da carta."));
  }, [relatorioId]);

  // Nome do PDF = "Carta" + número + razão social.
  useEffect(() => {
    if (!d) return;
    const cab = d.cabecalho;
    document.title = ["Carta", cab.numero, cab.empresa]
      .filter(Boolean)
      .join("_")
      .replace(/[\\/:*?"<>|]/g, "-");
  }, [d]);

  // Pagina com paged.js depois que os dados e as imagens carregarem.
  useEffect(() => {
    if (!d || !fonteRef.current || !alvoRef.current) return;
    let cancelado = false;
    (async () => {
      const fonte = fonteRef.current!;
      const alvo = alvoRef.current!;
      setStatus("Paginando…");
      const imgs = Array.from(fonte.querySelectorAll("img"));
      await Promise.all(
        imgs.map((im) =>
          im.complete ? Promise.resolve() : new Promise((res) => { im.onload = im.onerror = () => res(null); })
        )
      );
      if (cancelado) return;
      try {
        const { Previewer } = await import("pagedjs");
        alvo.innerHTML = "";
        await new Previewer().preview(fonte.innerHTML, [{ "paged.css": PAGED_RULES }], alvo);
        if (!cancelado) setStatus("");
      } catch {
        if (!cancelado) {
          setMostrarFonte(true);
          setStatus("Não foi possível paginar — mostrando layout simples.");
        }
      }
    })();
    return () => { cancelado = true; };
  }, [d]);

  if (erro) return <div className="p-6 text-sm text-red-600">{erro}</div>;

  return (
    <div>
      <style>{CHROME_CSS}</style>

      <div className="no-print sticky top-0 z-10 flex items-center justify-between gap-3 border-b border-slate-200 bg-white px-4 py-2">
        <Link
          href={`/relatorios-inspecao/${relatorioId}`}
          className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-500 hover:text-slate-800"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Voltar ao relatório
        </Link>
        <span className="hidden text-xs font-semibold text-slate-600 sm:block">Carta ao Cliente (A4)</span>
        <div className="flex items-center gap-3">
          {status && <span className="text-xs text-slate-500">{status}</span>}
          <button
            onClick={() => window.print()}
            disabled={!!status}
            className="inline-flex items-center gap-1.5 rounded-lg bg-slate-800 px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-slate-700 disabled:opacity-50"
          >
            <Printer className="h-3.5 w-3.5" /> Imprimir / PDF
          </button>
        </div>
      </div>

      {/* Fonte consumida pelo paged.js; revelada se a paginação falhar (fallback). */}
      <div ref={fonteRef} className={mostrarFonte ? "" : "paged-source"}>
        {d && <CartaCorpo d={d} />}
      </div>

      {/* paged.js injeta as folhas aqui. */}
      <div ref={alvoRef} />
    </div>
  );
}
