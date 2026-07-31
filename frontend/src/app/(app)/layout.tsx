"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import {
  Activity,
  Bell,
  Building2,
  ChevronDown,
  ClipboardList,
  Database,
  Factory,
  FileBarChart,
  FileText,
  Home,
  LayoutDashboard,
  LogOut,
  Menu,
  Pin,
  PinOff,
  Wrench,
  X,
  type LucideIcon,
} from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useClienteAtivo } from "@/lib/cliente-ativo";
import type { User } from "@/lib/types";
import { Spinner, ThemeToggle, cn } from "@/components/ui";
import { ClienteSwitcher } from "@/components/cliente-switcher";

type NavItem = {
  href: string;
  label: string;
  icon: LucideIcon;
  children?: { href: string; label: string }[];
};

// Submenu "Dados de sistema" — só tabelas de referência do sistema.
// Áreas/Setores saíram daqui: são dados do CLIENTE, ficam sob o menu Clientes.
const DADOS_SISTEMA: { href: string; label: string }[] = [
  { href: "/cadastros?item=normas", label: "Normas (NBRs)" },
  { href: "/cadastros?item=tecnologias", label: "Tecnologias de análise" },
  { href: "/cadastros?item=instrumentos", label: "Instrumentação" },
  { href: "/cadastros?item=tipos-equipamento", label: "Tipos de equipamento" },
  { href: "/cadastros?item=tipos-componente", label: "Tipos de componente" },
  { href: "/cadastros?item=tipos-anomalia", label: "Tipos de anomalia" },
  { href: "/cadastros?item=tipos-recomendacao", label: "Tipos de recomendação" },
  { href: "/cadastros?item=criticidades", label: "Tipos de criticidade" },
  { href: "/cadastros?item=classificacoes-inspecao", label: "Classificações de inspeção" },
  { href: "/cadastros?item=tipos-inspecao", label: "Tipos de inspeção" },
  { href: "/cadastros?item=falhas-recorrentes", label: "Falhas recorrentes" },
  { href: "/cadastros?item=grupos-acesso", label: "Grupos de acesso" },
];

// Estrutura do cliente ativo — só aparece sob "Clientes" quando há um ativo.
const ESTRUTURA_CLIENTE: { href: string; label: string }[] = [
  { href: "/cadastros?item=areas", label: "Áreas" },
  { href: "/cadastros?item=setores", label: "Setores" },
  { href: "/equipamentos", label: "Equipamentos" },
  { href: "/rotas", label: "Rotas" },
];

// Menu da equipe interna. Os filhos de "Clientes" são injetados só quando há
// um cliente ativo (ver montarNavInterno).
const NAV_INTERNO: NavItem[] = [
  { href: "/clientes", label: "Clientes", icon: Building2 },
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/inspecoes", label: "Inspeções", icon: ClipboardList },
  { href: "/osps", label: "Ordens de Serviço", icon: Wrench },
  { href: "/laudos", label: "Laudos", icon: FileText },
  { href: "/relatorios", label: "Relatórios", icon: FileBarChart },
  { href: "/cadastros", label: "Dados de sistema", icon: Database, children: DADOS_SISTEMA },
  { href: "/prestadores", label: "Prestadores", icon: Factory },
];

// Menu do cliente externo (Portal — Anexo I 2.7): só leitura do próprio parque.
const NAV_CLIENTE: NavItem[] = [
  { href: "/portal", label: "Início", icon: Home },
  { href: "/inspecoes", label: "Inspeções", icon: ClipboardList },
  { href: "/osps", label: "Ordens de Serviço", icon: Wrench },
  { href: "/equipamentos", label: "Equipamentos", icon: Activity },
  { href: "/laudos", label: "Laudos", icon: FileText },
  { href: "/relatorios", label: "Relatórios", icon: FileBarChart },
];

