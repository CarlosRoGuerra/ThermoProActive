"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import {
  Activity,
  Bell,
  Building2,
  ClipboardList,
  Database,
  Factory,
  FileBarChart,
  FileText,
  Home,
  LayoutDashboard,
  LogOut,
  Menu,
  Wrench,
  type LucideIcon,
} from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { User } from "@/lib/types";
import { Spinner, ThemeToggle, cn } from "@/components/ui";

type NavItem = {
  href: string;
  label: string;
  icon: LucideIcon;
  cliente: boolean;
  interno: boolean;
};

// "Início" é a home do Portal do Cliente (Anexo I 2.7); o "Dashboard" operacional/
// executivo é a home da equipe interna. As demais telas servem aos dois perfis
// (a API restringe os dados do cliente ao próprio parque — somente leitura).
const NAV: NavItem[] = [
  { href: "/portal", label: "Início", icon: Home, cliente: true, interno: false },
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard, cliente: false, interno: true },
  { href: "/inspecoes", label: "Inspeções", icon: ClipboardList, cliente: true, interno: true },
  { href: "/osps", label: "Ordens de Serviço", icon: Wrench, cliente: true, interno: true },
  { href: "/equipamentos", label: "Equipamentos", icon: Activity, cliente: true, interno: true },
  { href: "/laudos", label: "Laudos", icon: FileText, cliente: true, interno: true },
  { href: "/relatorios", label: "Relatórios", icon: FileBarChart, cliente: true, interno: true },
  { href: "/clientes", label: "Clientes", icon: Building2, cliente: false, interno: true },
  { href: "/prestadores", label: "Prestadores", icon: Factory, cliente: false, interno: true },
  { href: "/cadastros", label: "Dados de sistema", icon: Database, cliente: false, interno: true },
];

function iniciais(nome: string) {
  return nome
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0])
    .join("")
    .toUpperCase();
}

function SidebarContent({
  items,
  pathname,
  user,
  onNavigate,
  onLogout,
}: {
  items: NavItem[];
  pathname: string;
  user: User;
  onNavigate?: () => void;
  onLogout: () => void;
}) {
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2.5 px-5 py-5">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-accent to-accent-2 font-bold text-white shadow-sm">
          T
        </div>
        <div>
          <p className="text-sm font-semibold tracking-tight text-fg">ThermoProActive</p>
          <p className="text-[11px] text-fg-subtle">Manutenção Preditiva</p>
        </div>
      </div>

      <nav className="flex-1 space-y-0.5 px-3 py-2">
        {items.map((item) => {
          const active = pathname.startsWith(item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={onNavigate}
              aria-current={active ? "page" : undefined}
              className={cn(
                "relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors duration-150",
                active
                  ? "bg-accent-subtle text-accent-subtle-fg"
                  : "text-fg-muted hover:bg-surface-muted hover:text-fg"
              )}
            >
              {active && (
                <span className="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-full bg-accent" />
              )}
              <Icon className="h-5 w-5 shrink-0" />
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-border p-3">
        <div className="flex items-center gap-3 px-2 py-1.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-surface-muted text-sm font-semibold text-fg-muted">
            {iniciais(user.nome)}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-fg">{user.nome}</p>
            <p className="truncate text-[11px] text-fg-subtle" title={user.perfil_display}>
              {user.grupo_acesso}
            </p>
          </div>
          <button
            onClick={onLogout}
            aria-label="Sair"
            className="rounded-md p-1.5 text-fg-subtle transition-colors hover:bg-surface-muted hover:text-fg"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, loading, signOut } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [naoLidas, setNaoLidas] = useState(0);
  const [scrolled, setScrolled] = useState(false);
  const [drawer, setDrawer] = useState(false);

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [user, loading, router]);

  const carregarResumo = useCallback(() => {
    if (!user) return;
    api<{ nao_lidas: number }>("/notificacoes/resumo/")
      .then((d) => setNaoLidas(d.nao_lidas))
      .catch(() => {});
  }, [user]);

  useEffect(() => {
    carregarResumo();
    const t = setInterval(carregarResumo, 30000);
    return () => clearInterval(t);
  }, [carregarResumo, pathname]);

  // Fecha o drawer ao trocar de rota.
  useEffect(() => setDrawer(false), [pathname]);

  if (loading || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner />
      </div>
    );
  }

  const items = NAV.filter((n) => (user.is_cliente ? n.cliente : n.interno));
  const logout = () => {
    signOut();
    router.replace("/login");
  };

  return (
    <div className="flex h-screen overflow-hidden bg-bg">
      {/* Sidebar fixa (desktop) */}
      <aside className="no-print hidden w-64 shrink-0 border-r border-border bg-surface lg:block">
        <SidebarContent items={items} pathname={pathname} user={user} onLogout={logout} />
      </aside>

      {/* Drawer (mobile) */}
      <AnimatePresence>
        {drawer && (
          <div className="lg:hidden">
            <motion.div
              className="fixed inset-0 z-40 bg-fg/30 backdrop-blur-sm"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setDrawer(false)}
            />
            <motion.aside
              className="fixed inset-y-0 left-0 z-50 w-64 border-r border-border bg-surface"
              initial={{ x: -280 }}
              animate={{ x: 0 }}
              exit={{ x: -280 }}
              transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
            >
              <SidebarContent
                items={items}
                pathname={pathname}
                user={user}
                onNavigate={() => setDrawer(false)}
                onLogout={logout}
              />
            </motion.aside>
          </div>
        )}
      </AnimatePresence>

      {/* Coluna principal */}
      <div className="flex flex-1 flex-col overflow-hidden">
        <header
          className={cn(
            "no-print z-20 flex h-16 shrink-0 items-center gap-3 px-4 transition-colors duration-200 lg:px-8",
            scrolled ? "border-b border-border bg-surface/80 backdrop-blur-md" : "border-b border-transparent"
          )}
        >
          <button
            onClick={() => setDrawer(true)}
            aria-label="Abrir menu"
            className="rounded-lg p-2 text-fg-muted transition-colors hover:bg-surface-muted hover:text-fg lg:hidden"
          >
            <Menu className="h-5 w-5" />
          </button>
          <div className="flex-1" />
          <ThemeToggle />
          <Link
            href="/notificacoes"
            aria-label="Notificações"
            className="relative rounded-lg p-2 text-fg-muted transition-colors hover:bg-surface-muted hover:text-fg"
          >
            <Bell className="h-5 w-5" />
            {naoLidas > 0 && (
              <span className="absolute right-0.5 top-0.5 flex h-4 min-w-[16px] items-center justify-center rounded-full bg-danger px-1 text-[10px] font-bold leading-none text-white">
                {naoLidas > 9 ? "9+" : naoLidas}
              </span>
            )}
          </Link>
        </header>

        <main
          onScroll={(e) => setScrolled(e.currentTarget.scrollTop > 4)}
          className="flex-1 overflow-y-auto"
        >
          <div className="mx-auto max-w-6xl px-4 py-6 lg:px-8 lg:py-8">{children}</div>
        </main>
      </div>
    </div>
  );
}
