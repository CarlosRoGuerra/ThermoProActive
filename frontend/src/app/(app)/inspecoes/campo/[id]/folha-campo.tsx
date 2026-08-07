"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft, ClipboardCheck, CopyPlus, Pencil, Plus, Send, Trash2,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { Achado, Carregamento, Condicao, ItemInspecao, Paginated } from "@/lib/types";
import {
  type AchadoForm, formDeAchado, formVazio, payloadDeForm, tecnologiaTipo,
} from "@/lib/inspecoes";
import { AchadoCampos } from "@/components/achado-campos";
import { Badge, Button, Card, Select, Spinner } from "@/components/ui";

const ddmmaaaa = (iso: string | null) => (iso ? iso.split("-").reverse().join("/") : "—");

/* ---------------------------- Modal de análise ---------------------------- */
function AnaliseModal({
  item, achado, tecnologiaNome, tecnologiaId, onClose, onSaved,
}: {
  item: ItemInspecao;
  achado: Achado | null;
  tecnologiaNome: string;
  tecnologiaId: number;
  onClose: () => void;
  onSaved: () => void;
}) {
  // Nova análise herda a condição do item (reclassificável no escritório).
  const [form, setForm] = useState<AchadoForm>(
    achado
      ? formDeAchado(achado)
      : { ...formVazio(), condicao: item.condicao != null ? String(item.condicao) : "" }
  );
  const [salvando, setSalvando] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function salvar() {
    setSalvando(true);
    setMsg(null);
    try {
      const body = payloadDeForm(form);
      if (achado) {
        await api(`/achados/${achado.id}/`, { method: "PATCH", body });
      } else {
        await api("/achados/", { method: "POST", body: { ...body, item: item.id } });
      }
      onSaved();
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "Erro ao salvar a análise.");
      setSalvando(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/50 p-4">
      <div className="my-8 w-full max-w-3xl rounded-xl border border-border bg-surface p-6 shadow-xl">
        <div className="mb-4 flex items-start justify-between gap-3 border-b border-border pb-3">
          <div>
            <h2 className="text-base font-semibold text-fg">
              {achado ? "Editar análise" : "Nova análise"}
            </h2>
            <p className="mt-0.5 text-sm text-fg-muted">
              <span className="font-mono font-semibold text-fg">{item.equipamento_tag}</span>{" "}
              {item.equipamento_nome} · {tecnologiaNome}
            </p>
          </div>
        </div>

        <AchadoCampos form={form} setForm={setForm} tipo={tecnologiaTipo(tecnologiaNome)} tecnologiaId={tecnologiaId} />

        {msg && <p className="mt-3 text-sm text-danger-fg">{msg}</p>}
        <div className="mt-5 flex items-center justify-end gap-3 border-t border-border pt-4">
          <Button variant="secondary" onClick={onClose}>Cancelar</Button>
          <Button onClick={salvar} loading={salvando} icon={ClipboardCheck}>
            {achado ? "Salvar análise" : "Adicionar análise"}
          </Button>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------- Folha de campo --------------------------- */
export function FolhaCampo({ carregamentoId }: { carregamentoId: number }) {
  const router = useRouter();
  const [carreg, setCarreg] = useState<Carregamento | null>(null);
  const [condicoes, setCondicoes] = useState<Condicao[]>([]);
  const [loading, setLoading] = useState(true);
  const [modal, setModal] = useState<{ item: ItemInspecao; achado: Achado | null } | null>(null);
  const [transferindo, setTransferindo] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const recarregar = useCallback(async () => {
    const d = await api<Carregamento>(`/carregamentos/${carregamentoId}/`);
    setCarreg(d);
  }, [carregamentoId]);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      api<Carregamento>(`/carregamentos/${carregamentoId}/`),
      api<Paginated<Condicao>>("/condicoes/?page_size=1000"),
    ])
      .then(([c, cond]) => {
        setCarreg(c);
        setCondicoes(cond.results);
      })
      .catch(() => setMsg("Não foi possível carregar esta rota."))
      .finally(() => setLoading(false));
  }, [carregamentoId]);

  const condById = useMemo(() => new Map(condicoes.map((c) => [c.id, c])), [condicoes]);

  async function definirCondicao(item: ItemInspecao, valor: string) {
    setMsg(null);
    try {
      await api(`/itens-inspecao/${item.id}/`, {
        method: "PATCH",
        body: { condicao: valor === "" ? null : Number(valor) },
      });
      await recarregar();
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "Erro ao salvar a condição.");
    }
  }

  async function adicionarLinha(item: ItemInspecao) {
    const maxOrdem = Math.max(0, ...(carreg?.itens.map((i) => i.ordem) ?? [0]));
    await api("/itens-inspecao/", {
      method: "POST",
      body: { carregamento: carregamentoId, equipamento: item.equipamento, ordem: maxOrdem + 1 },
    });
    await recarregar();
  }

  async function removerItem(item: ItemInspecao) {
    if (!confirm(`Remover a linha do equipamento ${item.equipamento_tag}?`)) return;
    await api(`/itens-inspecao/${item.id}/`, { method: "DELETE" });
    await recarregar();
  }

  async function removerAchado(a: Achado) {
    if (!confirm("Remover esta análise?")) return;
    await api(`/achados/${a.id}/`, { method: "DELETE" });
    await recarregar();
  }

  async function transferir() {
    setTransferindo(true);
    setMsg(null);
    try {
      await api(`/carregamentos/${carregamentoId}/transferir/`, { method: "POST" });
      router.push("/inspecoes/campo");
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "Erro ao transferir.");
      setTransferindo(false);
    }
  }

  async function descartar() {
    if (!confirm("Apagar TUDO desta rota carregada? Esta ação não pode ser desfeita.")) return;
    await api(`/carregamentos/${carregamentoId}/descartar/`, { method: "POST" });
    router.push("/inspecoes/campo");
  }

  if (loading) return <Card><Spinner label="Carregando folha de campo…" /></Card>;
  if (!carreg) return <Card><p className="text-sm text-danger-fg">{msg ?? "Rota não encontrada."}</p></Card>;

  const pendentes = carreg.itens.filter((i) => i.condicao == null).length;
  const transferida = carreg.status !== "EM_CAMPO";

  return (
    <div className="space-y-5">
      <div>
        <Link
          href="/inspecoes/campo"
          className="inline-flex items-center gap-1.5 text-xs font-medium text-fg-muted transition-colors hover:text-fg"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Voltar para Análise de campo
        </Link>
      </div>

      {/* Cabeçalho da rota */}
      <Card>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="font-mono text-lg font-semibold tracking-tight text-fg">
                {carreg.numero || `Carregamento #${carreg.id}`}
              </h1>
              <Badge tone="accent">{carreg.tecnologia_nome}</Badge>
              {transferida && <Badge tone="neutral">{carreg.status_display}</Badge>}
            </div>
            <p className="mt-1 text-sm text-fg-muted">
              {carreg.rota_nome ? `Rota ${carreg.rota_nome} · ` : ""}
              {carreg.analista_nome} · término {ddmmaaaa(carreg.data_termino)}
            </p>
          </div>
          {!transferida && (
            <div className="flex flex-wrap items-center gap-2">
              <Button variant="ghost" icon={Trash2} onClick={descartar}>Apagar tudo</Button>
              <Button
                icon={Send}
                onClick={transferir}
                loading={transferindo}
                disabled={pendentes > 0 || carreg.itens.length === 0}
              >
                Transferir
              </Button>
            </div>
          )}
        </div>
        {!transferida && (
          <p className="mt-3 text-xs text-fg-subtle">
            {pendentes > 0
              ? `${pendentes} equipamento(s) sem condição — preencha todos para liberar a transferência.`
              : "Todos os equipamentos têm condição. Pode transferir."}
          </p>
        )}
        {msg && <p className="mt-2 text-sm text-danger-fg">{msg}</p>}
      </Card>

      {/* Itens da rota */}
      <div className="space-y-3">
        {carreg.itens.map((item) => {
          const cond = item.condicao != null ? condById.get(item.condicao) : null;
          const geraAcao = cond?.gera_acao ?? item.condicao_gera_acao ?? false;
          return (
            <Card key={item.id}>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="rounded bg-surface-muted px-1.5 py-0.5 font-mono text-xs text-fg-subtle">
                      #{item.ordem}
                    </span>
                    <span className="font-mono text-sm font-semibold text-fg">{item.equipamento_tag}</span>
                    <span className="truncate text-sm text-fg-muted">{item.equipamento_nome}</span>
                  </div>
                  <p className="mt-0.5 text-xs text-fg-subtle">
                    {item.area_nome} · {item.setor_nome} · {ddmmaaaa(item.data)}
                  </p>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <div className="w-52">
                    <Select
                      value={item.condicao != null ? String(item.condicao) : ""}
                      onChange={(e) => definirCondicao(item, e.target.value)}
                      disabled={transferida}
                    >
                      <option value="">— condição —</option>
                      {condicoes.map((c) => (
                        <option key={c.id} value={c.id}>{c.nome}</option>
                      ))}
                    </Select>
                  </div>
                  {!transferida && (
                    <>
                      {geraAcao && (
                        <Button
                          variant="secondary"
                          icon={Plus}
                          onClick={() => setModal({ item, achado: null })}
                        >
                          Analisar
                        </Button>
                      )}
                      <button
                        onClick={() => adicionarLinha(item)}
                        title="Adicionar outra linha deste equipamento"
                        className="inline-flex items-center gap-1 rounded-md px-2 py-1.5 text-xs font-medium text-fg-muted transition-colors hover:bg-surface-muted hover:text-fg"
                      >
                        <CopyPlus className="h-3.5 w-3.5" /> linha
                      </button>
                      <button
                        onClick={() => removerItem(item)}
                        title="Remover esta linha"
                        className="inline-flex items-center gap-1 rounded-md px-2 py-1.5 text-xs font-medium text-danger-fg transition-colors hover:bg-danger-subtle"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </>
                  )}
                </div>
              </div>

              {/* Análises registradas neste item */}
              {item.achados.length > 0 && (
                <div className="mt-3 space-y-1.5 border-t border-border pt-3">
                  {item.achados.map((a) => (
                    <div
                      key={a.id}
                      className="flex items-center justify-between gap-3 rounded-lg bg-surface-muted/50 px-3 py-2"
                    >
                      <div className="flex min-w-0 items-center gap-2 text-sm">
                        {(a.condicao_sigla || a.condicao_nome) && (
                          <Badge tone="warning">{a.condicao_sigla || a.condicao_nome}</Badge>
                        )}
                        <span className="truncate">
                          <span className="font-medium text-fg">
                            {a.tipo_componente_nome || a.componente_texto || "Análise"}
                          </span>
                          {(a.tipo_anomalia_nome || a.anomalia_texto) && (
                            <span className="text-fg-muted"> — {a.tipo_anomalia_nome || a.anomalia_texto}</span>
                          )}
                        </span>
                      </div>
                      {!transferida && (
                        <div className="flex shrink-0 items-center gap-1">
                          <button
                            onClick={() => setModal({ item, achado: a })}
                            className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-fg-muted transition-colors hover:bg-surface hover:text-fg"
                          >
                            <Pencil className="h-3.5 w-3.5" /> Editar
                          </button>
                          <button
                            onClick={() => removerAchado(a)}
                            className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-danger-fg transition-colors hover:bg-danger-subtle"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </Card>
          );
        })}
        {carreg.itens.length === 0 && (
          <Card>
            <p className="text-sm text-fg-muted">
              Esta rota não trouxe equipamentos. Verifique se a rota tem equipamentos selecionados.
            </p>
          </Card>
        )}
      </div>

      {modal && (
        <AnaliseModal
          item={modal.item}
          achado={modal.achado}
          tecnologiaNome={carreg.tecnologia_nome}
          tecnologiaId={carreg.tecnologia}
          onClose={() => setModal(null)}
          onSaved={async () => {
            setModal(null);
            await recarregar();
          }}
        />
      )}
    </div>
  );
}
