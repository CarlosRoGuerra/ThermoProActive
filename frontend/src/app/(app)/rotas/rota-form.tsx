"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, ChevronRight, MapPin, Route as RouteIcon, Save } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useClienteAtivo } from "@/lib/cliente-ativo";
import type { Paginated, Rota } from "@/lib/types";
import { Button, Card, Field, Input, Select, Spinner, cn } from "@/components/ui";

/* ============================ Árvore de seleção ============================ */
type EquipNode = { id: number; tag: string; nome: string };
type SetorNode = { id: number; nome: string; equipamentos: EquipNode[] };
type AreaNode = { id: number; nome: string; setores: SetorNode[] };

type AreaAPI = { id: number; identificacao: string };
type SetorAPI = { id: number; area: number; identificacao: string };
type EquipAPI = { id: number; tag: string; nome: string; setor: number };

/** Checkbox com estado "parcial" (indeterminado) — para área/setor. */
function Checkbox({
  checado,
  parcial = false,
  onChange,
}: {
  checado: boolean;
  parcial?: boolean;
  onChange: () => void;
}) {
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (ref.current) ref.current.indeterminate = parcial && !checado;
  }, [parcial, checado]);
  return (
    <input
      ref={ref}
      type="checkbox"
      checked={checado}
      onChange={onChange}
      onClick={(e) => e.stopPropagation()}
      className="h-4 w-4 shrink-0 cursor-pointer rounded border-border-strong"
      style={{ accentColor: "var(--accent)" }}
    />
  );
}

/**
 * Árvore Área → Setor → Equipamento com checkboxes em cascata. Marcar uma área
 * marca todos os equipamentos dela; um setor, todos os do setor. O que fica
 * guardado é o conjunto de EQUIPAMENTOS (as folhas).
 */
