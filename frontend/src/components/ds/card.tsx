"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { ArrowRight, TrendingDown, TrendingUp, type LucideIcon } from "lucide-react";
import { cn, TOM_TEXTO, type Tom } from "./utils";
import { DicaSelo } from "./badge";

/* ==========================================================================
   Card — a única superfície elevada do sistema.
   --------------------------------------------------------------------------
   Um card é um agrupamento com fronteira própria. Regra: NÃO se aninha card
   dentro de card. Dentro de um card, para separar assuntos, use `CardSection`
   (divisória), não outra borda.
   ========================================================================== */

export function Card({
  children,
  className = "",
  interactive = false,
  padding = true,
  tom = "neutral",
  as: Tag = "div",
}: {
  children: ReactNode;
  className?: string;
  /** Card clicável inteiro — some com o card de dentro do link. */
  interactive?: boolean;
  padding?: boolean;
  /** Realce de borda para cards que carregam estado (ex.: alerta crítico). */
  tom?: Tom;
  as?: "div" | "section" | "article" | "li";
}) {
  const borda: Record<Tom, string> = {
    neutral: "border-border",
    primary: "border-primary/35",
    success: "border-success/35",
    warning: "border-warning/40",
    danger: "border-danger/40",
    info: "border-info/35",
  };
  return (
    <Tag
      className={cn(
        "rounded-xl border bg-surface shadow-xs",
        borda[tom],
        padding && "p-4 sm:p-5",
        interactive &&
          "transition-[border-color,box-shadow] duration-normal ease-out-soft hover:border-border-strong hover:shadow-md",
        className
      )}
    >
      {children}
    </Tag>
  );
}

