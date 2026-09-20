"use client";

import { useId, useRef, type ReactNode } from "react";
import Link from "next/link";
import { cn } from "./utils";
import { Badge } from "./badge";
import type { LucideIcon } from "lucide-react";

/* ==========================================================================
   Tabs — divide uma tela densa em assuntos, sem trocar de página.
   --------------------------------------------------------------------------
   Usa o padrão ARIA de abas completo: setas ←/→ navegam, Home/End vão às
   pontas, só a aba ativa é tabulável. É o que quebra o "formulário gigante" de
   detalhe de cliente/equipamento em seções digeríveis.
   ========================================================================== */

export type Aba<T extends string> = {
  id: T;
  label: string;
  icon?: LucideIcon;
  /** Contador ao lado do rótulo (ex.: 3 alertas nesta aba). */
  contador?: number;
  disabled?: boolean;
};

export function Tabs<T extends string>({
  abas,
  ativa,
  onMudar,
  className = "",
  children,
}: {
  abas: Aba<T>[];
  ativa: T;
  onMudar: (id: T) => void;
  className?: string;
  /** Conteúdo do painel da aba ativa. */
  children?: ReactNode;
}) {
  const base = useId();
  const refLista = useRef<HTMLDivElement>(null);

  function aoTeclar(e: React.KeyboardEvent) {
    const habilitadas = abas.filter((a) => !a.disabled);
    const atual = habilitadas.findIndex((a) => a.id === ativa);
    let proximo = -1;
    if (e.key === "ArrowRight") proximo = (atual + 1) % habilitadas.length;
    else if (e.key === "ArrowLeft") proximo = (atual - 1 + habilitadas.length) % habilitadas.length;
    else if (e.key === "Home") proximo = 0;
    else if (e.key === "End") proximo = habilitadas.length - 1;
    if (proximo < 0) return;
    e.preventDefault();
    const alvo = habilitadas[proximo];
    onMudar(alvo.id);
    refLista.current?.querySelector<HTMLElement>(`#${base}-aba-${alvo.id}`)?.focus();
  }

  return (
    <div className={className}>
      <div
        ref={refLista}
        role="tablist"
        onKeyDown={aoTeclar}
        className="-mb-px flex gap-1 overflow-x-auto border-b border-border [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
      >
        {abas.map((a) => {
          const selecionada = a.id === ativa;
          const Icone = a.icon;
          return (
            <button
              key={a.id}
              id={`${base}-aba-${a.id}`}
              role="tab"
              type="button"
              aria-selected={selecionada}
              aria-controls={`${base}-painel-${a.id}`}
              tabIndex={selecionada ? 0 : -1}
              disabled={a.disabled}
              onClick={() => onMudar(a.id)}
              className={cn(
                "inline-flex shrink-0 items-center gap-2 whitespace-nowrap border-b-2 px-3 py-2.5 text-sm font-medium transition-colors duration-fast",
                "disabled:pointer-events-none disabled:opacity-40",
                selecionada
                  ? "border-primary text-fg"
                  : "border-transparent text-fg-muted hover:border-border-strong hover:text-fg"
              )}
            >
              {Icone && <Icone className="h-4 w-4" aria-hidden="true" />}
              {a.label}
              {a.contador !== undefined && a.contador > 0 && (
                <Badge tone={selecionada ? "primary" : "neutral"} className="px-1.5 py-0 text-2xs">
                  {a.contador}
                </Badge>
              )}
            </button>
          );
        })}
      </div>

      {children !== undefined && (
        <div
          role="tabpanel"
          id={`${base}-painel-${ativa}`}
          aria-labelledby={`${base}-aba-${ativa}`}
          tabIndex={0}
          className="pt-5 focus-visible:outline-none"
        >
          {children}
        </div>
      )}
    </div>
  );
}

/**
 * Abas que são rotas de verdade (mantêm URL compartilhável e botão Voltar).
 * Preferir esta versão quando cada aba tem conteúdo próprio e endereço.
 */
export function TabsLink({
  abas,
  ativa,
  className = "",
}: {
  abas: { href: string; label: string; icon?: LucideIcon; contador?: number }[];
  /** `href` da aba atual. */
  ativa: string;
  className?: string;
}) {
  return (
    <nav
      className={cn(
        "-mb-px flex gap-1 overflow-x-auto border-b border-border [scrollbar-width:none] [&::-webkit-scrollbar]:hidden",
        className
      )}
    >
      {abas.map((a) => {
        const selecionada = ativa === a.href || ativa.startsWith(`${a.href}/`);
        const Icone = a.icon;
        return (
          <Link
            key={a.href}
            href={a.href}
            aria-current={selecionada ? "page" : undefined}
            className={cn(
              "inline-flex shrink-0 items-center gap-2 whitespace-nowrap border-b-2 px-3 py-2.5 text-sm font-medium transition-colors duration-fast",
              selecionada
                ? "border-primary text-fg"
                : "border-transparent text-fg-muted hover:border-border-strong hover:text-fg"
            )}
          >
            {Icone && <Icone className="h-4 w-4" aria-hidden="true" />}
            {a.label}
            {a.contador !== undefined && a.contador > 0 && (
              <Badge tone={selecionada ? "primary" : "neutral"} className="px-1.5 py-0 text-2xs">
                {a.contador}
              </Badge>
            )}
          </Link>
        );
      })}
    </nav>
  );
}

/**
 * SegmentedControl — troca de recorte do MESMO conteúdo (operacional ×
 * executivo, mês × trimestre). Diferente de Tabs, que troca de assunto.
 */
export function SegmentedControl<T extends string>({
  opcoes,
  valor,
  onMudar,
  label,
  tamanho = "md",
  className = "",
}: {
  opcoes: { valor: T; label: string; icon?: LucideIcon }[];
  valor: T;
  onMudar: (v: T) => void;
  /** Rótulo acessível do grupo. */
  label: string;
  tamanho?: "sm" | "md";
  className?: string;
}) {
  return (
    <div
      role="radiogroup"
      aria-label={label}
      className={cn(
        "inline-flex items-center gap-0.5 rounded-lg border border-border bg-surface p-0.5 shadow-xs",
        className
      )}
    >
      {opcoes.map((o) => {
        const ativa = o.valor === valor;
        const Icone = o.icon;
        return (
          <button
            key={o.valor}
            type="button"
            role="radio"
            aria-checked={ativa}
            onClick={() => onMudar(o.valor)}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-md font-medium transition-colors duration-fast",
              tamanho === "sm" ? "px-2.5 py-1 text-xs" : "px-3.5 py-1.5 text-sm",
              ativa
                ? "bg-primary text-primary-fg shadow-xs"
                : "text-fg-muted hover:bg-surface-muted hover:text-fg"
            )}
          >
            {Icone && <Icone className="h-4 w-4" aria-hidden="true" />}
            {o.label}
          </button>
        );
      })}
    </div>
  );
}
