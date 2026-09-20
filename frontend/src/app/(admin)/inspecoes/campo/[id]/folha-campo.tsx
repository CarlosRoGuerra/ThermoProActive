"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  ClipboardCheck,
  ClipboardList,
  Loader2,
  Save,
  Send,
  Trash2,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Achado, Carregamento, Condicao, ItemInspecao, Paginated } from "@/lib/types";
import { AnaliseBalanceamento } from "@/components/analise-balanceamento";
import {
  Badge,
  Button,
  Card,
  ConfirmDialog,
  Field,
  LoadingState,
  PageBody,
  PageHeader,
  Textarea,
  cn,
  useConfirmacao,
  useToast,
} from "@/components/ds";
import { ModalAnalise } from "@/features/inspecoes/campo/modal-analise";
import { NavegadorEquipamentos, proximoPendente, vizinhos } from "@/features/inspecoes/campo/navegador-equipamentos";
import { PainelEquipamento } from "@/features/inspecoes/campo/painel-equipamento";
import { PainelPendencias } from "@/features/inspecoes/campo/painel-pendencias";
import { estadoDoItem } from "@/features/inspecoes/campo/progresso";

const ddmmaaaa = (iso: string | null) => (iso ? iso.split("-").reverse().join("/") : "—");

/* ---------------- Análise por equipamento — manutenção corretiva ---------------- */
// Reaproveita o mesmo painel que hoje vive em /servicos/atividades/[id]?item= — a
// Análise de campo é o único ponto de entrada, pra balanceamento ou qualquer outra
// tecnologia corretiva.
function AnaliseCorretivaItem({
  carregamentoId, item, podeEditar, onSaved,
}: {
  carregamentoId: number;
  item: ItemInspecao;
  podeEditar: boolean;
  onSaved: () => Promise<void>;
}) {
  const base = `/atividades-corretivas/${carregamentoId}`;
  const [observacoes, setObservacoes] = useState(item.observacoes_analise ?? "");
  const [ocupado, setOcupado] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => setObservacoes(item.observacoes_analise ?? ""), [item.id, item.observacoes_analise]);

  if (!item.analise) return <Card>Análise não encontrada nesta atividade.</Card>;

  return (
    <div className="space-y-3">
      {erro && <p role="alert" className="text-sm text-danger-fg">{erro}</p>}
      <Card className="space-y-4">
        <h2 className="font-semibold text-fg">{item.equipamento_tag} — {item.equipamento_nome}</h2>
        <p className="text-sm text-fg-muted">Condição: {item.condicao_nome || "Não informada"} · Análise iniciada</p>
        <p className="text-sm text-fg-muted">
          A análise está vinculada a este equipamento e à rota atual. O formulário técnico
          desta tecnologia corretiva estará disponível na próxima fase.
        </p>
        <Field label="Observações da atividade neste equipamento">
          <Textarea
            value={observacoes}
            onChange={(e) => setObservacoes(e.target.value)}
            disabled={!podeEditar || ocupado}
            rows={4}
          />
        </Field>
        {podeEditar && (
          <Button
            disabled={ocupado}
            onClick={async () => {
              setOcupado(true);
              setErro(null);
              try {
                await api(`${base}/itens/${item.id}/analise/`, { method: "PATCH", body: { observacoes } });
                await onSaved();
              } catch (e) {
                setErro(e instanceof ApiError ? e.message : "Não foi possível salvar. Tente novamente.");
              } finally {
                setOcupado(false);
              }
            }}
          >
            Salvar
          </Button>
        )}
      </Card>
    </div>
  );
}

/* ==========================================================================
   Folha de campo — Central de Análise de Campo, por equipamento.
   --------------------------------------------------------------------------
   Layout mestre-detalhe: navegador de equipamentos à esquerda (sempre visível
   no desktop, alternável no celular), painel do equipamento selecionado à
   direita. Sem seleção, a direita mostra a revisão da rota — resumo,
   pendências e transferência —, porque "onde eu parei" e "o que falta"
   respondem a mesma pergunta com o mesmo painel.

   Não existe botão de "Salvar" nesta tela: a condição é gravada assim que
   escolhida (PATCH imediato) e cada análise é gravada pelo próprio modal.
   A barra inferior do celular mostra o estado real dessa gravação — não um
   botão decorativo que fingiria acumular alterações que já foram para o
   servidor.
   ========================================================================== */
