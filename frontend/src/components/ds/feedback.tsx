"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import {
  CircleAlert,
  CircleCheck,
  Info,
  Lock,
  LoaderCircle,
  RotateCw,
  TriangleAlert,
  WifiOff,
  type LucideIcon,
} from "lucide-react";
import { cn, TOM_SUAVE, type Tom } from "./utils";
import { Button } from "./button";
import { Card } from "./card";
import type { Falha } from "@/lib/erros";

/* ==========================================================================
   Alert — mensagem contextual dentro da página.
   Use para condição persistente ("este laudo é rascunho"). Para confirmação de
   uma ação recém-feita, use Toast.
   ========================================================================== */

const ALERT_ICONE: Record<Tom, LucideIcon> = {
  neutral: Info,
  primary: Info,
  info: Info,
  success: CircleCheck,
  warning: TriangleAlert,
  danger: CircleAlert,
};

export function Alert({
  children,
  title,
  tone = "info",
  icon,
  actions,
  onClose,
  className = "",
}: {
  children?: ReactNode;
  title?: string;
  tone?: Tom;
  icon?: LucideIcon;
  actions?: ReactNode;
  onClose?: () => void;
  className?: string;
}) {
  const Icone = icon ?? ALERT_ICONE[tone];
  return (
    <div
      role={tone === "danger" ? "alert" : "status"}
      className={cn(
        "flex items-start gap-3 rounded-xl px-4 py-3 ring-1 ring-inset",
        TOM_SUAVE[tone],
        className
      )}
    >
      <Icone className="mt-0.5 h-4.5 w-4.5 shrink-0" aria-hidden="true" />
      <div className="min-w-0 flex-1">
        {title && <p className="text-sm font-semibold">{title}</p>}
        {children && <div className={cn("text-sm", title && "mt-0.5 opacity-90")}>{children}</div>}
        {actions && <div className="mt-2.5 flex flex-wrap items-center gap-2">{actions}</div>}
      </div>
      {onClose && (
        <button
          type="button"
          onClick={onClose}
          aria-label="Fechar aviso"
          className="-mr-1 -mt-1 shrink-0 rounded-md p-1 opacity-70 transition-opacity hover:opacity-100"
        >
          <span aria-hidden="true">✕</span>
        </button>
      )}
    </div>
  );
}

/* ==========================================================================
   Carregamento
   ========================================================================== */

export function Spinner({ label = "Carregando…", className = "" }: { label?: string; className?: string }) {
  return (
    <div role="status" className={cn("flex items-center gap-3 p-8 text-sm text-fg-muted", className)}>
      <LoaderCircle className="h-5 w-5 animate-spin text-primary" aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={cn("skeleton h-4 w-full", className)} aria-hidden="true" />;
}

/**
 * Espaço reservado com a forma do conteúdo que vai chegar.
 * Isso evita o "salto" de layout (CLS) e comunica que há algo vindo.
 */
export function LoadingState({
  label = "Carregando…",
  variante = "cartoes",
  linhas = 5,
  colunas = 5,
}: {
  label?: string;
  variante?: "cartoes" | "tabela" | "formulario" | "texto" | "indicadores";
  linhas?: number;
  colunas?: number;
}) {
  return (
    <div role="status" aria-busy="true" aria-live="polite">
      <span className="sr-only">{label}</span>

      {variante === "indicadores" && (
        <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
          {Array.from({ length: colunas }).map((_, i) => (
            <Card key={i} padding={false}>
              <div className="p-4">
                <Skeleton className="h-3 w-20" />
                <Skeleton className="mt-3 h-7 w-16" />
                <Skeleton className="mt-2 h-2.5 w-24" />
              </div>
            </Card>
          ))}
        </div>
      )}

      {variante === "tabela" && <TableSkeleton rows={linhas} cols={colunas} />}

      {variante === "cartoes" && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: linhas }).map((_, i) => (
            <Card key={i}>
              <Skeleton className="h-4 w-24" />
              <Skeleton className="mt-3 h-3 w-40" />
              <Skeleton className="mt-2 h-3 w-32" />
            </Card>
          ))}
        </div>
      )}

      {variante === "formulario" && (
        <Card>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {Array.from({ length: linhas * 2 }).map((_, i) => (
              <div key={i}>
                <Skeleton className="h-2.5 w-20" />
                <Skeleton className="mt-2 h-9 w-full" />
              </div>
            ))}
          </div>
        </Card>
      )}

      {variante === "texto" && (
        <div className="space-y-2.5">
          {Array.from({ length: linhas }).map((_, i) => (
            <Skeleton key={i} className={i === linhas - 1 ? "w-2/3" : "w-full"} />
          ))}
        </div>
      )}
    </div>
  );
}

