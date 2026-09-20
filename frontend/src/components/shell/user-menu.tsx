"use client";

import Link from "next/link";
import { ChevronDown, LifeBuoy, LogOut, ShieldCheck, UserCog } from "lucide-react";
import { Avatar, Badge, DropdownMenu, cn } from "@/components/ds";
import { NIVEL_LABEL, PERFIL_LABEL } from "@/lib/permissions";
import type { User } from "@/lib/types";

/**
 * Identidade + saída, num só lugar.
 *
 * Antes o logout era um ícone solto no rodapé da sidebar, sem confirmação de
 * quem estava logado nem onde ver o próprio perfil. Aqui o usuário lê seu nome,
 * seu papel e seu nível — informação que importa num sistema com 7 perfis e 4
 * níveis, onde "por que não consigo excluir?" é dúvida frequente.
 */
export function UserMenu({
  user,
  onSair,
  perfilHref,
  ajudaHref,
  variante = "topbar",
  colapsada = false,
}: {
  user: User;
  onSair: () => void;
  perfilHref: string;
  ajudaHref?: string;
  /** `topbar` = avatar compacto; `sidebar` = bloco com nome e papel. */
  variante?: "topbar" | "sidebar";
  colapsada?: boolean;
}) {
  const itens = [
    { label: "Meu perfil e preferências", href: perfilHref, icon: UserCog },
    ...(ajudaHref ? [{ label: "Ajuda", href: ajudaHref, icon: LifeBuoy }] : []),
    { label: "Sair da conta", onClick: onSair, icon: LogOut, destrutivo: true },
  ];

  const cabecalho = (
    <div className="border-b border-border px-2.5 pb-2.5 pt-1">
      <p className="truncate text-sm font-semibold text-fg">{user.nome}</p>
      <p className="truncate text-xs text-fg-muted">{user.email}</p>
      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        <Badge tone={user.is_interno ? "primary" : "info"} icon={ShieldCheck}>
          {PERFIL_LABEL[user.perfil] ?? user.perfil_display}
        </Badge>
        <Badge tone="neutral" title={`Grupo de acesso: ${user.grupo_acesso}`}>
          Nível {NIVEL_LABEL[user.nivel] ?? user.nivel_display}
        </Badge>
      </div>
    </div>
  );

  if (variante === "sidebar") {
    return (
      <DropdownMenu
        label="Conta e preferências"
        alinhamento="esquerda"
        direcao="cima"
        itens={itens}
        trigger={
          <span
            className={cn(
              "flex w-full items-center rounded-lg py-2 transition-colors hover:bg-chrome-muted",
              colapsada ? "justify-center px-1" : "gap-2.5 px-2"
            )}
          >
            <Avatar nome={user.nome} tamanho="sm" onChrome />
            {!colapsada && (
              <>
                <span className="min-w-0 flex-1 text-left">
                  <span className="block truncate text-sm font-medium text-chrome-fg">{user.nome}</span>
                  <span className="block truncate text-2xs text-chrome-fg-subtle">{user.grupo_acesso}</span>
                </span>
                <ChevronDown className="h-4 w-4 shrink-0 text-chrome-fg-subtle" aria-hidden="true" />
              </>
            )}
          </span>
        }
      />
    );
  }

  return (
    <DropdownMenu
      label="Conta e preferências"
      itens={itens}
      trigger={
        <span className="flex items-center gap-2 rounded-lg p-1 transition-colors hover:bg-surface-muted">
          <Avatar nome={user.nome} tamanho="sm" />
          <span className="hidden min-w-0 text-left lg:block">
            <span className="block max-w-32 truncate text-xs font-medium text-fg">{user.nome}</span>
            <span className="block text-2xs text-fg-subtle">{user.grupo_acesso}</span>
          </span>
          <ChevronDown className="h-4 w-4 shrink-0 text-fg-subtle" aria-hidden="true" />
        </span>
      }
    />
  );
}

/** Versão só-leitura da identidade, para o rodapé do drawer no celular. */
export function UserBlock({ user, perfilHref }: { user: User; perfilHref: string }) {
  return (
    <Link
      href={perfilHref}
      className="flex items-center gap-2.5 rounded-lg px-2 py-2 transition-colors hover:bg-chrome-muted"
    >
      <Avatar nome={user.nome} tamanho="sm" onChrome />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-medium text-chrome-fg">{user.nome}</span>
        <span className="block truncate text-2xs text-chrome-fg-subtle">{user.grupo_acesso}</span>
      </span>
    </Link>
  );
}
