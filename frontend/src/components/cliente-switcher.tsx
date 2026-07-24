"use client";

import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Building2, Check, ChevronDown, Clock, Search, X } from "lucide-react";
import { useClienteAtivo, type ClienteAtivo } from "@/lib/cliente-ativo";
import { useClientes } from "@/lib/hierarquia";
import { cn } from "./ui";

/**
 * Seletor de cliente ativo (o "ambiente" de trabalho).
 * Um chip no topo mostra o cliente atual; clicar abre um painel lateral com
 * busca e a lista dos últimos clientes acessados — inspirado no fluxo de
 * "trocar de entidade" do sistema que o cliente usa como referência.
 */
export function ClienteSwitcher() {
  const { clienteAtivo, recentes, ativar, limpar } = useClienteAtivo();
  const { clientes } = useClientes();
  const [aberto, setAberto] = useState(false);
  const [busca, setBusca] = useState("");

  // Trava o scroll do fundo enquanto o painel está aberto.
  useEffect(() => {
    if (!aberto) return;
    setBusca("");
    const antes = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = antes;
    };
  }, [aberto]);

  const resultados = useMemo(() => {
    const q = busca.trim().toLowerCase();
    if (!q) return [];
    return clientes
      .filter((c) =>
        [c.nome, c.nome_fantasia, c.cnpj, c.cidade_uf]
          .map((v) => String(v ?? "").toLowerCase())
          .join(" ")
          .includes(q)
      )
      .slice(0, 20);
  }, [clientes, busca]);

  function escolher(c: {
    id: number;
    nome: string;
    nome_fantasia: string;
    logomarca?: string | null;
  }) {
    ativar({ id: c.id, nome: c.nome, nome_fantasia: c.nome_fantasia, logomarca: c.logomarca });
    setAberto(false);
  }

  const titulo = clienteAtivo
    ? clienteAtivo.nome_fantasia || clienteAtivo.nome
    : "Selecionar cliente";

  return (
    <>
      {/* Chip no topo */}
      <button
        onClick={() => setAberto(true)}
        className={cn(
          "flex items-center gap-2 rounded-full border py-1 pl-1.5 pr-2.5 text-sm transition-colors",
          clienteAtivo
            ? "border-accent/30 bg-accent-subtle text-fg hover:bg-accent-subtle/70"
            : "border-dashed border-border-strong text-fg-muted hover:bg-surface-muted"
        )}
        title="Trocar de cliente"
      >
        <span className="flex h-6 w-6 shrink-0 items-center justify-center overflow-hidden rounded-full bg-surface">
          {clienteAtivo?.logomarca ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={clienteAtivo.logomarca} alt="" className="h-full w-full object-contain" />
          ) : (
            <Building2 className="h-3.5 w-3.5 text-accent" />
          )}
        </span>
        <span className="hidden max-w-[160px] truncate font-medium sm:inline">{titulo}</span>
        <ChevronDown className="h-3.5 w-3.5 shrink-0 opacity-70" />
      </button>

      {/* Painel lateral */}
      <AnimatePresence>
        {aberto && (
          <>
            <motion.div
              className="fixed inset-0 z-50 bg-fg/30 backdrop-blur-sm"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setAberto(false)}
            />
            <motion.aside
              className="fixed inset-y-0 right-0 z-50 flex w-[340px] max-w-[90vw] flex-col border-l border-border bg-surface shadow-xl"
              initial={{ x: 360 }}
              animate={{ x: 0 }}
              exit={{ x: 360 }}
              transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
            >
              <div className="flex items-center justify-between border-b border-border px-4 py-3.5">
                <h2 className="text-sm font-semibold text-fg">Trocar de cliente</h2>
                <button
                  onClick={() => setAberto(false)}
                  aria-label="Fechar"
                  className="rounded-md p-1 text-fg-subtle transition-colors hover:bg-surface-muted hover:text-fg"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              {/* Busca */}
              <div className="border-b border-border p-3">
                <div className="relative">
                  <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-fg-subtle" />
                  {/* eslint-disable-next-line jsx-a11y/no-autofocus */}
                  <input
                    autoFocus
                    value={busca}
                    onChange={(e) => setBusca(e.target.value)}
                    placeholder="Buscar por razão social, CNPJ, cidade…"
                    className="input pl-9"
                  />
                </div>
              </div>

              <div className="flex-1 overflow-y-auto p-3">
                {busca ? (
                  resultados.length === 0 ? (
                    <p className="px-1 py-6 text-center text-sm text-fg-subtle">
                      Nenhum cliente encontrado.
                    </p>
                  ) : (
                    <ul className="space-y-1">
                      {resultados.map((c) => (
                        <LinhaCliente
                          key={c.id}
                          cliente={c}
                          ativo={clienteAtivo?.id === c.id}
                          onClick={() => escolher(c)}
                        />
                      ))}
                    </ul>
                  )
                ) : (
                  <>
                    {clienteAtivo && (
                      <div className="mb-4">
                        <p className="mb-1.5 px-1 text-[11px] font-semibold uppercase tracking-wide text-fg-subtle">
                          Cliente ativo
                        </p>
                        <LinhaCliente
                          cliente={clienteAtivo}
                          ativo
                          onClick={() => setAberto(false)}
                        />
                        <button
                          onClick={() => {
                            limpar();
                            setAberto(false);
                          }}
                          className="mt-1 w-full rounded-lg px-3 py-1.5 text-left text-xs font-medium text-fg-muted transition-colors hover:bg-surface-muted hover:text-fg"
                        >
                          Sair do ambiente deste cliente
                        </button>
                      </div>
                    )}

                    <p className="mb-1.5 flex items-center gap-1.5 px-1 text-[11px] font-semibold uppercase tracking-wide text-fg-subtle">
                      <Clock className="h-3 w-3" /> Últimos acessados
                    </p>
                    {recentes.length === 0 ? (
                      <p className="px-1 py-4 text-sm text-fg-subtle">
                        Nenhum ainda. Use a busca acima para escolher um cliente.
                      </p>
                    ) : (
                      <ul className="space-y-1">
                        {recentes.map((c) => (
                          <LinhaCliente
                            key={c.id}
                            cliente={c}
                            ativo={clienteAtivo?.id === c.id}
                            onClick={() => escolher(c)}
                          />
                        ))}
                      </ul>
                    )}
                  </>
                )}
              </div>
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </>
  );
}

function LinhaCliente({
  cliente,
  ativo,
  onClick,
}: {
  cliente: { id: number; nome: string; nome_fantasia: string; cnpj?: string; logomarca?: string | null };
  ativo: boolean;
  onClick: () => void;
}) {
  return (
    <li>
      <button
        onClick={onClick}
        className={cn(
          "flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-left transition-colors",
          ativo ? "bg-accent-subtle" : "hover:bg-surface-muted"
        )}
      >
        <span className="flex h-8 w-8 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-surface-muted">
          {cliente.logomarca ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={cliente.logomarca} alt="" className="h-full w-full object-contain" />
          ) : (
            <Building2 className="h-4 w-4 text-fg-subtle" />
          )}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium text-fg">
            {cliente.nome_fantasia || cliente.nome}
          </span>
          <span className="block truncate text-xs text-fg-subtle">
            {cliente.nome_fantasia ? cliente.nome : cliente.cnpj || ""}
          </span>
        </span>
        {ativo && <Check className="h-4 w-4 shrink-0 text-accent" />}
      </button>
    </li>
  );
}

export type { ClienteAtivo };
