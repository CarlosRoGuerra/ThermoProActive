"use client";

import {
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { TriangleAlert, X, type LucideIcon } from "lucide-react";
import { cn, TOM_SUAVE, type Tom } from "./utils";
import { Button, IconButton, type ButtonVariant } from "./button";

const EASE = [0.22, 1, 0.36, 1] as const;

/* ==========================================================================
   Infra de overlay: portal + travas de acessibilidade.
   --------------------------------------------------------------------------
   Todo overlay do sistema (modal, drawer, confirmação) passa por aqui, então
   todos ganham de graça: Esc fecha, foco é aprisionado e devolvido, fundo não
   rola, leitor de tela anuncia diálogo e o conteúdo atrás fica inerte.
   ========================================================================== */

function usePortal() {
  const [pronto, setPronto] = useState(false);
  useEffect(() => setPronto(true), []);
  return pronto;
}

const SELETOR_FOCAVEL =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

function useArmadilhaDeFoco(aberto: boolean, refConteudo: React.RefObject<HTMLElement | null>, onFechar: () => void) {
  const focoAnterior = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!aberto) return;

    focoAnterior.current = document.activeElement as HTMLElement | null;

    // Trava a rolagem do fundo sem deslocar o layout (compensa a scrollbar).
    const larguraBarra = window.innerWidth - document.documentElement.clientWidth;
    const overflowAnterior = document.body.style.overflow;
    const paddingAnterior = document.body.style.paddingRight;
    document.body.style.overflow = "hidden";
    if (larguraBarra > 0) document.body.style.paddingRight = `${larguraBarra}px`;

    // Foca o primeiro elemento útil (ou o próprio painel, se não houver).
    const focarPrimeiro = () => {
      const alvo =
        refConteudo.current?.querySelector<HTMLElement>("[data-autofocus]") ??
        refConteudo.current?.querySelector<HTMLElement>(SELETOR_FOCAVEL) ??
        refConteudo.current;
      alvo?.focus?.();
    };
    const t = window.setTimeout(focarPrimeiro, 20);

    function aoTeclar(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.stopPropagation();
        onFechar();
        return;
      }
      if (e.key !== "Tab") return;
      const focaveis = Array.from(
        refConteudo.current?.querySelectorAll<HTMLElement>(SELETOR_FOCAVEL) ?? []
      ).filter((el) => el.offsetParent !== null);
      if (focaveis.length === 0) return;
      const primeiro = focaveis[0];
      const ultimo = focaveis[focaveis.length - 1];
      if (e.shiftKey && document.activeElement === primeiro) {
        e.preventDefault();
        ultimo.focus();
      } else if (!e.shiftKey && document.activeElement === ultimo) {
        e.preventDefault();
        primeiro.focus();
      }
    }

    document.addEventListener("keydown", aoTeclar, true);
    return () => {
      window.clearTimeout(t);
      document.removeEventListener("keydown", aoTeclar, true);
      document.body.style.overflow = overflowAnterior;
      document.body.style.paddingRight = paddingAnterior;
      // Devolve o foco a quem abriu — sem isto o teclado "se perde" ao fechar.
      focoAnterior.current?.focus?.();
    };
  }, [aberto, onFechar, refConteudo]);
}

/* ==========================================================================
   Modal — decisão ou formulário curto, no centro da tela.
   No celular vira uma folha que sobe de baixo (alcance do polegar).
   ========================================================================== */

export type ModalTamanho = "sm" | "md" | "lg" | "xl";

const MODAL_LARGURA: Record<ModalTamanho, string> = {
  sm: "sm:max-w-sm",
  md: "sm:max-w-lg",
  lg: "sm:max-w-2xl",
  xl: "sm:max-w-4xl",
};

