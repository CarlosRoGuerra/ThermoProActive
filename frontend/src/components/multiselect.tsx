"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Check, ChevronDown, Search, X } from "lucide-react";
import { cn } from "./ui";
import type { Opcao } from "./combobox";

/**
 * Lista suspensa de múltipla escolha — mostra o NOME de cada item, permite
 * buscar e marca os escolhidos. Os selecionados aparecem como etiquetas
 * removíveis abaixo do campo.
 */
export function MultiSelect({
  value,
  onChange,
  options,
  placeholder = "Selecione…",
  emptyText = "Nenhuma opção cadastrada.",
  className = "",
}: {
  value: number[];
  onChange: (ids: number[]) => void;
  options: Opcao[];
  placeholder?: string;
  emptyText?: string;
  className?: string;
}) {
  const [aberto, setAberto] = useState(false);
  const [busca, setBusca] = useState("");
  const raizRef = useRef<HTMLDivElement>(null);
  const buscaRef = useRef<HTMLInputElement>(null);

  const selecionadas = options.filter((o) => value.includes(o.id));

  const filtradas = useMemo(() => {
    const q = busca.trim().toLowerCase();
    if (!q) return options;
    return options.filter((o) => `${o.label} ${o.hint ?? ""}`.toLowerCase().includes(q));
  }, [options, busca]);

  useEffect(() => {
    if (!aberto) return;
    function aoClicar(e: MouseEvent) {
      if (raizRef.current && !raizRef.current.contains(e.target as Node)) setAberto(false);
    }
    document.addEventListener("mousedown", aoClicar);
    return () => document.removeEventListener("mousedown", aoClicar);
  }, [aberto]);

  useEffect(() => {
    if (aberto) {
      const t = setTimeout(() => buscaRef.current?.focus(), 10);
      return () => clearTimeout(t);
    }
    setBusca("");
  }, [aberto]);

  function alternar(id: number) {
    onChange(value.includes(id) ? value.filter((v) => v !== id) : [...value, id]);
  }

  return (
    <div ref={raizRef} className={cn("relative", className)}>
      <button
        type="button"
        onClick={() => setAberto((a) => !a)}
        className={cn(
          "input flex w-full items-center justify-between gap-2 text-left",
          selecionadas.length === 0 && "text-fg-subtle"
        )}
      >
        <span className="truncate">
          {selecionadas.length === 0
            ? placeholder
            : `${selecionadas.length} selecionada${selecionadas.length > 1 ? "s" : ""}`}
        </span>
        <ChevronDown className="h-4 w-4 shrink-0 text-fg-subtle" />
      </button>

      {aberto && (
        <div className="absolute z-30 mt-1 w-full overflow-hidden rounded-lg border border-border bg-surface shadow-lg">
          <div className="relative border-b border-border">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-fg-subtle" />
            <input
              ref={buscaRef}
              value={busca}
              onChange={(e) => setBusca(e.target.value)}
              placeholder="Digite para buscar…"
              className="w-full bg-transparent py-2 pl-9 pr-3 text-sm text-fg outline-none placeholder:text-fg-subtle"
            />
          </div>
          <ul className="max-h-64 overflow-y-auto py-1">
            {filtradas.length === 0 ? (
              <li className="px-3 py-6 text-center text-sm text-fg-subtle">{emptyText}</li>
            ) : (
              filtradas.map((o) => {
                const marcada = value.includes(o.id);
                return (
                  <li key={o.id}>
                    <button
                      type="button"
                      onClick={() => alternar(o.id)}
                      className={cn(
                        "flex w-full items-center gap-2.5 px-3 py-2 text-left text-sm hover:bg-surface-muted",
                        marcada ? "text-fg" : "text-fg-muted"
                      )}
                    >
                      <span
                        className={cn(
                          "flex h-4 w-4 shrink-0 items-center justify-center rounded border",
                          marcada ? "border-accent bg-accent text-accent-fg" : "border-border-strong"
                        )}
                      >
                        {marcada && <Check className="h-3 w-3" />}
                      </span>
                      <span className="min-w-0">
                        <span className="block truncate font-medium">{o.label}</span>
                        {o.hint && <span className="block truncate text-xs text-fg-subtle">{o.hint}</span>}
                      </span>
                    </button>
                  </li>
                );
              })
            )}
          </ul>
        </div>
      )}

      {/* Escolhidos: etiquetas removíveis, sempre pelo nome. */}
      {selecionadas.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {selecionadas.map((o) => (
            <span
              key={o.id}
              className="inline-flex items-center gap-1 rounded-full bg-accent-subtle px-2.5 py-1 text-xs font-medium text-accent-subtle-fg"
            >
              {o.label}
              <button
                type="button"
                onClick={() => alternar(o.id)}
                aria-label={`Remover ${o.label}`}
                className="rounded-full p-0.5 hover:bg-accent/20"
              >
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
