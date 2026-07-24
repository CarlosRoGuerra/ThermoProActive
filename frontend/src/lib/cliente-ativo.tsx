"use client";

import { createContext, useContext, useEffect, useState, ReactNode } from "react";

/**
 * Cliente ativo — o "tomador de serviço" que o analista está atendendo.
 *
 * Ao ativar um cliente, o sistema passa a trabalhar dentro do ambiente dele:
 * as telas de dados operacionais já entram filtradas por esse cliente, e o
 * nome fantasia aparece na barra lateral para deixar claro onde se está.
 * A escolha fica salva no navegador entre sessões.
 */
export type ClienteAtivo = {
  id: number;
  nome: string;
  nome_fantasia: string;
  logomarca?: string | null;
};

interface ClienteAtivoContextValue {
  clienteAtivo: ClienteAtivo | null;
  ativar: (cliente: ClienteAtivo) => void;
  limpar: () => void;
}

const CHAVE = "tpa-cliente-ativo";
const Ctx = createContext<ClienteAtivoContextValue | null>(null);

export function ClienteAtivoProvider({ children }: { children: ReactNode }) {
  const [clienteAtivo, setClienteAtivo] = useState<ClienteAtivo | null>(null);

  // Recupera a escolha anterior ao montar (evita “piscar” sem cliente).
  useEffect(() => {
    try {
      const bruto = localStorage.getItem(CHAVE);
      if (bruto) setClienteAtivo(JSON.parse(bruto));
    } catch {
      /* localStorage indisponível — segue sem cliente ativo */
    }
  }, []);

  function ativar(cliente: ClienteAtivo) {
    setClienteAtivo(cliente);
    try {
      localStorage.setItem(CHAVE, JSON.stringify(cliente));
    } catch {
      /* sessão sem persistência — ainda funciona nesta aba */
    }
  }

  function limpar() {
    setClienteAtivo(null);
    try {
      localStorage.removeItem(CHAVE);
    } catch {
      /* ignore */
    }
  }

  return (
    <Ctx.Provider value={{ clienteAtivo, ativar, limpar }}>{children}</Ctx.Provider>
  );
}

export function useClienteAtivo() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useClienteAtivo deve ser usado dentro de ClienteAtivoProvider");
  return ctx;
}
