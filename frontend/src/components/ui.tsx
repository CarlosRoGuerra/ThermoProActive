"use client";

import {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
  useEffect,
  useState,
} from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Check, Loader2, Moon, Sun, type LucideIcon } from "lucide-react";
import type { Criticidade } from "@/lib/types";

export function cn(...parts: (string | false | null | undefined)[]) {
  return parts.filter(Boolean).join(" ");
}

/* ============================ Button ============================ */
type ButtonVariant = "primary" | "secondary" | "ghost" | "destructive" | "danger";
type ButtonSize = "sm" | "md";

const BUTTON_VARIANTS: Record<ButtonVariant, string> = {
  primary: "bg-accent text-accent-fg shadow-xs hover:bg-accent-hover",
  secondary: "bg-surface text-fg ring-1 ring-inset ring-border hover:bg-surface-muted",
  ghost: "text-fg-muted hover:bg-surface-muted hover:text-fg",
  destructive: "bg-danger text-white shadow-xs hover:brightness-95",
  danger: "bg-danger text-white shadow-xs hover:brightness-95",
};
const BUTTON_SIZES: Record<ButtonSize, string> = {
  sm: "h-8 gap-1.5 px-3 text-xs",
  md: "h-10 gap-2 px-4 text-sm",
};

export function Button({
  children,
  variant = "primary",
  size = "md",
  loading = false,
  success = false,
  icon: Icon,
  className = "",
  disabled,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  success?: boolean;
  icon?: LucideIcon;
}) {
  return (
    <button
      disabled={disabled || loading}
      className={cn(
        "inline-flex select-none items-center justify-center rounded-lg font-medium transition-[background-color,color,box-shadow,transform] duration-200 ease-out-soft",
        "active:scale-[0.98] focus-visible:shadow-focus focus-visible:outline-none",
        "disabled:pointer-events-none disabled:opacity-50",
        BUTTON_VARIANTS[variant],
        BUTTON_SIZES[size],
        className
      )}
      {...props}
    >
      <AnimatePresence mode="wait" initial={false}>
        {loading ? (
          <motion.span key="l" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <Loader2 className="h-4 w-4 animate-spin" />
          </motion.span>
        ) : success ? (
          <motion.span
            key="s"
            initial={{ scale: 0.4, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ type: "spring", stiffness: 500, damping: 18 }}
          >
            <Check className="h-4 w-4" />
          </motion.span>
        ) : (
          <motion.span
            key="c"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="inline-flex items-center gap-2"
          >
            {Icon && <Icon className="h-4 w-4" />}
            {children}
          </motion.span>
        )}
      </AnimatePresence>
    </button>
  );
}

/* ============================ Card ============================ */
export function Card({
  children,
  className = "",
  interactive = false,
  padding = true,
}: {
  children: ReactNode;
  className?: string;
  interactive?: boolean;
  padding?: boolean;
}) {
  return (
    <div
      className={cn(
        "rounded-xl border border-border bg-surface shadow-xs",
        padding && "p-5",
        interactive &&
          "cursor-pointer transition duration-200 ease-out-soft hover:-translate-y-0.5 hover:border-border-strong hover:shadow-md",
        className
      )}
    >
      {children}
    </div>
  );
}

