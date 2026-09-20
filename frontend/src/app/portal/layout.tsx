"use client";

import { usePathname } from "next/navigation";
import { AppShell } from "@/components/shell/app-shell";
import { RouteGuard } from "@/components/shell/guard";
import { ToastProvider } from "@/components/ds";
import { navPortal } from "@/lib/nav";

/**
 * PORTAL DO CLIENTE — Anexo I 2.7.
 *
 * Experiência separada de propósito: menu curto, sem submenu, sem vocabulário
 * interno, tudo em leitura. O cliente entra para responder uma pergunta só —
 * "o que está acontecendo com a minha operação?" — e o portal é organizado em
 * volta disso.
 *
 * Nenhuma função administrativa é montada aqui. Mesmo que alguém descubra uma
 * URL interna, o guarda de área a traduz para o equivalente do portal, e o
 * backend recusa qualquer escrita (InternoEditaClienteVisualiza).
 */
export default function PortalLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const publica = [
    "/portal/login", "/portal/cadastro", "/portal/verificar-email",
    "/portal/esqueci-senha", "/portal/redefinir-senha", "/portal/primeiro-acesso",
  ].some((rota) => pathname === rota) || pathname.startsWith("/portal/convite/");

  if (publica) return <>{children}</>;

  return (
    <ToastProvider>
      <RouteGuard area="portal">
        {(user) => (
          <AppShell
            user={user}
            grupos={navPortal()}
            inicioHref="/portal/dashboard"
            perfilHref="/portal/perfil"
            alertasHref="/portal/alertas"
            ajudaHref="/portal/ajuda"
          >
            {children}
          </AppShell>
        )}
      </RouteGuard>
    </ToastProvider>
  );
}
