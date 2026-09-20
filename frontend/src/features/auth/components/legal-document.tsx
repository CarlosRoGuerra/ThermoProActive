import Link from "next/link";
import { Logo, ThemeToggle } from "@/components/ds";

export function LegalDocument({
  title,
  summary,
  children,
}: {
  title: string;
  summary: string;
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-[100dvh] bg-bg text-fg">
      <header className="border-b border-border bg-surface">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-5 py-5 sm:px-8">
          <Link href="/portal/login" aria-label="Voltar ao Portal do Cliente">
            <Logo tamanho="md" />
          </Link>
          <ThemeToggle />
        </div>
      </header>
      <main id="conteudo" className="mx-auto max-w-3xl px-5 py-10 sm:px-8 sm:py-14">
        <Link href="/portal/login" className="text-sm font-medium text-primary hover:underline">
          Voltar ao Portal do Cliente
        </Link>
        <article className="mt-8">
          <p className="text-xs font-semibold uppercase tracking-wide text-primary">Documento público</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">{title}</h1>
          <p className="mt-4 text-base leading-relaxed text-fg-muted">{summary}</p>
          <p className="mt-3 text-xs text-fg-subtle">Versão de 18 de setembro de 2026.</p>
          <div className="mt-10 space-y-9 [&_h2]:text-xl [&_h2]:font-semibold [&_li]:leading-relaxed [&_p]:leading-relaxed [&_p]:text-fg-muted [&_ul]:list-disc [&_ul]:space-y-2 [&_ul]:pl-5">
            {children}
          </div>
        </article>
      </main>
      <footer className="border-t border-border px-5 py-6 text-center text-xs text-fg-muted">
        ThermoProActive Serviços Ltda. · Documentos de acesso à plataforma
      </footer>
    </div>
  );
}