/* ============================ PageHeader ============================ */
export function PageHeader({
  title,
  description,
  actions,
  icon: Icon,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
  icon?: LucideIcon;
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="flex items-start gap-3">
        {Icon && (
          <div className="mt-0.5 flex h-10 w-10 items-center justify-center rounded-lg bg-accent-subtle text-accent">
            <Icon className="h-5 w-5" />
          </div>
        )}
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-fg">{title}</h1>
          {description && <p className="mt-0.5 text-sm text-fg-muted">{description}</p>}
        </div>
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}

/* ============================ StatCard ============================ */
export function StatCard({
  label,
  value,
  tone = "default",
  icon: Icon,
  hint,
}: {
  label: string;
  value: ReactNode;
  tone?: "default" | "ok" | "warn" | "crit";
  icon?: LucideIcon;
  hint?: string;
}) {
  const tones = {
    default: "text-fg",
    ok: "text-success",
    warn: "text-warning",
    crit: "text-danger",
  };
  return (
    <Card>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-fg-muted">{label}</p>
          <p className={cn("mt-2 font-mono text-2xl font-semibold tracking-tight tabular-nums", tones[tone])}>
            {value}
          </p>
          {hint && <p className="mt-1 text-xs text-fg-subtle">{hint}</p>}
        </div>
        {Icon && (
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-surface-muted text-fg-subtle">
            <Icon className="h-5 w-5" />
          </div>
        )}
      </div>
    </Card>
  );
}

/* ============================ Badges ============================ */
type Tone = "neutral" | "accent" | "success" | "warning" | "danger";
const TONE_STYLE: Record<Tone, string> = {
  neutral: "bg-surface-muted text-fg-muted ring-border",
  accent: "bg-accent-subtle text-accent-subtle-fg ring-accent/20",
  success: "bg-success-subtle text-success-fg ring-success/20",
  warning: "bg-warning-subtle text-warning-fg ring-warning/20",
  danger: "bg-danger-subtle text-danger-fg ring-danger/20",
};

export function Badge({
  children,
  tone = "neutral",
  dot = false,
  className = "",
}: {
  children: ReactNode;
  tone?: Tone;
  dot?: boolean;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset",
        TONE_STYLE[tone],
        className
      )}
    >
      {dot && <span className="h-1.5 w-1.5 rounded-full bg-current opacity-70" />}
      {children}
    </span>
  );
}

const CRIT: Record<string, [Tone, string]> = {
  NORMAL: ["success", "Normal"],
  ALERTA: ["warning", "Alerta"],
  CRITICO: ["danger", "Crítico"],
};
export function CriticidadeBadge({ value }: { value: Criticidade | string }) {
  const [tone, label] = CRIT[value] ?? (["neutral", String(value)] as [Tone, string]);
  return (
    <Badge tone={tone} dot>
      {label}
    </Badge>
  );
}

export function StatusBadge({ value }: { value: string }) {
  return <Badge tone="neutral">{value}</Badge>;
}

const PRIO: Record<string, Tone> = {
  URGENTE: "danger",
  ALTA: "warning",
  MEDIA: "warning",
  BAIXA: "neutral",
};
export function PriorityBadge({ value, label }: { value: string; label?: string }) {
  return <Badge tone={PRIO[value] ?? "neutral"}>{label ?? value}</Badge>;
}

/* ============================ Form ============================ */
export function Field({
  label,
  children,
  htmlFor,
  className = "",
}: {
  label: string;
  children: ReactNode;
  htmlFor?: string;
  className?: string;
}) {
  return (
    <div className={className}>
      <label htmlFor={htmlFor} className="label">
        {label}
      </label>
      {children}
    </div>
  );
}

export function Input({ className = "", ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cn("input", className)} {...props} />;
}

export function Select({
  className = "",
  children,
  ...props
}: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select className={cn("input cursor-pointer", className)} {...props}>
      {children}
    </select>
  );
}