export function Modal({
  aberto,
  onFechar,
  title,
  description,
  children,
  footer,
  tamanho = "md",
  /** Impede fechar clicando no fundo — para formulário com dados digitados. */
  travarFundo = false,
}: {
  aberto: boolean;
  onFechar: () => void;
  title: string;
  description?: string;
  children: ReactNode;
  footer?: ReactNode;
  tamanho?: ModalTamanho;
  travarFundo?: boolean;
}) {
  const pronto = usePortal();
  const refPainel = useRef<HTMLDivElement>(null);
  const idTitulo = useId();
  const idDesc = useId();
  const reduzir = useReducedMotion();
  useArmadilhaDeFoco(aberto, refPainel, onFechar);

  if (!pronto) return null;

  return createPortal(
    <AnimatePresence>
      {aberto && (
        <div className="fixed inset-0 z-modal flex items-end justify-center sm:items-center sm:p-4">
          <motion.div
            className="absolute inset-0 bg-overlay backdrop-blur-[2px]"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.16 }}
            onClick={travarFundo ? undefined : onFechar}
            aria-hidden="true"
          />
          <motion.div
            ref={refPainel}
            role="dialog"
            aria-modal="true"
            aria-labelledby={idTitulo}
            aria-describedby={description ? idDesc : undefined}
            tabIndex={-1}
            initial={reduzir ? { opacity: 0 } : { opacity: 0, y: 24, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={reduzir ? { opacity: 0 } : { opacity: 0, y: 12, scale: 0.99 }}
            transition={{ duration: 0.22, ease: EASE }}
            className={cn(
              "relative flex max-h-[92dvh] w-full flex-col overflow-hidden rounded-t-2xl border border-border bg-surface shadow-xl",
              "sm:rounded-2xl",
              MODAL_LARGURA[tamanho]
            )}
          >
            <header className="flex items-start justify-between gap-4 border-b border-border px-5 py-4">
              <div className="min-w-0">
                <h2 id={idTitulo} className="text-base font-semibold text-fg">
                  {title}
                </h2>
                {description && (
                  <p id={idDesc} className="mt-0.5 text-sm text-fg-muted">
                    {description}
                  </p>
                )}
              </div>
              <IconButton icon={X} label="Fechar" onClick={onFechar} size="sm" />
            </header>

            <div className="flex-1 overflow-y-auto px-5 py-4">{children}</div>

            {footer && (
              <footer className="flex flex-wrap items-center justify-end gap-2 border-t border-border bg-surface-muted/40 px-5 py-3.5">
                {footer}
              </footer>
            )}
          </motion.div>
        </div>
      )}
    </AnimatePresence>,
    document.body
  );
}

/* ==========================================================================
   Drawer — painel lateral para contexto auxiliar (detalhe, filtros).
   ========================================================================== */

export function Drawer({
  aberto,
  onFechar,
  title,
  description,
  children,
  footer,
  lado = "direita",
  largura = "md",
}: {
  aberto: boolean;
  onFechar: () => void;
  title: string;
  description?: string;
  children: ReactNode;
  footer?: ReactNode;
  lado?: "direita" | "esquerda";
  largura?: "sm" | "md" | "lg";
}) {
  const pronto = usePortal();
  const refPainel = useRef<HTMLDivElement>(null);
  const idTitulo = useId();
  const reduzir = useReducedMotion();
  useArmadilhaDeFoco(aberto, refPainel, onFechar);

  if (!pronto) return null;

  const larguras = { sm: "sm:max-w-sm", md: "sm:max-w-md", lg: "sm:max-w-xl" };
  const deslocamento = lado === "direita" ? 420 : -420;

  return createPortal(
    <AnimatePresence>
      {aberto && (
        <div className="fixed inset-0 z-drawer">
          <motion.div
            className="absolute inset-0 bg-overlay backdrop-blur-[2px]"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.16 }}
            onClick={onFechar}
            aria-hidden="true"
          />
          <motion.aside
            ref={refPainel}
            role="dialog"
            aria-modal="true"
            aria-labelledby={idTitulo}
            tabIndex={-1}
            initial={reduzir ? { opacity: 0 } : { x: deslocamento }}
            animate={reduzir ? { opacity: 1 } : { x: 0 }}
            exit={reduzir ? { opacity: 0 } : { x: deslocamento }}
            transition={{ duration: 0.26, ease: EASE }}
            className={cn(
              "absolute inset-y-0 flex w-full flex-col border-border bg-surface shadow-xl",
              larguras[largura],
              lado === "direita" ? "right-0 border-l" : "left-0 border-r"
            )}
          >
            <header className="flex items-start justify-between gap-4 border-b border-border px-5 py-4">
              <div className="min-w-0">
                <h2 id={idTitulo} className="text-base font-semibold text-fg">
                  {title}
                </h2>
                {description && <p className="mt-0.5 text-sm text-fg-muted">{description}</p>}
              </div>
              <IconButton icon={X} label="Fechar" onClick={onFechar} size="sm" />
            </header>
            <div className="flex-1 overflow-y-auto px-5 py-4">{children}</div>
            {footer && (
              <footer className="flex flex-wrap items-center justify-end gap-2 border-t border-border px-5 py-3.5">
                {footer}
              </footer>
            )}
          </motion.aside>
        </div>
      )}
    </AnimatePresence>,
    document.body
  );
}

/* ==========================================================================
   ConfirmDialog — substitui o `window.confirm()`.
   --------------------------------------------------------------------------
   O confirm nativo não diz O QUE será apagado, não tem estado de envio, não
   segue o tema e trava a aba. Este diz o nome do registro, avisa quando a ação
   não tem volta e mostra o progresso.
   ========================================================================== */

