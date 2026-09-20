/** Junta classes ignorando falsy. Único utilitário de classe do projeto. */
export function cn(...parts: (string | false | null | undefined)[]) {
  return parts.filter(Boolean).join(" ");
}

/**
 * Tons semânticos compartilhados por Badge, Alert, MetricCard e StatusBadge.
 *
 * `neutral` é ausência de julgamento; `primary` é identidade/ação; os demais são
 * ESTADO. Nenhum componente inventa o seu próprio mapa de cor — todos leem daqui,
 * o que garante que "crítico" tenha a mesma aparência em qualquer tela.
 */
export type Tom = "neutral" | "primary" | "success" | "warning" | "danger" | "info";

export const TOM_SUAVE: Record<Tom, string> = {
  neutral: "bg-surface-muted text-fg-muted ring-border",
  primary: "bg-primary-subtle text-primary-subtle-fg ring-primary/25",
  success: "bg-success-subtle text-success-fg ring-success/25",
  warning: "bg-warning-subtle text-warning-fg ring-warning/25",
  danger: "bg-danger-subtle text-danger-fg ring-danger/25",
  info: "bg-info-subtle text-info-fg ring-info/25",
};

export const TOM_SOLIDO: Record<Tom, string> = {
  neutral: "bg-secondary text-white",
  primary: "bg-primary text-primary-fg",
  success: "bg-success text-white",
  warning: "bg-warning text-white",
  danger: "bg-danger text-white",
  info: "bg-info text-white",
};

export const TOM_TEXTO: Record<Tom, string> = {
  neutral: "text-fg-muted",
  primary: "text-primary",
  success: "text-success-fg",
  warning: "text-warning-fg",
  danger: "text-danger-fg",
  info: "text-info-fg",
};

export const TOM_BORDA: Record<Tom, string> = {
  neutral: "border-border",
  primary: "border-primary/40",
  success: "border-success/40",
  warning: "border-warning/40",
  danger: "border-danger/40",
  info: "border-info/40",
};
