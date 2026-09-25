"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  ChevronsRight,
  ClipboardCheck,
  ClipboardList,
  Loader2,
  Save,
  Send,
  Trash2,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { mensagemDeErro } from "@/lib/erros";
import { plural } from "@/lib/format";
import type { Achado, Carregamento, Condicao, ItemInspecao, Paginated } from "@/lib/types";
import { AnaliseBalanceamento } from "@/components/analise-balanceamento";
import { EditorTransformador } from "@/features/ensaios/editor";
import { ehModuloTransformador, type TransformadorInspecao } from "@/features/ensaios/tipos";
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
import {
  NavegadorEquipamentos,
  filtrarPorBusca,
  proximoPendente,
  vizinhos,
  type Filtro,
} from "@/features/inspecoes/campo/navegador-equipamentos";
import { PainelEquipamento } from "@/features/inspecoes/campo/painel-equipamento";
import { PainelPendencias } from "@/features/inspecoes/campo/painel-pendencias";
import { estadoDoItem } from "@/features/inspecoes/campo/progresso";
import { condicoesEmOrdem } from "@/features/inspecoes/campo/seletor-condicao";

const ddmmaaaa = (iso: string | null) => (iso ? iso.split("-").reverse().join("/") : "—");

/* ---------------- Condição no estado local ---------------- */

type CamposCondicao = Pick<ItemInspecao, "condicao" | "condicao_nome" | "condicao_gera_acao">;

function camposDe(c: Condicao | null): CamposCondicao {
  return { condicao: c?.id ?? null, condicao_nome: c?.nome ?? null, condicao_gera_acao: c ? c.gera_acao : null };
}

function camposDoItem(i: ItemInspecao): CamposCondicao {
  return { condicao: i.condicao, condicao_nome: i.condicao_nome, condicao_gera_acao: i.condicao_gera_acao };
}

/** Troca SÓ a condição dos itens indicados — achados e o resto seguem como estão. */
function comCondicoes(c: Carregamento | null, campos: Map<number, CamposCondicao>): Carregamento | null {
  if (!c || campos.size === 0) return c;
  return {
    ...c,
    itens: c.itens.map((i) => {
      const novo = campos.get(i.id);
      return novo ? { ...i, ...novo } : i;
    }),
  };
}

/** Troca itens inteiros pela versão que o servidor devolveu. */
function comItens(c: Carregamento | null, novos: ItemInspecao[]): Carregamento | null {
  if (!c || novos.length === 0) return c;
  const porId = new Map(novos.map((i) => [i.id, i]));
  return { ...c, itens: c.itens.map((i) => porId.get(i.id) ?? i) };
}

const ehPendente = (i: ItemInspecao) => {
  const e = estadoDoItem(i);
  return e === "PENDENTE" || e === "INCOMPLETO";
};

/** Depois do avanço automático o botão tocado continua sob o dedo: um toque
 *  duplo marcaria o PRÓXIMO equipamento sem o técnico ver. Cliques dentro desta
 *  janela são descartados — o teclado não passa por ela. */
