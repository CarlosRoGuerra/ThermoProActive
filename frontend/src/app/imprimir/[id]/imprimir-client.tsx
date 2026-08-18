"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Printer } from "lucide-react";
import { api } from "@/lib/api";
import { RelatorioCorpo, type Dossie } from "@/app/(app)/relatorios-inspecao/[id]/dossie";

/* Regras que o paged.js PRECISA processar (transforma @page/running/quebras em
   elementos reais — o navegador sozinho ignora essas regras). Vão pelo polisher. */
const PAGED_RULES = `
  @page {
    size: A4;
    margin: 2.6cm 1.3cm 2.2cm;
    @top-left      { content: element(runCabLogo); }
    @top-right     { content: element(runCabDados); }
    @bottom-center { content: element(runRodapeSite); }
    @bottom-right  { content: "pág. " counter(page) " de " counter(pages); font-size: 9px; color: #64748b; }
  }
  /* Capa e contracapas: página nomeada SEM cabeçalho e SEM nº de página
     (o papel timbrado só vale nas páginas internas). */
  .pagina-capa { page: capa; }
  @page capa {
    @top-left     { content: none; }
    @top-right    { content: none; }
    @bottom-right { content: none; }
  }
  .run-cab-logo    { position: running(runCabLogo); }
  .run-cab-dados   { position: running(runCabDados); }
  .run-rodape-site { position: running(runRodapeSite); }
  .pagina { break-before: page; }
  .evitar-quebra { break-inside: avoid; }
`;

/* Aparência de tela/impressão (CSS comum — não precisa do paged.js). */
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

export default function ImprimirClient({ relatorioId }: { relatorioId: number }) {
  const [d, setD] = useState<Dossie | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [status, setStatus] = useState("Carregando relatório…");
  const [mostrarFonte, setMostrarFonte] = useState(false);
  const fonteRef = useRef<HTMLDivElement>(null);
  const alvoRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api<Dossie>(`/relatorios-inspecao/${relatorioId}/dossie/`)
      .then(setD)
      .catch(() => setErro("Não foi possível carregar o relatório."));
  }, [relatorioId]);

  // Nome do PDF = número + razão social + nome fantasia.
  useEffect(() => {
    if (!d) return;
    const cab = d.cabecalho;
    document.title = [cab.numero, cab.empresa, cab.nome_fantasia]
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
      // paged.js mede a altura real — espere as imagens carregarem antes.
      const imgs = Array.from(fonte.querySelectorAll("img"));
      await Promise.all(
        imgs.map((im) =>
          im.complete
            ? Promise.resolve()
            : new Promise((res) => {
                im.onload = im.onerror = () => res(null);
              })
        )
      );
      if (cancelado) return;
      try {
        const { Previewer } = await import("pagedjs");
        alvo.innerHTML = "";
        await new Previewer().preview(fonte.innerHTML, [{ "paged.css": PAGED_RULES }], alvo);
        if (!cancelado) setStatus("");
      } catch {
        // Fallback: revela o conteúdo sem paginação, para ainda ser possível imprimir.
        if (!cancelado) {
          setMostrarFonte(true);
          setStatus("Não foi possível paginar — mostrando layout simples (sem nº de página).");
        }
      }
    })();
    return () => {
      cancelado = true;
    };
  }, [d]);

  if (erro) return <div className="p-6 text-sm text-red-600">{erro}</div>;

  const prestador = d?.cabecalho.prestador ?? null;

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
        <span className="hidden text-xs font-semibold text-slate-600 sm:block">
          PDF com numeração de página (pág. X de Y)
        </span>
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

      {/* Fonte consumida pelo paged.js: cabeçalho/rodapé correntes + corpo.
          Fica oculta enquanto pagina; se o paged.js falhar, é revelada (fallback). */}
      <div ref={fonteRef} className={mostrarFonte ? "" : "paged-source"}>
        {d && (
          <>
            {prestador?.logomarca && (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                className="run-cab-logo"
                src={prestador.logomarca}
                alt=""
                style={{ width: 260, maxWidth: "none", objectFit: "contain" }}
              />
            )}
            {prestador && (
              <div className="run-cab-dados" style={{ textAlign: "right", fontSize: 9, lineHeight: 1.25, color: "#64748b" }}>
                <div style={{ fontWeight: 600, color: "#64748b" }}>{prestador.nome}</div>
                {prestador.cnpj && (
                  <div style={{ color: "#94a3b8" }}>CNPJ {prestador.cnpj}{prestador.inscricao_estadual ? ` | IE ${prestador.inscricao_estadual}` : ""}</div>
                )}
                <div style={{ marginTop: 2, color: "#94a3b8" }}>
                  {prestador.endereco_linha1 && <div>{prestador.endereco_linha1}</div>}
                  {prestador.endereco_linha2 && <div>{prestador.endereco_linha2}</div>}
                  {prestador.telefone && <div>{prestador.telefone}</div>}
                  {prestador.email && <div>{prestador.email}</div>}
                </div>
              </div>
            )}
            <div className="run-rodape-site" style={{ fontSize: 9, color: "#64748b", textAlign: "center", lineHeight: 1.3 }}>
              {[prestador?.cidade_uf, prestador?.telefone, prestador?.email]
                .filter(Boolean)
                .map((x, i) => <div key={i}>{x}</div>)}
            </div>
            <RelatorioCorpo d={d} />
          </>
        )}
      </div>

      {/* paged.js injeta as páginas aqui. */}
      <div ref={alvoRef} />
    </div>
  );
}
