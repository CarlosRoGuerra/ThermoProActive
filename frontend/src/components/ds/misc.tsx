"use client";

import { useEffect, useState, type ReactNode } from "react";
import { Moon, Sun } from "lucide-react";
import { cn, type Tom } from "./utils";
import { iniciais } from "@/lib/format";

/* ==========================================================================
   Avatar — pessoa ou empresa. Sem foto, iniciais estáveis.
   ========================================================================== */

const AVATAR_TAMANHO = {
  xs: "h-6 w-6 text-2xs",
  sm: "h-8 w-8 text-xs",
  md: "h-9 w-9 text-sm",
  lg: "h-12 w-12 text-base",
} as const;

export function Avatar({
  nome,
  src,
  tamanho = "md",
  onChrome = false,
  className = "",
}: {
  nome: string;
  /** URL de logomarca/foto; cai nas iniciais se falhar. */
  src?: string | null;
  tamanho?: keyof typeof AVATAR_TAMANHO;
  onChrome?: boolean;
  className?: string;
}) {
  const [falhou, setFalhou] = useState(false);
  const classes = cn(
    "flex shrink-0 items-center justify-center overflow-hidden rounded-full font-semibold",
    AVATAR_TAMANHO[tamanho],
    onChrome ? "bg-chrome-muted text-chrome-fg-muted" : "bg-surface-muted text-fg-muted",
    className
  );

  if (src && !falhou) {
    return (
      // eslint-disable-next-line @next/next/no-img-element -- logomarca vem da API
      // (media do Django), com host variável; next/image exigiria allowlist por ambiente.
      <img
        src={src}
        alt=""
        aria-hidden="true"
        onError={() => setFalhou(true)}
        className={cn(classes, "object-cover")}
      />
    );
  }

  return (
    <span className={classes} aria-hidden="true" title={nome}>
      {iniciais(nome)}
    </span>
  );
}

/* ==========================================================================
   ThemeToggle
   ========================================================================== */

export function ThemeToggle({
  className = "",
  onChrome = false,
}: {
  className?: string;
  onChrome?: boolean;
}) {
  const [escuro, setEscuro] = useState(false);
  const [montado, setMontado] = useState(false);

  useEffect(() => {
    let salvo: string | null = null;
    try {
      salvo = localStorage.getItem("tpa-theme");
    } catch {
      /* navegação privada / storage bloqueado — segue a preferência do SO */
    }
    setEscuro(salvo ? salvo === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches);
    setMontado(true);
  }, []);

  function alternar() {
    const proximo = !escuro;
    setEscuro(proximo);
    document.documentElement.dataset.theme = proximo ? "dark" : "light";
    try {
      localStorage.setItem("tpa-theme", proximo ? "dark" : "light");
    } catch {
      /* sem persistência: vale para esta sessão */
    }
  }

  // Antes de montar não sabemos o tema real: mostra a lua (estado neutro) sem
  // anunciar nada errado para o leitor de tela.
  const mostrarSol = montado && escuro;
  const rotulo = mostrarSol ? "Ativar tema claro" : "Ativar tema escuro";

  return (
    <button
      type="button"
      onClick={alternar}
      aria-label={rotulo}
      title={rotulo}
      className={cn(
        "inline-flex h-9 w-9 items-center justify-center rounded-lg transition-colors duration-fast",
        onChrome
          ? "text-chrome-fg-muted hover:bg-chrome-muted hover:text-chrome-fg"
          : "text-fg-muted hover:bg-surface-muted hover:text-fg",
        className
      )}
    >
      {mostrarSol ? <Sun className="h-4.5 w-4.5" aria-hidden="true" /> : <Moon className="h-4.5 w-4.5" aria-hidden="true" />}
    </button>
  );
}

/* ==========================================================================
   Barra de proporção — comparação simples sem trazer biblioteca de gráfico.
   Usada onde um gráfico não acrescentaria nada (distribuição, custo × custo).
   ========================================================================== */

export function BarMeter({
  itens,
  total,
  className = "",
  formatarValor,
}: {
  itens: { label: string; valor: number; tom: Tom }[];
  /** Base do percentual; padrão é a soma dos itens. */
  total?: number;
  className?: string;
  formatarValor?: (v: number) => string;
}) {
  const base = total ?? itens.reduce((s, i) => s + i.valor, 0);
  const cor: Record<Tom, string> = {
    neutral: "bg-fg-subtle",
    primary: "bg-primary",
    success: "bg-success",
    warning: "bg-warning",
    danger: "bg-danger",
    info: "bg-info",
  };

  return (
    <div className={cn("space-y-3.5", className)}>
      {itens.map((i) => {
        const pct = base > 0 ? Math.round((i.valor / base) * 100) : 0;
        return (
          <div key={i.label}>
            <div className="mb-1.5 flex items-baseline justify-between gap-2 text-sm">
              <span className="truncate text-fg-muted">{i.label}</span>
              <span className="shrink-0 font-medium text-fg">
                <span className="data">{formatarValor ? formatarValor(i.valor) : i.valor.toLocaleString("pt-BR")}</span>
                {base > 0 && <span className="ml-1 text-xs text-fg-subtle">({pct}%)</span>}
              </span>
            </div>
            <div
              className="h-2 w-full overflow-hidden rounded-full bg-surface-muted"
              role="meter"
              aria-label={i.label}
              aria-valuenow={i.valor}
              aria-valuemin={0}
              aria-valuemax={base}
            >
              <div
                className={cn("h-full rounded-full transition-[width] duration-slow ease-out", cor[i.tom])}
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

/** Indicador de progresso de etapa (onboarding, fluxo de inspeção). */
export function ProgressBar({
  valor,
  max = 100,
  label,
  className = "",
}: {
  valor: number;
  max?: number;
  label: string;
  className?: string;
}) {
  const pct = max > 0 ? Math.min(100, Math.round((valor / max) * 100)) : 0;
  return (
    <div className={className}>
      <div
        className="h-1.5 w-full overflow-hidden rounded-full bg-surface-muted"
        role="progressbar"
        aria-label={label}
        aria-valuenow={valor}
        aria-valuemin={0}
        aria-valuemax={max}
      >
        <div
          className="h-full rounded-full bg-primary transition-[width] duration-slow ease-out"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

/* ==========================================================================
   Linha do tempo — histórico de ocorrências (serviço, laudo, OSP).
   ========================================================================== */

export function Timeline({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <ol className={cn("relative space-y-4 border-l border-border pl-5", className)}>{children}</ol>;
}

export function TimelineItem({
  titulo,
  quando,
  children,
  tom = "neutral",
}: {
  titulo: ReactNode;
  quando: string;
  children?: ReactNode;
  tom?: Tom;
}) {
  const cor: Record<Tom, string> = {
    neutral: "bg-fg-subtle",
    primary: "bg-primary",
    success: "bg-success",
    warning: "bg-warning",
    danger: "bg-danger",
    info: "bg-info",
  };
  return (
    <li className="relative">
      <span
        className={cn(
          "absolute -left-[1.4375rem] top-1.5 h-2.5 w-2.5 rounded-full ring-2 ring-surface",
          cor[tom]
        )}
        aria-hidden="true"
      />
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-sm font-medium text-fg">{titulo}</p>
        <time className="text-xs text-fg-subtle">{quando}</time>
      </div>
      {children && <div className="mt-0.5 text-xs text-fg-muted">{children}</div>}
    </li>
  );
}