const GUARDA_TOQUE_DUPLO_MS = 400;

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

   Ritmo de campo: numa rota quase tudo está normal, então o caminho comum
   custa um gesto por equipamento. Classificar um pendente com condição que
   não exige ação grava e já abre o próximo pendente; com condição que exige
   ação, abre o registro da análise e só segue depois de salvo. Corrigir uma
   condição já dada não mexe na navegação. No desktop, 1–9 escolhem a
   condição e ←/→ trocam de equipamento. Para a rota inteira normal, o
   navegador tem o lançamento em lote.

   Gravação otimista: a condição aparece na hora e o PATCH segue por baixo.
   A resposta troca só aquele item — reler a rota inteira a cada toque era o
   que deixava a tela lenta em campo. Se o envio falha, a condição volta ao
   que era e o técnico é avisado com a TAG. Cada envio leva uma versão, e só
   a resposta do mais recente de cada item vale (dois toques rápidos no mesmo
   equipamento não se atropelam).

   Não existe botão de "Salvar" nesta tela: a condição é gravada assim que
   escolhida e cada análise é gravada pelo próprio modal. A barra inferior do
   celular mostra o estado real dessa gravação — não um botão decorativo que
   fingiria acumular alterações que já foram para o servidor.
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
  const [busca, setBusca] = useState("");
  const [filtro, setFiltro] = useState<Filtro>("todos");

  // Condições a caminho do servidor, por item, com a versão do envio.
  const emVoo = useRef(new Map<number, { versao: number; condicao: Condicao | null }>());
  const ultimaVersao = useRef(0);
  const envios = useRef(new Set<Promise<unknown>>());
  const [salvandoIds, setSalvandoIds] = useState<Set<number>>(new Set());

  // Pista do último avanço automático: o que acabou de ser gravado e o caminho de volta.
  const [ultimo, setUltimo] = useState<{ id: number; tag: string; condicao: string } | null>(null);
  const avancouEm = useRef(0);

  const [modal, setModal] = useState<{
    item: ItemInspecao;
    achado: Achado | null;
    /** Aberto pela classificação: salvo o registro, a folha segue para o próximo. */
    avancarAoSalvar?: boolean;
  } | null>(null);
  const [transferindo, setTransferindo] = useState(false);
  const [analisando, setAnalisando] = useState(false);
  const remocaoItem = useConfirmacao<ItemInspecao>();
  const remocaoAchado = useConfirmacao<Achado>();
  const [descartando, setDescartando] = useState(false);
  const [confirmandoDescarte, setConfirmandoDescarte] = useState(false);

  const itemId = params.get("item");
  const ehCorretiva = !!carreg?.tipo_corretiva;
  // Óleo isolante / ensaios elétricos: cada transformador tem o lançamento próprio (?item=).
  const moduloTrafo = ehModuloTransformador(carreg?.modulo_tecnico) ? carreg!.modulo_tecnico : null;
  const podeEditar = !!user?.is_interno && carreg?.status === "EM_CAMPO";
  const [resumoTrafo, setResumoTrafo] = useState<Map<number, TransformadorInspecao> | null>(null);

  const recarregar = useCallback(async () => {
    const d = await api<Carregamento>(`/carregamentos/${carregamentoId}/`);
    // Condição ainda a caminho vale mais que esta leitura: o GET pode ter
    // saído antes de o PATCH gravar.
    const voando = new Map(Array.from(emVoo.current, ([id, v]) => [id, camposDe(v.condicao)] as const));
    const atual = comCondicoes(d, voando) ?? d;
    setCarreg(atual);
    return atual;
  }, [carregamentoId]);

  const atualizar = useCallback(async () => {
    await recarregar();
  }, [recarregar]);

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

  // Resumo dos ensaios por transformador (registro e laudos) para o painel. Relido
  // ao voltar do lançamento de um transformador, que é onde ele muda.
  useEffect(() => {
    if (!moduloTrafo || itemId) return;
    api<Paginated<TransformadorInspecao>>(`/transformadores-inspecao/?carregamento=${carregamentoId}&page_size=500`)
      .then((r) => setResumoTrafo(new Map(r.results.map((t) => [t.id, t]))))
      .catch(() => setResumoTrafo(new Map()));
  }, [moduloTrafo, itemId, carregamentoId]);

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

  function irPara(item: ItemInspecao | null) {
    setSelecionadoId(item?.id ?? null);
    setMostrarListaMobile(false);
  }

  /** Navegação escolhida pelo técnico — encerra a pista do último avanço. */
  function selecionar(item: ItemInspecao | null) {
    setUltimo(null);
    irPara(item);
  }

  function iniciarEnvio(ids: number[], condicao: Condicao | null) {
    const versao = ++ultimaVersao.current;
    for (const id of ids) emVoo.current.set(id, { versao, condicao });
    setSalvandoIds((s) => {
      const n = new Set(s);
      ids.forEach((id) => n.add(id));
      return n;
    });
    return versao;
  }

  /** Fecha o envio e devolve os itens em que ele ainda é o mais recente. */
  function concluirEnvio(ids: number[], versao: number): Set<number> {
    const vigentes = new Set(ids.filter((id) => emVoo.current.get(id)?.versao === versao));
    vigentes.forEach((id) => emVoo.current.delete(id));
    setSalvandoIds((s) => {
      const n = new Set(s);
      vigentes.forEach((id) => n.delete(id));
      return n;
    });
    return vigentes;
  }

  /** Guarda o envio para a transferência esperar por ele. */
  function rastrear<T>(p: Promise<T>): Promise<T> {
    envios.current.add(p);
    const fim = () => {
      envios.current.delete(p);
    };
    p.then(fim, fim);
    return p;
  }

  /** Grava a pista do avanço e abre o próximo pendente (respeitando a busca). */
  function avancar(itens: ItemInspecao[], de: ItemInspecao, condicao: Condicao) {
    setUltimo({ id: de.id, tag: de.equipamento_tag, condicao: condicao.sigla || condicao.nome });
    avancouEm.current = performance.now();
    const prox = proximoPendente(filtrarPorBusca(itens, busca), de.id);
    if (prox) irPara(prox);
    // Nada mais pendente na rota: a revisão é o próximo passo (transferir).
    else if (!itens.some(ehPendente)) irPara(null);
  }

  async function definirCondicao(item: ItemInspecao, condicao: Condicao) {
    if (!carreg || item.condicao === condicao.id) return;
    const antes = camposDoItem(item);
    const atualizado = { ...item, ...camposDe(condicao) };
    const versao = iniciarEnvio([item.id], condicao);
    setCarreg((c) => comCondicoes(c, new Map([[item.id, camposDe(condicao)]])));

    // Só a PRIMEIRA classificação move a folha: corrigir uma condição já dada
    // é trabalho neste equipamento, não no próximo.
    if (item.condicao == null) {
      if (!condicao.gera_acao) {
        avancar(carreg.itens.map((i) => (i.id === item.id ? atualizado : i)), atualizado, condicao);
      } else if (!ehCorretiva && (item.achados?.length ?? 0) === 0) {
        setModal({ item: atualizado, achado: null, avancarAoSalvar: true });
      }
    }

    try {
      const salvo = await rastrear(
        api<ItemInspecao>(`/itens-inspecao/${item.id}/`, {
          method: "PATCH",
          body: { condicao: condicao.id },
        })
      );
      if (concluirEnvio([item.id], versao).size) setCarreg((c) => comItens(c, [salvo]));
    } catch (e) {
      if (concluirEnvio([item.id], versao).size) {
        setCarreg((c) => comCondicoes(c, new Map([[item.id, antes]])));
        setUltimo((u) => (u?.id === item.id ? null : u));
      }
      // A folha pode já ter avançado: o aviso leva de volta ao equipamento.
      toast.erro(`A condição de ${item.equipamento_tag} não foi salva`, {
        descricao: mensagemDeErro(e),
        acao: { label: "Abrir", onClick: () => selecionar(item) },
      });
    }
  }

  function escolherPeloClique(item: ItemInspecao, condicao: Condicao) {
    if (performance.now() - avancouEm.current < GUARDA_TOQUE_DUPLO_MS) return;
    void definirCondicao(item, condicao);
  }

  async function aplicarEmLote(itens: ItemInspecao[], condicao: Condicao): Promise<boolean> {
    const ids = itens.map((i) => i.id);
    const antes = new Map(itens.map((i) => [i.id, camposDoItem(i)]));
    const versao = iniciarEnvio(ids, condicao);
    setCarreg((c) => comCondicoes(c, new Map(ids.map((id) => [id, camposDe(condicao)]))));
    setUltimo(null);
    try {
      const salvos = await rastrear(
        api<ItemInspecao[]>(`/carregamentos/${carregamentoId}/definir-condicao/`, {
          method: "POST",
          body: { itens: ids, condicao: condicao.id },
        })
      );
      const vigentes = concluirEnvio(ids, versao);
      setCarreg((c) => comItens(c, salvos.filter((i) => vigentes.has(i.id))));
      toast.sucesso(
        `${plural(ids.length, "equipamento marcado", "equipamentos marcados")} como ${condicao.sigla || condicao.nome}`
      );
      return true;
    } catch (e) {
      const vigentes = concluirEnvio(ids, versao);
      setCarreg((c) => comCondicoes(c, new Map(Array.from(antes).filter(([id]) => vigentes.has(id)))));
      toast.falha(e, "Não foi possível aplicar a condição aos equipamentos.");
      return false;
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
      // Condição ainda a caminho precisa chegar antes: o servidor confere a
      // rota inteira no momento da transferência.
      if (envios.current.size) await Promise.allSettled(Array.from(envios.current));
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

  // Atalhos do desktop. Sem lista de dependências de propósito: reassina a
  // cada render e sempre enxerga o estado atual (o React aplica a render de
  // uma tecla antes de entregar a próxima).
  useEffect(() => {
    if (!carreg || ((ehCorretiva || moduloTrafo) && itemId)) return;
    const itens = carreg.itens;
    function aoTeclar(e: KeyboardEvent) {
      if (e.defaultPrevented || e.ctrlKey || e.metaKey || e.altKey || !selecionado) return;
      const alvo = e.target as HTMLElement | null;
      if (alvo && (alvo.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(alvo.tagName))) return;
      if (document.querySelector('[role="dialog"][aria-modal="true"]')) return;

      if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
        const viz = vizinhos(itens, selecionado.id);
        const destino = e.key === "ArrowRight" ? viz.proximo : viz.anterior;
        if (destino) {
          e.preventDefault();
          selecionar(destino);
        }
        return;
      }
      if (!podeEditar) return;
      if (/^[1-9]$/.test(e.key)) {
        const condicao = condicoesEmOrdem(condicoes)[Number(e.key) - 1];
        if (condicao) {
          e.preventDefault();
          void definirCondicao(selecionado, condicao);
        }
      } else if (e.key === "a" || e.key === "A") {
        e.preventDefault();
        if (ehCorretiva) void analisarCorretiva(selecionado);
        else setModal({ item: selecionado, achado: null });
      }
    }
    window.addEventListener("keydown", aoTeclar);
    return () => window.removeEventListener("keydown", aoTeclar);
  });

  if (loading) return <LoadingState variante="tabela" linhas={6} colunas={5} label="Carregando a folha de campo…" />;
  if (!carreg) return <Card><p className="text-sm text-danger-fg">{msg ?? "Rota não encontrada."}</p></Card>;

  const pendentes = carreg.itens.filter((i) => i.condicao == null).length;
  const transferida = carreg.status !== "EM_CAMPO";

  // Óleo isolante / ensaios elétricos — lançamento do transformador (registro,
  // inspeção visual, medições e laudos), o mesmo editor da Análise final.
  if (moduloTrafo && itemId) {
    return (
      <EditorTransformador
        key={itemId}
        itemId={Number(itemId)}
        podeEditar={podeEditar}
        voltar={{ href: `/inspecoes/campo/${carregamentoId}`, label: "Voltar para equipamentos da rota" }}
      />
    );
  }

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
            onSaved={atualizar}
          />
        ) : (
          <AnaliseCorretivaItem
            carregamentoId={carregamentoId}
            item={item}
            podeEditar={podeEditar}
            onSaved={atualizar}
          />
        )}
      </div>
    );
  }

  const viz = vizinhos(carreg.itens, selecionadoId);
  const salvandoAtual = selecionado ? salvandoIds.has(selecionado.id) : false;
  const candidatos = filtrarPorBusca(carreg.itens, busca);
  const proxPendente = selecionado ? proximoPendente(candidatos, selecionado.id) : null;

  const navegador = {
    itens: carreg.itens,
    condicoes,
    selecionadoId,
    onSelecionar: selecionar,
    busca,
    onBusca: setBusca,
    filtro,
    onFiltro: setFiltro,
    podeEditar,
    onAplicarEmLote: aplicarEmLote,
  };

  return (
    <PageBody className={cn(selecionado && !mostrarListaMobile && "pb-24 lg:pb-6")}>
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
          <NavegadorEquipamentos {...navegador} className="max-h-[calc(100dvh-104px)]" />
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
            <NavegadorEquipamentos {...navegador} className="max-h-[65dvh]" />
          </div>
        </div>

        {/* Conteúdo — desktop: sempre visível. Celular: só quando a lista está fechada. */}
        <div className={cn("min-w-0 space-y-4", mostrarListaMobile && "hidden lg:block")}>
          <div className="flex min-h-9 flex-wrap items-center justify-between gap-x-3 gap-y-2">
            <button
              type="button"
              onClick={() => setMostrarListaMobile(true)}
              className="inline-flex items-center gap-1.5 text-xs font-medium text-fg-muted transition-colors hover:text-fg lg:hidden"
            >
              <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
              Equipamentos
            </button>

            {ultimo && (
              <UltimoLancamento
                key={ultimo.id}
                tag={ultimo.tag}
                condicao={ultimo.condicao}
                salvando={salvandoIds.has(ultimo.id)}
                onVoltar={() => selecionar(carreg.itens.find((i) => i.id === ultimo.id) ?? null)}
              />
            )}

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
                {proxPendente && (
                  <Button
                    size="sm"
                    variant="secondary"
                    iconRight={ChevronsRight}
                    onClick={() => selecionar(proxPendente)}
                    className="ml-1"
                  >
                    Próximo pendente
                  </Button>
                )}
              </div>
            )}
          </div>

          {selecionado ? (
            // A chave refaz a entrada a cada equipamento: com o avanço
            // automático o layout é idêntico, e sem o movimento a troca de
            // TAG passaria despercebida.
            <div key={selecionado.id} className="animate-slide-up">
              <PainelEquipamento
                item={selecionado}
                condicoes={condicoes}
                podeEditar={podeEditar}
                ehCorretiva={ehCorretiva}
                salvandoCondicao={salvandoAtual}
                onDefinirCondicao={(c) => escolherPeloClique(selecionado, c)}
                onNovaAnalise={() => setModal({ item: selecionado, achado: null })}
                onEditarAnalise={(a) => setModal({ item: selecionado, achado: a })}
                onRemoverAnalise={(a) => remocaoAchado.pedir(a)}
                onAnalisarCorretiva={() => {
                  if (!analisando) void analisarCorretiva(selecionado);
                }}
                onAdicionarLinha={() => adicionarLinha(selecionado)}
                onRemoverItem={() => remocaoItem.pedir(selecionado)}
                transformador={
                  moduloTrafo
                    ? {
                        modulo: moduloTrafo,
                        resumo: resumoTrafo?.get(selecionado.id) ?? null,
                        carregando: resumoTrafo == null,
                        onAbrir: () => router.push(`/inspecoes/campo/${carregamentoId}?item=${selecionado.id}`),
                      }
                    : undefined
                }
              />
            </div>
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
            const aberto = modal;
            setModal(null);
            const atual = await recarregar();
            if (!aberto?.avancarAoSalvar) return;
            const item = atual.itens.find((i) => i.id === aberto.item.id);
            const condicao = condicoes.find((c) => c.id === item?.condicao);
            if (item && condicao) avancar(atual.itens, item, condicao);
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
      {selecionado && !mostrarListaMobile && (
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

            {proxPendente ? (
              <Button size="sm" block onClick={() => selecionar(proxPendente)} iconRight={ChevronRight}>
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
            )}
          </div>
        </div>
      )}
    </PageBody>
  );
}

