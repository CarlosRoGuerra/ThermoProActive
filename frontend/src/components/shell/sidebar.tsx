"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ChevronDown, PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { cn } from "@/components/ds";
import { Logo, Simbolo } from "@/components/ds";
import type { GrupoNav, ItemNav } from "@/lib/nav";
import { can } from "@/lib/permissions";
import type { User } from "@/lib/types";

/* ==========================================================================
   Sidebar
   --------------------------------------------------------------------------
   Aço escuro nos dois temas: a navegação é o "chassi" do produto e fica
   visivelmente separada do conteúdo. Dois estados no desktop — trilho de ícones
   (padrão, devolve espaço à tela) e expandida (preferência salva). No celular
   ela não existe: vira Drawer (ver AppShell).

   Decisões de acessibilidade:
     • <nav> com aria-label, grupos em <ul>/<li> e cabeçalhos de seção reais;
     • item ativo tem aria-current="page" — não só a cor da barrinha;
     • no trilho, cada ícone tem título (tooltip nativo) e rótulo para leitor
       de tela, porque ícone sozinho não é rótulo;
     • submenu é <button aria-expanded> + região controlada, navegável por teclado.
   ========================================================================== */

function itemAtivo(item: ItemNav, pathname: string): boolean {
  const casa = (base: string) => pathname === base || pathname.startsWith(`${base}/`);
  if (casa(item.href.split("?")[0])) return true;
  return (item.tambemAtivoEm ?? []).some(casa);
}

function ItemLink({
  href,
  label,
  ativo,
  colapsada,
  onNavegar,
  icone: Icone,
  contador,
}: {
  href: string;
  label: string;
  ativo: boolean;
  colapsada: boolean;
  onNavegar?: () => void;
  icone: ItemNav["icon"];
  contador?: number;
}) {
  return (
    <Link
      href={href}
      onClick={onNavegar}
      aria-current={ativo ? "page" : undefined}
      title={colapsada ? label : undefined}
      className={cn(
        "group relative flex items-center rounded-lg py-2 text-sm font-medium transition-colors duration-fast",
        colapsada ? "justify-center px-2" : "gap-3 px-3",
        ativo
          ? "bg-chrome-active text-chrome-fg"
          : "text-chrome-fg-muted hover:bg-chrome-muted hover:text-chrome-fg"
      )}
    >
      {/* Marcador de item ativo: segunda pista além da cor de fundo. */}
      {ativo && (
        <span
          className="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-r-full bg-primary"
          aria-hidden="true"
        />
      )}
      <Icone className="h-[1.125rem] w-[1.125rem] shrink-0" aria-hidden="true" />
      {colapsada ? (
        <span className="sr-only">{label}</span>
      ) : (
        <span className="min-w-0 flex-1 truncate">{label}</span>
      )}
      {contador !== undefined && contador > 0 && (
        <span
          className={cn(
            "flex items-center justify-center rounded-full bg-danger font-bold leading-none text-white",
            colapsada
              ? "absolute right-1.5 top-1.5 h-2 w-2"
              : "h-4 min-w-4 px-1 text-2xs"
          )}
          aria-label={`${contador} não lidos`}
        >
          {!colapsada && (contador > 9 ? "9+" : contador)}
        </span>
      )}
    </Link>
  );
}

/**
 * Um sub-item está ativo quando a rota bate E, no caso das telas de dados de
 * sistema, quando o parâmetro `?item=` também bate — é o que diferencia
 * "Normas" de "Instrumentação", que compartilham a rota /cadastros.
 */
function subItemAtivo(href: string, pathname: string, itemAtual: string | null): boolean {
  const [base, query] = href.split("?");
  if (pathname !== base) return false;
  if (!query) return true;
  const esperado = new URLSearchParams(query).get("item");
  return esperado === null || esperado === itemAtual;
}