export function FolhaCampo({ carregamentoId }: { carregamentoId: number }) {
  const router = useRouter();
  const params = useSearchParams();
  const { user } = useAuth();
  const toast = useToast();

  const [carreg, setCarreg] = useState<Carregamento | null>(null);
  const [condicoes, setCondicoes] = useState<Condicao[]>([]);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState<string | null>(null);

  const itemQuery = params.get("item");
  const [selecionadoId, setSelecionadoId] = useState<number | null>(
    itemQuery ? Number(itemQuery) : null
  );
  const [mostrarListaMobile, setMostrarListaMobile] = useState(!itemQuery);
  const [salvandoCondicaoIds, setSalvandoCondicaoIds] = useState<Set<number>>(new Set());

  const [modal, setModal] = useState<{ item: ItemInspecao; achado: Achado | null } | null>(null);
  const [transferindo, setTransferindo] = useState(false);
  const [analisando, setAnalisando] = useState(false);
  const remocaoItem = useConfirmacao<ItemInspecao>();
  const remocaoAchado = useConfirmacao<Achado>();
  const [descartando, setDescartando] = useState(false);
  const [confirmandoDescarte, setConfirmandoDescarte] = useState(false);

  const itemId = params.get("item");
  const ehCorretiva = !!carreg?.tipo_corretiva;
  const podeEditar = !!user?.is_interno && carreg?.status === "EM_CAMPO";

  const recarregar = useCallback(async () => {
    const d = await api<Carregamento>(`/carregamentos/${carregamentoId}/`);
    setCarreg(d);
  }, [carregamentoId]);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      api<Carregamento>(`/carregamentos/${carregamentoId}/`),
      api<Paginated<Condicao>>("/condicoes/?page_size=500"),
    ])
      .then(([c, cond]) => {
        setCarreg(c);
        setCondicoes(cond.results);
      })
      .catch(() => setMsg("Não foi possível carregar esta rota."))
      .finally(() => setLoading(false));
  }, [carregamentoId]);

  // Se o item selecionado sair da rota (removido, ou rota recarregada sem ele),
  // volta para a revisão em vez de mostrar um painel de equipamento fantasma.
  useEffect(() => {
    if (!carreg || selecionadoId == null) return;
    if (!carreg.itens.some((i) => i.id === selecionadoId)) setSelecionadoId(null);
  }, [carreg, selecionadoId]);

  const selecionado = useMemo(
    () => carreg?.itens.find((i) => i.id === selecionadoId) ?? null,
    [carreg, selecionadoId]
  );

  function selecionar(item: ItemInspecao | null) {
    setSelecionadoId(item?.id ?? null);
    setMostrarListaMobile(false);
  }

  async function definirCondicao(item: ItemInspecao, valor: string) {
    setSalvandoCondicaoIds((s) => new Set(s).add(item.id));
    try {
      await api(`/itens-inspecao/${item.id}/`, {
        method: "PATCH",
        body: { condicao: valor === "" ? null : Number(valor) },
      });
      await recarregar();
    } catch (e) {
      toast.falha(e, "Não foi possível salvar a condição.");
    } finally {
      setSalvandoCondicaoIds((s) => {
        const n = new Set(s);
        n.delete(item.id);
        return n;
      });
    }
  }

  // Manutenção corretiva: "Analisar" cria (se preciso) o ServicoCampo do equipamento
  // e abre o painel de análise por equipamento (?item=), sem sair da Análise de campo.
  async function analisarCorretiva(item: ItemInspecao) {
    if (item.analise) {
      router.push(`/inspecoes/campo/${carregamentoId}?item=${item.id}`);
      return;
    }
    setAnalisando(true);
    try {
      await api(`/atividades-corretivas/${carregamentoId}/itens/${item.id}/analise/`, { method: "POST" });
      await recarregar();
      router.push(`/inspecoes/campo/${carregamentoId}?item=${item.id}`);
    } catch (e) {
      toast.falha(e, "Não foi possível iniciar a análise.");
    } finally {
      setAnalisando(false);
    }
  }

  async function adicionarLinha(item: ItemInspecao) {
    const maxOrdem = Math.max(0, ...(carreg?.itens.map((i) => i.ordem) ?? [0]));
    try {
      await api("/itens-inspecao/", {
        method: "POST",
        body: { carregamento: carregamentoId, equipamento: item.equipamento, ordem: maxOrdem + 1 },
      });
      toast.sucesso(`Nova linha de ${item.equipamento_tag} adicionada`);
      await recarregar();
    } catch (e) {
      toast.falha(e, "Não foi possível adicionar a linha.");
    }
  }

  async function removerItem(item: ItemInspecao) {
    try {
      await api(`/itens-inspecao/${item.id}/`, { method: "DELETE" });
      toast.sucesso(`Linha de ${item.equipamento_tag} removida`);
      await recarregar();
    } catch (e) {
      toast.falha(e, "Não foi possível remover esta linha.");
    }
  }

  async function removerAchado(a: Achado) {
    try {
      await api(`/achados/${a.id}/`, { method: "DELETE" });
      toast.sucesso("Análise removida");
      await recarregar();
    } catch (e) {
      toast.falha(e, "Não foi possível remover esta análise.");
    }
  }

  async function transferir() {
    setTransferindo(true);
    try {
      await api(`/carregamentos/${carregamentoId}/transferir/`, { method: "POST" });
      toast.sucesso("Rota transferida para o escritório");
      router.push("/inspecoes/campo");
    } catch (e) {
      toast.falha(e, "Não foi possível transferir a rota.");
      setTransferindo(false);
    }
  }

  async function descartar() {
    setDescartando(true);
    try {
      await api(`/carregamentos/${carregamentoId}/descartar/`, { method: "POST" });
      toast.sucesso("Rota descartada");
      router.push("/inspecoes/campo");
    } catch (e) {
      setDescartando(false);
      setConfirmandoDescarte(false);
      toast.falha(e, "Não foi possível descartar esta rota.");
    }
  }

  if (loading) return <LoadingState variante="tabela" linhas={6} colunas={5} label="Carregando a folha de campo…" />;
  if (!carreg) return <Card><p className="text-sm text-danger-fg">{msg ?? "Rota não encontrada."}</p></Card>;

  const pendentes = carreg.itens.filter((i) => i.condicao == null).length;
  const transferida = carreg.status !== "EM_CAMPO";

  // Manutenção corretiva — "Análise por equipamento": mesmo painel de
  // /servicos/atividades/[id]?item=, agora dentro da Análise de campo.
  if (ehCorretiva && itemId) {
    const item = carreg.itens.find((i) => String(i.id) === itemId);
    return (
      <div className="space-y-5">
        <Link
          href={`/inspecoes/campo/${carregamentoId}`}
          className="inline-flex items-center gap-1.5 text-xs font-medium text-fg-muted transition-colors hover:text-fg"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Voltar para equipamentos da rota
        </Link>
        {!item ? (
          <Card>Análise não encontrada nesta atividade.</Card>
        ) : carreg.tipo_corretiva === "BALANCEAMENTO" ? (
          <AnaliseBalanceamento
            key={item.id}
            atividadeId={String(carregamentoId)}
            item={item}
            podeEditar={podeEditar}
            onSaved={recarregar}
          />
        ) : (
          <AnaliseCorretivaItem
            carregamentoId={carregamentoId}
            item={item}
            podeEditar={podeEditar}
            onSaved={recarregar}
          />
        )}
      </div>
    );
  }

  const viz = vizinhos(carreg.itens, selecionadoId);
  const salvandoAtual = selecionado ? salvandoCondicaoIds.has(selecionado.id) : false;

  return (
    <PageBody className={cn(selecionado && "pb-24 lg:pb-6")}>
      <PageHeader
        icon={ClipboardCheck}
        title={carreg.numero || `Carregamento #${carreg.id}`}
        description={`${carreg.rota_nome ? `Rota ${carreg.rota_nome} · ` : ""}${carreg.analista_nome} · término ${ddmmaaaa(carreg.data_termino)}`}
        trilha={[
          { label: "Inspeções", href: "/inspecoes/campo" },
          { label: "Análise de campo", href: "/inspecoes/campo" },
          { label: carreg.numero || `#${carreg.id}` },
        ]}
        selo={
          <>
            <Badge tone="primary">{carreg.tecnologia_nome}</Badge>
            {transferida && <Badge tone="neutral">{carreg.status_display}</Badge>}
          </>
        }
        actions={
          !transferida ? (
            <>
              <Button variant="ghost" icon={Trash2} onClick={() => setConfirmandoDescarte(true)}>
                Apagar tudo
              </Button>
              <Button
                icon={Send}
                onClick={transferir}
                loading={transferindo}
                disabled={pendentes > 0 || carreg.itens.length === 0}
                title={
                  pendentes > 0
                    ? "Preencha a condição de todos os equipamentos para liberar a transferência"
                    : undefined
                }
              >
                Transferir para o escritório
              </Button>
            </>
          ) : undefined
        }
      />

      {msg && (
        <Card>
          <p className="text-sm text-danger-fg">{msg}</p>
        </Card>
      )}

      {/* ---------- Mestre-detalhe ---------- */}
      <div className="lg:grid lg:grid-cols-[336px_1fr] lg:items-start lg:gap-6">
        {/* Navegador — desktop: sempre visível, fixo, rolagem própria. */}
        <div className="hidden lg:sticky lg:top-[88px] lg:block lg:max-h-[calc(100dvh-104px)] lg:overflow-hidden lg:rounded-xl lg:border lg:border-border lg:bg-surface">
          <NavegadorEquipamentos
            itens={carreg.itens}
            selecionadoId={selecionadoId}
            onSelecionar={selecionar}
            className="max-h-[calc(100dvh-104px)]"
          />
        </div>

        {/* Navegador — celular: uma das duas telas (lista OU conteúdo). */}
        <div className={cn("lg:hidden", !mostrarListaMobile && "hidden")}>
          <div className="overflow-hidden rounded-xl border border-border bg-surface">
            <div className="flex items-center justify-between gap-2 border-b border-border px-3 py-2.5">
              <p className="text-sm font-medium text-fg">Equipamentos da rota</p>
              <button
                type="button"
                onClick={() => selecionar(null)}
                className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-primary transition-colors hover:bg-primary-subtle"
              >
                <ClipboardList className="h-3.5 w-3.5" aria-hidden="true" />
                Revisão e transferência
              </button>
            </div>
            <NavegadorEquipamentos
              itens={carreg.itens}
              selecionadoId={selecionadoId}
              onSelecionar={selecionar}
              className="max-h-[65dvh]"
            />
          </div>
        </div>

        {/* Conteúdo — desktop: sempre visível. Celular: só quando a lista está fechada. */}
        <div className={cn("min-w-0 space-y-4", mostrarListaMobile && "hidden lg:block")}>
          <div className="flex items-center justify-between gap-3">
            <button
              type="button"
              onClick={() => setMostrarListaMobile(true)}
              className="inline-flex items-center gap-1.5 text-xs font-medium text-fg-muted transition-colors hover:text-fg lg:hidden"
            >
              <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
              Equipamentos
            </button>

            {selecionado && (
              <div className="ml-auto hidden items-center gap-1 lg:flex">
                <Button
                  size="sm"
                  variant="ghost"
                  icon={ChevronLeft}
                  disabled={!viz.anterior}
                  onClick={() => selecionar(viz.anterior)}
                >
                  Anterior
                </Button>
                <span className="data px-1 text-xs text-fg-subtle">
                  {viz.posicao}/{viz.total}
                </span>
                <Button
                  size="sm"
                  variant="ghost"
                  iconRight={ChevronRight}
                  disabled={!viz.proximo}
                  onClick={() => selecionar(viz.proximo)}
                >
                  Próximo
                </Button>
              </div>
            )}
          </div>

          {selecionado ? (
            ehCorretiva ? (
              <PainelEquipamento
                item={selecionado}
                condicoes={condicoes}
                podeEditar={podeEditar}
                ehCorretiva
                salvandoCondicao={salvandoAtual}
                onDefinirCondicao={(v) => definirCondicao(selecionado, v)}
                onNovaAnalise={() => {}}
                onEditarAnalise={() => {}}
                onRemoverAnalise={() => {}}
                onAnalisarCorretiva={() => analisarCorretiva(selecionado)}
                onAdicionarLinha={() => adicionarLinha(selecionado)}
                onRemoverItem={() => remocaoItem.pedir(selecionado)}
              />
            ) : (
              <PainelEquipamento
                item={selecionado}
                condicoes={condicoes}
                podeEditar={podeEditar}
                ehCorretiva={false}
                salvandoCondicao={salvandoAtual}
                onDefinirCondicao={(v) => definirCondicao(selecionado, v)}
                onNovaAnalise={() => setModal({ item: selecionado, achado: null })}
                onEditarAnalise={(a) => setModal({ item: selecionado, achado: a })}
                onRemoverAnalise={(a) => remocaoAchado.pedir(a)}
                onAnalisarCorretiva={() => {}}
                onAdicionarLinha={() => adicionarLinha(selecionado)}
                onRemoverItem={() => remocaoItem.pedir(selecionado)}
              />
            )
          ) : (
            <PainelPendencias
              carregamento={carreg}
              itens={carreg.itens}
              podeEditar={podeEditar}
              transferindo={transferindo}
              onTransferir={transferir}
              onSelecionar={selecionar}
            />
          )}
        </div>
      </div>

      {!ehCorretiva && (
        <ModalAnalise
          aberto={!!modal}
          item={modal?.item ?? null}
          achado={modal?.achado ?? null}
          tecnologiaNome={carreg.tecnologia_nome}
          tecnologiaId={carreg.tecnologia}
          onFechar={() => setModal(null)}
          onSalvo={async () => {
            setModal(null);
            await recarregar();
          }}
        />
      )}

      <ConfirmDialog
        aberto={!!remocaoItem.alvo}
        onFechar={remocaoItem.cancelar}
        onConfirmar={() => remocaoItem.executar(removerItem)}
        enviando={remocaoItem.enviando}
        title="Remover esta linha?"
        confirmarLabel="Remover linha"
        mensagem={
          <>
            A linha do equipamento <strong>{remocaoItem.alvo?.equipamento_tag}</strong> sai desta
            folha de campo.
          </>
        }
        detalhe={
          remocaoItem.alvo?.achados?.length
            ? `As ${remocaoItem.alvo.achados.length} análise(s) registradas nesta linha também são apagadas.`
            : "O equipamento continua cadastrado e nas outras rotas."
        }
        irreversivel
      />

      <ConfirmDialog
        aberto={!!remocaoAchado.alvo}
        onFechar={remocaoAchado.cancelar}
        onConfirmar={() => remocaoAchado.executar(removerAchado)}
        enviando={remocaoAchado.enviando}
        title="Remover esta análise?"
        confirmarLabel="Remover análise"
        mensagem={
          <>
            A análise{" "}
            <strong>
              {remocaoAchado.alvo?.tipo_componente_nome ||
                remocaoAchado.alvo?.componente_texto ||
                "registrada"}
            </strong>{" "}
            será apagada desta folha.
          </>
        }
        irreversivel
      />

      <ConfirmDialog
        aberto={confirmandoDescarte}
        onFechar={() => setConfirmandoDescarte(false)}
        onConfirmar={descartar}
        enviando={descartando}
        title="Apagar tudo desta rota carregada?"
        confirmarLabel="Apagar tudo"
        mensagem={
          <>
            Todas as condições e análises lançadas nesta carga da rota{" "}
            <strong>{carreg.rota_nome}</strong> serão apagadas.
          </>
        }
        detalhe="A rota volta a estar disponível para carregar de novo, em branco."
        irreversivel
      />

      {/* ---------- Barra fixa do celular ---------- */}
      {selecionado && (
        <div className="fixed inset-x-0 bottom-0 z-sticky border-t border-border bg-surface/95 px-3 py-2.5 pb-[calc(0.625rem+env(safe-area-inset-bottom))] backdrop-blur-md lg:hidden">
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="secondary"
              icon={ChevronLeft}
              disabled={!viz.anterior}
              onClick={() => selecionar(viz.anterior)}
              className="shrink-0"
            >
              <span className="sr-only sm:not-sr-only">Anterior</span>
            </Button>

            <EstadoSalvamento salvando={salvandoAtual} estado={estadoDoItem(selecionado)} />

            {(() => {
              const prox = proximoPendente(carreg.itens, selecionado.id);
              return prox ? (
                <Button size="sm" block onClick={() => selecionar(prox)} iconRight={ChevronRight}>
                  Próximo pendente
                </Button>
              ) : (
                <Button
                  size="sm"
                  variant="secondary"
                  iconRight={ChevronRight}
                  disabled={!viz.proximo}
                  onClick={() => selecionar(viz.proximo)}
                  className="shrink-0"
                >
                  <span className="sr-only sm:not-sr-only">Próximo</span>
                </Button>
              );
            })()}
          </div>
        </div>
      )}
    </PageBody>
  );
}

/**
 * Estado de gravação do item atual, no centro da barra inferior.
 *
 * Não é um botão "Salvar": a condição já foi enviada ao servidor assim que
 * escolhida. Isto só relata o que aconteceu — inclusive porque, em campo,
 * a rede cai, e sem esta pista o técnico não saberia se a última condição
 * marcada realmente chegou ao servidor.
 */
function EstadoSalvamento({
  salvando,
  estado,
}: {
  salvando: boolean;
  estado: ReturnType<typeof estadoDoItem>;
}) {
  if (salvando) {
    return (
      <span className="inline-flex flex-1 items-center justify-center gap-1.5 text-xs text-fg-muted">
        <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
        Salvando…
      </span>
    );
  }
  if (estado === "PENDENTE") {
    return (
      <span className="inline-flex flex-1 items-center justify-center gap-1.5 text-xs text-fg-subtle">
        <Save className="h-3.5 w-3.5" aria-hidden="true" />
        Sem condição
      </span>
    );
  }
  return (
    <span className="inline-flex flex-1 items-center justify-center gap-1.5 text-xs text-success-fg">
      <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
      Salvo
    </span>
  );
}