function ArvoreEquipamentos({
  clienteId,
  selecionados,
  onChange,
}: {
  clienteId: number;
  selecionados: number[];
  onChange: (ids: number[]) => void;
}) {
  const [arvore, setArvore] = useState<AreaNode[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [abertos, setAbertos] = useState<Set<string>>(new Set());
  const [q, setQ] = useState("");
  const sel = useMemo(() => new Set(selecionados), [selecionados]);

  useEffect(() => {
    setCarregando(true);
    Promise.all([
      api<Paginated<AreaAPI>>(`/areas/?cliente=${clienteId}&page_size=1000`),
      api<Paginated<SetorAPI>>(`/setores/?area__cliente=${clienteId}&page_size=1000`),
      api<Paginated<EquipAPI>>(`/equipamentos/?setor__area__cliente=${clienteId}&page_size=1000`),
    ])
      .then(([areas, setores, equipamentos]) => {
        const equipPorSetor = new Map<number, EquipNode[]>();
        for (const e of equipamentos.results) {
          const lista = equipPorSetor.get(e.setor) ?? [];
          lista.push({ id: e.id, tag: e.tag, nome: e.nome });
          equipPorSetor.set(e.setor, lista);
        }
        const setoresPorArea = new Map<number, SetorNode[]>();
        for (const s of setores.results) {
          const lista = setoresPorArea.get(s.area) ?? [];
          lista.push({ id: s.id, nome: s.identificacao, equipamentos: equipPorSetor.get(s.id) ?? [] });
          setoresPorArea.set(s.area, lista);
        }
        setArvore(
          areas.results.map((a) => ({
            id: a.id,
            nome: a.identificacao,
            setores: setoresPorArea.get(a.id) ?? [],
          }))
        );
      })
      .catch(() => setArvore([]))
      .finally(() => setCarregando(false));
  }, [clienteId]);

  const toggleAberto = (chave: string) =>
    setAbertos((s) => {
      const n = new Set(s);
      n.has(chave) ? n.delete(chave) : n.add(chave);
      return n;
    });

  function marcar(ids: number[], marcar: boolean) {
    const n = new Set(sel);
    for (const id of ids) (marcar ? n.add(id) : n.delete(id));
    onChange([...n]);
  }
  const equipDoSetor = (s: SetorNode) => s.equipamentos.map((e) => e.id);
  const equipDaArea = (a: AreaNode) => a.setores.flatMap(equipDoSetor);
  const todosMarcados = (ids: number[]) => ids.length > 0 && ids.every((id) => sel.has(id));
  const algunsMarcados = (ids: number[]) => ids.some((id) => sel.has(id));

  // Filtro de busca: mantém áreas/setores que tenham algo correspondente.
  const arvoreFiltrada = useMemo(() => {
    const termo = q.trim().toLowerCase();
    if (!termo) return arvore;
    const bate = (t: string) => t.toLowerCase().includes(termo);
    return arvore
      .map((a) => {
        const setores = a.setores
          .map((s) => {
            if (bate(s.nome)) return s;
            const equipamentos = s.equipamentos.filter((e) => bate(e.tag) || bate(e.nome));
            return equipamentos.length ? { ...s, equipamentos } : null;
          })
          .filter((s): s is SetorNode => s !== null);
        return bate(a.nome) || setores.length ? { ...a, setores: bate(a.nome) ? a.setores : setores } : null;
      })
      .filter((a): a is AreaNode => a !== null);
  }, [arvore, q]);

  const buscando = q.trim() !== "";

  if (carregando) return <Spinner label="Carregando estrutura…" />;
  if (arvore.length === 0)
    return (
      <p className="py-6 text-center text-sm text-fg-subtle">
        Este cliente ainda não tem áreas/equipamentos cadastrados.
      </p>
    );

  return (
    <div>
      <Input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Buscar área, setor ou equipamento…"
        className="mb-3"
      />
      <div className="max-h-[420px] overflow-y-auto rounded-lg border border-border">
        {arvoreFiltrada.map((area) => {
          const idsArea = equipDaArea(area);
          const abertoA = abertos.has(`a-${area.id}`) || buscando;
          return (
            <div key={area.id} className="border-b border-border last:border-b-0">
              <div className="flex items-center gap-2 bg-surface-muted/50 px-3 py-2">
                <Checkbox
                  checado={todosMarcados(idsArea)}
                  parcial={algunsMarcados(idsArea)}
                  onChange={() => marcar(idsArea, !todosMarcados(idsArea))}
                />
                <button
                  type="button"
                  onClick={() => toggleAberto(`a-${area.id}`)}
                  className="flex flex-1 items-center gap-1.5 text-left text-sm font-semibold text-fg"
                >
                  <ChevronRight className={cn("h-4 w-4 shrink-0 text-fg-subtle transition-transform", abertoA && "rotate-90")} />
                  {area.nome}
                  <span className="ml-1 text-xs font-normal text-fg-subtle">
                    ({idsArea.length} equip.)
                  </span>
                </button>
              </div>

              {abertoA &&
                area.setores.map((setor) => {
                  const idsSetor = equipDoSetor(setor);
                  const abertoS = abertos.has(`s-${setor.id}`) || buscando;
                  return (
                    <div key={setor.id} className="border-t border-border/60">
                      <div className="flex items-center gap-2 py-1.5 pl-8 pr-3">
                        <Checkbox
                          checado={todosMarcados(idsSetor)}
                          parcial={algunsMarcados(idsSetor)}
                          onChange={() => marcar(idsSetor, !todosMarcados(idsSetor))}
                        />
                        <button
                          type="button"
                          onClick={() => toggleAberto(`s-${setor.id}`)}
                          className="flex flex-1 items-center gap-1.5 text-left text-[13px] font-medium text-fg-muted"
                        >
                          <ChevronRight className={cn("h-3.5 w-3.5 shrink-0 text-fg-subtle transition-transform", abertoS && "rotate-90")} />
                          {setor.nome}
                          <span className="ml-1 text-xs font-normal text-fg-subtle">
                            ({idsSetor.length})
                          </span>
                        </button>
                      </div>

                      {abertoS &&
                        (setor.equipamentos.length === 0 ? (
                          <p className="py-1 pl-16 pr-3 text-xs text-fg-subtle">Sem equipamentos.</p>
                        ) : (
                          setor.equipamentos.map((eq) => (
                            <label
                              key={eq.id}
                              className="flex cursor-pointer items-center gap-2 py-1.5 pl-16 pr-3 text-[13px] hover:bg-surface-muted/40"
                            >
                              <Checkbox
                                checado={sel.has(eq.id)}
                                onChange={() => marcar([eq.id], !sel.has(eq.id))}
                              />
                              <span className="font-mono text-xs font-semibold text-fg">{eq.tag}</span>
                              <span className="truncate text-fg-muted">{eq.nome}</span>
                            </label>
                          ))
                        ))}
                    </div>
                  );
                })}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ============================ Formulário ============================ */
type TecOpt = { id: number; nome: string };

export function RotaForm({ rotaId }: { rotaId?: number }) {
  const router = useRouter();
  const editando = rotaId !== undefined;
  const { clienteAtivo } = useClienteAtivo();

  const [nome, setNome] = useState("");
  const [tecnologia, setTecnologia] = useState<string>("");
  const [periodicidade, setPeriodicidade] = useState("");
  const [descricao, setDescricao] = useState("");
  const [equipamentos, setEquipamentos] = useState<number[]>([]);
  const [tecnologias, setTecnologias] = useState<TecOpt[]>([]);
  const [carregando, setCarregando] = useState(editando);
  const [salvando, setSalvando] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    api<Paginated<TecOpt>>("/tecnologias-analise/?page_size=1000")
      .then((d) => setTecnologias(d.results))
      .catch(() => setTecnologias([]));
  }, []);

  useEffect(() => {
    if (!editando) return;
    api<Rota>(`/rotas/${rotaId}/`)
      .then((r) => {
        setNome(r.nome ?? "");
        setTecnologia(r.tecnologia ? String(r.tecnologia) : "");
        setPeriodicidade(r.periodicidade_dias ? String(r.periodicidade_dias) : "");
        setDescricao(r.descricao ?? "");
        setEquipamentos(r.equipamentos ?? []);
      })
      .catch(() => setMsg("Não foi possível carregar esta rota."))
      .finally(() => setCarregando(false));
  }, [rotaId, editando]);

  async function salvar() {
    if (!clienteAtivo) return;
    setSalvando(true);
    setMsg(null);
    try {
      const body = {
        cliente: clienteAtivo.id,
        nome,
        tecnologia: tecnologia === "" ? null : Number(tecnologia),
        periodicidade_dias: periodicidade === "" ? null : Number(periodicidade),
        descricao,
        equipamentos,
      };
      if (editando) {
        await api(`/rotas/${rotaId}/`, { method: "PATCH", body });
      } else {
        await api("/rotas/", { method: "POST", body });
      }
      router.push("/rotas");
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "Erro ao salvar a rota.");
      setSalvando(false);
    }
  }

  const podeSalvar = nome.trim() !== "" && clienteAtivo;

  if (!clienteAtivo) {
    return (
      <Card>
        <p className="text-sm text-fg-muted">
          Ative um cliente no seletor do topo para montar uma rota.
        </p>
      </Card>
    );
  }
  if (carregando) {
    return (
      <Card>
        <Spinner label="Carregando rota…" />
      </Card>
    );
  }

  return (
    <div className="space-y-5">
      <div>
        <Link
          href="/rotas"
          className="inline-flex items-center gap-1.5 text-xs font-medium text-fg-muted transition-colors hover:text-fg"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Voltar para rotas
        </Link>
        <h1 className="mt-2 text-xl font-semibold tracking-tight text-fg">
          {editando ? "Editar rota" : "Nova rota"}
        </h1>
        <p className="mt-0.5 text-sm text-fg-muted">
          Rota de {clienteAtivo.nome_fantasia || clienteAtivo.nome}.
        </p>
      </div>

      <Card>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Field label="Nome da rota *" className="sm:col-span-2">
            <Input
              value={nome}
              maxLength={120}
              placeholder="Ex.: Rota Vibração — Utilidades"
              onChange={(e) => setNome(e.target.value)}
            />
          </Field>
          <Field label="Tecnologia">
            <Select value={tecnologia} onChange={(e) => setTecnologia(e.target.value)}>
              <option value="">— selecione —</option>
              {tecnologias.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.nome}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Periodicidade (dias)">
            <Input
              type="number"
              value={periodicidade}
              placeholder="Ex.: 30"
              onChange={(e) => setPeriodicidade(e.target.value)}
            />
          </Field>
          <Field label="Descrição" className="sm:col-span-2 lg:col-span-4">
            <Input value={descricao} onChange={(e) => setDescricao(e.target.value)} />
          </Field>
        </div>
      </Card>

      <Card>
        <div className="mb-4 flex items-start gap-3 border-b border-border pb-3">
          <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-accent-subtle text-accent">
            <MapPin className="h-4 w-4" />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-fg">Equipamentos da rota</h2>
            <p className="text-xs text-fg-subtle">
              Marque áreas, setores ou equipamentos. {equipamentos.length} selecionado
              {equipamentos.length === 1 ? "" : "s"}.
            </p>
          </div>
        </div>
        <ArvoreEquipamentos
          clienteId={clienteAtivo.id}
          selecionados={equipamentos}
          onChange={setEquipamentos}
        />
      </Card>

      {msg && (
        <Card>
          <p className="text-sm text-danger-fg">{msg}</p>
        </Card>
      )}
      <div className="flex flex-wrap items-center justify-end gap-3 pb-2">
        <span className="mr-auto text-xs text-fg-subtle">* campo obrigatório</span>
        <Button variant="secondary" onClick={() => router.push("/rotas")}>
          Cancelar
        </Button>
        <Button onClick={salvar} loading={salvando} disabled={!podeSalvar} icon={Save}>
          {editando ? "Salvar alterações" : "Criar rota"}
        </Button>
      </div>
    </div>
  );
}
