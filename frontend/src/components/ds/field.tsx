"use client";

import {
  createContext,
  forwardRef,
  useContext,
  useId,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from "react";
import { Check, CircleAlert, Search, X } from "lucide-react";
import { cn } from "./utils";

/* ==========================================================================
   Formulários
   --------------------------------------------------------------------------
   Contrato do Design System: todo campo tem rótulo visível, e os estados
   (normal · hover · foco · desabilitado · erro · sucesso) vivem no componente,
   não na tela. O `Field` faz a amarração de acessibilidade sozinho:
     label ↔ controle (id/for) · aria-describedby (ajuda + erro) · aria-invalid
     · aria-required.
   Assim nenhuma tela precisa lembrar de fazer isso — e nenhuma esquece.
   ========================================================================== */

type CampoContexto = {
  id: string;
  descritoPor?: string;
  invalido: boolean;
  obrigatorio: boolean;
};

const Ctx = createContext<CampoContexto | null>(null);

/** Props que os controles herdam do Field quando estão dentro de um. */
function useCampo(idExplicito?: string) {
  const ctx = useContext(Ctx);
  return {
    id: idExplicito ?? ctx?.id,
    "aria-describedby": ctx?.descritoPor,
    "aria-invalid": ctx?.invalido ? (true as const) : undefined,
    "aria-required": ctx?.obrigatorio ? (true as const) : undefined,
  };
}

export function Field({
  label,
  children,
  htmlFor,
  hint,
  erro,
  sucesso,
  obrigatorio = false,
  className = "",
}: {
  label: string;
  children: ReactNode;
  /** Só quando o controle tem id próprio; normalmente deixe o Field gerar. */
  htmlFor?: string;
  /** Texto auxiliar permanente (formato esperado, unidade, origem do dado). */
  hint?: ReactNode;
  /** Mensagem de erro — substitui o hint e marca o controle como inválido. */
  erro?: string | null;
  /** Confirmação pontual (ex.: "TAG disponível"). */
  sucesso?: string | null;
  obrigatorio?: boolean;
  className?: string;
}) {
  const gerado = useId();
  const id = htmlFor ?? gerado;
  const idAjuda = `${id}-ajuda`;
  const idErro = `${id}-erro`;
  const invalido = !!erro;
  const descritoPor = [hint ? idAjuda : null, invalido ? idErro : null].filter(Boolean).join(" ") || undefined;

  return (
    <div className={className}>
      <label htmlFor={id} className="label">
        {label}
        {obrigatorio && (
          <span className="ml-0.5 text-danger" aria-hidden="true">
            *
          </span>
        )}
      </label>

      <Ctx.Provider value={{ id, descritoPor, invalido, obrigatorio }}>{children}</Ctx.Provider>

      {/* Erro tem prioridade sobre ajuda: não competem pelo mesmo espaço. */}
      {invalido ? (
        <p id={idErro} role="alert" className="mt-1.5 flex items-start gap-1.5 text-xs text-danger-fg">
          <CircleAlert className="mt-px h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          <span>{erro}</span>
        </p>
      ) : sucesso ? (
        <p className="mt-1.5 flex items-start gap-1.5 text-xs text-success-fg">
          <Check className="mt-px h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          <span>{sucesso}</span>
        </p>
      ) : hint ? (
        <p id={idAjuda} className="mt-1.5 text-xs text-fg-subtle">
          {hint}
        </p>
      ) : null}
    </div>
  );
}

/* ============================ Input ============================ */

export type InputProps = InputHTMLAttributes<HTMLInputElement> & {
  /** Ícone decorativo à esquerda (busca, calendário…). */
  iconeEsquerda?: ReactNode;
  /** Sufixo textual fixo: unidade (mm/s, °C, kW). */
  sufixo?: string;
  /** Dado numérico/técnico: fonte monoespaçada e dígitos alinhados. */
  tecnico?: boolean;
};

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { className = "", iconeEsquerda, sufixo, tecnico, id, ...props },
  ref
) {
  const campo = useCampo(id);
  const control = (
    <input
      ref={ref}
      {...campo}
      className={cn(
        "field-control",
        !!iconeEsquerda && "pl-9",
        !!sufixo && "pr-12",
        tecnico && "data",
        className
      )}
      {...props}
    />
  );

  if (!iconeEsquerda && !sufixo) return control;

  return (
    <div className="relative">
      {iconeEsquerda && (
        <span
          className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-fg-subtle"
          aria-hidden="true"
        >
          {iconeEsquerda}
        </span>
      )}
      {control}
      {sufixo && (
        <span
          className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-xs text-fg-subtle"
          aria-hidden="true"
        >
          {sufixo}
        </span>
      )}
    </div>
  );
});