/** Cabeçalho interno do card: título, apoio e ações do próprio bloco. */
export function CardHeader({
  title,
  description,
  actions,
  dica,
  icon: Icon,
  className = "",
}: {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  /** Texto de ajuda no selo "?" ao lado do título. */
  dica?: string;
  icon?: LucideIcon;
  className?: string;
}) {
  return (
    <div className={cn("mb-4 flex items-start justify-between gap-3", className)}>
      <div className="min-w-0">
        <h2 className="flex items-center gap-1.5 text-sm font-semibold text-fg">
          {Icon && <Icon className="h-4 w-4 shrink-0 text-fg-subtle" aria-hidden="true" />}
          <span className="truncate">{title}</span>
          {dica && <DicaSelo texto={dica} />}
        </h2>
        {description && <p className="mt-0.5 text-xs text-fg-muted">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-1.5">{actions}</div>}
    </div>
  );
}

/** Divisória interna — o substituto de "card dentro de card". */
export function CardSection({
  children,
  className = "",
  title,
}: {
  children: ReactNode;
  className?: string;
  title?: string;
}) {
  return (
    <div className={cn("-mx-4 mt-4 border-t border-border px-4 pt-4 sm:-mx-5 sm:px-5", className)}>
      {title && <h3 className="mb-2.5 text-2xs font-semibold uppercase tracking-wide text-fg-subtle">{title}</h3>}
      {children}
    </div>
  );
}

/* ==========================================================================
   MetricCard — um número que responde a uma pergunta.
   --------------------------------------------------------------------------
   Regra do produto: número sozinho não informa. Todo indicador declara
   `label` (o que é) e, quando existir, `contexto` (em relação a quê) — é a
   diferença entre "Total: 321" e "3 de 214 equipamentos exigem intervenção".
   ========================================================================== */

export function MetricCard({
  label,
  value,
  unidade,
  contexto,
  tone = "neutral",
  icon: Icon,
  dica,
  tendencia,
  href,
  hrefLabel,
  className = "",
}: {
  label: string;
  value: ReactNode;
  /** Unidade exibida menor, ao lado do número (%, h, dias, mm/s). */
  unidade?: string;
  /** A referência que dá sentido ao número ("de 214 monitorados"). */
  contexto?: ReactNode;
  tone?: Tom | /* aliases legados do StatCard */ "default" | "ok" | "warn" | "crit";
  icon?: LucideIcon;
  dica?: string;
  /** Variação contra o período anterior, em pontos percentuais ou absoluto. */
  tendencia?: { valor: number; label: string; bomQuandoSobe?: boolean };
  /** Torna o indicador um caminho para a lista que o explica. */
  href?: string;
  hrefLabel?: string;
  className?: string;
}) {
  const tom: Tom =
    tone === "default"
      ? "neutral"
      : tone === "ok"
      ? "success"
      : tone === "warn"
      ? "warning"
      : tone === "crit"
      ? "danger"
      : tone;

  const corValor = tom === "neutral" ? "text-fg" : TOM_TEXTO[tom];
  const fundoIcone: Record<Tom, string> = {
    neutral: "bg-surface-muted text-fg-subtle",
    primary: "bg-primary-subtle text-primary",
    success: "bg-success-subtle text-success-fg",
    warning: "bg-warning-subtle text-warning-fg",
    danger: "bg-danger-subtle text-danger-fg",
    info: "bg-info-subtle text-info-fg",
  };

  const corpo = (
    <>
      <div className="flex items-start justify-between gap-3">
        <p className="flex items-center gap-1.5 text-xs font-medium text-fg-muted">
          {label}
          {dica && <DicaSelo texto={dica} />}
        </p>
        {Icon && (
          <span
            className={cn("flex h-8 w-8 shrink-0 items-center justify-center rounded-lg", fundoIcone[tom])}
            aria-hidden="true"
          >
            <Icon className="h-4 w-4" />
          </span>
        )}
      </div>

      <p className={cn("mt-2 flex items-baseline gap-1 font-mono text-2xl font-semibold tabular-nums", corValor)}>
        <span className="truncate">{value}</span>
        {unidade && <span className="text-sm font-medium text-fg-subtle">{unidade}</span>}
      </p>

      {(contexto || tendencia) && (
        <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1">
          {contexto && <p className="text-xs text-fg-subtle">{contexto}</p>}
          {tendencia && tendencia.valor !== 0 && (
            <span
              className={cn(
                "inline-flex items-center gap-1 text-xs font-medium",
                (tendencia.valor > 0) === (tendencia.bomQuandoSobe ?? true)
                  ? "text-success-fg"
                  : "text-danger-fg"
              )}
            >
              {tendencia.valor > 0 ? (
                <TrendingUp className="h-3.5 w-3.5" aria-hidden="true" />
              ) : (
                <TrendingDown className="h-3.5 w-3.5" aria-hidden="true" />
              )}
              {Math.abs(tendencia.valor).toLocaleString("pt-BR")} {tendencia.label}
            </span>
          )}
        </div>
      )}

      {href && (
        <span className="mt-3 inline-flex items-center gap-1 text-xs font-medium text-primary">
          {hrefLabel ?? "Ver detalhes"}
          <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
        </span>
      )}
    </>
  );

  if (href) {
    return (
      <Link
        href={href}
        className={cn(
          "block rounded-xl border border-border bg-surface p-4 shadow-xs",
          "transition-[border-color,box-shadow] duration-normal hover:border-border-strong hover:shadow-md",
          className
        )}
      >
        {corpo}
      </Link>
    );
  }

  return (
    <Card className={className} padding={false} tom={tom === "danger" ? "danger" : "neutral"}>
      <div className="p-4">{corpo}</div>
    </Card>
  );
}

/**
 * Alias de compatibilidade: as telas atuais chamam `StatCard`.
 * Mapeia a API antiga (`hint`) para a nova (`contexto`).
 */
export function StatCard({
  label,
  value,
  tone = "default",
  icon,
  hint,
}: {
  label: string;
  value: ReactNode;
  tone?: "default" | "ok" | "warn" | "crit";
  icon?: LucideIcon;
  hint?: string;
}) {
  return <MetricCard label={label} value={value} tone={tone} icon={icon} contexto={hint} />;
}

/* ==========================================================================
   DescriptionList — pares rótulo/valor (ficha de equipamento, de laudo).
   Substitui o `<div><dt/><dd/></div>` solto repetido nas telas de detalhe.
   ========================================================================== */

export function DescriptionList({
  items,
  colunas = 2,
  className = "",
}: {
  items: { label: string; value: ReactNode; largo?: boolean; tecnico?: boolean }[];
  colunas?: 1 | 2 | 3 | 4;
  className?: string;
}) {
  return (
    <dl
      className={cn(
        "grid gap-x-6 gap-y-3.5",
        colunas === 1 && "grid-cols-1",
        colunas === 2 && "grid-cols-1 sm:grid-cols-2",
        colunas === 3 && "grid-cols-1 sm:grid-cols-2 lg:grid-cols-3",
        colunas === 4 && "grid-cols-2 lg:grid-cols-4",
        className
      )}
    >
      {items.map((i) => (
        <div key={i.label} className={cn("min-w-0", i.largo && "sm:col-span-2 lg:col-span-3")}>
          <dt className="text-2xs font-medium uppercase tracking-wide text-fg-subtle">{i.label}</dt>
          <dd className={cn("mt-0.5 break-words text-sm text-fg", i.tecnico && "data")}>{i.value}</dd>
        </div>
      ))}
    </dl>
  );
}