function montarNavInterno(temClienteAtivo: boolean): NavItem[] {
  return NAV_INTERNO.map((item) =>
    item.href === "/clientes"
      ? { ...item, children: temClienteAtivo ? ESTRUTURA_CLIENTE : undefined }
      : item
  );
}

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
  colapsada = false,
  fixada = false,
  onNavigate,
  onLogout,
  onTogglePin,
}: {
  items: NavItem[];
  pathname: string;
  user: User;
  colapsada?: boolean;
  fixada?: boolean;
  onNavigate?: () => void;
  onLogout: () => void;
  onTogglePin?: () => void;
}) {
  const { clienteAtivo, limpar: limparCliente } = useClienteAtivo();
  const [submenus, setSubmenus] = useState<Record<string, boolean>>(() => ({
    "/cadastros": pathname.startsWith("/cadastros"),
  }));

  return (
    <div className="flex h-full flex-col">
      {/* Marca */}
      <div className={cn("flex items-center py-5", colapsada ? "justify-center px-2" : "gap-2.5 px-5")}>
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-accent to-accent-2 font-bold text-white shadow-sm">
          T
        </div>
        {!colapsada && (
          <div>
            <p className="text-sm font-semibold tracking-tight text-fg">ThermoProActive</p>
            <p className="text-[11px] text-fg-subtle">Manutenção Preditiva</p>
          </div>
        )}
      </div>

      <nav className="flex-1 space-y-0.5 overflow-y-auto px-3 py-2">
        {items.map((item) => {
          const active = pathname.startsWith(item.href);
          const Icon = item.icon;

          // Grupo com submenu — só no modo expandido; colapsado vira link direto.
          // O rótulo navega para a página; a setinha expande/recolhe o submenu.
          if (item.children && !colapsada) {
            const aberto = submenus[item.href] ?? (item.href === "/clientes" ? true : active);
            return (
              <div key={item.href}>
                <div
                  className={cn(
                    "relative flex items-center rounded-lg pr-1 transition-colors duration-150",
                    active ? "bg-accent-subtle" : "hover:bg-surface-muted"
                  )}
                >
                  {active && (
                    <span className="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-full bg-accent" />
                  )}
                  <Link
                    href={item.href}
                    onClick={onNavigate}
                    className={cn(
                      "flex flex-1 items-center gap-3 px-3 py-2 text-sm font-medium",
                      active ? "text-accent-subtle-fg" : "text-fg-muted"
                    )}
                  >
                    <Icon className="h-5 w-5 shrink-0" />
                    {item.label}
                  </Link>
                  <button
                    onClick={() => setSubmenus((s) => ({ ...s, [item.href]: !aberto }))}
                    aria-label={aberto ? "Recolher submenu" : "Expandir submenu"}
                    className="rounded p-1 text-fg-subtle transition-colors hover:text-fg"
                  >
                    <ChevronDown className={cn("h-4 w-4 transition-transform", aberto && "rotate-180")} />
                  </button>
                </div>
                {aberto && (
                  <div className="mb-1 ml-5 space-y-0.5 border-l border-border pl-2">
                    {item.children.map((c) => (
                      <Link
                        key={c.href}
                        href={c.href}
                        onClick={onNavigate}
                        className="block rounded-md px-3 py-1.5 text-[13px] text-fg-muted transition-colors hover:bg-surface-muted hover:text-fg"
                      >
                        {c.label}
                      </Link>
                    ))}
                  </div>
                )}
              </div>
            );
          }

          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={onNavigate}
              aria-current={active ? "page" : undefined}
              title={colapsada ? item.label : undefined}
              className={cn(
                "relative flex items-center rounded-lg py-2 text-sm font-medium transition-colors duration-150",
                colapsada ? "justify-center px-2" : "gap-3 px-3",
                active
                  ? "bg-accent-subtle text-accent-subtle-fg"
                  : "text-fg-muted hover:bg-surface-muted hover:text-fg"
              )}
            >
              {active && !colapsada && (
                <span className="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-full bg-accent" />
              )}
              <Icon className="h-5 w-5 shrink-0" />
              {!colapsada && item.label}
            </Link>
          );
        })}
      </nav>

      {/* Fixar aberto / desafixar (aparece só quando expandida, no desktop) */}
      {onTogglePin && !colapsada && (
        <div className="px-3 pb-1">
          <button
            onClick={onTogglePin}
            title={fixada ? "Desafixar — recolher ao tirar o mouse" : "Fixar o menu aberto"}
            className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-xs font-medium text-fg-subtle transition-colors hover:bg-surface-muted hover:text-fg"
          >
            {fixada ? <PinOff className="h-4 w-4 shrink-0" /> : <Pin className="h-4 w-4 shrink-0" />}
            {fixada ? "Desafixar" : "Fixar aberto"}
          </button>
        </div>
      )}

      {/* Rodapé */}
      <div className="border-t border-border p-3">
        {/* Cliente ativo (só no modo expandido — no colapsado, o chip do topo mostra). */}
        {!colapsada &&
          (clienteAtivo ? (
            <div className="mb-2 rounded-lg border border-accent/30 bg-accent-subtle px-2.5 py-2">
              <div className="flex items-center gap-2">
                <Building2 className="h-4 w-4 shrink-0 text-accent" />
                <div className="min-w-0 flex-1">
                  <p className="text-[10px] font-semibold uppercase tracking-wide text-accent-subtle-fg">
                    Atendendo
                  </p>
                  <p className="truncate text-xs font-semibold text-fg" title={clienteAtivo.nome}>
                    {clienteAtivo.nome_fantasia || clienteAtivo.nome}
                  </p>
                </div>
                <button
                  onClick={limparCliente}
                  aria-label="Sair do ambiente do cliente"
                  className="rounded p-1 text-fg-subtle transition-colors hover:bg-surface hover:text-fg"
                  title="Sair do ambiente do cliente"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          ) : (
            <Link
              href="/clientes"
              onClick={onNavigate}
              className="mb-2 block rounded-lg border border-dashed border-border-strong px-2.5 py-2 text-center text-[11px] text-fg-subtle transition-colors hover:border-accent hover:text-fg"
            >
              Nenhum cliente ativo · escolher
            </Link>
          ))}

        <div className={cn("flex items-center py-1.5", colapsada ? "flex-col gap-2" : "gap-3 px-2")}>
          <div
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-surface-muted text-sm font-semibold text-fg-muted"
            title={colapsada ? user.nome : undefined}
          >
            {iniciais(user.nome)}
          </div>
          {!colapsada && (
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-fg">{user.nome}</p>
              <p className="truncate text-[11px] text-fg-subtle" title={user.perfil_display}>
                {user.grupo_acesso}
              </p>
            </div>
          )}
          <button
            onClick={onLogout}
            aria-label="Sair"
            title="Sair"
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
  const { clienteAtivo } = useClienteAtivo();
  const router = useRouter();
  const pathname = usePathname();
  const [naoLidas, setNaoLidas] = useState(0);
  const [scrolled, setScrolled] = useState(false);
  const [drawer, setDrawer] = useState(false);
  // Padrão: menu recolhido (trilho de ícones) que expande ao passar o mouse.
  // "fixada" trava o menu aberto (empurra o conteúdo); preferência salva.
  const [fixada, setFixada] = useState(false);
  const [hoverMenu, setHoverMenu] = useState(false);
  const menuExpandido = fixada || hoverMenu;

  useEffect(() => {
    try {
      setFixada(localStorage.getItem("tpa-sidebar-fixada") === "1");
    } catch {
      /* localStorage indisponível */
    }
  }, []);

  function togglePin() {
    setFixada((v) => {
      const nova = !v;
      try {
        localStorage.setItem("tpa-sidebar-fixada", nova ? "1" : "0");
      } catch {
        /* ignore */
      }
      if (nova) setHoverMenu(false);
      return nova;
    });
  }

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

  const items = user.is_cliente ? NAV_CLIENTE : montarNavInterno(!!clienteAtivo);
  const logout = () => {
    signOut();
    router.replace("/login");
  };

  return (
    <div className="flex h-screen overflow-hidden bg-bg">
      {/* Sidebar (desktop): trilho de 68px que expande sobre o conteúdo ao passar
          o mouse. Fixada, ocupa a largura cheia e empurra o conteúdo. */}
      <aside
        className={cn(
          "no-print relative hidden shrink-0 transition-[width] duration-200 lg:block",
          fixada ? "w-64" : "w-[68px]"
        )}
      >
        <div
          onMouseEnter={() => !fixada && setHoverMenu(true)}
          onMouseLeave={() => setHoverMenu(false)}
          className={cn(
            "absolute inset-y-0 left-0 border-r border-border bg-surface transition-[width] duration-200",
            menuExpandido ? "w-64" : "w-[68px]",
            menuExpandido && !fixada ? "z-40 shadow-xl" : "z-10"
          )}
        >
          <SidebarContent
            items={items}
            pathname={pathname}
            user={user}
            colapsada={!menuExpandido}
            fixada={fixada}
            onLogout={logout}
            onTogglePin={togglePin}
          />
        </div>
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
          {/* Seletor do cliente ativo (só faz sentido para a equipe interna). */}
          {user.is_interno && <ClienteSwitcher />}
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