/**
 * O que o avanço automático acabou de gravar, com o caminho de volta.
 *
 * Sem esta linha a folha "pula" de equipamento e o técnico fica sem saber se
 * o toque pegou e onde foi parar. Mostra o envio em curso (a rede de campo
 * cai) e some quando a navegação volta a ser manual.
 */
function UltimoLancamento({
  tag,
  condicao,
  salvando,
  onVoltar,
}: {
  tag: string;
  condicao: string;
  salvando: boolean;
  onVoltar: () => void;
}) {
  return (
    <p
      role="status"
      className="order-last flex w-full min-w-0 animate-fade-in items-center gap-1.5 text-xs text-fg-muted lg:order-none lg:w-auto"
    >
      {salvando ? (
        <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin" aria-hidden="true" />
      ) : (
        <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-success" aria-hidden="true" />
      )}
      <span className="min-w-0 truncate">
        <span className="data font-medium text-fg">{tag}</span> marcado como{" "}
        <span className="data font-medium text-fg">{condicao}</span>
        {salvando ? " · salvando…" : ""}
      </span>
      <button
        type="button"
        onClick={onVoltar}
        aria-label={`Voltar para ${tag} e corrigir`}
        className="shrink-0 rounded px-1 font-medium text-primary underline-offset-4 hover:underline"
      >
        Corrigir
      </button>
    </p>
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
