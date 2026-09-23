"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { MouseEvent } from "react";
import {
  Check,
  CircleCheck,
  CircleDot,
  CornerDownRight,
  ListChecks,
  TriangleAlert,
} from "lucide-react";
import { Badge, Checkbox, ProgressBar, SearchInput, SegmentedControl, cn } from "@/components/ds";
import { normalizar, plural } from "@/lib/format";
import type { Condicao, ItemInspecao } from "@/lib/types";
import {
  EXPLICACAO_ESTADO,
  ROTULO_ESTADO,
  estadoDoItem,
  pesoEstado,
  progressoDosItens,
  type EstadoItem,
} from "./progresso";
import { AcoesCondicao, CorCondicao } from "./seletor-condicao";

/* ==========================================================================
   Navegador de equipamentos — a coluna esquerda da folha de campo.
   --------------------------------------------------------------------------
   O técnico precisa de três coisas aqui, nesta ordem: achar a TAG que está na
   frente dele, ver o que ainda falta, e pular para o próximo pendente.

   A busca cobre TAG, nome, área e setor — no campo o crachá da máquina às vezes
   traz só parte da TAG, e a pessoa lembra "a bomba da casa de bombas".

   Busca e filtro moram na folha (chegam por props): as duas instâncias —
   desktop e celular — mostram o mesmo recorte, e o avanço automático da
   folha respeita a busca em andamento.

   "Lançar em lote" transforma a lista em seleção: marca vários (Shift+clique
   pega um intervalo) e aplica uma condição a todos numa requisição só. É o
   caminho para a rota em que quase tudo está normal.
   ========================================================================== */

const ICONE_ESTADO: Record<EstadoItem, typeof CircleCheck> = {
  PENDENTE: CircleDot,
  INCOMPLETO: TriangleAlert,
  COM_ACHADO: TriangleAlert,
  SEM_ACAO: CircleCheck,
};

const COR_ESTADO: Record<EstadoItem, string> = {
  PENDENTE: "text-fg-subtle",
  INCOMPLETO: "text-warning",
  COM_ACHADO: "text-danger",
  SEM_ACAO: "text-success",
};

export type Filtro = "todos" | "pendentes" | "com_achado" | "sem_acao";

const ROTULO_FILTRO: Record<Filtro, string> = {
  todos: "Todos",
  pendentes: "Pendentes",
  com_achado: "Com achado",
  sem_acao: "Sem ação",
};

/** Itens cuja TAG, nome, área, setor ou tipo contêm o texto buscado. */
export function filtrarPorBusca(itens: ItemInspecao[], busca: string): ItemInspecao[] {
  const q = normalizar(busca).trim();
  if (!q) return itens;
  return itens.filter((i) =>
    normalizar(
      [i.equipamento_tag, i.equipamento_nome, i.area_nome, i.setor_nome, i.tipo_equipamento_nome].join(" ")
    ).includes(q)
  );
}

function passaNoFiltro(item: ItemInspecao, filtro: Filtro): boolean {
  const estado = estadoDoItem(item);
  if (filtro === "pendentes") return estado === "PENDENTE" || estado === "INCOMPLETO";
  if (filtro === "com_achado") return estado === "COM_ACHADO";
  if (filtro === "sem_acao") return estado === "SEM_ACAO";
  return true;
}