export function ConfirmDialog({
  aberto,
  onFechar,
  onConfirmar,
  title,
  mensagem,
  detalhe,
  confirmarLabel = "Confirmar",
  cancelarLabel = "Cancelar",
  tom = "danger",
  irreversivel = false,
  enviando = false,
  icon,
}: {
  aberto: boolean;
  onFechar: () => void;
  onConfirmar: () => void | Promise<void>;
  title: string;
  /** O que exatamente vai acontecer, com o nome do registro. */
  mensagem: ReactNode;
  /** Consequência lateral relevante ("as medições vinculadas também somem"). */
  detalhe?: ReactNode;
  confirmarLabel?: string;
  cancelarLabel?: string;
  tom?: Extract<Tom, "danger" | "warning" | "primary">;
  irreversivel?: boolean;
  enviando?: boolean;
  icon?: LucideIcon;
}) {
  const Icone = icon ?? TriangleAlert;
  const variante: ButtonVariant = tom === "danger" ? "destructive" : "primary";

  return (
    <Modal
      aberto={aberto}
      onFechar={enviando ? () => {} : onFechar}
      title={title}
      tamanho="sm"
      travarFundo={enviando}
      footer={
        <>
          <Button variant="secondary" size="sm" onClick={onFechar} disabled={enviando}>
            {cancelarLabel}
          </Button>
          <Button variant={variante} size="sm" loading={enviando} onClick={() => void onConfirmar()} data-autofocus>
            {confirmarLabel}
          </Button>
        </>
      }
    >
      <div className="flex gap-3.5">
        <div
          className={cn(
            "flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ring-1 ring-inset",
            TOM_SUAVE[tom]
          )}
        >
          <Icone className="h-5 w-5" aria-hidden="true" />
        </div>
        <div className="min-w-0 space-y-2 text-sm">
          <div className="text-fg">{mensagem}</div>
          {detalhe && <div className="text-fg-muted">{detalhe}</div>}
          {irreversivel && (
            <p className="text-xs font-medium text-danger-fg">Esta ação não pode ser desfeita.</p>
          )}
        </div>
      </div>
    </Modal>
  );
}

/**
 * Estado pronto para confirmações: guarda o alvo e o envio.
 *
 *   const remocao = useConfirmacao<Cliente>();
 *   <Button onClick={() => remocao.pedir(cliente)} />
 *   <ConfirmDialog aberto={!!remocao.alvo} ... onConfirmar={() => remocao.executar(apagar)} />
 */
export function useConfirmacao<T>() {
  const [alvo, setAlvo] = useState<T | null>(null);
  const [enviando, setEnviando] = useState(false);

  const executar = useCallback(
    async (acao: (alvo: T) => Promise<unknown>) => {
      if (!alvo) return;
      setEnviando(true);
      try {
        await acao(alvo);
        setAlvo(null);
      } finally {
        setEnviando(false);
      }
    },
    [alvo]
  );

  return {
    alvo,
    enviando,
    pedir: (a: T) => setAlvo(a),
    cancelar: () => setAlvo(null),
    executar,
  };
}

/* ==========================================================================
   DropdownMenu — ações secundárias de uma linha/objeto.
   Evita "dez botões visíveis por linha" nas tabelas.
   ========================================================================== */

export type ItemMenu = {
  label: string;
  onClick?: () => void;
  href?: string;
  icon?: LucideIcon;
  /** Vermelho + separador acima: ações destrutivas ficam isoladas no fim. */
  destrutivo?: boolean;
  disabled?: boolean;
  /** Explica por que está desabilitado (nível de acesso, estado do registro). */
  motivoDesabilitado?: string;
};

