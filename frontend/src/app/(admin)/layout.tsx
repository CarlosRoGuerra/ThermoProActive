"use client";

import Link from "next/link";
import { Building2, X } from "lucide-react";
import { AppShell } from "@/components/shell/app-shell";
import { RouteGuard, useRotaBloqueada } from "@/components/shell/guard";
import { PermissionDenied, ToastProvider, cn } from "@/components/ds";
import { ClienteSwitcher } from "@/components/cliente-switcher";
import { useClienteAtivo } from "@/lib/cliente-ativo";
import { navAdmin } from "@/lib/nav";
import type { User } from "@/lib/types";

/**
 * PORTAL OPERACIONAL — equipe interna (ambiente "BackEnd" na hierarquia
 * acordada com o cliente). Somente perfis internos entram aqui; um usuário
 * cliente que chegue por URL antiga é levado ao equivalente no /portal.
 */
export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <ToastProvider>
      <RouteGuard area="admin">{(user) => <Interno user={user}>{children}</Interno>}</RouteGuard>
    </ToastProvider>
  );
}

function Interno({ user, children }: { user: User; children: React.ReactNode }) {
  const { clienteAtivo } = useClienteAtivo();
  const bloqueada = useRotaBloqueada(user);

  return (
    <AppShell
      user={user}
      grupos={navAdmin(!!clienteAtivo)}
      inicioHref="/admin/dashboard"
      perfilHref="/admin/seguranca"
      alertasHref="/notificacoes"
      acoesTopbar={<ClienteSwitcher />}
      rodapeSidebar={(colapsada) => <ClienteEmAtendimento colapsada={colapsada} />}
    >
      {bloqueada ? (
        <PermissionDenied
          destino="/dashboard"
          destinoLabel="Ir para a visão geral"
          motivo="Esta área exige um nível de acesso que seu usuário não tem. O nível Master da sua equipe pode conceder."
        />
      ) : (
        children
      )}
    </AppShell>
  );
}

/**
 * Cliente em atendimento — o "onde estou trabalhando" da equipe interna.
 * Fica no rodapé da sidebar porque é contexto persistente, não ação.
 */
function ClienteEmAtendimento({ colapsada = false }: { colapsada?: boolean }) {
  const { clienteAtivo, limpar } = useClienteAtivo();

  if (!clienteAtivo) {
    return (
      <Link
        href="/clientes"
        title={colapsada ? "Nenhum cliente em atendimento · escolher" : undefined}
        className={cn(
          "block rounded-lg border border-dashed border-chrome-border text-2xs text-chrome-fg-subtle transition-colors hover:border-primary hover:text-chrome-fg",
          colapsada ? "flex h-9 items-center justify-center px-0" : "px-2.5 py-2 text-center"
        )}
      >
        {colapsada ? (
          <>
            <Building2 className="h-4 w-4" aria-hidden="true" />
            <span className="sr-only">Nenhum cliente em atendimento · escolher</span>
          </>
        ) : (
          "Nenhum cliente em atendimento · escolher"
        )}
      </Link>
    );
  }

  // Trilho: só o ícone cabe. O nome vai no title/sr-only para não vazar da sidebar.
  if (colapsada) {
    const nome = clienteAtivo.nome_fantasia || clienteAtivo.nome;
    return (
      <div
        title={`Atendendo: ${nome}`}
        className="flex h-9 items-center justify-center rounded-lg bg-chrome-active"
      >
        <Building2 className="h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
        <span className="sr-only">Atendendo: {nome}</span>
      </div>
    );
  }

  return (
    <div className="rounded-lg bg-chrome-active px-2.5 py-2">
      <div className="flex items-center gap-2">
        <Building2 className="h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
        <div className="min-w-0 flex-1">
          <p className="text-[0.625rem] font-semibold uppercase tracking-wide text-chrome-fg-subtle">
            Atendendo
          </p>
          <p className="truncate text-xs font-semibold text-chrome-fg" title={clienteAtivo.nome}>
            {clienteAtivo.nome_fantasia || clienteAtivo.nome}
          </p>
        </div>
        <button
          type="button"
          onClick={limpar}
          aria-label="Sair do ambiente deste cliente"
          title="Sair do ambiente deste cliente"
          className="rounded p-1 text-chrome-fg-subtle transition-colors hover:bg-chrome-muted hover:text-chrome-fg"
        >
          <X className="h-3.5 w-3.5" aria-hidden="true" />
        </button>
      </div>
    </div>
  );
}