/* ============================ Textarea ============================ */

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(
  function Textarea({ className = "", id, rows = 3, ...props }, ref) {
    const campo = useCampo(id);
    return (
      <textarea
        ref={ref}
        rows={rows}
        {...campo}
        className={cn("field-control resize-y leading-relaxed", className)}
        {...props}
      />
    );
  }
);

/* ============================ Select ============================ */

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(
  function Select({ className = "", children, id, ...props }, ref) {
    const campo = useCampo(id);
    return (
      <select
        ref={ref}
        {...campo}
        className={cn(
          "field-control cursor-pointer appearance-none bg-no-repeat pr-9",
          // Seta desenhada em CSS: um SVG inline evita depender de imagem externa.
          "[background-image:url(\"data:image/svg+xml;charset=utf-8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%237d8899' stroke-width='2' stroke-linecap='round'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E\")]",
          "[background-position:right_0.625rem_center] [background-size:1rem]",
          className
        )}
        {...props}
      >
        {children}
      </select>
    );
  }
);

/* ============================ Busca ============================ */

/**
 * Campo de busca com ícone e botão de limpar. Substitui o
 * `<div class="relative"><Search/><Input class="pl-9"/></div>` copiado em cada
 * listagem, e já vem com `role="searchbox"` e rótulo acessível.
 */
export function SearchInput({
  value,
  onChange,
  placeholder = "Buscar…",
  label = "Buscar",
  className = "",
  autoFocus,
}: {
  value: string;
  onChange: (valor: string) => void;
  placeholder?: string;
  /** Rótulo acessível (fica oculto; o placeholder não serve como rótulo). */
  label?: string;
  className?: string;
  autoFocus?: boolean;
}) {
  const id = useId();
  return (
    <div className={cn("relative", className)}>
      <label htmlFor={id} className="sr-only">
        {label}
      </label>
      <Search
        className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-fg-subtle"
        aria-hidden="true"
      />
      <input
        id={id}
        type="search"
        value={value}
        autoFocus={autoFocus}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="field-control pl-9 pr-9 [&::-webkit-search-cancel-button]:hidden"
      />
      {value && (
        <button
          type="button"
          onClick={() => onChange("")}
          aria-label="Limpar busca"
          className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-1 text-fg-subtle transition-colors hover:bg-surface-muted hover:text-fg"
        >
          <X className="h-3.5 w-3.5" aria-hidden="true" />
        </button>
      )}
    </div>
  );
}

/* ============================ Checkbox ============================ */

export function Checkbox({
  checked,
  onChange,
  label,
  hint,
  disabled,
  className = "",
  indeterminate = false,
}: {
  checked: boolean;
  onChange: (valor: boolean) => void;
  label: ReactNode;
  hint?: ReactNode;
  disabled?: boolean;
  className?: string;
  /** Seleção parcial (cabeçalho de tabela com algumas linhas marcadas). */
  indeterminate?: boolean;
}) {
  const id = useId();
  return (
    <div className={cn("flex items-start gap-2.5", className)}>
      <span className="relative flex h-5 items-center">
        <input
          id={id}
          type="checkbox"
          checked={checked}
          disabled={disabled}
          ref={(el) => {
            if (el) el.indeterminate = indeterminate && !checked;
          }}
          onChange={(e) => onChange(e.target.checked)}
          className={cn(
            "peer h-4 w-4 shrink-0 cursor-pointer appearance-none rounded border border-border-strong bg-surface",
            "transition-colors duration-fast",
            "checked:border-primary checked:bg-primary indeterminate:border-primary indeterminate:bg-primary",
            "disabled:cursor-not-allowed disabled:opacity-50"
          )}
        />
        {/* Marca desenhada por cima; o input fica sem aparência nativa. */}
        <Check
          className="pointer-events-none absolute left-0 top-1/2 h-4 w-4 -translate-y-1/2 text-primary-fg opacity-0 peer-checked:opacity-100"
          strokeWidth={3}
          aria-hidden="true"
        />
        {indeterminate && !checked && (
          <span className="pointer-events-none absolute left-[3px] top-1/2 h-0.5 w-2.5 -translate-y-1/2 rounded-full bg-primary-fg" />
        )}
      </span>
      <label htmlFor={id} className={cn("cursor-pointer select-none text-sm", disabled && "opacity-50")}>
        <span className="text-fg">{label}</span>
        {hint && <span className="block text-xs text-fg-subtle">{hint}</span>}
      </label>
    </div>
  );
}

/* ============================ Switch ============================ */

