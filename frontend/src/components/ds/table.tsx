"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  ChevronLeft,
  ChevronRight,
  MoreVertical,
  Search,
  type LucideIcon,
} from "lucide-react";
import { cn } from "./utils";
import { Card } from "./card";
import { Checkbox } from "./field";
import { IconButton } from "./button";
import { DropdownMenu, type ItemMenu } from "./overlay";
import { EmptyState, ErrorState, TableSkeleton } from "./feedback";
import { compararTexto, normalizar } from "@/lib/format";
import type { Falha } from "@/lib/erros";

/* ==========================================================================
   Primitivas de tabela — para tabelas artesanais (folha de campo, laudos).
   ========================================================================== */

export function Table({
  children,
  className = "",
  /** Quando true, a tabela não vem dentro de um Card (já está em um). */
  semMoldura = false,
  legenda,
}: {
  children: ReactNode;
  className?: string;
  semMoldura?: boolean;
  /** Descrição da tabela para leitor de tela (`<caption>` visualmente oculta). */
  legenda?: string;
}) {
  const tabela = (
    <div className="overflow-x-auto">
      <table className={cn("w-full text-sm", className)}>
        {legenda && <caption className="sr-only">{legenda}</caption>}
        {children}
      </table>
    </div>
  );
  if (semMoldura) return tabela;
  return (
    <Card padding={false} className="overflow-hidden">
      {tabela}
    </Card>
  );
}

export function THead({ children }: { children: ReactNode }) {
  return (
    <thead className="border-b border-border bg-surface-muted/50 text-left">
      <tr>{children}</tr>
    </thead>
  );
}

export function TH({
  children,
  className = "",
  scope = "col",
  colSpan,
}: {
  children?: ReactNode;
  className?: string;
  scope?: "col" | "row";
  colSpan?: number;
}) {
  return (
    <th
      scope={scope}
      colSpan={colSpan}
      className={cn(
        "whitespace-nowrap px-3 py-2.5 text-2xs font-semibold uppercase tracking-wide text-fg-subtle sm:px-4",
        className
      )}
    >
      {children}
    </th>
  );
}

export function TBody({ children }: { children: ReactNode }) {
  return <tbody className="divide-y divide-border">{children}</tbody>;
}

export function TR({
  children,
  className = "",
  onClick,
  tom,
}: {
  children: ReactNode;
  className?: string;
  onClick?: () => void;
  /** Realce sutil de linha com estado (crítico, cancelado). */
  tom?: "danger" | "warning" | "muted";
}) {
  const tons = {
    danger: "bg-danger-subtle/40",
    warning: "bg-warning-subtle/40",
    muted: "opacity-60",
  };
  return (
    <tr
      onClick={onClick}
      className={cn(
        "transition-colors duration-fast hover:bg-surface-muted/60",
        onClick && "cursor-pointer",
        tom && tons[tom],
        className
      )}
    >
      {children}
    </tr>
  );
}

export function TD({
  children,
  className = "",
  colSpan,
  tecnico = false,
}: {
  children?: ReactNode;
  className?: string;
  colSpan?: number;
  tecnico?: boolean;
}) {
  return (
    <td className={cn("px-3 py-2.5 text-fg-muted sm:px-4", tecnico && "data", className)}>
      {children}
    </td>
  );
}

/* ==========================================================================
   Pagination
   ========================================================================== */

function janelaDePaginas(atual: number, total: number): (number | "…")[] {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
  const saida: (number | "…")[] = [1];
  const inicio = Math.max(2, atual - 1);
  const fim = Math.min(total - 1, atual + 1);
  if (inicio > 2) saida.push("…");
  for (let i = inicio; i <= fim; i++) saida.push(i);
  if (fim < total - 1) saida.push("…");
  saida.push(total);
  return saida;
}

