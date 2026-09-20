"use client";

import { useEffect, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { LoaderCircle } from "lucide-react";
import { Logo } from "@/components/ds";
import { useAuth } from "@/lib/auth";
import { can, destinoNoPortal, podeAcessarRota, rotaInicial, type Habilidade } from "@/lib/permissions";
import type { User } from "@/lib/types";

/* ==========================================================================
   Guarda de rota
   --------------------------------------------------------------------------
   IMPORTANTE: isto não é segurança — é navegação. Quem protege os dados é o
   DRF (ver apps/accounts/permissions.py). O guarda existe para que ninguém
   chegue a uma tela que só saberia devolver 403, e para que um cliente que
   clicou num link antigo de área interna seja levado ao equivalente do portal
   em vez de bater numa parede.

   Três desfechos possíveis:
     1. sem sessão            → /login
     2. área errada           → redireciona ao portal correto (traduz a rota)
     3. rota certa, sem nível → a página é renderizada pelo layout com
                                PermissionDenied, explicando o que falta
   ========================================================================== */

/** Tela de espera enquanto a sessão é verificada — com marca, não em branco. */
function Verificando() {
  return (
    <div className="flex min-h-[100dvh] flex-col items-center justify-center gap-5 bg-bg px-6">
      <Logo tamanho="lg" />
      <p
        role="status"
        className="flex items-center gap-2.5 text-sm text-fg-muted"
      >
        <LoaderCircle className="h-4 w-4 animate-spin text-primary" aria-hidden="true" />
        Verificando seu acesso…
      </p>
    </div>
  );
}

export function RouteGuard({
  /** Área que este layout representa. */
  area,
  children,
}: {
  area: "admin" | "portal";
  children: (user: User) => ReactNode;
}) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  const habilidadeDaArea: Habilidade = area === "admin" ? "area:admin" : "area:portal";
  const podeEstarAqui = can(user, habilidadeDaArea);

  useEffect(() => {
    if (loading) return;

    if (!user) {
      // Guarda o destino para voltar a ele depois de entrar.
      const destino = pathname && pathname !== "/" ? `?proximo=${encodeURIComponent(pathname)}` : "";
      router.replace(`/${area}/login${destino}`);
      return;
    }

    if (!podeEstarAqui) {
      // Cliente numa rota interna → equivalente no portal, preservando o /:id.
      // Equipe interna numa rota do portal → painel operacional.
      router.replace(user.is_cliente ? destinoNoPortal(pathname) : rotaInicial(user));
    }
  }, [loading, user, podeEstarAqui, pathname, router]);

  if (loading || !user || !podeEstarAqui) return <Verificando />;

  return <>{children(user)}</>;
}

/**
 * Bloqueio por permissão dentro de uma área correta.
 * Devolve `true` quando a rota atual não é permitida ao usuário — o layout então
 * mostra `PermissionDenied` no lugar do conteúdo, mantendo o menu e a saída.
 */
export function useRotaBloqueada(user: User): boolean {
  const pathname = usePathname();
  return !podeAcessarRota(user, pathname);
}
