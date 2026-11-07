"use client";

/**
 * Execução da OSP (Anexo I 2.6.2.2 a 2.6.2.8): checklist técnico, peças aplicadas,
 * evidências fotográficas, tempo de execução e assinatura do cliente.
 *
 * Modo "interno": responde checklist, lança peças e fotos, aponta horas.
 * Modo "cliente": lê tudo da própria OSP e assina (canvas) quando a execução estiver
 * registrada. O servidor é quem decide cada permissão; aqui só se esconde o que não
 * se aplica ao perfil.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import type { PointerEvent } from "react";
import { ClipboardCheck, Camera, Clock, PenLine, Plus, Trash2 } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { Paginated } from "@/lib/types";
import { Badge, Button, Card, Field, Input, Select } from "@/components/ds";

interface ItemChecklist {
  id: number;
  ordem: number;
  descricao: string;
  obrigatorio: boolean;
  situacao: "CONFORME" | "NAO_CONFORME" | "NAO_SE_APLICA" | null;
  observacao: string;
}
interface ModeloChecklistRespondido {
  modelo: number;
  nome: string;
  obrigatorio_para_finalizar: boolean;
  itens: ItemChecklist[];
}
interface Peca {
  id: number;
  descricao: string;
  codigo: string;
  quantidade: string;
  unidade: string;
  custo_unitario: string;
  custo_total: string;
}
interface Evidencia {
  id: number;
  fase: string;
  fase_display: string;
  legenda: string;
  url: string | null;
}
interface Apontamento {
  id: number;
  inicio: string;
  fim: string | null;
  duracao_minutos: number | null;
  origem_display: string;
  observacao: string;
}
interface OspResumo {
  status: string;
  assinatura: { nome: string; cargo: string; assinado_em: string; estado_sha256: string } | null;
  tempo_execucao_min: number;
  custo_material_real: string | null;
}

const SITUACOES = [
  { valor: "CONFORME", texto: "Conforme" },
  { valor: "NAO_CONFORME", texto: "Não conforme" },
  { valor: "NAO_SE_APLICA", texto: "Não se aplica" },
];
const FASES = [
  { valor: "ANTES", texto: "Antes" },
  { valor: "DURANTE", texto: "Durante" },
  { valor: "DEPOIS", texto: "Depois" },
  { valor: "OUTRA", texto: "Outra" },
];
/** Estados em que o cliente pode assinar (espelha `osp.execucao.ESTADOS_ASSINAVEIS`). */
const ESTADOS_ASSINAVEIS = new Set(["EXECUTADA", "AGUARDANDO_APROVACAO", "FINALIZADA"]);
const ESTADOS_ENCERRADOS = new Set(["FINALIZADA", "CANCELADA"]);

function msgErro(e: unknown, padrao: string): string {
  return e instanceof ApiError ? e.message || padrao : padrao;
}

