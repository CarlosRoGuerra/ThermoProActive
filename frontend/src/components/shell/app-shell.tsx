"use client";

import { useEffect, useState, type ReactNode } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import { Bell, Menu, X } from "lucide-react";
import { IconButton, OfflineBanner, ThemeToggle, cn } from "@/components/ds";
import { Breadcrumb } from "@/components/ds";
import { RodapeMarca } from "./rodape";
import { SidebarContent } from "./sidebar";
import { UserBlock, UserMenu } from "./user-menu";
import { useAlertas } from "@/lib/alertas";
import { useAuth } from "@/lib/auth";
import type { GrupoNav } from "@/lib/nav";
import { trilhaDe } from "@/lib/nav";
import type { User } from "@/lib/types";

/* ==========================================================================
   AppShell — o quadro compartilhado pelos dois portais.
   --------------------------------------------------------------------------
   Estrutura, de fora para dentro:
     skip-link → sidebar (desktop) / drawer (mobile) → topbar → <main>

   O que ele garante para toda a aplicação:
     • um único <h1> por página (o PageHeader), landmarks corretos
       (banner/navigation/main), e link de salto para o conteúdo;
     • trilha de navegação automática, derivada da rota;
     • aviso de rede caída;
     • estado do menu (fixado/trilho) salvo por usuário no navegador.
   ========================================================================== */

