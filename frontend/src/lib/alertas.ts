"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import { useAuth } from "./auth";

/**
 * Contador de alertas não lidos, compartilhado pela sidebar e pela topbar dos
 * dois portais.
 *
 * Antes isto vivia dentro do layout com um `setInterval(30s)` e `.catch(() => {})`
 * — ou seja, em conexão instável ficava tentando de 30 em 30 segundos para
 * sempre, sem sinal nenhum. Agora: para de insistir depois de falhas seguidas,
 * pausa quando a aba está em segundo plano (economiza bateria em campo) e
 * recarrega ao voltar.
 */

const INTERVALO_MS = 60_000;
const MAX_FALHAS = 3;

export function useAlertas() {
  const { user } = useAuth();
  const [naoLidas, setNaoLidas] = useState(0);
  const [falhas, setFalhas] = useState(0);

  const carregar = useCallback(async () => {
    if (!user) return;
    try {
      const d = await api<{ nao_lidas: number }>("/notificacoes/resumo/");
      setNaoLidas(d.nao_lidas);
      setFalhas(0);
    } catch {
      setFalhas((n) => n + 1);
    }
  }, [user]);

  useEffect(() => {
    if (!user || falhas >= MAX_FALHAS) return;
    void carregar();

    const intervalo = window.setInterval(() => {
      if (document.visibilityState === "visible") void carregar();
    }, INTERVALO_MS);

    const aoVoltar = () => {
      if (document.visibilityState === "visible") void carregar();
    };
    document.addEventListener("visibilitychange", aoVoltar);

    return () => {
      window.clearInterval(intervalo);
      document.removeEventListener("visibilitychange", aoVoltar);
    };
    // `falhas` entra de propósito: ao estourar o limite, o efeito para de agendar.
  }, [user, carregar, falhas]);

  return { naoLidas, recarregar: carregar };
}
