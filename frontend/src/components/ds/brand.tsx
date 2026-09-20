"use client";

import { useState } from "react";
import { cn } from "./utils";

/* ==========================================================================
   Marca
   --------------------------------------------------------------------------
   O símbolo oficial (engrenagem + setas de tendência) vive em
   `frontend/public/brand/mark.png`, derivado do logotipo entregue pelo cliente
   (`logotipoPredAtivos.png`, na raiz do repositório).

   Arranjo escolhido: SÍMBOLO como imagem + NOME como texto HTML.
     • o nome acompanha o tema claro/escuro e a sidebar escura sem precisar de
       três variantes de arquivo;
     • é selecionável e o leitor de tela lê o nome do produto, não "imagem";
     • no trilho recolhido da sidebar e no favicon só o símbolo aparece — texto
       a 28 px seria borrão.

   Trocar a marca = trocar os arquivos em `public/brand/`. Nenhuma tela muda.
   Se `mark.png` sumir, o desenho embutido abaixo entra no lugar e nada quebra.
   ========================================================================== */

/** Último recurso: se o arquivo do símbolo não existir, nada fica vazio. */
function SimboloEmbutido({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 48 48" className={className} aria-hidden="true" focusable="false">
      <rect width="48" height="48" rx="11" fill="var(--primary)" />
      <circle cx="16" cy="32" r="4" fill="var(--primary-fg)" />
      <path d="M16 24a8 8 0 0 1 8 8" stroke="var(--primary-fg)" strokeWidth="3.2" strokeLinecap="round" fill="none" opacity=".95" />
      <path d="M16 17.5a14.5 14.5 0 0 1 14.5 14.5" stroke="var(--primary-fg)" strokeWidth="3.2" strokeLinecap="round" fill="none" opacity=".72" />
      <path d="M16 11a21 21 0 0 1 21 21" stroke="var(--primary-fg)" strokeWidth="3.2" strokeLinecap="round" fill="none" opacity=".48" />
    </svg>
  );
}

const TAMANHO_SIMBOLO = {
  sm: "h-7 w-7",
  md: "h-9 w-9",
  lg: "h-11 w-11",
  xl: "h-14 w-14",
} as const;

export function Simbolo({
  tamanho = "md",
  className = "",
}: {
  tamanho?: keyof typeof TAMANHO_SIMBOLO;
  className?: string;
}) {
  const [semArquivo, setSemArquivo] = useState(false);
  const classes = cn("shrink-0 object-contain", TAMANHO_SIMBOLO[tamanho], className);

  if (semArquivo) return <SimboloEmbutido className={cn(classes, "rounded-[0.55em]")} />;
  return (
    // eslint-disable-next-line @next/next/no-img-element -- imagem de marca estática;
    // next/image acrescentaria um passo de otimização sem ganho (22 KB, já dimensionada).
    <img
      src="/brand/mark.png"
      alt=""
      aria-hidden="true"
      width={112}
      height={112}
      className={classes}
      onError={() => setSemArquivo(true)}
    />
  );
}

const TAMANHO_NOME = {
  sm: { nome: "text-sm", sub: "text-2xs" },
  md: { nome: "text-[0.9375rem]", sub: "text-2xs" },
  lg: { nome: "text-lg", sub: "text-xs" },
  xl: { nome: "text-2xl", sub: "text-sm" },
} as const;

/**
 * Assinatura da marca: símbolo + nome + descritor.
 * `onChrome` usa os tokens da navegação escura; sem ele, os tokens de texto
 * normais — funciona igual sobre fundo claro e escuro.
 */
export function Logo({
  tamanho = "md",
  onChrome = false,
  mostrarDescritor = true,
  className = "",
}: {
  tamanho?: keyof typeof TAMANHO_SIMBOLO;
  onChrome?: boolean;
  mostrarDescritor?: boolean;
  className?: string;
}) {
  const t = TAMANHO_NOME[tamanho];
  return (
    <span className={cn("flex items-center gap-2.5", className)}>
      <Simbolo tamanho={tamanho} />
      <span className="min-w-0">
        <span
          className={cn(
            "block truncate font-semibold tracking-tight",
            t.nome,
            onChrome ? "text-chrome-fg" : "text-fg"
          )}
        >
          Pred <span className={onChrome ? "text-[#a8c9fc]" : "text-primary"}>Ativos</span>
        </span>
        {mostrarDescritor && (
          <span
            className={cn(
              "block truncate font-medium uppercase tracking-[0.08em]",
              t.sub,
              onChrome ? "text-chrome-fg-subtle" : "text-fg-subtle"
            )}
          >
            Manutenção preditiva
          </span>
        )}
      </span>
    </span>
  );
}