function reais(valor: string | number | null | undefined): string {
  const n = Number(valor ?? 0);
  return n.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

export function PainelExecucaoOSP({ ospId, modo }: { ospId: number; modo: "interno" | "cliente" }) {
  const interno = modo === "interno";
  const [osp, setOsp] = useState<OspResumo | null>(null);
  const [modelos, setModelos] = useState<ModeloChecklistRespondido[]>([]);
  const [pendencias, setPendencias] = useState<string[]>([]);
  const [pecas, setPecas] = useState<Peca[]>([]);
  const [fotos, setFotos] = useState<Evidencia[]>([]);
  const [tempos, setTempos] = useState<Apontamento[]>([]);
  const [erro, setErro] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);

  const carregar = useCallback(async () => {
    try {
      const [o, ck, pc, ev, ap] = await Promise.all([
        api<OspResumo>(`/osps/${ospId}/`),
        api<{ modelos: ModeloChecklistRespondido[]; pendencias: string[] }>(`/osps/${ospId}/checklist/`),
        api<Paginated<Peca>>(`/osp-pecas/?osp=${ospId}&page_size=200`),
        api<Paginated<Evidencia>>(`/osp-evidencias/?osp=${ospId}&page_size=200`),
        api<Paginated<Apontamento>>(`/osp-apontamentos/?osp=${ospId}&page_size=200`),
      ]);
      setOsp(o);
      setModelos(ck.modelos);
      setPendencias(ck.pendencias);
      setPecas(pc.results);
      setFotos(ev.results);
      setTempos(ap.results);
    } catch (e) {
      setErro(msgErro(e, "Não foi possível carregar a execução da OSP."));
    }
  }, [ospId]);

  useEffect(() => {
    carregar();
  }, [carregar]);

  if (!osp) {
    return (
      <Card as="section">
        {erro ? <p role="alert" className="text-sm text-danger-fg">{erro}</p> : <p className="text-sm text-fg-muted">Carregando execução…</p>}
      </Card>
    );
  }

  const encerrada = ESTADOS_ENCERRADOS.has(osp.status);

  return (
    <div className="space-y-4">
      {erro && <p role="alert" className="text-sm text-danger-fg">{erro}</p>}
      {aviso && <p className="text-sm text-fg-muted">{aviso}</p>}

      <ChecklistSec
        ospId={ospId} modelos={modelos} pendencias={pendencias} interno={interno && !encerrada}
        onSalvo={carregar} setErro={setErro} setAviso={setAviso}
      />
      <PecasSec
        ospId={ospId} pecas={pecas} interno={interno && !encerrada} onMudou={carregar}
        setErro={setErro} custo={osp.custo_material_real}
      />
      <EvidenciasSec
        ospId={ospId} fotos={fotos} interno={interno && !encerrada} onMudou={carregar} setErro={setErro}
      />
      <TempoSec
        ospId={ospId} tempos={tempos} total={osp.tempo_execucao_min} interno={interno && !encerrada}
        onMudou={carregar} setErro={setErro}
      />
      <AssinaturaSec
        ospId={ospId} assinatura={osp.assinatura} podeAssinar={!interno && ESTADOS_ASSINAVEIS.has(osp.status)}
        onAssinou={carregar} setErro={setErro}
      />
    </div>
  );
}