export function Pagination({
  pagina,
  totalPaginas,
  onMudar,
  /** Total de registros, para o texto "mostrando X–Y de Z". */
  total,
  porPagina,
  className = "",
}: {
  pagina: number;
  totalPaginas: number;
  onMudar: (p: number) => void;
  total?: number;
  porPagina?: number;
  className?: string;
}) {
  if (totalPaginas <= 1) return null;
  const de = porPagina ? (pagina - 1) * porPagina + 1 : null;
  const ate = porPagina && total ? Math.min(pagina * porPagina, total) : null;

  return (
    <nav
      aria-label="Paginação"
      className={cn("flex flex-wrap items-center justify-between gap-3 px-1", className)}
    >
      {de !== null && total !== undefined ? (
        <p className="text-xs text-fg-subtle">
          Mostrando <span className="data">{de}</span>–<span className="data">{ate}</span> de{" "}
          <span className="data">{total.toLocaleString("pt-BR")}</span>
        </p>
      ) : (
        <span />
      )}

      <div className="flex items-center gap-1">
        <IconButton
          icon={ChevronLeft}
          label="Página anterior"
          size="xs"
          variant="ghost"
          disabled={pagina === 1}
          onClick={() => onMudar(pagina - 1)}
        />
        {janelaDePaginas(pagina, totalPaginas).map((n, i) =>
          n === "…" ? (
            <span key={`e${i}`} className="px-1 text-xs text-fg-subtle" aria-hidden="true">
              …
            </span>
          ) : (
            <button
              key={n}
              type="button"
              onClick={() => onMudar(n)}
              aria-current={n === pagina ? "page" : undefined}
              aria-label={`Página ${n}`}
              className={cn(
                "min-w-8 rounded-md px-2 py-1.5 text-xs font-medium tabular-nums transition-colors",
                n === pagina
                  ? "bg-primary text-primary-fg"
                  : "text-fg-muted hover:bg-surface-muted hover:text-fg"
              )}
            >
              {n}
            </button>
          )
        )}
        <IconButton
          icon={ChevronRight}
          label="Próxima página"
          size="xs"
          variant="ghost"
          disabled={pagina === totalPaginas}
          onClick={() => onMudar(pagina + 1)}
        />
      </div>
    </nav>
  );
}

/* ==========================================================================
   DataTable — a tabela padrão das listagens.
   --------------------------------------------------------------------------
   Resolve, em um lugar, o que estava reescrito em cada tela: busca, ordenação,
   paginação, estados (carregando/vazio/erro), ações por linha em menu e
   estratégia mobile de verdade — abaixo de `md` a tabela deixa de ser tabela e
   passa a ser uma lista de fichas, usando as colunas marcadas como `titulo`,
   `subtitulo` e `meta`. Nada de rolagem horizontal como única resposta.
   ========================================================================== */

export type Coluna<T> = {
  /** Identificador estável da coluna (usado na ordenação). */
  chave: string;
  header: string;
  celula: (item: T) => ReactNode;
  /**
   * Valor cru para ordenar e buscar. Sem isto a coluna não é ordenável nem
   * pesquisável (células com JSX não servem para comparar).
   */
  valor?: (item: T) => string | number | null | undefined;
  ordenavel?: boolean;
  alinhamento?: "esquerda" | "centro" | "direita";
  /** Fonte monoespaçada para TAG, número de série, medição. */
  tecnico?: boolean;
  className?: string;
  larguraClasse?: string;
  /**
   * Papel da coluna na ficha mobile:
   *   titulo    → linha principal (uma por tabela)
   *   subtitulo → logo abaixo do título
   *   meta      → pares rótulo/valor no corpo da ficha
   *   oculta    → não aparece no celular
   */
  mobile?: "titulo" | "subtitulo" | "meta" | "oculta";
};

type Ordenacao = { chave: string; direcao: "asc" | "desc" } | null;

