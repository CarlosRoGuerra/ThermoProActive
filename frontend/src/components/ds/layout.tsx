"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { ChevronRight, House, type LucideIcon } from "lucide-react";
import { cn } from "./utils";
import { DicaSelo } from "./badge";

/* ==========================================================================
   Breadcrumb — onde estou e como volto.
   --------------------------------------------------------------------------
   Aparece em toda página que não é raiz de módulo. O último item é a página
   atual e NÃO é link (aria-current="page").
   ========================================================================== */

export type Trilha = { label: string; href?: string };

export function Breadcrumb({
  itens,
  raiz = { label: "Início", href: "/" },
  className = "",
}: {
  itens: Trilha[];
  raiz?: Trilha;
  className?: string;
}) {
  const todos = [raiz, ...itens];
  return (
    <nav aria-label="Trilha de navegação" className={cn("min-w-0", className)}>
      <ol className="flex items-center gap-1 text-xs text-fg-muted">
        {todos.map((item, i) => {
          const ultimo = i === todos.length - 1;
          return (
            <li key={`${item.label}-${i}`} className={cn("flex min-w-0 items-center gap-1", !ultimo && "shrink-0")}>
              {i > 0 && <ChevronRight className="h-3.5 w-3.5 shrink-0 text-fg-subtle" aria-hidden="true" />}
              {ultimo || !item.href ? (
                <span aria-current={ultimo ? "page" : undefined} className={cn("truncate", ultimo && "font-medium text-fg")}>
                  {i === 0 && <House className="mr-1 inline h-3.5 w-3.5 align-[-2px]" aria-hidden="true" />}
                  {item.label}
                </span>
              ) : (
                <Link
                  href={item.href}
                  className="truncate rounded transition-colors hover:text-fg hover:underline"
                >
                  {i === 0 && <House className="mr-1 inline h-3.5 w-3.5 align-[-2px]" aria-hidden="true" />}
                  {item.label}
                </Link>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

/* ==========================================================================
   PageHeader — identidade da página.
   --------------------------------------------------------------------------
   Estrutura fixa: trilha · título (h1, um por página) · frase que explica para
   que serve · ações. A frase é obrigatória em tela nova: é o que faz um cliente
   entender o módulo sem treinamento.
   ========================================================================== */

export function PageHeader({
  title,
  description,
  actions,
  icon: Icon,
  trilha,
  dica,
  /** Selo ao lado do título (estado do registro, cliente em contexto). */
  selo,
  className = "",
}: {
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
  icon?: LucideIcon;
  trilha?: Trilha[];
  dica?: string;
  selo?: ReactNode;
  className?: string;
}) {
  return (
    <header className={cn("space-y-3", className)}>
      {trilha && trilha.length > 0 && <Breadcrumb itens={trilha} />}
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-3">
        <div className="flex min-w-0 items-start gap-3">
          {Icon && (
            <span
              className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary-subtle text-primary"
              aria-hidden="true"
            >
              <Icon className="h-5 w-5" />
            </span>
          )}
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-xl font-semibold text-fg">{title}</h1>
              {selo}
              {dica && <DicaSelo texto={dica} />}
            </div>
            {description && <p className="mt-1 max-w-3xl text-sm text-fg-muted">{description}</p>}
          </div>
        </div>
        {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
      </div>
    </header>
  );
}

/** Título de seção dentro da página (h2). */
export function SectionHeader({
  title,
  description,
  actions,
  dica,
  className = "",
}: {
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
  dica?: string;
  className?: string;
}) {
  return (
    <div className={cn("mb-3 flex flex-wrap items-end justify-between gap-x-4 gap-y-2", className)}>
      <div className="min-w-0">
        <h2 className="flex items-center gap-1.5 text-sm font-semibold text-fg">
          {title}
          {dica && <DicaSelo texto={dica} />}
        </h2>
        {description && <p className="mt-0.5 text-xs text-fg-muted">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  );
}

/**
 * Toolbar — a faixa de busca/filtros/ações acima de uma listagem.
 * Empilha no celular; no desktop, busca cresce e os filtros ficam à direita.
 */
export function Toolbar({
  busca,
  filtros,
  acoes,
  resumo,
  className = "",
}: {
  busca?: ReactNode;
  filtros?: ReactNode;
  acoes?: ReactNode;
  /** Ex.: "12 de 214 equipamentos · filtrado por Área 2". */
  resumo?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("space-y-2.5", className)}>
      <div className="flex flex-col gap-2.5 sm:flex-row sm:items-center">
        {busca && <div className="min-w-0 flex-1 sm:max-w-md">{busca}</div>}
        {(filtros || acoes) && (
          <div className="flex flex-wrap items-center gap-2 sm:ml-auto">
            {filtros}
            {acoes}
          </div>
        )}
      </div>
      {resumo && <p className="text-xs text-fg-subtle">{resumo}</p>}
    </div>
  );
}

/** Espaçamento vertical padrão de uma página. Evita `space-y-` improvisado. */
export function PageBody({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={cn("space-y-5 lg:space-y-6", className)}>{children}</div>;
}

/**
 * Grade de indicadores. 2 colunas no celular (números curtos cabem),
 * 4 no desktop. Nunca mais de 5 indicadores na mesma faixa.
 */
export function MetricGrid({
  children,
  colunas = 4,
  className = "",
}: {
  children: ReactNode;
  colunas?: 2 | 3 | 4 | 5;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "grid grid-cols-2 gap-3 sm:gap-4",
        colunas === 2 && "lg:grid-cols-2",
        colunas === 3 && "lg:grid-cols-3",
        colunas === 4 && "lg:grid-cols-4",
        colunas === 5 && "lg:grid-cols-5",
        className
      )}
    >
      {children}
    </div>
  );
}

/** Duas colunas assimétricas: conteúdo principal + coluna de apoio. */
export function SplitLayout({
  principal,
  apoio,
  className = "",
}: {
  principal: ReactNode;
  apoio: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("grid grid-cols-1 gap-5 lg:grid-cols-3 lg:gap-6", className)}>
      <div className="space-y-5 lg:col-span-2 lg:space-y-6">{principal}</div>
      <div className="space-y-5 lg:space-y-6">{apoio}</div>
    </div>
  );
}