// --------------------------------------------------------------- Checklist (2.6.2.2)
function ChecklistSec({
  ospId, modelos, pendencias, interno, onSalvo, setErro, setAviso,
}: {
  ospId: number; modelos: ModeloChecklistRespondido[]; pendencias: string[]; interno: boolean;
  onSalvo: () => Promise<void> | void; setErro: (m: string | null) => void; setAviso: (m: string | null) => void;
}) {
  const [respostas, setRespostas] = useState<Record<number, { situacao: string; observacao: string }>>({});
  const [salvando, setSalvando] = useState(false);

  useEffect(() => {
    const inicial: Record<number, { situacao: string; observacao: string }> = {};
    modelos.forEach((m) => m.itens.forEach((i) => {
      inicial[i.id] = { situacao: i.situacao ?? "", observacao: i.observacao };
    }));
    setRespostas(inicial);
  }, [modelos]);

  if (modelos.length === 0) {
    return (
      <Card as="section" className="space-y-2">
        <h2 className="flex items-center gap-2 font-semibold text-fg"><ClipboardCheck className="h-4 w-4" aria-hidden /> Checklist técnico</h2>
        <p className="text-sm text-fg-muted">Nenhum modelo de checklist se aplica a este equipamento.</p>
      </Card>
    );
  }

  async function salvar() {
    setSalvando(true);
    setErro(null);
    try {
      const itens = Object.entries(respostas)
        .filter(([, r]) => r.situacao)
        .map(([item, r]) => ({ item: Number(item), situacao: r.situacao, observacao: r.observacao }));
      await api(`/osps/${ospId}/checklist/`, { method: "POST", body: { respostas: itens } });
      setAviso("Checklist salvo.");
      await onSalvo();
    } catch (e) {
      setErro(msgErro(e, "Não foi possível salvar o checklist."));
    } finally {
      setSalvando(false);
    }
  }

  return (
    <Card as="section" className="space-y-3">
      <h2 className="flex items-center gap-2 font-semibold text-fg"><ClipboardCheck className="h-4 w-4" aria-hidden /> Checklist técnico</h2>
      {pendencias.length > 0 && interno && (
        <p className="text-sm text-warning-fg">
          Para finalizar faltam {pendencias.length} item(ns) obrigatório(s).
        </p>
      )}
      {modelos.map((m) => (
        <div key={m.modelo} className="space-y-2">
          <p className="text-sm font-medium text-fg">
            {m.nome}{m.obrigatorio_para_finalizar && <Badge tone="warning" className="ml-2">Obrigatório para finalizar</Badge>}
          </p>
          <ul className="divide-y divide-border">
            {m.itens.map((item) => {
              const r = respostas[item.id] ?? { situacao: "", observacao: "" };
              return (
                <li key={item.id} className="grid gap-2 py-2 sm:grid-cols-[1fr_180px]">
                  <div>
                    <p className="text-sm text-fg">{item.ordem}. {item.descricao}{item.obrigatorio ? " *" : ""}</p>
                    {!interno && item.situacao && (
                      <p className="text-xs text-fg-muted">{SITUACOES.find((s) => s.valor === item.situacao)?.texto}</p>
                    )}
                  </div>
                  {interno ? (
                    <Select
                      value={r.situacao}
                      onChange={(e) => setRespostas((prev) => ({ ...prev, [item.id]: { ...r, situacao: e.target.value } }))}
                    >
                      <option value="">— não respondido —</option>
                      {SITUACOES.map((s) => <option key={s.valor} value={s.valor}>{s.texto}</option>)}
                    </Select>
                  ) : null}
                </li>
              );
            })}
          </ul>
        </div>
      ))}
      {interno && (
        <Button onClick={salvar} loading={salvando}>Salvar checklist</Button>
      )}
    </Card>
  );
}

