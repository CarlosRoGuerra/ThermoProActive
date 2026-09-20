"use client";

import { useEffect } from "react";
import Link from "next/link";
import { RotateCw } from "lucide-react";
import { Button, Card, Logo } from "@/components/ds";
import { registrarFalha } from "@/lib/erros";

/**
 * Último anteparo: erro não tratado em qualquer tela.
 *
 * O usuário lê uma frase em português e tem duas saídas (tentar de novo ou
 * voltar ao início). A mensagem técnica vai para o console, nunca para a tela —
 * `digest` é a chave que o suporte usa para achar o evento no log do servidor.
 */
export default function ErroGlobal({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    registrarFalha("erro não tratado na interface", error);
  }, [error]);

  return (
    <main className="flex min-h-[100dvh] items-center justify-center bg-bg px-4 py-10">
      <div className="w-full max-w-md">
        <div className="mb-6 flex justify-center">
          <Logo tamanho="lg" />
        </div>
        <Card>
          <h1 className="text-lg font-semibold text-fg">Algo não funcionou como esperado</h1>
          <p className="mt-1.5 text-sm text-fg-muted">
            A tela não conseguiu terminar de carregar. Tente novamente; se continuar, avise o suporte
            com o horário em que aconteceu.
          </p>
          <div className="mt-5 flex flex-wrap items-center gap-2">
            <Button size="sm" icon={RotateCw} onClick={reset}>
              Tentar novamente
            </Button>
            <Link href="/">
              <Button size="sm" variant="secondary">
                Voltar ao início
              </Button>
            </Link>
          </div>
          {error.digest && (
            <p className="mt-4 text-2xs text-fg-subtle">
              Código para o suporte: <span className="data">{error.digest}</span>
            </p>
          )}
        </Card>
      </div>
    </main>
  );
}