export function NavegadorEquipamentos({
  itens,
  condicoes,
  selecionadoId,
  onSelecionar,
  busca,
  onBusca,
  filtro,
  onFiltro,
  podeEditar = false,
  onAplicarEmLote,
  className = "",
}: {
  itens: ItemInspecao[];
  condicoes: Condicao[];
  selecionadoId: number | null;
  onSelecionar: (item: ItemInspecao) => void;
  busca: string;
  onBusca: (valor: string) => void;
  filtro: Filtro;
  onFiltro: (valor: Filtro) => void;
  podeEditar?: boolean;
  /** Aplica a condição aos itens; resolve `true` quando gravou. */
  onAplicarEmLote?: (itens: ItemInspecao[], condicao: Condicao) => Promise<boolean>;
  className?: string;
}) {
  const [selecionando, setSelecionando] = useState(false);
  const [marcados, setMarcados] = useState<Set<number>>(new Set());
  const [aplicando, setAplicando] = useState(false);
  const ultimoMarcado = useRef<number | null>(null);
  const listaRef = useRef<HTMLDivElement>(null);

  const progresso = useMemo(() => progressoDosItens(itens), [itens]);
  const condicaoPorId = useMemo(() => new Map(condicoes.map((c) => [c.id, c])), [condicoes]);

  const contagem = useMemo(() => {
    const c: Record<Filtro, number> = { todos: itens.length, pendentes: 0, com_achado: 0, sem_acao: 0 };
    for (const i of itens) {
      const e = estadoDoItem(i);
      if (e === "PENDENTE" || e === "INCOMPLETO") c.pendentes += 1;
      else if (e === "COM_ACHADO") c.com_achado += 1;
      else c.sem_acao += 1;
    }
    return c;
  }, [itens]);

  const visiveis = useMemo(
    () => filtrarPorBusca(itens, busca).filter((i) => passaNoFiltro(i, filtro)),
    [itens, busca, filtro]
  );

  // A seleção vale para o que está À VISTA: o que um filtro escondeu não
  // recebe condição sem o técnico ver.
  const marcadosVisiveis = useMemo(
    () => visiveis.filter((i) => marcados.has(i.id)),
    [visiveis, marcados]
  );

  // A folha avança sozinha depois de cada condição: a linha aberta à direita
  // precisa continuar à vista aqui. Rola só a lista — nunca a página.
  useEffect(() => {
    const lista = listaRef.current;
    if (!lista || selecionadoId == null || selecionando) return;
    const linha = lista.querySelector<HTMLElement>(`[data-item="${selecionadoId}"]`);
    if (!linha) return;
    const caixa = lista.getBoundingClientRect();
    const alvo = linha.getBoundingClientRect();
    if (alvo.top < caixa.top) lista.scrollTop -= caixa.top - alvo.top;
    else if (alvo.bottom > caixa.bottom) lista.scrollTop += alvo.bottom - caixa.bottom;
  }, [selecionadoId, selecionando]);

  function sairDaSelecao() {
    setSelecionando(false);
    setMarcados(new Set());
    ultimoMarcado.current = null;
  }

  function alternar(item: ItemInspecao, e: MouseEvent) {
    const marcar = !marcados.has(item.id);
    const novo = new Set(marcados);
    const de = visiveis.findIndex((i) => i.id === ultimoMarcado.current);
    const ate = visiveis.findIndex((i) => i.id === item.id);
    if (e.shiftKey && de >= 0 && ate >= 0) {
      // Shift+clique: o intervalo inteiro assume o estado da linha clicada.
      const [a, b] = de < ate ? [de, ate] : [ate, de];
      for (const i of visiveis.slice(a, b + 1)) {
        if (marcar) novo.add(i.id);
        else novo.delete(i.id);
      }
    } else if (marcar) {
      novo.add(item.id);
    } else {
      novo.delete(item.id);
    }
    ultimoMarcado.current = item.id;
    setMarcados(novo);
  }

  function marcarTodos(marcar: boolean) {
    setMarcados(marcar ? new Set(visiveis.map((i) => i.id)) : new Set());
  }

  async function aplicar(condicao: Condicao) {
    if (!onAplicarEmLote || marcadosVisiveis.length === 0) return;
    setAplicando(true);
    const ok = await onAplicarEmLote(marcadosVisiveis, condicao);
    setAplicando(false);
    if (ok) sairDaSelecao();
  }

  const todosMarcados = visiveis.length > 0 && marcadosVisiveis.length === visiveis.length;

  return (
    <div className={cn("flex min-h-0 flex-col", className)}>
      {/* Progresso: é o que decide se a rota pode ser transferida. */}
      <div className="border-b border-border px-3 py-3">
        <div className="mb-1.5 flex items-baseline justify-between gap-2">
          <span className="text-xs text-fg-muted">
            <span className="data font-semibold text-fg">
              {progresso.concluidos}/{progresso.total}
            </span>{" "}
            concluídos
          </span>
          <span
            className={cn(
              "text-xs font-semibold",
              progresso.percentual === 100 ? "text-success-fg" : "text-fg-muted"
            )}
          >
            {progresso.percentual}%
          </span>
        </div>
        <ProgressBar
          valor={progresso.concluidos}
          max={Math.max(1, progresso.total)}
          label="Progresso da folha de campo"
        />
      </div>

      {/* Busca + filtros */}
      <div className="space-y-2.5 border-b border-border px-3 py-3">
        <SearchInput
          value={busca}
          onChange={onBusca}
          label="Buscar equipamento"
          placeholder="Buscar TAG ou equipamento…"
        />
        <div className="overflow-x-auto pb-0.5">
          <SegmentedControl
            label="Filtrar equipamentos"
            tamanho="sm"
            valor={filtro}
            onMudar={onFiltro}
            opcoes={(["todos", "pendentes", "com_achado", "sem_acao"] as const).map((f) => ({
              valor: f,
              label: `${ROTULO_FILTRO[f]} (${contagem[f]})`,
            }))}
          />
        </div>
      </div>

      {/* Lista */}
      <div ref={listaRef} className="min-h-0 flex-1 overflow-y-auto">
        {visiveis.length === 0 ? (
          <p className="px-3 py-8 text-center text-sm text-fg-subtle">
            {busca
              ? `Nenhum equipamento corresponde a “${busca}”.`
              : "Nenhum equipamento nesta visão."}
          </p>
        ) : (
          <ul className="divide-y divide-border">
            {visiveis.map((item) => {
              const estado = estadoDoItem(item);
              const Icone = ICONE_ESTADO[estado];
              const ativo = !selecionando && item.id === selecionadoId;
              const marcado = selecionando && marcados.has(item.id);
              const achados = item.achados?.length ?? 0;
              const condicao = item.condicao != null ? condicaoPorId.get(item.condicao) : undefined;
              return (
                <li key={item.id} data-item={item.id}>
                  <button
                    type="button"
                    onClick={(e) => (selecionando ? alternar(item, e) : onSelecionar(item))}
                    role={selecionando ? "checkbox" : undefined}
                    aria-checked={selecionando ? marcado : undefined}
                    aria-current={ativo ? "true" : undefined}
                    className={cn(
                      "flex w-full items-start gap-2.5 px-3 py-3 text-left transition-colors",
                      selecionando && "select-none",
                      ativo || marcado ? "bg-primary-subtle" : "hover:bg-surface-muted"
                    )}
                  >
                    {selecionando ? (
                      <span
                        aria-hidden="true"
                        className={cn(
                          "mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded border transition-colors",
                          marcado
                            ? "border-primary bg-primary text-primary-fg"
                            : "border-border-strong bg-surface"
                        )}
                      >
                        {marcado && <Check className="h-3 w-3" strokeWidth={3} />}
                      </span>
                    ) : (
                      <Icone
                        className={cn("mt-0.5 h-4 w-4 shrink-0", COR_ESTADO[estado])}
                        aria-hidden="true"
                      />
                    )}
                    <span className="min-w-0 flex-1">
                      <span className="flex items-center gap-1.5">
                        <span className="data truncate text-sm font-semibold text-fg">
                          {item.equipamento_tag}
                        </span>
                        {achados > 0 && (
                          <Badge tone="danger" className="px-1.5 py-0 text-2xs">
                            {achados}
                          </Badge>
                        )}
                      </span>
                      <span className="block truncate text-xs text-fg-muted">
                        {item.equipamento_nome}
                      </span>
                      <span className="mt-0.5 flex items-center gap-1 text-2xs text-fg-subtle">
                        <CornerDownRight className="h-3 w-3 shrink-0" aria-hidden="true" />
                        <span className="truncate">
                          {item.area_nome} · {item.setor_nome}
                        </span>
                      </span>
                      <span className="mt-1 flex items-center gap-1.5 text-2xs font-medium">
                        <span className={COR_ESTADO[estado]} title={EXPLICACAO_ESTADO[estado]}>
                          {ROTULO_ESTADO[estado]}
                        </span>
                        {/* Qual condição foi marcada — revisar a rota sem abrir item por item. */}
                        {condicao && (
                          <>
                            <span className="text-fg-subtle" aria-hidden="true">
                              ·
                            </span>
                            <span
                              className="inline-flex min-w-0 items-center gap-1 text-fg-muted"
                              title={condicao.nome}
                            >
                              <CorCondicao cor={condicao.cor} className="h-2 w-2" />
                              <span className="data truncate">{condicao.sigla || condicao.nome}</span>
                            </span>
                          </>
                        )}
                      </span>
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {selecionando ? (
        <div className="space-y-3 border-t border-border bg-surface-muted px-3 py-3">
          <div className="flex items-center justify-between gap-2">
            <Checkbox
              checked={todosMarcados}
              indeterminate={marcadosVisiveis.length > 0}
              onChange={marcarTodos}
              disabled={visiveis.length === 0 || aplicando}
              label={
                <span className="text-xs">
                  {marcadosVisiveis.length > 0
                    ? `${plural(marcadosVisiveis.length, "selecionado")} de ${visiveis.length}`
                    : `Todos nesta visão (${visiveis.length})`}
                </span>
              }
            />
            <button
              type="button"
              onClick={sairDaSelecao}
              disabled={aplicando}
              className="shrink-0 rounded-md px-2 py-1 text-xs font-medium text-fg-muted transition-colors hover:bg-surface-muted hover:text-fg disabled:opacity-50"
            >
              Cancelar
            </button>
          </div>
          <AcoesCondicao
            condicoes={condicoes}
            onAplicar={aplicar}
            disabled={marcadosVisiveis.length === 0 || aplicando}
          />
          <p className="text-2xs text-fg-subtle">
            {aplicando ? (
              "Gravando…"
            ) : (
              <>
                Marque os equipamentos e toque na condição.
                <span className="hidden lg:inline"> Shift+clique marca um intervalo.</span>
              </>
            )}
          </p>
        </div>
      ) : (
        <div className="flex items-center justify-between gap-2 border-t border-border px-3 py-1.5">
          <p className="text-2xs text-fg-subtle">{plural(visiveis.length, "equipamento")} nesta visão</p>
          {podeEditar && onAplicarEmLote && itens.length > 1 && (
            <button
              type="button"
              onClick={() => setSelecionando(true)}
              className="inline-flex shrink-0 items-center gap-1 rounded-md px-2 py-1 text-2xs font-medium text-primary transition-colors hover:bg-primary-subtle"
            >
              <ListChecks className="h-3.5 w-3.5" aria-hidden="true" />
              Lançar em lote
            </button>
          )}
        </div>
      )}
    </div>
  );
}

/** Próximo equipamento pendente a partir do atual — alimenta "Próximo pendente". */
export function proximoPendente(
  itens: ItemInspecao[],
  atualId: number | null
): ItemInspecao | null {
  const pendentes = itens.filter((i) => {
    const e = estadoDoItem(i);
    return e === "PENDENTE" || e === "INCOMPLETO";
  });
  if (pendentes.length === 0) return null;

  const indiceAtual = itens.findIndex((i) => i.id === atualId);
  // Procura o próximo depois do atual; se não houver, volta ao começo da fila.
  const adiante = pendentes.find((p) => itens.indexOf(p) > indiceAtual);
  return adiante ?? pendentes.find((p) => p.id !== atualId) ?? null;
}

/** Vizinhos do item atual, para os botões Anterior / Próximo. */
export function vizinhos(itens: ItemInspecao[], atualId: number | null) {
  const i = itens.findIndex((x) => x.id === atualId);
  return {
    anterior: i > 0 ? itens[i - 1] : null,
    proximo: i >= 0 && i < itens.length - 1 ? itens[i + 1] : null,
    posicao: i >= 0 ? i + 1 : 0,
    total: itens.length,
  };
}

/** Ordena preservando a ordem da rota (Área → Setor → TAG já vem do servidor). */
export function ordenarPorUrgencia(itens: ItemInspecao[]): ItemInspecao[] {
  return [...itens].sort(
    (a, b) => pesoEstado(estadoDoItem(a)) - pesoEstado(estadoDoItem(b)) || a.ordem - b.ordem
  );
}