export function TableSkeleton({ rows = 5, cols = 4 }: { rows?: number; cols?: number }) {
  return (
    <Card padding={false} className="overflow-hidden">
      <div className="flex gap-4 border-b border-border bg-surface-muted/50 px-4 py-3">
        {Array.from({ length: cols }).map((_, i) => (
          <Skeleton key={i} className="h-2.5 w-24" />
        ))}
      </div>
      <div className="divide-y divide-border">
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

/** Alias legado usado pelas telas atuais. */
export function CardsSkeleton({ count = 6 }: { count?: number }) {
  return <LoadingState variante="cartoes" linhas={count} />;
}

/* ==========================================================================
   EmptyState — vazio que ENSINA.
   --------------------------------------------------------------------------
   Três situações diferentes, três textos diferentes:
     "ainda não existe"  → explica o que é e oferece a primeira ação;
     "o filtro não achou" → oferece limpar o filtro;
     "não se aplica a você" → explica de quem é a responsabilidade.
   Nunca "Nenhum registro encontrado." seco.
   ========================================================================== */

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  secundaria,
  /** Lista curta de "como isso costuma chegar aqui" — onboarding embutido. */
  comoFunciona,
  compacto = false,
  className = "",
}: {
  icon: LucideIcon;
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  secundaria?: ReactNode;
  comoFunciona?: string[];
  compacto?: boolean;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center px-6 text-center",
        compacto ? "py-8" : "py-14",
        className
      )}
    >
      <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-surface-muted text-fg-subtle">
        <Icon className="h-6 w-6" aria-hidden="true" />
      </div>
      <p className="text-sm font-semibold text-fg">{title}</p>
      {description && <p className="mt-1 max-w-md text-sm text-fg-muted">{description}</p>}

      {comoFunciona && comoFunciona.length > 0 && (
        <ol className="mt-4 max-w-md space-y-1.5 text-left text-xs text-fg-muted">
          {comoFunciona.map((passo, i) => (
            <li key={i} className="flex gap-2.5">
              <span className="mt-px flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-surface-muted text-2xs font-semibold text-fg-subtle">
                {i + 1}
              </span>
              <span>{passo}</span>
            </li>
          ))}
        </ol>
      )}

      {(action || secundaria) && (
        <div className="mt-5 flex flex-wrap items-center justify-center gap-2">
          {action}
          {secundaria}
        </div>
      )}
    </div>
  );
}

/* ==========================================================================
   ErrorState — falha de carregamento, com saída.
   ========================================================================== */