/** Liga/desliga com efeito imediato (não precisa de "salvar"). */
export function Switch({
  checked,
  onChange,
  label,
  hint,
  disabled,
  className = "",
}: {
  checked: boolean;
  onChange: (valor: boolean) => void;
  label: ReactNode;
  hint?: ReactNode;
  disabled?: boolean;
  className?: string;
}) {
  const id = useId();
  const idHint = `${id}-hint`;
  return (
    <div className={cn("flex items-start justify-between gap-4", className)}>
      <label htmlFor={id} className={cn("cursor-pointer select-none text-sm", disabled && "opacity-50")}>
        <span className="font-medium text-fg">{label}</span>
        {hint && (
          <span id={idHint} className="block text-xs text-fg-muted">
            {hint}
          </span>
        )}
      </label>
      <button
        id={id}
        type="button"
        role="switch"
        aria-checked={checked}
        aria-describedby={hint ? idHint : undefined}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={cn(
          "relative h-6 w-10 shrink-0 rounded-full transition-colors duration-normal",
          "disabled:cursor-not-allowed disabled:opacity-50",
          checked ? "bg-primary" : "bg-border-strong"
        )}
      >
        <span
          className={cn(
            "absolute top-0.5 h-5 w-5 rounded-full bg-white shadow-sm transition-transform duration-normal ease-out-soft",
            checked ? "translate-x-[1.125rem]" : "translate-x-0.5"
          )}
        />
      </button>
    </div>
  );
}

/* ============================ RadioGroup ============================ */

export function RadioGroup<T extends string>({
  value,
  onChange,
  options,
  label,
  name,
  className = "",
  orientacao = "vertical",
}: {
  value: T | "";
  onChange: (valor: T) => void;
  options: { valor: T; label: string; hint?: string; disabled?: boolean }[];
  /** Rótulo do grupo — vira o `aria-label` do fieldset. */
  label: string;
  name?: string;
  className?: string;
  orientacao?: "vertical" | "horizontal";
}) {
  const gerado = useId();
  const grupo = name ?? gerado;
  return (
    <fieldset className={className}>
      <legend className="label">{label}</legend>
      <div
        className={cn(
          "gap-2.5",
          orientacao === "vertical" ? "flex flex-col" : "flex flex-wrap items-center gap-x-5"
        )}
      >
        {options.map((o) => {
          const id = `${grupo}-${o.valor}`;
          return (
            <div key={o.valor} className="flex items-start gap-2.5">
              <input
                id={id}
                type="radio"
                name={grupo}
                value={o.valor}
                checked={value === o.valor}
                disabled={o.disabled}
                onChange={() => onChange(o.valor)}
                className={cn(
                  "mt-0.5 h-4 w-4 shrink-0 cursor-pointer appearance-none rounded-full border border-border-strong bg-surface",
                  "transition-colors duration-fast",
                  "checked:border-[5px] checked:border-primary",
                  "disabled:cursor-not-allowed disabled:opacity-50"
                )}
              />
              <label htmlFor={id} className={cn("cursor-pointer select-none text-sm", o.disabled && "opacity-50")}>
                <span className="text-fg">{o.label}</span>
                {o.hint && <span className="block text-xs text-fg-subtle">{o.hint}</span>}
              </label>
            </div>
          );
        })}
      </div>
    </fieldset>
  );
}

/* ============================ Estrutura de formulário ============================ */

/** Bloco temático dentro de um formulário longo — evita "formulário gigante". */
export function FormSection({
  title,
  description,
  children,
  className = "",
}: {
  title: string;
  description?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("border-t border-border pt-5 first:border-t-0 first:pt-0", className)}>
      <div className="mb-4">
        <h3 className="text-sm font-semibold text-fg">{title}</h3>
        {description && <p className="mt-0.5 text-xs text-fg-muted">{description}</p>}
      </div>
      {children}
    </section>
  );
}

/** Grade responsiva padrão de formulário: 1 coluna no celular, 2–3 no desktop. */
export function FormGrid({
  children,
  colunas = 2,
  className = "",
}: {
  children: ReactNode;
  colunas?: 1 | 2 | 3;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "grid gap-x-4 gap-y-4",
        colunas === 1 && "grid-cols-1",
        colunas === 2 && "grid-cols-1 sm:grid-cols-2",
        colunas === 3 && "grid-cols-1 sm:grid-cols-2 lg:grid-cols-3",
        className
      )}
    >
      {children}
    </div>
  );
}

/**
 * Barra de ações de formulário. Fica grudada no rodapé no celular (o usuário não
 * precisa rolar até o fim para achar "Salvar") e alinhada à direita no desktop.
 */
export function FormActions({
  children,
  className = "",
  alinhamento = "direita",
}: {
  children: ReactNode;
  className?: string;
  alinhamento?: "direita" | "entre";
}) {
  return (
    <div
      className={cn(
        "sticky bottom-0 z-raised -mx-4 mt-2 flex flex-wrap items-center gap-2 border-t border-border bg-surface/95 px-4 py-3 backdrop-blur",
        "sm:static sm:mx-0 sm:border-0 sm:bg-transparent sm:px-0 sm:py-0 sm:backdrop-blur-none",
        alinhamento === "direita" ? "justify-end" : "justify-between",
        className
      )}
    >
      {children}
    </div>
  );
}