export function Textarea({ className = "", ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={cn("input", className)} {...props} />;
}

/* ============================ Table ============================ */
export function Table({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <Card padding={false} className="overflow-hidden">
      <div className="overflow-x-auto">
        <table className={cn("w-full text-sm", className)}>{children}</table>
      </div>
    </Card>
  );
}

export function THead({ children }: { children: ReactNode }) {
  return (
    <thead className="border-b border-border bg-surface-muted/40 text-left">
      <tr>{children}</tr>
    </thead>
  );
}

export function TH({ children, className = "" }: { children?: ReactNode; className?: string }) {
  return (
    <th className={cn("px-4 py-3 text-xs font-medium uppercase tracking-wide text-fg-subtle", className)}>
      {children}
    </th>
  );
}

export function TBody({ children }: { children: ReactNode }) {
  return <tbody className="divide-y divide-border">{children}</tbody>;
}

export function TR({
  children,
  className = "",
  onClick,
}: {
  children: ReactNode;
  className?: string;
  onClick?: () => void;
}) {
  return (
    <tr
      onClick={onClick}
      className={cn(
        "transition-colors duration-150",
        onClick && "cursor-pointer",
        "hover:bg-surface-muted/60",
        className
      )}
    >
      {children}
    </tr>
  );
}

export function TD({ children, className = "" }: { children?: ReactNode; className?: string }) {
  return <td className={cn("px-4 py-3 text-fg-muted", className)}>{children}</td>;
}

/* ============================ EmptyState ============================ */
export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
}: {
  icon: LucideIcon;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-16 text-center">
      <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-surface-muted text-fg-subtle">
        <Icon className="h-6 w-6" />
      </div>
      <p className="text-sm font-semibold text-fg">{title}</p>
      {description && <p className="mt-1 max-w-sm text-sm text-fg-muted">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

/* ============================ ThemeToggle ============================ */
export function ThemeToggle({ className = "" }: { className?: string }) {
  const [dark, setDark] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem("tpa-theme");
    const isDark = stored
      ? stored === "dark"
      : window.matchMedia("(prefers-color-scheme: dark)").matches;
    setDark(isDark);
    setMounted(true);
  }, []);

  function toggle() {
    const next = !dark;
    setDark(next);
    document.documentElement.dataset.theme = next ? "dark" : "light";
    try {
      localStorage.setItem("tpa-theme", next ? "dark" : "light");
    } catch {
      /* localStorage indisponível — o tema ainda funciona nesta sessão */
    }
  }

  const showSun = mounted && dark;
  return (
    <button
      onClick={toggle}
      aria-label={showSun ? "Ativar tema claro" : "Ativar tema escuro"}
      title={showSun ? "Tema claro" : "Tema escuro"}
      className={cn(
        "rounded-lg p-2 text-fg-muted transition-colors hover:bg-surface-muted hover:text-fg",
        className
      )}
    >
      {showSun ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
    </button>
  );
}

/* ============================ Loading ============================ */
export function Spinner({ label = "Carregando…" }: { label?: string }) {
  return (
    <div className="flex items-center gap-3 p-8 text-sm text-fg-muted">
      <Loader2 className="h-5 w-5 animate-spin text-accent" />
      <span>{label}</span>
    </div>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={cn("skeleton h-4 w-full", className)} />;
}

export function TableSkeleton({ rows = 5, cols = 4 }: { rows?: number; cols?: number }) {
  return (
    <Card padding={false} className="overflow-hidden">
      <div className="space-y-px">
        <div className="flex gap-4 border-b border-border bg-surface-muted/40 px-4 py-3">
          {Array.from({ length: cols }).map((_, i) => (
            <Skeleton key={i} className="h-3 w-24" />
          ))}
        </div>
        {Array.from({ length: rows }).map((_, r) => (
          <div key={r} className="flex items-center gap-4 px-4 py-3.5">
            {Array.from({ length: cols }).map((_, c) => (
              <Skeleton key={c} className={cn("h-4", c === 0 ? "w-16" : "w-28")} />
            ))}
          </div>
        ))}
      </div>
    </Card>
  );
}

export function CardsSkeleton({ count = 6 }: { count?: number }) {
  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
      {Array.from({ length: count }).map((_, i) => (
        <Card key={i}>
          <Skeleton className="h-5 w-24" />
          <Skeleton className="mt-3 h-3 w-40" />
          <Skeleton className="mt-2 h-3 w-32" />
        </Card>
      ))}
    </div>
  );
}
