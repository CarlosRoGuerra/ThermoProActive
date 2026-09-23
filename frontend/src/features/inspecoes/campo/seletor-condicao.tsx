"use client";

import type { ReactNode } from "react";
import { Check } from "lucide-react";
import { cn } from "@/components/ds";
import type { Condicao } from "@/lib/types";

/* ==========================================================================
   Seletor de condição — botões no lugar da lista suspensa.
   --------------------------------------------------------------------------
   A condição é O gesto da folha de campo: um por equipamento, dezenas por
   rota. No <select> isso custava três toques (abrir, rolar, escolher); aqui
   é um. O catálogo é curto (hoje 11 condições), então cabe inteiro na tela.

   Agrupado pelo que acontece depois do toque: "Sem ação" libera o
   equipamento e a folha segue para o próximo; "Exige análise" pede o
   registro do achado. A ordem de exibição é também a dos atalhos 1–9.

   A cor vem do catálogo e aparece só como bolinha de reforço: há condições
   cadastradas em preto e em amarelo puro, que sumiriam como texto num dos
   dois temas. Quem identifica a condição é a sigla.
   ========================================================================== */

type Grupo = { chave: "seguir" | "analise"; titulo: string; itens: Condicao[] };

export function gruposDeCondicao(condicoes: Condicao[]): Grupo[] {
  const grupos: Grupo[] = [
    { chave: "seguir", titulo: "Sem ação", itens: condicoes.filter((c) => !c.gera_acao) },
    { chave: "analise", titulo: "Exige análise", itens: condicoes.filter((c) => c.gera_acao) },
  ];
  return grupos.filter((g) => g.itens.length > 0);
}

/** Ordem de exibição — é ela que numera os atalhos (1 = primeiro botão). */
export function condicoesEmOrdem(condicoes: Condicao[]): Condicao[] {
  return gruposDeCondicao(condicoes).flatMap((g) => g.itens);
}

export function CorCondicao({ cor, className = "" }: { cor: string; className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={cn("inline-block h-2.5 w-2.5 shrink-0 rounded-full ring-1 ring-border-strong", className)}
      style={{ background: cor }}
    />
  );
}

export function Tecla({ children }: { children: ReactNode }) {
  return (
    <kbd className="inline-flex h-4 min-w-4 items-center justify-center rounded border border-border bg-surface-muted px-1 font-mono text-2xs leading-none text-fg-subtle">
      {children}
    </kbd>
  );
}

/** Escolha da condição de UM equipamento (painel da direita). */
export function SeletorCondicao({
  condicoes,
  valor,
  onEscolher,
  disabled = false,
}: {
  condicoes: Condicao[];
  valor: number | null;
  onEscolher: (c: Condicao) => void;
  disabled?: boolean;
}) {
  const atalho = new Map(condicoesEmOrdem(condicoes).map((c, i) => [c.id, i + 1]));

  return (
    <div role="radiogroup" aria-label="Condição do equipamento" className="space-y-3">
      {gruposDeCondicao(condicoes).map((g) => (
        <div key={g.chave}>
          <p className="mb-1.5 text-2xs font-medium uppercase tracking-wide text-fg-subtle">{g.titulo}</p>
          <div className="grid grid-cols-[repeat(auto-fill,minmax(8.5rem,1fr))] gap-2">
            {g.itens.map((c) => {
              const ativa = c.id === valor;
              const n = atalho.get(c.id) ?? 0;
              return (
                <button
                  key={c.id}
                  type="button"
                  role="radio"
                  aria-checked={ativa}
                  aria-keyshortcuts={n <= 9 ? String(n) : undefined}
                  disabled={disabled}
                  onClick={() => onEscolher(c)}
                  title={c.descricao || c.nome}
                  className={cn(
                    "relative flex min-h-[3.25rem] min-w-0 flex-col justify-center rounded-lg px-3 py-2 text-left",
                    "transition-[background-color,box-shadow,transform] duration-fast ease-out-soft",
                    "disabled:cursor-not-allowed",
                    ativa
                      ? "bg-primary-subtle ring-2 ring-inset ring-primary"
                      : "bg-surface ring-1 ring-inset ring-border hover:bg-surface-muted hover:ring-border-strong active:scale-[0.985] disabled:opacity-50"
                  )}
                >
                  <span className="flex items-center gap-1.5 pr-5">
                    <CorCondicao cor={c.cor} />
                    <span className="data truncate text-sm font-semibold text-fg">{c.sigla || c.nome}</span>
                  </span>
                  {c.sigla && <span className="mt-0.5 truncate text-2xs text-fg-muted">{c.nome}</span>}
                  <span className="absolute right-2 top-2 flex">
                    {ativa ? (
                      <Check className="h-3.5 w-3.5 text-primary" strokeWidth={3} aria-hidden="true" />
                    ) : (
                      n <= 9 &&
                      !disabled && (
                        <span className="hidden lg:flex">
                          <Tecla>{n}</Tecla>
                        </span>
                      )
                    )}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

/** Aplicar uma condição a VÁRIOS equipamentos (barra do lançamento em lote). */
export function AcoesCondicao({
  condicoes,
  onAplicar,
  disabled = false,
}: {
  condicoes: Condicao[];
  onAplicar: (c: Condicao) => void;
  disabled?: boolean;
}) {
  return (
    <div className="space-y-2">
      {gruposDeCondicao(condicoes).map((g) => (
        <div key={g.chave} role="group" aria-label={g.titulo}>
          <p className="mb-1 text-2xs font-medium uppercase tracking-wide text-fg-subtle">{g.titulo}</p>
          {/* Grade fixa: na coluna de 336px o flex-wrap deixava um botão sozinho por linha. */}
          <div className="grid grid-cols-3 gap-1.5">
            {g.itens.map((c) => (
              <button
                key={c.id}
                type="button"
                disabled={disabled}
                onClick={() => onAplicar(c)}
                title={c.nome}
                aria-label={`Marcar os selecionados como ${c.sigla ? `${c.sigla} — ${c.nome}` : c.nome}`}
                className={cn(
                  "inline-flex h-9 min-w-0 items-center gap-1.5 rounded-md bg-surface px-2.5 text-xs font-semibold text-fg",
                  "ring-1 ring-inset ring-border transition-colors duration-fast",
                  "hover:bg-surface-muted hover:ring-border-strong active:scale-[0.985]",
                  "disabled:pointer-events-none disabled:opacity-50"
                )}
              >
                <CorCondicao cor={c.cor} className="h-2 w-2" />
                <span className="data truncate">{c.sigla || c.nome}</span>
              </button>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
