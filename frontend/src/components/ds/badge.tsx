"use client";

import type { ReactNode } from "react";
import {
  CircleAlert,
  CircleCheck,
  CircleHelp,
  CircleMinus,
  OctagonAlert,
  TriangleAlert,
  WifiOff,
  type LucideIcon,
} from "lucide-react";
import { cn, TOM_SOLIDO, TOM_SUAVE, type Tom } from "./utils";

/* ==========================================================================
   Badge — rótulo curto de estado ou categoria.
   ========================================================================== */

export function Badge({
  children,
  tone = "neutral",
  variante = "suave",
  dot = false,
  icon: Icon,
  className = "",
  title,
}: {
  children: ReactNode;
  tone?: Tom | /* alias legado */ "accent";
  variante?: "suave" | "solido";
  /** Ponto de cor antes do texto — reforço visual, nunca a única pista. */
  dot?: boolean;
  icon?: LucideIcon;
  className?: string;
  title?: string;
}) {
  const tom: Tom = tone === "accent" ? "primary" : tone;
  return (
    <span
      title={title}
      className={cn(
        "inline-flex max-w-full items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium",
        variante === "suave" ? cn("ring-1 ring-inset", TOM_SUAVE[tom]) : TOM_SOLIDO[tom],
        className
      )}
    >
      {dot && <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-current opacity-80" aria-hidden="true" />}
      {Icon && <Icon className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />}
      <span className="truncate">{children}</span>
    </span>
  );
}

/* ==========================================================================
   Semântica de monitoramento — a escala de leitura do produto.
   --------------------------------------------------------------------------
   Regra dura (WCAG 1.4.1): estado NUNCA é só cor. Cada grau carrega
   ícone + rótulo em texto + forma do ícone diferente, para que funcione em
   monocromático, em impressão e para quem não distingue vermelho de verde.
   A forma muda de propósito: círculo → triângulo → octógono conforme a
   gravidade sobe, do mesmo jeito que a sinalização viária faz.

   O que o backend hoje emite: NORMAL · ALERTA · CRITICO (Criticidade) e a
   ausência de medição. ATENCAO é derivada na interface (tendência subindo dentro
   do normal) e SEM_DADOS representa equipamento ainda não medido.
   OFFLINE está definido aqui para a coleta automática por sensor/IoT prevista
   no Anexo I 2.3.1.5; nenhuma tela o usa enquanto essa origem não existir.
   ========================================================================== */

export type GrauMonitoramento =
  | "NORMAL"
  | "ATENCAO"
  | "ALERTA"
  | "CRITICO"
  | "OFFLINE"
  | "SEM_DADOS";

type DefinicaoGrau = {
  label: string;
  tom: Tom;
  icone: LucideIcon;
  /** Frase curta explicando o que o grau significa (tooltip / legenda). */
  significado: string;
};

export const GRAUS: Record<GrauMonitoramento, DefinicaoGrau> = {
  NORMAL: {
    label: "Normal",
    tom: "success",
    icone: CircleCheck,
    significado: "Medições dentro dos limites da norma. Nenhuma ação necessária.",
  },
  ATENCAO: {
    label: "Atenção",
    tom: "info",
    icone: CircleAlert,
    significado: "Dentro do limite, mas com tendência de piora. Acompanhar na próxima rota.",
  },
  ALERTA: {
    label: "Alerta",
    tom: "warning",
    icone: TriangleAlert,
    significado: "Acima do limite aceitável. Programar intervenção.",
  },
  CRITICO: {
    label: "Crítico",
    tom: "danger",
    icone: OctagonAlert,
    significado: "Risco de falha. Intervenção imediata — gera Ordem de Serviço.",
  },
  OFFLINE: {
    label: "Sem comunicação",
    tom: "neutral",
    icone: WifiOff,
    significado: "O sensor parou de enviar leituras. O estado mostrado pode estar desatualizado.",
  },
  SEM_DADOS: {
    label: "Sem medição",
    tom: "neutral",
    icone: CircleMinus,
    significado: "Equipamento cadastrado, ainda sem coleta registrada.",
  },
};

/** Ordem de gravidade — para ordenar listas pelo que importa primeiro. */
export const ORDEM_GRAVIDADE: GrauMonitoramento[] = [
  "CRITICO",
  "ALERTA",
  "ATENCAO",
  "OFFLINE",
  "SEM_DADOS",
  "NORMAL",
];

export function pesoGravidade(grau: GrauMonitoramento): number {
  const i = ORDEM_GRAVIDADE.indexOf(grau);
  return i === -1 ? ORDEM_GRAVIDADE.length : i;
}

/** Normaliza o que vem da API (string livre) para a escala da interface. */
export function grauDe(valor: string | null | undefined): GrauMonitoramento {
  if (!valor) return "SEM_DADOS";
  const v = String(valor).toUpperCase().replace(/[^A-Z_]/g, "");
  if (v in GRAUS) return v as GrauMonitoramento;
  if (v.startsWith("CRIT")) return "CRITICO";
  if (v.startsWith("ALERT")) return "ALERTA";
  if (v.startsWith("ATEN")) return "ATENCAO";
  if (v.startsWith("NORM")) return "NORMAL";
  return "SEM_DADOS";
}

/**
 * Selo de estado de monitoramento. É o componente que dá a leitura do produto —
 * use este, e não um Badge solto, sempre que a informação for "como está".
 */
export function EstadoBadge({
  grau,
  tamanho = "md",
  mostrarSignificado = false,
  className = "",
}: {
  grau: GrauMonitoramento | string | null | undefined;
  tamanho?: "sm" | "md";
  /** Anexa o significado como `title` — ajuda quem está aprendendo a escala. */
  mostrarSignificado?: boolean;
  className?: string;
}) {
  const g = typeof grau === "string" || grau == null ? grauDe(grau) : grau;
  const def = GRAUS[g];
  const Icone = def.icone;
  return (
    <span
      title={mostrarSignificado ? def.significado : undefined}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full font-medium ring-1 ring-inset",
        TOM_SUAVE[def.tom],
        tamanho === "sm" ? "px-2 py-0.5 text-2xs" : "px-2.5 py-0.5 text-xs",
        className
      )}
    >
      <Icone className={tamanho === "sm" ? "h-3 w-3 shrink-0" : "h-3.5 w-3.5 shrink-0"} aria-hidden="true" />
      {def.label}
    </span>
  );
}

