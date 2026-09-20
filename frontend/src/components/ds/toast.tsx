"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion } from "framer-motion";
import { CircleAlert, CircleCheck, Info, TriangleAlert, X, type LucideIcon } from "lucide-react";
import { cn, type Tom } from "./utils";
import { mensagemDeErro } from "@/lib/erros";

/* ==========================================================================
   Toast — confirmação efêmera de uma ação que o usuário acabou de fazer.
   --------------------------------------------------------------------------
   Substitui o `alert()` e as mensagens que ficavam empilhadas dentro de um Card
   no meio da tela. Regras:
     • some sozinho (sucesso/info), fica até fechar (erro) — quem errou precisa ler;
     • máximo 3 na tela: fila, não pilha infinita;
     • anunciado por leitor de tela via região aria-live;
     • posição: canto inferior direito no desktop, topo no celular (onde o
       polegar não cobre e não briga com a barra de ações fixa).
   ========================================================================== */

type Tipo = "sucesso" | "erro" | "aviso" | "info";

type Toast = {
  id: number;
  tipo: Tipo;
  titulo: string;
  descricao?: string;
  /** Ação de desfazer / ver detalhe. */
  acao?: { label: string; onClick: () => void };
  duracao: number;
};

const ICONE: Record<Tipo, LucideIcon> = {
  sucesso: CircleCheck,
  erro: CircleAlert,
  aviso: TriangleAlert,
  info: Info,
};

const TOM: Record<Tipo, Tom> = {
  sucesso: "success",
  erro: "danger",
  aviso: "warning",
  info: "info",
};

const BARRA: Record<Tipo, string> = {
  sucesso: "bg-success",
  erro: "bg-danger",
  aviso: "bg-warning",
  info: "bg-info",
};

const COR_ICONE: Record<Tipo, string> = {
  sucesso: "text-success",
  erro: "text-danger",
  aviso: "text-warning",
  info: "text-info",
};

type Opcoes = { descricao?: string; acao?: Toast["acao"]; duracao?: number };

type ContextoToast = {
  sucesso: (titulo: string, opcoes?: Opcoes) => void;
  erro: (titulo: string, opcoes?: Opcoes) => void;
  aviso: (titulo: string, opcoes?: Opcoes) => void;
  info: (titulo: string, opcoes?: Opcoes) => void;
  /** Atalho: recebe a exceção e mostra a frase humana correspondente. */
  falha: (e: unknown, padrao?: string) => void;
};

const Ctx = createContext<ContextoToast | null>(null);
const MAXIMO = 3;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [montado, setMontado] = useState(false);
  const proximoId = useRef(1);

  useEffect(() => setMontado(true), []);

  const remover = useCallback((id: number) => {
    setToasts((atuais) => atuais.filter((t) => t.id !== id));
  }, []);

  const adicionar = useCallback((tipo: Tipo, titulo: string, opcoes?: Opcoes) => {
    const id = proximoId.current++;
    // Erro não desaparece sozinho: o usuário precisa poder ler e agir.
    const duracao = opcoes?.duracao ?? (tipo === "erro" ? 0 : 4500);
    setToasts((atuais) => [
      ...atuais.slice(-(MAXIMO - 1)),
      { id, tipo, titulo, descricao: opcoes?.descricao, acao: opcoes?.acao, duracao },
    ]);
  }, []);

  const valor = useMemo<ContextoToast>(
    () => ({
      sucesso: (t, o) => adicionar("sucesso", t, o),
      erro: (t, o) => adicionar("erro", t, o),
      aviso: (t, o) => adicionar("aviso", t, o),
      info: (t, o) => adicionar("info", t, o),
      falha: (e, padrao) => adicionar("erro", mensagemDeErro(e, padrao)),
    }),
    [adicionar]
  );

  return (
    <Ctx.Provider value={valor}>
      {children}
      {montado &&
        createPortal(
          <div
            // `polite` para não interromper o que o leitor de tela está falando.
            aria-live="polite"
            aria-atomic="false"
            className="pointer-events-none fixed inset-x-0 top-0 z-toast flex flex-col items-center gap-2 p-4 sm:inset-x-auto sm:bottom-0 sm:right-0 sm:top-auto sm:items-end"
          >
            <AnimatePresence initial={false}>
              {toasts.map((t) => (
                <ItemToast key={t.id} toast={t} onFechar={() => remover(t.id)} />
              ))}
            </AnimatePresence>
          </div>,
          document.body
        )}
    </Ctx.Provider>
  );
}

function ItemToast({ toast, onFechar }: { toast: Toast; onFechar: () => void }) {
  const Icone = ICONE[toast.tipo];
  const [pausado, setPausado] = useState(false);

  useEffect(() => {
    if (!toast.duracao || pausado) return;
    const t = window.setTimeout(onFechar, toast.duracao);
    return () => window.clearTimeout(t);
  }, [toast.duracao, pausado, onFechar]);

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: -16, scale: 0.97 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, x: 24, scale: 0.97 }}
      transition={{ duration: 0.2, ease: [0.22, 1, 0.36, 1] }}
      onMouseEnter={() => setPausado(true)}
      onMouseLeave={() => setPausado(false)}
      role={toast.tipo === "erro" ? "alert" : "status"}
      className="pointer-events-auto flex w-full max-w-sm overflow-hidden rounded-xl border border-border bg-surface-raised shadow-lg"
    >
      {/* Faixa lateral: reforça o tipo sem depender só da cor do ícone. */}
      <span className={cn("w-1 shrink-0", BARRA[toast.tipo])} aria-hidden="true" />
      <div className="flex flex-1 items-start gap-3 p-3.5">
        <Icone className={cn("mt-0.5 h-4.5 w-4.5 shrink-0", COR_ICONE[toast.tipo])} aria-hidden="true" />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-fg">{toast.titulo}</p>
          {toast.descricao && <p className="mt-0.5 text-xs text-fg-muted">{toast.descricao}</p>}
          {toast.acao && (
            <button
              type="button"
              onClick={() => {
                toast.acao?.onClick();
                onFechar();
              }}
              className="mt-2 text-xs font-semibold text-primary underline-offset-2 hover:underline"
            >
              {toast.acao.label}
            </button>
          )}
        </div>
        <button
          type="button"
          onClick={onFechar}
          aria-label="Fechar notificação"
          className="-mr-1 -mt-1 shrink-0 rounded-md p-1 text-fg-subtle transition-colors hover:bg-surface-muted hover:text-fg"
        >
          <X className="h-3.5 w-3.5" aria-hidden="true" />
        </button>
      </div>
    </motion.div>
  );
}

/**
 * Avisos efêmeros. Fora do ToastProvider devolve um objeto silencioso em vez de
 * quebrar — assim páginas de documento (impressão/carta) podem reusar
 * componentes sem montar o provider.
 */
export function useToast(): ContextoToast {
  const ctx = useContext(Ctx);
  return (
    ctx ?? {
      sucesso: () => {},
      erro: () => {},
      aviso: () => {},
      info: () => {},
      falha: () => {},
    }
  );
}