// --------------------------------------------------------------- Peças (2.6.2.7)
function PecasSec({
  ospId, pecas, interno, onMudou, setErro, custo,
}: {
  ospId: number; pecas: Peca[]; interno: boolean; onMudou: () => Promise<void> | void;
  setErro: (m: string | null) => void; custo: string | null;
}) {
  const [descricao, setDescricao] = useState("");
  const [codigo, setCodigo] = useState("");
  const [quantidade, setQuantidade] = useState("1");
  const [unidade, setUnidade] = useState("un");
  const [custoUnit, setCustoUnit] = useState("0");
  const [salvando, setSalvando] = useState(false);

  async function adicionar() {
    setSalvando(true);
    setErro(null);
    try {
      await api("/osp-pecas/", {
        method: "POST",
        // O campo aceita vírgula decimal ("45,50"); a API espera ponto.
        body: { osp: ospId, descricao, codigo, unidade,
          quantidade: quantidade.trim().replace(",", "."), custo_unitario: custoUnit.trim().replace(",", ".") },
      });
      setDescricao(""); setCodigo(""); setQuantidade("1"); setCustoUnit("0");
      await onMudou();
    } catch (e) {
      setErro(msgErro(e, "Não foi possível lançar a peça."));
    } finally {
      setSalvando(false);
    }
  }

  async function remover(p: Peca) {
    if (!window.confirm(`Remover "${p.descricao}"? Só o Master pode excluir.`)) return;
    try {
      await api(`/osp-pecas/${p.id}/`, { method: "DELETE" });
      await onMudou();
    } catch (e) {
      setErro(msgErro(e, "Não foi possível remover a peça."));
    }
  }

  return (
    <Card as="section" className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold text-fg">Peças e materiais aplicados</h2>
        <span className="text-sm text-fg-muted">Total: {reais(custo ?? "0")}</span>
      </div>
      {pecas.length === 0 ? (
        <p className="text-sm text-fg-muted">Nenhuma peça lançada.</p>
      ) : (
        <ul className="divide-y divide-border">
          {pecas.map((p) => (
            <li key={p.id} className="flex flex-wrap items-center gap-2 py-2 text-sm">
              <span className="flex-1 text-fg">{p.descricao}{p.codigo ? ` (${p.codigo})` : ""}</span>
              <span className="text-fg-muted">{p.quantidade} {p.unidade} × {reais(p.custo_unitario)} = {reais(p.custo_total)}</span>
              {interno && <Button variant="ghost" icon={Trash2} onClick={() => remover(p)}>Remover</Button>}
            </li>
          ))}
        </ul>
      )}
      {interno && (
        <div className="grid gap-3 border-t border-border pt-3 sm:grid-cols-3">
          <Field label="Descrição"><Input value={descricao} maxLength={200} onChange={(e) => setDescricao(e.target.value)} /></Field>
          <Field label="Código"><Input value={codigo} maxLength={60} onChange={(e) => setCodigo(e.target.value)} /></Field>
          <Field label="Quantidade"><Input inputMode="decimal" value={quantidade} onChange={(e) => setQuantidade(e.target.value)} /></Field>
          <Field label="Unidade"><Input value={unidade} maxLength={10} onChange={(e) => setUnidade(e.target.value)} /></Field>
          <Field label="Custo unitário (R$)"><Input inputMode="decimal" value={custoUnit} onChange={(e) => setCustoUnit(e.target.value)} /></Field>
          <div className="flex items-end">
            <Button icon={Plus} onClick={adicionar} loading={salvando} disabled={!descricao.trim()}>Lançar peça</Button>
          </div>
        </div>
      )}
    </Card>
  );
}

// --------------------------------------------------------------- Evidências (2.6.2.4)
function EvidenciasSec({
  ospId, fotos, interno, onMudou, setErro,
}: {
  ospId: number; fotos: Evidencia[]; interno: boolean; onMudou: () => Promise<void> | void;
  setErro: (m: string | null) => void;
}) {
  const [fase, setFase] = useState("DEPOIS");
  const [legenda, setLegenda] = useState("");
  const [enviando, setEnviando] = useState(false);

  async function enviar(arquivo: File) {
    setEnviando(true);
    setErro(null);
    try {
      const corpo = new FormData();
      corpo.append("osp", String(ospId));
      corpo.append("fase", fase);
      corpo.append("legenda", legenda);
      corpo.append("arquivo", arquivo);
      await api("/osp-evidencias/", { method: "POST", body: corpo });
      setLegenda("");
      await onMudou();
    } catch (e) {
      setErro(msgErro(e, "Não foi possível enviar a foto."));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Card as="section" className="space-y-3">
      <h2 className="flex items-center gap-2 font-semibold text-fg"><Camera className="h-4 w-4" aria-hidden /> Evidências fotográficas</h2>
      {fotos.length === 0 ? (
        <p className="text-sm text-fg-muted">Nenhuma foto nesta OSP.</p>
      ) : (
        <ul className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {fotos.map((f) => (
            <li key={f.id} className="space-y-1 text-xs text-fg-muted">
              {f.url && <img src={f.url} alt={f.legenda || f.fase_display} className="h-28 w-full rounded-md object-cover" />}
              <p>{f.fase_display}{f.legenda ? ` · ${f.legenda}` : ""}</p>
            </li>
          ))}
        </ul>
      )}
      {interno && (
        <div className="grid gap-3 border-t border-border pt-3 sm:grid-cols-3">
          <Field label="Fase">
            <Select value={fase} onChange={(e) => setFase(e.target.value)}>
              {FASES.map((f) => <option key={f.valor} value={f.valor}>{f.texto}</option>)}
            </Select>
          </Field>
          <Field label="Legenda"><Input value={legenda} maxLength={200} onChange={(e) => setLegenda(e.target.value)} /></Field>
          <Field label="Foto (JPEG, PNG ou WEBP)">
            <Input
              type="file"
              accept="image/jpeg,image/png,image/webp"
              disabled={enviando}
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) enviar(f);
                e.target.value = "";
              }}
            />
          </Field>
        </div>
      )}
    </Card>
  );
}

