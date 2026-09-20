"use client";

import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";
import { Check, LoaderCircle, type LucideIcon } from "lucide-react";
import { cn } from "./utils";

/* ==========================================================================
   Button
   --------------------------------------------------------------------------
   Variantes com intenção declarada, não decorativa:
     primary     → a ação principal da tela. Uma por tela.
     secondary   → ações alternativas de mesmo peso.
     ghost       → ação terciária dentro de listas e barras.
     subtle      → ação em fundo colorido/chrome.
     destructive → remove ou cancela de forma difícil de desfazer.
     link        → navegação disfarçada de texto.
   Altura mínima 36px (sm) e 40px (md) para respeitar alvo de toque
   (WCAG 2.2 — 2.5.8 Target Size, mínimo 24×24 com folga; usamos bem acima).
   ========================================================================== */

export type ButtonVariant =
  | "primary"
  | "secondary"
  | "ghost"
  | "subtle"
  | "destructive"
  | "link"
  /** Alias legado mantido para telas ainda não migradas. */
  | "danger";

export type ButtonSize = "xs" | "sm" | "md" | "lg";

const VARIANTES: Record<ButtonVariant, string> = {
  primary:
    "bg-primary text-primary-fg shadow-xs hover:bg-primary-hover active:bg-primary-active",
  secondary:
    "bg-surface text-fg ring-1 ring-inset ring-border hover:bg-surface-muted hover:ring-border-strong",
  ghost: "text-fg-muted hover:bg-surface-muted hover:text-fg",
  subtle: "bg-surface-muted text-fg hover:bg-border",
  destructive: "bg-danger text-white shadow-xs hover:brightness-110 active:brightness-95",
  danger: "bg-danger text-white shadow-xs hover:brightness-110 active:brightness-95",
  link: "text-primary underline-offset-4 hover:underline px-0",
};

const TAMANHOS: Record<ButtonSize, string> = {
  xs: "h-7 gap-1 px-2 text-2xs",
  sm: "h-9 gap-1.5 px-3 text-xs",
  md: "h-10 gap-2 px-4 text-sm",
  lg: "h-11 gap-2 px-5 text-base",
};

const ICONE: Record<ButtonSize, string> = {
  xs: "h-3.5 w-3.5",
  sm: "h-4 w-4",
  md: "h-4 w-4",
  lg: "h-[1.125rem] w-[1.125rem]",
};

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
  /** Troca o conteúdo por um spinner e bloqueia o clique. */
  loading?: boolean;
  /** Confirmação momentânea depois de salvar. */
  success?: boolean;
  icon?: LucideIcon;
  /** Ícone à direita (ex.: seta de "avançar"). */
  iconRight?: LucideIcon;
  /** Ocupa toda a largura disponível (formulários, mobile). */
  block?: boolean;
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  {
    children,
    variant = "primary",
    size = "md",
    loading = false,
    success = false,
    icon: Icon,
    iconRight: IconRight,
    block = false,
    className = "",
    disabled,
    type = "button",
    ...props
  },
  ref
) {
  const tamanhoIcone = ICONE[size];
  return (
    <button
      ref={ref}
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cn(
        "relative inline-flex select-none items-center justify-center rounded-lg font-medium",
        "transition-[background-color,color,box-shadow,opacity] duration-fast ease-out-soft",
        "active:scale-[0.985] disabled:pointer-events-none disabled:opacity-50",
        VARIANTES[variant],
        TAMANHOS[size],
        block && "w-full",
        className
      )}
      {...props}
    >
      {/* O conteúdo permanece no fluxo (invisível) durante loading para que o
          botão não mude de largura e a página não "salte". */}
      <span
        className={cn(
          "inline-flex items-center",
          size === "xs" ? "gap-1" : "gap-2",
          (loading || success) && "invisible"
        )}
      >
        {Icon && <Icon className={cn(tamanhoIcone, "shrink-0")} aria-hidden="true" />}
        {children}
        {IconRight && <IconRight className={cn(tamanhoIcone, "shrink-0")} aria-hidden="true" />}
      </span>

      {loading && (
        <span className="absolute inset-0 inline-flex items-center justify-center">
          <LoaderCircle className={cn(tamanhoIcone, "animate-spin")} aria-hidden="true" />
          <span className="sr-only">Processando…</span>
        </span>
      )}
      {!loading && success && (
        <span className="absolute inset-0 inline-flex items-center justify-center">
          <Check className={tamanhoIcone} aria-hidden="true" />
          <span className="sr-only">Concluído</span>
        </span>
      )}
    </button>
  );
});

/* ==========================================================================
   IconButton — ação sem rótulo visível. `label` é OBRIGATÓRIO e vira
   aria-label + title: nenhum ícone solto fica sem nome acessível.
   ========================================================================== */

export type IconButtonProps = Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children"> & {
  icon: LucideIcon;
  label: string;
  variant?: Extract<ButtonVariant, "primary" | "secondary" | "ghost" | "subtle" | "destructive">;
  size?: Extract<ButtonSize, "xs" | "sm" | "md">;
  loading?: boolean;
  /** Usa os tokens de chrome (sidebar/topbar escuros). */
  onChrome?: boolean;
};

const ICON_BUTTON_TAMANHO: Record<"xs" | "sm" | "md", string> = {
  xs: "h-7 w-7",
  sm: "h-9 w-9",
  md: "h-10 w-10",
};

export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(function IconButton(
  {
    icon: Icon,
    label,
    variant = "ghost",
    size = "sm",
    loading = false,
    onChrome = false,
    className = "",
    disabled,
    type = "button",
    ...props
  },
  ref
) {
  return (
    <button
      ref={ref}
      type={type}
      aria-label={label}
      title={label}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-lg transition-colors duration-fast",
        "disabled:pointer-events-none disabled:opacity-50",
        onChrome
          ? "text-chrome-fg-muted hover:bg-chrome-muted hover:text-chrome-fg"
          : VARIANTES[variant],
        ICON_BUTTON_TAMANHO[size],
        className
      )}
      {...props}
    >
      {loading ? (
        <LoaderCircle className={cn(ICONE[size], "animate-spin")} aria-hidden="true" />
      ) : (
        <Icon className={ICONE[size]} aria-hidden="true" />
      )}
    </button>
  );
});

/** Agrupa botões relacionados numa peça só (ex.: densidade, visualização). */
export function ButtonGroup({
  children,
  className = "",
  "aria-label": ariaLabel,
}: {
  children: ReactNode;
  className?: string;
  "aria-label"?: string;
}) {
  return (
    <div
      role="group"
      aria-label={ariaLabel}
      className={cn(
        "inline-flex items-center gap-0.5 rounded-lg border border-border bg-surface p-0.5 shadow-xs",
        className
      )}
    >
      {children}
    </div>
  );
}