function GrupoComSubmenu({
  item,
  pathname,
  onNavegar,
  contador,
}: {
  item: ItemNav;
  pathname: string;
  onNavegar?: () => void;
  contador?: number;
}) {
  const parametros = useSearchParams();
  const itemAtual = parametros?.get("item") ?? null;
  const ativo = itemAtivo(item, pathname);
  const [aberto, setAberto] = useState(ativo);
  const Icone = item.icon;

  // Navegar para dentro do grupo abre o submenu — o usuário não fica perdido.
  useEffect(() => {
    if (ativo) setAberto(true);
  }, [ativo]);

  return (
    <li>
      <div
        className={cn(
          "relative flex items-center rounded-lg pr-1 transition-colors duration-fast",
          ativo ? "bg-chrome-active" : "hover:bg-chrome-muted"
        )}
      >
        {ativo && (
          <span
            className="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-r-full bg-primary"
            aria-hidden="true"
          />
        )}
        <Link
          href={item.href}
          onClick={onNavegar}
          aria-current={ativo ? "page" : undefined}
          className={cn(
            "flex min-w-0 flex-1 items-center gap-3 px-3 py-2 text-sm font-medium",
            ativo ? "text-chrome-fg" : "text-chrome-fg-muted hover:text-chrome-fg"
          )}
        >
          <Icone className="h-[1.125rem] w-[1.125rem] shrink-0" aria-hidden="true" />
          <span className="truncate">{item.label}</span>
        </Link>
        {contador !== undefined && contador > 0 && (
          <span className="mr-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-danger px-1 text-2xs font-bold leading-none text-white">
            {contador > 9 ? "9+" : contador}
          </span>
        )}
        <button
          type="button"
          onClick={() => setAberto((v) => !v)}
          aria-expanded={aberto}
          aria-label={aberto ? `Recolher ${item.label}` : `Expandir ${item.label}`}
          className="rounded p-1 text-chrome-fg-subtle transition-colors hover:text-chrome-fg"
        >
          <ChevronDown
            className={cn("h-4 w-4 transition-transform duration-fast", aberto && "rotate-180")}
            aria-hidden="true"
          />
        </button>
      </div>

      {aberto && item.filhos && (
        <ul className="mb-1 ml-[1.4375rem] mt-0.5 space-y-px border-l border-chrome-border pl-2.5">
          {item.filhos.map((f) => {
            const filhoAtivo = subItemAtivo(f.href, pathname, itemAtual);
            return (
              <li key={f.href}>
                <Link
                  href={f.href}
                  onClick={onNavegar}
                  className={cn(
                    "block truncate rounded-md px-2.5 py-1.5 text-[0.8125rem] transition-colors duration-fast",
                    filhoAtivo
                      ? "text-chrome-fg"
                      : "text-chrome-fg-muted hover:bg-chrome-muted hover:text-chrome-fg"
                  )}
                >
                  {f.label}
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </li>
  );
}

export function SidebarContent({
  grupos,
  pathname,
  user,
  colapsada = false,
  fixada = false,
  onNavegar,
  onAlternarFixacao,
  contadores,
  rodape,
  inicioHref,
}: {
  grupos: GrupoNav[];
  pathname: string;
  user: User;
  colapsada?: boolean;
  fixada?: boolean;
  onNavegar?: () => void;
  onAlternarFixacao?: () => void;
  /** Valores dos contadores declarados na navegação. */
  contadores?: { alertas?: number };
  /** Bloco acima da área do usuário (ex.: cliente em atendimento). */
  rodape?: React.ReactNode;
  inicioHref: string;
}) {
  return (
    <div className="flex h-full flex-col bg-chrome">
      {/* Marca — link para a página inicial do portal do usuário. */}
      <div className={cn("flex items-center py-4", colapsada ? "justify-center px-2" : "px-4")}>
        <Link
          href={inicioHref}
          onClick={onNavegar}
          className="flex min-w-0 items-center rounded-lg"
          aria-label="Pred Ativos — página inicial"
        >
          {colapsada ? <Simbolo tamanho="sm" /> : <Logo tamanho="md" onChrome />}
        </Link>
      </div>

      <nav aria-label="Navegação principal" className="flex-1 overflow-y-auto overflow-x-hidden px-2.5 pb-2">
        {grupos.map((grupo, i) => {
          const visiveis = grupo.itens.filter((item) => !item.exige || can(user, item.exige));
          if (visiveis.length === 0) return null;
          return (
            <div key={grupo.titulo ?? `grupo-${i}`} className={i > 0 ? "mt-4" : ""}>
              {grupo.titulo && !colapsada && (
                <h2 className="mb-1.5 px-3 text-2xs font-semibold uppercase tracking-[0.08em] text-chrome-fg-subtle">
                  {grupo.titulo}
                </h2>
              )}
              {/* No trilho, uma linha substitui o título da seção. */}
              {grupo.titulo && colapsada && (
                <div className="mx-2 mb-2 h-px bg-chrome-border" role="separator" aria-label={grupo.titulo} />
              )}
              <ul className="space-y-px">
                {visiveis.map((item) => {
                  const contador = item.contador ? contadores?.[item.contador] : undefined;
                  const filhosVisiveis = item.filhos?.filter((f) => !f.exige || can(user, f.exige));

                  if (filhosVisiveis?.length && !colapsada) {
                    return (
                      <GrupoComSubmenu
                        key={item.href}
                        item={{ ...item, filhos: filhosVisiveis }}
                        pathname={pathname}
                        onNavegar={onNavegar}
                        contador={contador}
                      />
                    );
                  }
                  return (
                    <li key={item.href}>
                      <ItemLink
                        href={item.href}
                        label={item.label}
                        icone={item.icon}
                        ativo={itemAtivo(item, pathname)}
                        colapsada={colapsada}
                        onNavegar={onNavegar}
                        contador={contador}
                      />
                    </li>
                  );
                })}
              </ul>
            </div>
          );
        })}
      </nav>

      {/* Fixar/soltar o menu — só faz sentido no desktop expandido. */}
      {onAlternarFixacao && !colapsada && (
        <div className="px-2.5 pb-1">
          <button
            type="button"
            onClick={onAlternarFixacao}
            aria-pressed={fixada}
            className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-xs font-medium text-chrome-fg-subtle transition-colors hover:bg-chrome-muted hover:text-chrome-fg"
          >
            {fixada ? (
              <PanelLeftClose className="h-4 w-4 shrink-0" aria-hidden="true" />
            ) : (
              <PanelLeftOpen className="h-4 w-4 shrink-0" aria-hidden="true" />
            )}
            {fixada ? "Recolher menu" : "Manter menu aberto"}
          </button>
        </div>
      )}

      {rodape && <div className="border-t border-chrome-border p-2.5">{rodape}</div>}
    </div>
  );
}