// --------------------------------------------------------------- Tempo (2.6.2.8)
function TempoSec({
  ospId, tempos, total, interno, onMudou, setErro,
}: {
  ospId: number; tempos: Apontamento[]; total: number; interno: boolean;
  onMudou: () => Promise<void> | void; setErro: (m: string | null) => void;
}) {
  const [inicio, setInicio] = useState("");
  const [fim, setFim] = useState("");
  const [observacao, setObservacao] = useState("");
  const [salvando, setSalvando] = useState(false);

  async function apontar() {
    setSalvando(true);
    setErro(null);
    try {
      await api("/osp-apontamentos/", {
        method: "POST",
        body: {
          osp: ospId,
          inicio: new Date(inicio).toISOString(),
          fim: new Date(fim).toISOString(),
          observacao,
        },
      });
      setInicio(""); setFim(""); setObservacao("");
      await onMudou();
    } catch (e) {
      setErro(msgErro(e, "Não foi possível registrar o apontamento."));
    } finally {
      setSalvando(false);
    }
  }

  return (
    <Card as="section" className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-2 font-semibold text-fg"><Clock className="h-4 w-4" aria-hidden /> Tempo de execução</h2>
        <span className="text-sm text-fg-muted">Total: {Math.floor(total / 60)} h {String(total % 60).padStart(2, "0")} min</span>
      </div>
      {tempos.length === 0 ? (
        <p className="text-sm text-fg-muted">Nenhum intervalo registrado.</p>
      ) : (
        <ul className="divide-y divide-border text-sm">
          {tempos.map((t) => (
            <li key={t.id} className="flex flex-wrap gap-2 py-2 text-fg">
              <span>{new Date(t.inicio).toLocaleString("pt-BR")}</span>
              <span>→ {t.fim ? new Date(t.fim).toLocaleString("pt-BR") : "em andamento"}</span>
              <span className="text-fg-muted">{t.duracao_minutos !== null ? `${t.duracao_minutos} min` : ""} · {t.origem_display}{t.observacao ? ` · ${t.observacao}` : ""}</span>
            </li>
          ))}
        </ul>
      )}
      {interno && (
        <div className="grid gap-3 border-t border-border pt-3 sm:grid-cols-4">
          <Field label="Início"><Input type="datetime-local" value={inicio} onChange={(e) => setInicio(e.target.value)} /></Field>
          <Field label="Fim"><Input type="datetime-local" value={fim} onChange={(e) => setFim(e.target.value)} /></Field>
          <Field label="Observação"><Input value={observacao} maxLength={200} onChange={(e) => setObservacao(e.target.value)} /></Field>
          <div className="flex items-end">
            <Button icon={Clock} onClick={apontar} loading={salvando} disabled={!inicio || !fim}>Apontar horas</Button>
          </div>
        </div>
      )}
    </Card>
  );
}