export function DataTable<T>({
  itens,
  colunas,
  getId,
  carregando = false,
  falha = null,
  onRetry,
  vazio,
  busca,
  camposBusca,
  onLinhaClick,
  acoes,
  porPagina = 12,
  ordenacaoInicial,
  tomDaLinha,
  selecao,
  className = "",
  legenda,
}: {
  itens: T[];
  colunas: Coluna<T>[];
  getId: (item: T) => string | number;
  carregando?: boolean;
  falha?: Falha | null;
  onRetry?: () => void;
  /** EmptyState pronto — a tela decide o texto, que é parte do onboarding. */
  vazio: ReactNode;
  /** Texto de busca (controlado pela tela, para caber na Toolbar). */
  busca?: string;
  /** Campos extras de busca além dos `valor` das colunas. */
  camposBusca?: (item: T) => (string | number | null | undefined)[];
  onLinhaClick?: (item: T) => void;
  /** Ações da linha — vão para um menu "⋮", não para botões soltos. */
  acoes?: (item: T) => ItemMenu[];
  porPagina?: number;
  ordenacaoInicial?: { chave: string; direcao?: "asc" | "desc" };
  tomDaLinha?: (item: T) => "danger" | "warning" | "muted" | undefined;
  /** Seleção múltipla para ações em lote. */
  selecao?: {
    selecionados: Set<string | number>;
    onMudar: (ids: Set<string | number>) => void;
    /** Barra de ações que aparece quando há seleção. */
    acoesEmLote?: ReactNode;
  };
  className?: string;
  /** Descrição da tabela para leitor de tela (`<caption>` oculta). */
  legenda?: string;
}) {
  const [ordenacao, setOrdenacao] = useState<Ordenacao>(
    ordenacaoInicial ? { chave: ordenacaoInicial.chave, direcao: ordenacaoInicial.direcao ?? "asc" } : null
  );
  const [pagina, setPagina] = useState(1);

  const filtrados = useMemo(() => {
    const q = normalizar(busca ?? "").trim();
    if (!q) return itens;
    return itens.filter((item) => {
      const daColuna = colunas.map((c) => c.valor?.(item));
      const extras = camposBusca?.(item) ?? [];
      return normalizar([...daColuna, ...extras].join(" ")).includes(q);
    });
  }, [itens, busca, colunas, camposBusca]);

  const ordenados = useMemo(() => {
    if (!ordenacao) return filtrados;
    const coluna = colunas.find((c) => c.chave === ordenacao.chave);
    if (!coluna?.valor) return filtrados;
    const fator = ordenacao.direcao === "asc" ? 1 : -1;
    return [...filtrados].sort((a, b) => {
      const va = coluna.valor!(a);
      const vb = coluna.valor!(b);
      // Vazio sempre por último, independente da direção: "sem dado" não é o
      // menor valor, é ausência de valor.
      if (va == null || va === "") return 1;
      if (vb == null || vb === "") return -1;
      if (typeof va === "number" && typeof vb === "number") return (va - vb) * fator;
      return compararTexto(va, vb) * fator;
    });
  }, [filtrados, ordenacao, colunas]);

  const totalPaginas = Math.max(1, Math.ceil(ordenados.length / porPagina));
  const paginaAtual = Math.min(pagina, totalPaginas);
  const visiveis = ordenados.slice((paginaAtual - 1) * porPagina, paginaAtual * porPagina);

  // Buscar ou reordenar volta para a primeira página: senão o usuário vê "nada
  // encontrado" só porque estava na página 4.
  useEffect(() => setPagina(1), [busca, ordenacao]);
  useEffect(() => {
    if (pagina > totalPaginas) setPagina(totalPaginas);
  }, [pagina, totalPaginas]);

  if (carregando) return <TableSkeleton rows={6} cols={Math.min(colunas.length, 6)} />;
  if (falha)
    return (
      <Card padding={false}>
        <ErrorState falha={falha} onRetry={onRetry} />
      </Card>
    );
  if (itens.length === 0) return <Card padding={false}>{vazio}</Card>;
  if (ordenados.length === 0)
    return (
      <Card padding={false}>
        <EmptyState
          icon={Search}
          title="Nada corresponde à sua busca"
          description={
            busca
              ? `Nenhum registro encontrado para “${busca}”. Verifique a grafia ou limpe a busca.`
              : "Ajuste os filtros para ver resultados."
          }
        />
      </Card>
    );

  function alternarOrdenacao(chave: string) {
    setOrdenacao((atual) =>
      atual?.chave === chave
        ? { chave, direcao: atual.direcao === "asc" ? "desc" : "asc" }
        : { chave, direcao: "asc" }
    );
  }

  const alinhamentos = { esquerda: "text-left", centro: "text-center", direita: "text-right" };
  const idsVisiveis = visiveis.map(getId);
  const todosSelecionados =
    !!selecao && idsVisiveis.length > 0 && idsVisiveis.every((id) => selecao.selecionados.has(id));
  const algunsSelecionados = !!selecao && idsVisiveis.some((id) => selecao.selecionados.has(id));

  const colunaTitulo = colunas.find((c) => c.mobile === "titulo") ?? colunas[0];
  const colunaSubtitulo = colunas.find((c) => c.mobile === "subtitulo");
  const colunasMeta = colunas.filter((c) => c.mobile === "meta");

  return (
    <div className={cn("space-y-3", className)}>
      {selecao && selecao.selecionados.size > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-primary/30 bg-primary-subtle px-4 py-2.5">
          <p className="text-sm font-medium text-primary-subtle-fg">
            {selecao.selecionados.size} selecionado{selecao.selecionados.size > 1 ? "s" : ""}
          </p>
          <div className="flex items-center gap-2">
            {selecao.acoesEmLote}
            <button
              type="button"
              onClick={() => selecao.onMudar(new Set())}
              className="text-xs font-medium text-primary-subtle-fg underline-offset-2 hover:underline"
            >
              Limpar seleção
            </button>
          </div>
        </div>
      )}

      {/* ---------- Desktop: tabela ---------- */}
      <Card padding={false} className="hidden overflow-hidden md:block">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            {legenda && <caption className="sr-only">{legenda}</caption>}
            <thead className="border-b border-border bg-surface-muted/50">
              <tr>
                {selecao && (
                  <th scope="col" className="w-10 px-3 py-2.5">
                    <Checkbox
                      checked={todosSelecionados}
                      indeterminate={algunsSelecionados}
                      onChange={(marcar) => {
                        const proximo = new Set(selecao.selecionados);
                        idsVisiveis.forEach((id) => (marcar ? proximo.add(id) : proximo.delete(id)));
                        selecao.onMudar(proximo);
                      }}
                      label={<span className="sr-only">Selecionar todos nesta página</span>}
                    />
                  </th>
                )}
                {colunas.map((c) => {
                  const ordenavel = c.ordenavel !== false && !!c.valor;
                  const ativa = ordenacao?.chave === c.chave;
                  const Icone: LucideIcon = !ativa
                    ? ArrowUpDown
                    : ordenacao!.direcao === "asc"
                    ? ArrowUp
                    : ArrowDown;
                  return (
                    <th
                      key={c.chave}
                      scope="col"
                      aria-sort={ativa ? (ordenacao!.direcao === "asc" ? "ascending" : "descending") : undefined}
                      className={cn(
                        "whitespace-nowrap px-3 py-2.5 text-2xs font-semibold uppercase tracking-wide text-fg-subtle sm:px-4",
                        alinhamentos[c.alinhamento ?? "esquerda"],
                        c.larguraClasse
                      )}
                    >
                      {ordenavel ? (
                        <button
                          type="button"
                          onClick={() => alternarOrdenacao(c.chave)}
                          className={cn(
                            "group inline-flex items-center gap-1 rounded transition-colors hover:text-fg",
                            ativa && "text-fg"
                          )}
                        >
                          {c.header}
                          <Icone
                            className={cn(
                              "h-3 w-3 transition-opacity",
                              ativa ? "opacity-100" : "opacity-0 group-hover:opacity-60"
                            )}
                            aria-hidden="true"
                          />
                        </button>
                      ) : (
                        c.header
                      )}
                    </th>
                  );
                })}
                {acoes && (
                  <th scope="col" className="w-12 px-3 py-2.5">
                    <span className="sr-only">Ações</span>
                  </th>
                )}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {visiveis.map((item) => {
                const id = getId(item);
                const itensMenu = acoes?.(item) ?? [];
                const tom = tomDaLinha?.(item);
                return (
                  <TR key={id} onClick={onLinhaClick ? () => onLinhaClick(item) : undefined} tom={tom}>
                    {selecao && (
                      <TD className="w-10">
                        <span onClick={(e) => e.stopPropagation()}>
                          <Checkbox
                            checked={selecao.selecionados.has(id)}
                            onChange={(marcar) => {
                              const proximo = new Set(selecao.selecionados);
                              if (marcar) proximo.add(id);
                              else proximo.delete(id);
                              selecao.onMudar(proximo);
                            }}
                            label={<span className="sr-only">Selecionar registro</span>}
                          />
                        </span>
                      </TD>
                    )}
                    {colunas.map((c) => (
                      <TD
                        key={c.chave}
                        tecnico={c.tecnico}
                        className={cn(alinhamentos[c.alinhamento ?? "esquerda"], c.className)}
                      >
                        {c.celula(item)}
                      </TD>
                    ))}
                    {acoes && (
                      <TD className="w-12 text-right">
                        {itensMenu.length > 0 && (
                          <span onClick={(e) => e.stopPropagation()} className="inline-flex">
                            <DropdownMenu
                              trigger={
                                <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-fg-subtle transition-colors hover:bg-surface-muted hover:text-fg">
                                  <MoreVertical className="h-4 w-4" aria-hidden="true" />
                                </span>
                              }
                              itens={itensMenu}
                            />
                          </span>
                        )}
                      </TD>
                    )}
                  </TR>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>

      {/* ---------- Mobile: fichas ---------- */}
      <ul className="space-y-2.5 md:hidden">
        {visiveis.map((item) => {
          const id = getId(item);
          const itensMenu = acoes?.(item) ?? [];
          const tom = tomDaLinha?.(item);
          return (
            <Card
              as="li"
              key={id}
              padding={false}
              tom={tom === "danger" ? "danger" : tom === "warning" ? "warning" : "neutral"}
              className={cn(tom === "muted" && "opacity-60")}
            >
              <div className="flex items-start gap-2 p-3.5">
                <button
                  type="button"
                  onClick={onLinhaClick ? () => onLinhaClick(item) : undefined}
                  disabled={!onLinhaClick}
                  className="min-w-0 flex-1 text-left disabled:cursor-default"
                >
                  <div className={cn("text-sm font-semibold text-fg", colunaTitulo.tecnico && "data")}>
                    {colunaTitulo.celula(item)}
                  </div>
                  {colunaSubtitulo && (
                    <div className="mt-0.5 text-xs text-fg-muted">{colunaSubtitulo.celula(item)}</div>
                  )}
                  {colunasMeta.length > 0 && (
                    <dl className="mt-2.5 grid grid-cols-2 gap-x-3 gap-y-2">
                      {colunasMeta.map((c) => (
                        <div key={c.chave} className="min-w-0">
                          <dt className="text-2xs uppercase tracking-wide text-fg-subtle">{c.header}</dt>
                          <dd className={cn("truncate text-xs text-fg", c.tecnico && "data")}>
                            {c.celula(item)}
                          </dd>
                        </div>
                      ))}
                    </dl>
                  )}
                </button>
                {acoes && itensMenu.length > 0 && (
                  <DropdownMenu
                    trigger={
                      <span className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-fg-subtle transition-colors hover:bg-surface-muted hover:text-fg">
                        <MoreVertical className="h-4 w-4" aria-hidden="true" />
                      </span>
                    }
                    itens={itensMenu}
                  />
                )}
              </div>
            </Card>
          );
        })}
      </ul>

      <Pagination
        pagina={paginaAtual}
        totalPaginas={totalPaginas}
        onMudar={setPagina}
        total={ordenados.length}
        porPagina={porPagina}
      />
    </div>
  );
}