export function ErrorState({
  falha,
  onRetry,
  className = "",
  compacto = false,
}: {
  falha: Falha;
  onRetry?: () => void;
  className?: string;
  compacto?: boolean;
}) {
  const ICONE: Record<Falha["tipo"], LucideIcon> = {
    permissao: Lock,
    sessao: Lock,
    "nao-encontrado": CircleAlert,
    validacao: CircleAlert,
    conexao: WifiOff,
    servidor: TriangleAlert,
  };
  const Icone = ICONE[falha.tipo];
  const tom: Tom = falha.tipo === "permissao" || falha.tipo === "sessao" ? "neutral" : "danger";

  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col items-center justify-center px-6 text-center",
        compacto ? "py-8" : "py-14",
        className
      )}
    >
      <div
        className={cn(
          "mb-4 flex h-12 w-12 items-center justify-center rounded-xl ring-1 ring-inset",
          TOM_SUAVE[tom]
        )}
      >
        <Icone className="h-6 w-6" aria-hidden="true" />
      </div>
      <p className="text-sm font-semibold text-fg">{falha.titulo}</p>
      <p className="mt-1 max-w-md text-sm text-fg-muted">{falha.descricao}</p>

      <div className="mt-5 flex flex-wrap items-center justify-center gap-2">
        {falha.tipo === "sessao" ? (
          <Link href="/portal/login">
            <Button size="sm">Entrar novamente</Button>
          </Link>
        ) : (
          onRetry &&
          falha.podeTentarNovamente && (
            <Button size="sm" variant="secondary" icon={RotateCw} onClick={onRetry}>
              Tentar novamente
            </Button>
          )
        )}
      </div>
    </div>
  );
}

/** Erro ocupando o lugar de um card/tabela. */
export function ErrorCard({ falha, onRetry }: { falha: Falha; onRetry?: () => void }) {
  return (
    <Card padding={false}>
      <ErrorState falha={falha} onRetry={onRetry} />
    </Card>
  );
}

/* ==========================================================================
   PermissionDenied — tela cheia quando a rota não é do usuário.
   ========================================================================== */

export function PermissionDenied({
  destino = "/",
  destinoLabel = "Voltar ao início",
  motivo,
}: {
  destino?: string;
  destinoLabel?: string;
  motivo?: string;
}) {
  return (
    <Card padding={false}>
      <div className="flex flex-col items-center justify-center px-6 py-16 text-center">
        <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-surface-muted text-fg-subtle">
          <Lock className="h-6 w-6" aria-hidden="true" />
        </div>
        <h1 className="text-lg font-semibold text-fg">Esta área não faz parte do seu acesso</h1>
        <p className="mt-1.5 max-w-md text-sm text-fg-muted">
          {motivo ??
            "Seu perfil não inclui esta parte do sistema. Se você precisa dela para trabalhar, peça ao administrador para ajustar seu nível de acesso."}
        </p>
        <Link href={destino} className="mt-5">
          <Button size="sm" variant="secondary">
            {destinoLabel}
          </Button>
        </Link>
      </div>
    </Card>
  );
}

/* ==========================================================================
   Estado offline — faixa global quando o navegador perde a rede.
   ========================================================================== */

export function OfflineBanner() {
  return (
    <div
      role="status"
      className="flex items-center justify-center gap-2 bg-warning px-4 py-1.5 text-xs font-medium text-white"
    >
      <WifiOff className="h-3.5 w-3.5" aria-hidden="true" />
      Você está sem conexão. As informações mostradas podem estar desatualizadas.
    </div>
  );
}

/* ==========================================================================
   Envelope de estados — resolve carregando / erro / vazio / conteúdo.
   --------------------------------------------------------------------------
   É o componente que garante a regra "nenhuma tela fica vazia sem explicar".
   ========================================================================== */

export function Resultado<T>({
  carregando,
  falha,
  dados,
  vazio,
  onRetry,
  esqueleto = "cartoes",
  children,
}: {
  carregando: boolean;
  falha: Falha | null;
  /** O conteúdo só renderiza quando isto não é vazio. */
  dados: T[] | T | null | undefined;
  /** O que mostrar quando não há nada (EmptyState pronto). */
  vazio: ReactNode;
  onRetry?: () => void;
  esqueleto?: "cartoes" | "tabela" | "formulario" | "texto" | "indicadores";
  children: (dados: NonNullable<T[] | T>) => ReactNode;
}) {
  if (carregando) return <LoadingState variante={esqueleto} />;
  if (falha) return <ErrorCard falha={falha} onRetry={onRetry} />;
  const semDados = dados == null || (Array.isArray(dados) && dados.length === 0);
  if (semDados) return <>{vazio}</>;
  return <>{children(dados as NonNullable<T[] | T>)}</>;
}