// --------------------------------------------------------------- Assinatura (2.6.2.6)
function AssinaturaSec({
  ospId, assinatura, podeAssinar, onAssinou, setErro,
}: {
  ospId: number;
  assinatura: OspResumo["assinatura"]; podeAssinar: boolean;
  onAssinou: () => Promise<void> | void; setErro: (m: string | null) => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const desenhando = useRef(false);
  const [temTraco, setTemTraco] = useState(false);
  const [nome, setNome] = useState("");
  const [cargo, setCargo] = useState("");
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    const c = canvasRef.current;
    if (!c || !podeAssinar) return;
    const ctx = c.getContext("2d");
    if (ctx) {
      ctx.fillStyle = "#ffffff";
      ctx.fillRect(0, 0, c.width, c.height);
      ctx.lineWidth = 2;
      ctx.lineCap = "round";
      ctx.strokeStyle = "#111111";
    }
  }, [podeAssinar]);

  function ponto(e: PointerEvent<HTMLCanvasElement>) {
    const c = canvasRef.current!;
    const r = c.getBoundingClientRect();
    return { x: ((e.clientX - r.left) * c.width) / r.width, y: ((e.clientY - r.top) * c.height) / r.height };
  }

  function inicio(e: PointerEvent<HTMLCanvasElement>) {
    desenhando.current = true;
    const ctx = canvasRef.current!.getContext("2d")!;
    const p = ponto(e);
    ctx.beginPath();
    ctx.moveTo(p.x, p.y);
  }

  function mover(e: PointerEvent<HTMLCanvasElement>) {
    if (!desenhando.current) return;
    const ctx = canvasRef.current!.getContext("2d")!;
    const p = ponto(e);
    ctx.lineTo(p.x, p.y);
    ctx.stroke();
    setTemTraco(true);
  }

  function fim() {
    desenhando.current = false;
  }

  function limpar() {
    const c = canvasRef.current!;
    const ctx = c.getContext("2d")!;
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, c.width, c.height);
    setTemTraco(false);
  }

  async function assinar() {
    setEnviando(true);
    setErro(null);
    try {
      const png = canvasRef.current!.toDataURL("image/png");
      await api("/osp-assinaturas/", {
        method: "POST",
        body: { osp: ospId, nome, cargo, assinatura_png: png },
      });
      await onAssinou();
    } catch (e) {
      setErro(msgErro(e, "Não foi possível registrar a assinatura."));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Card as="section" className="space-y-3">
      <h2 className="flex items-center gap-2 font-semibold text-fg"><PenLine className="h-4 w-4" aria-hidden /> Assinatura do cliente</h2>
      {assinatura ? (
        <div className="space-y-1 text-sm text-fg">
          <p>Assinado por <strong>{assinatura.nome}</strong> ({assinatura.cargo}) em {new Date(assinatura.assinado_em).toLocaleString("pt-BR")}.</p>
          <p className="break-all font-mono text-xs text-fg-muted">SHA-256 do estado: {assinatura.estado_sha256}</p>
        </div>
      ) : podeAssinar ? (
        <div className="space-y-3">
          <p className="text-sm text-fg-muted">
            Ao assinar, o sistema registra seu nome, cargo, data e hora, o endereço de origem e o hash do estado atual da OSP.
          </p>
          <canvas
            ref={canvasRef}
            width={600}
            height={200}
            aria-label="Área para desenhar a assinatura"
            className="w-full touch-none rounded-md border border-border bg-white"
            onPointerDown={inicio}
            onPointerMove={mover}
            onPointerUp={fim}
            onPointerLeave={fim}
          />
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Nome do signatário"><Input value={nome} maxLength={160} onChange={(e) => setNome(e.target.value)} /></Field>
            <Field label="Cargo"><Input value={cargo} maxLength={120} onChange={(e) => setCargo(e.target.value)} /></Field>
          </div>
          <div className="flex gap-2">
            <Button variant="secondary" onClick={limpar} disabled={!temTraco}>Limpar</Button>
            <Button onClick={assinar} loading={enviando} disabled={!temTraco || !nome.trim() || !cargo.trim()}>
              Assinar execução
            </Button>
          </div>
        </div>
      ) : (
        <p className="text-sm text-fg-muted">A assinatura fica disponível depois da execução da OSP.</p>
      )}
    </Card>
  );
}
