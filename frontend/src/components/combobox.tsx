"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Check, ChevronDown, Search, X } from "lucide-react";
import { cn } from "./ui";

export type Opcao = {
  id: number;
  label: string;
  /** Texto secundário para desambiguar (ex.: CNPJ, cidade/UF). */
  hint?: string;
};

/**
 * Seletor com busca — substitui o `<select>` quando a lista é grande.
 * Digitar filtra por label e hint; ↑/↓ navegam, Enter escolhe, Esc fecha.
 */
export function Combobox({
  value,
  onChange,
  options,
  placeholder = "Selecione…",
  emptyText = "Nada encontrado.",
  disabled = false,
  limparLabel = "Todos",
  permiteLimpar = true,
  className = "",
}: {
  value: number | "";
  onChange: (valor: number | "") => void;
  options: Opcao[];
  placeholder?: string;
  emptyText?: string;
  disabled?: boolean;
  limparLabel?: string;
  permiteLimpar?: boolean;
  className?: string;
}) {
  const [aberto, setAberto] = useState(false);
  const [busca, setBusca] = useState("");
  const [destaque, setDestaque] = useState(0);
  const raizRef = useRef<HTMLDivElement>(null);
  const buscaRef = useRef<HTMLInputElement>(null);

  const selecionada = options.find((o) => o.id === value) ?? null;

  const filtradas = useMemo(() => {
    const q = busca.trim().toLowerCase();
    if (!q) return options;
    return options.filter((o) => `${o.label} ${o.hint ?? ""}`.toLowerCase().includes(q));
  }, [options, busca]);

  // Fecha ao clicar fora.
  useEffect(() => {
    if (!aberto) return;
    function aoClicar(e: MouseEvent) {
      if (raizRef.current && !raizRef.current.contains(e.target as Node)) setAberto(false);
    }
    document.addEventListener("mousedown", aoClicar);
    return () => document.removeEventListener("mousedown", aoClicar);
  }, [aberto]);

  // Ao abrir, foca a busca e reinicia o destaque.
  useEffect(() => {
    if (aberto) {
      setDestaque(0);
      const t = setTimeout(() => buscaRef.current?.focus(), 10);
      return () => clearTimeout(t);
    }
    setBusca("");
  }, [aberto]);

  function escolher(id: number | "") {
    onChange(id);
    setAberto(false);
  }

  function aoTeclar(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setDestaque((d) => Math.min(d + 1, filtradas.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setDestaque((d) => Math.max(d - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const alvo = filtradas[destaque];
      if (alvo) escolher(alvo.id);
    } else if (e.key === "Escape") {
      setAberto(false);
    }
  }

  return (
    <div ref={raizRef} className={cn("relative", className)}>
      <button
        type="button"
        disabled={disabled}
        onClick={() => setAberto((a) => !a)}
        className={cn(
          "input flex w-full items-center justify-between gap-2 text-left",
          disabled && "cursor-not-allowed bg-surface-muted text-fg-subtle",
          !selecionada && "text-fg-subtle"
        )}
      >
        <span className="truncate">
          {selecionada ? (
            <>
              {selecionada.label}
              {selecionada.hint && (
                <span className="ml-2 text-xs text-fg-subtle">{selecionada.hint}</span>
              )}
            </>
          ) : (
            placeholder
          )}
        </span>
        <span className="flex shrink-0 items-center gap-1">
          {permiteLimpar && selecionada && !disabled && (
            <span
              role="button"
              tabIndex={-1}
              aria-label="Limpar"
              onClick={(e) => {
                e.stopPropagation();
                escolher("");
              }}
              className="rounded p-0.5 text-fg-subtle hover:bg-surface-muted hover:text-fg"
            >
              <X className="h-3.5 w-3.5" />
            </span>
          )}
          <ChevronDown className="h-4 w-4 text-fg-subtle" />
        </span>
      </button>

      {aberto && (
        <div className="absolute z-30 mt-1 w-full overflow-hidden rounded-lg border border-border bg-surface shadow-lg">
          <div className="relative border-b border-border">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-fg-subtle" />
            <input
              ref={buscaRef}
              value={busca}
              onChange={(e) => {
                setBusca(e.target.value);
                setDestaque(0);
              }}
              onKeyDown={aoTeclar}
              placeholder="Digite para buscar…"
              className="w-full bg-transparent py-2 pl-9 pr-3 text-sm text-fg outline-none placeholder:text-fg-subtle"
            />
          </div>

          <ul className="max-h-64 overflow-y-auto py-1">
            {permiteLimpar && !busca && (
              <li>
                <button
                  type="button"
                  onClick={() => escolher("")}
                  className="flex w-full items-center px-3 py-2 text-left text-sm text-fg-muted hover:bg-surface-muted"
                >
                  {limparLabel}
                </button>
              </li>
            )}
            {filtradas.length === 0 ? (
              <li className="px-3 py-6 text-center text-sm text-fg-subtle">{emptyText}</li>
            ) : (
              filtradas.map((o, i) => (
                <li key={o.id}>
                  <button
                    type="button"
                    onMouseEnter={() => setDestaque(i)}
                    onClick={() => escolher(o.id)}
                    className={cn(
                      "flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm",
                      i === destaque ? "bg-surface-muted text-fg" : "text-fg-muted"
                    )}
                  >
                    <span className="min-w-0">
                      <span className="block truncate font-medium text-fg">{o.label}</span>
                      {o.hint && <span className="block truncate text-xs text-fg-subtle">{o.hint}</span>}
                    </span>
                    {o.id === value && <Check className="h-4 w-4 shrink-0 text-accent" />}
                  </button>
                </li>
              ))
            )}
          </ul>
        </div>
      )}
    </div>
  );
}
