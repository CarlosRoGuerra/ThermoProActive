"use client";

import { useMemo, useState } from "react";
import { CircleCheck, CircleDot, CircleMinus, CornerDownRight, TriangleAlert } from "lucide-react";
import { Badge, ProgressBar, SearchInput, SegmentedControl, cn } from "@/components/ds";
import { normalizar, plural } from "@/lib/format";
import type { ItemInspecao } from "@/lib/types";
import {
  EXPLICACAO_ESTADO,
  ROTULO_ESTADO,
  estadoDoItem,
  pesoEstado,
  progressoDosItens,
  type EstadoItem,
} from "./progresso";

/* ==========================================================================
   Navegador de equipamentos — a coluna esquerda da folha de campo.
   --------------------------------------------------------------------------
   O técnico precisa de três coisas aqui, nesta ordem: achar a TAG que está na
   frente dele, ver o que ainda falta, e pular para o próximo pendente.

   A busca cobre TAG, nome, área e setor — no campo o crachá da máquina às vezes
   traz só parte da TAG, e a pessoa lembra "a bomba da casa de bombas".
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

type Filtro = "todos" | "pendentes" | "com_achado" | "sem_acao";

const ROTULO_FILTRO: Record<Filtro, string> = {
  todos: "Todos",
  pendentes: "Pendentes",
  com_achado: "Com achado",
  sem_acao: "Sem ação",
};

export function NavegadorEquipamentos({
  itens,
  selecionadoId,
  onSelecionar,
  className = "",
}: {
  itens: ItemInspecao[];
  selecionadoId: number | null;
  onSelecionar: (item: ItemInspecao) => void;
  className?: string;
}) {
  const [busca, setBusca] = useState("");
  const [filtro, setFiltro] = useState<Filtro>("todos");

  const progresso = useMemo(() => progressoDosItens(itens), [itens]);

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

  const visiveis = useMemo(() => {
    const q = normalizar(busca).trim();
    return itens.filter((i) => {
      const estado = estadoDoItem(i);
      if (filtro === "pendentes" && estado !== "PENDENTE" && estado !== "INCOMPLETO") return false;
      if (filtro === "com_achado" && estado !== "COM_ACHADO") return false;
      if (filtro === "sem_acao" && estado !== "SEM_ACAO") return false;
      if (!q) return true;
      return normalizar(
        [i.equipamento_tag, i.equipamento_nome, i.area_nome, i.setor_nome, i.tipo_equipamento_nome].join(" ")
      ).includes(q);
    });
  }, [itens, busca, filtro]);

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
          onChange={setBusca}
          label="Buscar equipamento"
          placeholder="Buscar TAG ou equipamento…"
        />
        <div className="overflow-x-auto pb-0.5">
          <SegmentedControl
            label="Filtrar equipamentos"
            tamanho="sm"
            valor={filtro}
            onMudar={setFiltro}
            opcoes={(["todos", "pendentes", "com_achado", "sem_acao"] as const).map((f) => ({
              valor: f,
              label: `${ROTULO_FILTRO[f]} (${contagem[f]})`,
            }))}
          />
        </div>
      </div>

      {/* Lista */}
      <div className="min-h-0 flex-1 overflow-y-auto">
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
              const ativo = item.id === selecionadoId;
              const achados = item.achados?.length ?? 0;
              return (
                <li key={item.id}>
                  <button
                    type="button"
                    onClick={() => onSelecionar(item)}
                    aria-current={ativo ? "true" : undefined}
                    className={cn(
                      "flex w-full items-start gap-2.5 px-3 py-3 text-left transition-colors",
                      ativo ? "bg-primary-subtle" : "hover:bg-surface-muted"
                    )}
                  >
                    <Icone
                      className={cn("mt-0.5 h-4 w-4 shrink-0", COR_ESTADO[estado])}
                      aria-hidden="true"
                    />
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
                      <span
                        className={cn("mt-1 block text-2xs font-medium", COR_ESTADO[estado])}
                        title={EXPLICACAO_ESTADO[estado]}
                      >
                        {ROTULO_ESTADO[estado]}
                      </span>
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      <p className="border-t border-border px-3 py-2 text-2xs text-fg-subtle">
        {plural(visiveis.length, "equipamento")} nesta visão
      </p>
    </div>
  );
}

/** Próximo equipamento pendente a partir do atual — alimenta "Salvar e próximo". */
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
