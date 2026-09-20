"use client";

import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { api } from "./api";
import { useAuth } from "./auth";

/**
 * Cliente ativo — o "tomador de serviço" que o analista está atendendo.
 *
 * Ao ativar um cliente, o sistema passa a trabalhar dentro do ambiente dele:
 * as telas de dados operacionais já entram filtradas por esse cliente, e o
 * nome fantasia aparece na barra lateral para deixar claro onde se está.
 * A escolha fica salva no navegador entre sessões.
 *
 * Usuário do Portal não escolhe nada: o cliente ativo É a própria empresa
 * dele, sempre — travado, sem trilho de "recentes" nem opção de trocar. É o
 * que deixa as MESMAS telas de cadastro (equipamentos, rotas) que a equipe
 * interna usa funcionarem também para o Master do cliente, sem duplicar
 * formulário: elas já leem tudo daqui, nunca direto do usuário logado.
 */
export type ClienteAtivo = {
  id: number;
  nome: string;
  nome_fantasia: string;
  logomarca?: string | null;
};

interface ClienteAtivoContextValue {
  clienteAtivo: ClienteAtivo | null;
  recentes: ClienteAtivo[];
  ativar: (cliente: ClienteAtivo) => void;
  limpar: () => void;
}

const CHAVE = "tpa-cliente-ativo";
const CHAVE_RECENTES = "tpa-clientes-recentes";
const MAX_RECENTES = 6;
const Ctx = createContext<ClienteAtivoContextValue | null>(null);

export function ClienteAtivoProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const [clienteAtivo, setClienteAtivo] = useState<ClienteAtivo | null>(null);
  const [recentes, setRecentes] = useState<ClienteAtivo[]>([]);

  // Portal: trava no cliente do próprio usuário — nunca lê nem grava o
  // "trilho de recentes" do lado interno.
  useEffect(() => {
    if (!user?.is_cliente) return;
    if (!user.cliente) {
      setClienteAtivo(null);
      return;
    }
    let vivo = true;
    api<ClienteAtivo>(`/clientes/${user.cliente}/`)
      .then((c) => {
        if (vivo) setClienteAtivo(c);
      })
      .catch(() => {
        if (vivo) setClienteAtivo(null);
      });
    return () => {
      vivo = false;
    };
  }, [user?.is_cliente, user?.cliente]);

  // Interno: recupera a escolha anterior e os últimos acessados ao montar.
  useEffect(() => {
    if (user?.is_cliente) return;
    try {
      const bruto = localStorage.getItem(CHAVE);
      if (bruto) setClienteAtivo(JSON.parse(bruto));
      const rec = localStorage.getItem(CHAVE_RECENTES);
      if (rec) setRecentes(JSON.parse(rec));
    } catch {
      /* localStorage indisponível — segue sem cliente ativo */
    }
  }, [user?.is_cliente]);

  function ativar(cliente: ClienteAtivo) {
    setClienteAtivo(cliente);
    // Recentes: move o escolhido para o topo, sem duplicar, com teto.
    setRecentes((atuais) => {
      const semEle = atuais.filter((c) => c.id !== cliente.id);
      const novos = [cliente, ...semEle].slice(0, MAX_RECENTES);
      try {
        localStorage.setItem(CHAVE_RECENTES, JSON.stringify(novos));
      } catch {
        /* ignore */
      }
      return novos;
    });
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
    <Ctx.Provider value={{ clienteAtivo, recentes, ativar, limpar }}>{children}</Ctx.Provider>
  );
}

export function useClienteAtivo() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useClienteAtivo deve ser usado dentro de ClienteAtivoProvider");
  return ctx;
}