export function DropdownMenu({
  trigger,
  itens,
  label = "Mais ações",
  alinhamento = "direita",
  direcao = "baixo",
}: {
  trigger: ReactNode;
  itens: ItemMenu[];
  label?: string;
  alinhamento?: "direita" | "esquerda";
  /**
   * Para onde o painel abre. `cima` é necessário quando o gatilho mora no
   * rodapé da sidebar: ali `top-full` joga o menu abaixo da dobra e o
   * `overflow-hidden` do AppShell o recorta — o menu some sem deixar rastro.
   */
  direcao?: "baixo" | "cima";
}) {
  const [aberto, setAberto] = useState(false);
  const refRaiz = useRef<HTMLDivElement>(null);
  const refLista = useRef<HTMLDivElement>(null);
  const idMenu = useId();

  useEffect(() => {
    if (!aberto) return;
    function aoClicarFora(e: MouseEvent) {
      if (refRaiz.current && !refRaiz.current.contains(e.target as Node)) setAberto(false);
    }
    function aoTeclar(e: KeyboardEvent) {
      if (e.key === "Escape") {
        setAberto(false);
        return;
      }
      if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
      e.preventDefault();
      const opcoes = Array.from(
        refLista.current?.querySelectorAll<HTMLElement>('[role="menuitem"]:not([aria-disabled="true"])') ?? []
      );
      if (!opcoes.length) return;
      const atual = opcoes.indexOf(document.activeElement as HTMLElement);
      const proximo =
        e.key === "ArrowDown"
          ? (atual + 1) % opcoes.length
          : (atual - 1 + opcoes.length) % opcoes.length;
      opcoes[proximo < 0 ? 0 : proximo].focus();
    }
    document.addEventListener("mousedown", aoClicarFora);
    document.addEventListener("keydown", aoTeclar);
    return () => {
      document.removeEventListener("mousedown", aoClicarFora);
      document.removeEventListener("keydown", aoTeclar);
    };
  }, [aberto]);

  const visiveis = itens.filter(Boolean);
  if (visiveis.length === 0) return null;

  return (
    <div ref={refRaiz} className="relative inline-flex">
      <span
        onClick={() => setAberto((v) => !v)}
        role="button"
        tabIndex={0}
        aria-haspopup="menu"
        aria-expanded={aberto}
        aria-controls={aberto ? idMenu : undefined}
        aria-label={label}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            setAberto((v) => !v);
          }
        }}
        className="inline-flex"
      >
        {trigger}
      </span>

      <AnimatePresence>
        {aberto && (
          <motion.div
            ref={refLista}
            id={idMenu}
            role="menu"
            aria-label={label}
            initial={{ opacity: 0, y: direcao === "cima" ? 4 : -4, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: direcao === "cima" ? 4 : -4, scale: 0.98 }}
            transition={{ duration: 0.14, ease: EASE }}
            className={cn(
              "absolute z-dropdown min-w-52 overflow-hidden rounded-xl border border-border bg-surface-raised p-1 shadow-lg",
              direcao === "cima" ? "bottom-full mb-1" : "top-full mt-1",
              alinhamento === "direita" ? "right-0" : "left-0"
            )}
          >
            {visiveis.map((item, i) => {
              const anterior = visiveis[i - 1];
              const precisaSeparador = item.destrutivo && anterior && !anterior.destrutivo;
              const classe = cn(
                "flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-sm transition-colors",
                item.disabled
                  ? "cursor-not-allowed text-fg-subtle"
                  : item.destrutivo
                  ? "text-danger-fg hover:bg-danger-subtle"
                  : "text-fg-muted hover:bg-surface-muted hover:text-fg"
              );
              const conteudo = (
                <>
                  {item.icon && <item.icon className="h-4 w-4 shrink-0" aria-hidden="true" />}
                  <span className="flex-1 truncate">{item.label}</span>
                </>
              );

              return (
                <div key={item.label}>
                  {precisaSeparador && <div className="my-1 h-px bg-border" role="separator" />}
                  {item.href && !item.disabled ? (
                    <a
                      role="menuitem"
                      href={item.href}
                      className={classe}
                      onClick={() => setAberto(false)}
                    >
                      {conteudo}
                    </a>
                  ) : (
                    <button
                      role="menuitem"
                      type="button"
                      aria-disabled={item.disabled || undefined}
                      title={item.disabled ? item.motivoDesabilitado : undefined}
                      onClick={() => {
                        if (item.disabled) return;
                        setAberto(false);
                        item.onClick?.();
                      }}
                      className={classe}
                    >
                      {conteudo}
                    </button>
                  )}
                </div>
              );
            })}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/* ==========================================================================
   Tooltip — só para nomear ícone ou dar unidade. Nunca para informação
   essencial (não existe em toque nem em leitor de tela por padrão).
   ========================================================================== */

export function Tooltip({
  texto,
  children,
  lado = "cima",
}: {
  texto: string;
  children: ReactNode;
  lado?: "cima" | "baixo";
}) {
  const [visivel, setVisivel] = useState(false);
  const id = useId();
  return (
    <span
      className="relative inline-flex"
      onMouseEnter={() => setVisivel(true)}
      onMouseLeave={() => setVisivel(false)}
      onFocus={() => setVisivel(true)}
      onBlur={() => setVisivel(false)}
    >
      <span aria-describedby={visivel ? id : undefined} className="inline-flex">
        {children}
      </span>
      <AnimatePresence>
        {visivel && (
          <motion.span
            id={id}
            role="tooltip"
            initial={{ opacity: 0, y: lado === "cima" ? 4 : -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.12 }}
            className={cn(
              "pointer-events-none absolute left-1/2 z-tooltip w-max max-w-64 -translate-x-1/2 rounded-lg bg-chrome px-2.5 py-1.5 text-xs font-medium text-chrome-fg shadow-lg",
              lado === "cima" ? "bottom-full mb-1.5" : "top-full mt-1.5"
            )}
          >
            {texto}
          </motion.span>
        )}
      </AnimatePresence>
    </span>
  );
}