/** Ponto de estado para tabelas densas — sempre acompanhado de texto ao lado. */
export function EstadoPonto({ grau, className = "" }: { grau: GrauMonitoramento; className?: string }) {
  const def = GRAUS[grau];
  const cor: Record<Tom, string> = {
    neutral: "bg-fg-subtle",
    primary: "bg-primary",
    success: "bg-success",
    warning: "bg-warning",
    danger: "bg-danger",
    info: "bg-info",
  };
  return (
    <span
      role="img"
      aria-label={def.label}
      title={def.significado}
      className={cn("inline-block h-2 w-2 shrink-0 rounded-full", cor[def.tom], className)}
    />
  );
}

/** Legenda da escala — usada no onboarding e no rodapé dos painéis. */
export function LegendaEstados({
  graus = ["NORMAL", "ATENCAO", "ALERTA", "CRITICO", "SEM_DADOS"],
  className = "",
}: {
  graus?: GrauMonitoramento[];
  className?: string;
}) {
  return (
    <ul className={cn("flex flex-wrap items-center gap-x-4 gap-y-2", className)}>
      {graus.map((g) => (
        <li key={g} className="flex items-center gap-1.5 text-xs text-fg-muted">
          <EstadoBadge grau={g} tamanho="sm" />
          <span className="hidden sm:inline">{GRAUS[g].significado}</span>
        </li>
      ))}
    </ul>
  );
}

/* ==========================================================================
   Badges de domínio — mantêm a API antiga para as telas já existentes.
   ========================================================================== */

/** Criticidade da medição (NORMAL / ALERTA / CRITICO vindos da API). */
export function CriticidadeBadge({ value }: { value: string | null | undefined }) {
  return <EstadoBadge grau={grauDe(value)} mostrarSignificado />;
}

/** Status de processo (rascunho, emitido, finalizada…) — categoria, não gravidade. */
const STATUS_TOM: Record<string, Tom> = {
  RASCUNHO: "neutral",
  EM_CAMPO: "info",
  EM_ANALISE: "info",
  EM_EXECUCAO: "info",
  PLANEJADA: "primary",
  ABERTA: "warning",
  AGUARDANDO_APROVACAO: "warning",
  EXECUTADA: "primary",
  EMITIDO: "success",
  CONCLUIDA: "success",
  CONCLUIDO: "success",
  FINALIZADA: "success",
  CANCELADA: "danger",
  CANCELADO: "danger",
};

export function StatusBadge({
  value,
  label,
  className = "",
}: {
  value: string | null | undefined;
  /** Texto exibido; por padrão usa o `*_display` que a API já manda. */
  label?: string;
  className?: string;
}) {
  const chave = String(value ?? "").toUpperCase().replace(/\s+/g, "_");
  return (
    <Badge tone={STATUS_TOM[chave] ?? "neutral"} className={className}>
      {label ?? value ?? "—"}
    </Badge>
  );
}

const PRIORIDADE_TOM: Record<string, Tom> = {
  URGENTE: "danger",
  ALTA: "warning",
  MEDIA: "info",
  BAIXA: "neutral",
};

export function PriorityBadge({ value, label }: { value: string; label?: string }) {
  const chave = String(value ?? "").toUpperCase();
  return (
    <Badge tone={PRIORIDADE_TOM[chave] ?? "neutral"} icon={chave === "URGENTE" ? TriangleAlert : undefined}>
      {label ?? value}
    </Badge>
  );
}

/** Classe de criticidade do ativo (A/B/C) — importância, não estado atual. */
export function ClasseAtivoBadge({ value, label }: { value: string; label?: string }) {
  const tom: Record<string, Tom> = { A: "danger", B: "warning", C: "neutral" };
  if (!value) return <span className="text-fg-subtle">—</span>;
  return (
    <Badge tone={tom[value] ?? "neutral"} title="Classe de criticidade do ativo para a operação">
      {label ?? `Classe ${value}`}
    </Badge>
  );
}

/** Marca "sem informação" de forma consistente em qualquer célula. */
export function SemDado({ children = "—" }: { children?: ReactNode }) {
  return <span className="text-fg-subtle">{children}</span>;
}

/** Selo de ajuda contextual — explica um número sem poluir a tela. */
export function DicaSelo({ texto }: { texto: string }) {
  return (
    <span
      tabIndex={0}
      title={texto}
      aria-label={texto}
      className="inline-flex h-4 w-4 cursor-help items-center justify-center rounded-full text-fg-subtle transition-colors hover:text-fg"
    >
      <CircleHelp className="h-3.5 w-3.5" aria-hidden="true" />
    </span>
  );
}
