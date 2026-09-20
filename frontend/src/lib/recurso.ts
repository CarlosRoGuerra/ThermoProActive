"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import { interpretarFalha, registrarFalha, type Falha } from "./erros";
import type { Paginated } from "./types";

/**
 * Carregamento de dados da API com os estados que TODA tela precisa prever:
 * carregando · conteúdo · vazio · erro · sem permissão.
 *
 * Antes, cada página fazia `api(...).then(setData).finally(() => setLoading(false))`:
 * quando a chamada falhava, o `then` não rodava, ninguém pegava a exceção e a
 * tela ficava eternamente vazia sem explicar nada. Este hook fecha esse buraco
 * em um lugar só, e cancela a requisição quando o componente desmonta.
 */

export type EstadoRecurso = "carregando" | "ok" | "erro";

export type Recurso<T> = {
  dados: T | null;
  falha: Falha | null;
  carregando: boolean;
  estado: EstadoRecurso;
  /** Refaz a busca (usado pelo botão "Tentar novamente" e após mutações). */
  recarregar: () => void;
  /** Atualização otimista local, sem ir à rede (ex.: remover uma linha). */
  definirDados: (atualizar: T | null | ((atual: T | null) => T | null)) => void;
};

/**
 * @param caminho Rota da API (ex.: `/clientes/?page=1`). Passe `null` para não
 *   buscar ainda — é o caso de telas que dependem de um cliente ativo.
 * @param contexto Nome do carregamento no log de falhas (não aparece na tela).
 */
export function useRecurso<T>(caminho: string | null, contexto = "carregamento"): Recurso<T> {
  const [dados, setDados] = useState<T | null>(null);
  const [falha, setFalha] = useState<Falha | null>(null);
  const [carregando, setCarregando] = useState<boolean>(caminho !== null);
  const [tentativa, setTentativa] = useState(0);
  // Guarda o contexto em ref para não reexecutar o efeito quando só ele muda.
  const contextoRef = useRef(contexto);
  contextoRef.current = contexto;

  useEffect(() => {
    if (caminho === null) {
      setDados(null);
      setFalha(null);
      setCarregando(false);
      return;
    }

    const controle = new AbortController();
    let vivo = true;
    setCarregando(true);
    setFalha(null);

    api<T>(caminho, { signal: controle.signal })
      .then((resposta) => {
        if (!vivo) return;
        setDados(resposta);
      })
      .catch((e) => {
        if (!vivo || (e instanceof DOMException && e.name === "AbortError")) return;
        registrarFalha(`${contextoRef.current} — GET ${caminho}`, e);
        setFalha(interpretarFalha(e));
        setDados(null);
      })
      .finally(() => {
        if (vivo) setCarregando(false);
      });

    return () => {
      vivo = false;
      controle.abort();
    };
  }, [caminho, tentativa]);

  const recarregar = useCallback(() => setTentativa((n) => n + 1), []);

  const definirDados = useCallback(
    (atualizar: T | null | ((atual: T | null) => T | null)) => {
      setDados((atual) =>
        typeof atualizar === "function" ? (atualizar as (a: T | null) => T | null)(atual) : atualizar
      );
    },
    []
  );

  const estado: EstadoRecurso = carregando ? "carregando" : falha ? "erro" : "ok";

  return { dados, falha, carregando, estado, recarregar, definirDados };
}

/**
 * Mesma coisa para endpoints paginados do DRF (`{ count, results }`).
 * Devolve `itens` sempre como array — a tela nunca precisa checar `null`.
 */
export function useLista<T>(caminho: string | null, contexto = "listagem") {
  const recurso = useRecurso<Paginated<T>>(caminho, contexto);
  return {
    ...recurso,
    itens: recurso.dados?.results ?? [],
    total: recurso.dados?.count ?? 0,
    temMaisPaginas: !!recurso.dados?.next,
    /** Remove um item da lista em memória, depois de um DELETE bem-sucedido. */
    removerItem: (predicado: (item: T) => boolean) =>
      recurso.definirDados((atual) =>
        atual ? { ...atual, results: atual.results.filter((i) => !predicado(i)), count: Math.max(0, atual.count - 1) } : atual
      ),
  };
}

/**
 * Executa uma mutação (POST/PATCH/DELETE) controlando `enviando` e traduzindo a
 * falha. Devolve `true` no sucesso — a tela decide o que fazer depois.
 */
export function useMutacao(contexto = "operação") {
  const [enviando, setEnviando] = useState(false);
  const [falha, setFalha] = useState<Falha | null>(null);

  const executar = useCallback(
    async <R>(acao: () => Promise<R>): Promise<{ ok: true; dados: R } | { ok: false; falha: Falha }> => {
      setEnviando(true);
      setFalha(null);
      try {
        const dados = await acao();
        return { ok: true, dados };
      } catch (e) {
        registrarFalha(contexto, e);
        const f = interpretarFalha(e);
        setFalha(f);
        return { ok: false, falha: f };
      } finally {
        setEnviando(false);
      }
    },
    [contexto]
  );

  return { executar, enviando, falha, limparFalha: () => setFalha(null) };
}