export function AppShell({
  user,
  grupos,
  inicioHref,
  perfilHref,
  alertasHref,
  ajudaHref,
  /** Bloco extra na topbar (ex.: seletor de cliente ativo, no portal interno). */
  acoesTopbar,
  /**
   * Bloco no rodapé da sidebar acima do usuário (ex.: cliente em atendimento).
   * Recebe `colapsada` porque no trilho (68px) só cabe ícone: sem isso o bloco
   * mantém a largura da sidebar expandida e vaza para fora dela.
   */
  rodapeSidebar,
  children,
}: {
  user: User;
  grupos: GrupoNav[];
  inicioHref: string;
  perfilHref: string;
  alertasHref: string;
  ajudaHref?: string;
  acoesTopbar?: ReactNode;
  rodapeSidebar?: (colapsada: boolean) => ReactNode;
  children: ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const { signOut } = useAuth();
  const { naoLidas } = useAlertas();

  const [drawer, setDrawer] = useState(false);
  const [fixada, setFixada] = useState(false);
  const [hover, setHover] = useState(false);
  const [rolou, setRolou] = useState(false);
  const [offline, setOffline] = useState(false);
  const expandida = fixada || hover;

  useEffect(() => {
    try {
      setFixada(localStorage.getItem("tpa-sidebar-fixada") === "1");
    } catch {
      /* storage indisponível — usa o padrão (trilho) */
    }
  }, []);

  // Estado da rede: a faixa só aparece quando o navegador avisa que caiu.
  useEffect(() => {
    const atualizar = () => setOffline(!navigator.onLine);
    atualizar();
    window.addEventListener("online", atualizar);
    window.addEventListener("offline", atualizar);
    return () => {
      window.removeEventListener("online", atualizar);
      window.removeEventListener("offline", atualizar);
    };
  }, []);

  // Trocar de rota fecha o drawer e devolve a rolagem ao topo do conteúdo.
  useEffect(() => setDrawer(false), [pathname]);

  function alternarFixacao() {
    setFixada((atual) => {
      const nova = !atual;
      try {
        localStorage.setItem("tpa-sidebar-fixada", nova ? "1" : "0");
      } catch {
        /* segue só nesta sessão */
      }
      if (nova) setHover(false);
      return nova;
    });
  }

  async function sair() {
    await signOut();
    router.replace(user.is_cliente ? "/portal/login" : "/admin/login");
  }

  const trilha = trilhaDe(pathname);
  const contadores = { alertas: naoLidas };

  const rodape = (
    <div className="space-y-1.5">
      {rodapeSidebar?.(!expandida)}
      <UserMenu
        user={user}
        onSair={sair}
        perfilHref={perfilHref}
        ajudaHref={ajudaHref}
        variante="sidebar"
        colapsada={!expandida}
      />
    </div>
  );

  return (
    <div className="flex h-[100dvh] flex-col overflow-hidden bg-bg">
      {offline && <OfflineBanner />}

      <a href="#conteudo" className="skip-link">
        Ir para o conteúdo
      </a>

      <div className="flex min-h-0 flex-1">
        {/* ---------- Sidebar (desktop) ----------
            Trilho de ícones que expande sobre o conteúdo ao passar o mouse;
            fixada, ela empurra o conteúdo e não cobre nada. */}
        <aside
          className={cn(
            "no-print relative hidden shrink-0 transition-[width] duration-normal lg:block",
            fixada ? "w-sidebar" : "w-rail"
          )}
        >
          <div
            onMouseEnter={() => !fixada && setHover(true)}
            onMouseLeave={() => setHover(false)}
            className={cn(
              "absolute inset-y-0 left-0 border-r border-chrome-border transition-[width] duration-normal",
              expandida ? "w-sidebar" : "w-rail",
              expandida && !fixada ? "z-rail shadow-rail" : "z-raised"
            )}
          >
            <SidebarContent
              grupos={grupos}
              pathname={pathname}
              user={user}
              colapsada={!expandida}
              fixada={fixada}
              onAlternarFixacao={alternarFixacao}
              contadores={contadores}
              rodape={rodape}
              inicioHref={inicioHref}
            />
          </div>
        </aside>

        {/* ---------- Drawer (mobile) ---------- */}
        <AnimatePresence>
          {drawer && (
            <div className="lg:hidden">
              <motion.div
                className="fixed inset-0 z-drawer bg-overlay backdrop-blur-[2px]"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.16 }}
                onClick={() => setDrawer(false)}
                aria-hidden="true"
              />
              <motion.div
                role="dialog"
                aria-modal="true"
                aria-label="Menu de navegação"
                className="fixed inset-y-0 left-0 z-drawer flex w-[17rem] flex-col border-r border-chrome-border"
                initial={{ x: -288 }}
                animate={{ x: 0 }}
                exit={{ x: -288 }}
                transition={{ duration: 0.26, ease: [0.22, 1, 0.36, 1] }}
              >
                <div className="absolute right-2 top-3 z-raised">
                  <IconButton icon={X} label="Fechar menu" onClick={() => setDrawer(false)} onChrome />
                </div>
                <SidebarContent
                  grupos={grupos}
                  pathname={pathname}
                  user={user}
                  onNavegar={() => setDrawer(false)}
                  contadores={contadores}
                  inicioHref={inicioHref}
                  rodape={
                    <div className="space-y-1.5">
                      {rodapeSidebar?.(false)}
                      <UserBlock user={user} perfilHref={perfilHref} />
                      <button
                        type="button"
                        onClick={sair}
                        className="w-full rounded-lg px-2 py-2 text-left text-sm font-medium text-chrome-fg-muted transition-colors hover:bg-chrome-muted hover:text-chrome-fg"
                      >
                        Sair da conta
                      </button>
                    </div>
                  }
                />
              </motion.div>
            </div>
          )}
        </AnimatePresence>

        {/* ---------- Coluna principal ---------- */}
        <div className="flex min-w-0 flex-1 flex-col">
          <header
            className={cn(
              "no-print z-sticky flex h-topbar shrink-0 items-center gap-2 px-3 transition-colors duration-normal sm:px-4 lg:px-6",
              rolou ? "border-b border-border bg-surface/85 backdrop-blur-md" : "border-b border-transparent"
            )}
          >
            <IconButton
              icon={Menu}
              label="Abrir menu"
              onClick={() => setDrawer(true)}
              className="lg:hidden"
            />

            {/* Contexto da página. No celular a trilha sai: só o essencial cabe. */}
            <div className="hidden min-w-0 flex-1 sm:block">
              {trilha.length > 1 ? (
                <Breadcrumb itens={trilha} raiz={{ label: "Início", href: inicioHref }} />
              ) : (
                <span className="text-sm font-medium text-fg">{trilha[0]?.label ?? "Início"}</span>
              )}
            </div>
            <div className="min-w-0 flex-1 sm:hidden" />

            <div className="flex shrink-0 items-center gap-1">
              {acoesTopbar}
              <Link
                href={alertasHref}
                aria-label={naoLidas > 0 ? `Alertas — ${naoLidas} não lidos` : "Alertas"}
                className="relative inline-flex h-9 w-9 items-center justify-center rounded-lg text-fg-muted transition-colors hover:bg-surface-muted hover:text-fg"
              >
                <Bell className="h-4.5 w-4.5" aria-hidden="true" />
                {naoLidas > 0 && (
                  <span className="absolute right-1 top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-danger px-1 text-2xs font-bold leading-none text-white">
                    {naoLidas > 9 ? "9+" : naoLidas}
                  </span>
                )}
              </Link>
              <ThemeToggle />
              <div className="ml-1 hidden lg:block">
                <UserMenu user={user} onSair={sair} perfilHref={perfilHref} ajudaHref={ajudaHref} />
              </div>
            </div>
          </header>

          <main
            id="conteudo"
            onScroll={(e) => setRolou(e.currentTarget.scrollTop > 4)}
            className="flex-1 overflow-y-auto focus-visible:outline-none"
            tabIndex={-1}
          >
            <div className="page-shell">{children}</div>
            <RodapeMarca />
          </main>
        </div>
      </div>
    </div>
  );
}
