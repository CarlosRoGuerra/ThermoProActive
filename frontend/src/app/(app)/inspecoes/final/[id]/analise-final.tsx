"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, CheckCircle2, ImagePlus, Save, Trash2 } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { Achado, AchadoImagem, Condicao, ItemInspecao, Paginated, TipoImagemAchado } from "@/lib/types";
import {
  type AchadoForm, formDeAchado, payloadDeForm, tecnologiaTipo,
} from "@/lib/inspecoes";
import { AchadoCampos } from "@/components/achado-campos";
import { Badge, Button, Card, Field, Input, Select, Spinner } from "@/components/ui";

const ddmmaaaa = (iso: string | null) => (iso ? iso.split("-").reverse().join("/") : "—");

// Tipos de imagem oferecidos por tecnologia (padrão 800×600).
const IMAGENS_POR_TIPO: Record<string, { valor: TipoImagemAchado; texto: string }[]> = {
  termografia: [
    { valor: "REAL", texto: "Foto real" },
    { valor: "TERMICA", texto: "Imagem térmica" },
  ],
  vibracao: [
    { valor: "TENDENCIA", texto: "Linha de tendência" },
    { valor: "ESPECTRO", texto: "Espectro" },
    { valor: "REAL", texto: "Foto real" },
  ],
  outro: [
    { valor: "REAL", texto: "Foto real" },
    { valor: "TERMICA", texto: "Imagem térmica" },
    { valor: "TENDENCIA", texto: "Linha de tendência" },
    { valor: "ESPECTRO", texto: "Espectro" },
  ],
};

/* ------------------------------- Upload de imagens ------------------------ */
function Imagens({
  achado, tipoTecnologia, onChange,
}: {
  achado: Achado;
  tipoTecnologia: "vibracao" | "termografia" | "outro";
  onChange: () => void;
}) {
  const [tipo, setTipo] = useState<TipoImagemAchado>(IMAGENS_POR_TIPO[tipoTecnologia][0].valor);
  const [legenda, setLegenda] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  function medir(file: File): Promise<{ w: number; h: number }> {
    return new Promise((resolve, reject) => {
      const url = URL.createObjectURL(file);
      const img = new Image();
      img.onload = () => {
        URL.revokeObjectURL(url);
        resolve({ w: img.naturalWidth, h: img.naturalHeight });
      };
      img.onerror = () => {
        URL.revokeObjectURL(url);
        reject(new Error("Arquivo de imagem inválido."));
      };
      img.src = url;
    });
  }

  async function enviar(file: File) {
    setMsg(null);
    try {
      const { w, h } = await medir(file);
      if (w !== 800 || h !== 600) {
        setMsg(`A imagem precisa ser 800×600px (esta é ${w}×${h}).`);
        if (inputRef.current) inputRef.current.value = "";
        return;
      }
      setEnviando(true);
      const fd = new FormData();
      fd.append("achado", String(achado.id));
      fd.append("tipo", tipo);
      fd.append("legenda", legenda);
      fd.append("arquivo", file);
      await api("/achados-imagens/", { method: "POST", body: fd });
      setLegenda("");
      if (inputRef.current) inputRef.current.value = "";
      onChange();
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : e instanceof Error ? e.message : "Erro ao enviar a imagem.");
    } finally {
      setEnviando(false);
    }
  }

  async function remover(img: AchadoImagem) {
    if (!confirm("Remover esta imagem?")) return;
    await api(`/achados-imagens/${img.id}/`, { method: "DELETE" });
    onChange();
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <Field label="Tipo de imagem">
          <Select value={tipo} onChange={(e) => setTipo(e.target.value as TipoImagemAchado)}>
            {IMAGENS_POR_TIPO[tipoTecnologia].map((o) => (
              <option key={o.valor} value={o.valor}>{o.texto}</option>
            ))}
          </Select>
        </Field>
        <Field label="Legenda (opcional)">
          <Input value={legenda} onChange={(e) => setLegenda(e.target.value)} />
        </Field>
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) enviar(f);
          }}
        />
        <Button
          variant="secondary"
          icon={ImagePlus}
          loading={enviando}
          onClick={() => inputRef.current?.click()}
        >
          Anexar imagem
        </Button>
        <span className="text-xs text-fg-subtle">Padrão 800×600px.</span>
      </div>
      {msg && <p className="text-sm text-danger-fg">{msg}</p>}

      {achado.imagens.length > 0 && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {achado.imagens.map((img) => (
            <div key={img.id} className="overflow-hidden rounded-lg border border-border">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={img.arquivo} alt={img.tipo_display} className="aspect-[4/3] w-full object-cover" />
              <div className="flex items-center justify-between gap-2 px-2 py-1.5">
                <span className="truncate text-xs text-fg-muted" title={img.legenda || img.tipo_display}>
                  {img.tipo_display}
                </span>
                <button
                  onClick={() => remover(img)}
                  className="shrink-0 rounded p-1 text-danger-fg transition-colors hover:bg-danger-subtle"
                  aria-label="Remover imagem"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ------------------------------- Página ----------------------------------- */
export function AnaliseFinal({ achadoId }: { achadoId: number }) {
  const router = useRouter();
  const [achado, setAchado] = useState<Achado | null>(null);
  const [item, setItem] = useState<ItemInspecao | null>(null);
  const [condicoes, setCondicoes] = useState<Condicao[]>([]);
  const [form, setForm] = useState<AchadoForm | null>(null);
  const [numeroOsp, setNumeroOsp] = useState("");
  const [condicao, setCondicao] = useState("");
  const [loading, setLoading] = useState(true);
  const [salvando, setSalvando] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const carregar = useCallback(async () => {
    const a = await api<Achado>(`/achados/${achadoId}/`);
    setAchado(a);
    setForm(formDeAchado(a));
    setNumeroOsp(a.numero_osp ?? "");
    const it = await api<ItemInspecao>(`/itens-inspecao/${a.item}/`);
    setItem(it);
    setCondicao(it.condicao != null ? String(it.condicao) : "");
  }, [achadoId]);

  useEffect(() => {
    setLoading(true);
    Promise.all([carregar(), api<Paginated<Condicao>>("/condicoes/?page_size=1000")])
      .then(([, cond]) => setCondicoes(cond.results))
      .catch(() => setMsg("Não foi possível carregar a análise."))
      .finally(() => setLoading(false));
  }, [carregar]);

  async function salvar(confirmar: boolean) {
    if (!form || !achado || !item) return;
    if (confirmar && achado.imagens.length === 0) {
      setMsg("Anexe ao menos uma imagem (800×600) antes de confirmar e publicar.");
      return;
    }
    setSalvando(true);
    setMsg(null);
    try {
      // Condição pertence ao item (pode ser corrigida aqui).
      if (condicao !== (item.condicao != null ? String(item.condicao) : "")) {
        await api(`/itens-inspecao/${item.id}/`, {
          method: "PATCH",
          body: { condicao: condicao === "" ? null : Number(condicao) },
        });
      }
      const body: Record<string, unknown> = { ...payloadDeForm(form), numero_osp: numeroOsp };
      if (confirmar) {
        body.confirmada = true;
        body.visivel_cliente = true;
      }
      await api(`/achados/${achado.id}/`, { method: "PATCH", body });
      // Confirmar → cai na visão "Confirmadas" (senão o item some da lista padrão).
      router.push(confirmar ? "/inspecoes/final?situacao=sim" : "/inspecoes/final");
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "Erro ao salvar.");
      setSalvando(false);
    }
  }

  if (loading) return <Card><Spinner label="Carregando análise…" /></Card>;
  if (!achado || !form) return <Card><p className="text-sm text-danger-fg">{msg ?? "Análise não encontrada."}</p></Card>;

  const tipo = tecnologiaTipo(achado.tecnologia_nome);

  const infos: [string, string][] = [
    ["Analista", achado.analista_nome],
    ["Área", achado.area_nome],
    ["Setor", achado.setor_nome],
    ["Tag", achado.equipamento_tag],
    ["Equipamento", achado.equipamento_nome],
    ["Tipo de equipamento", achado.tipo_equipamento_nome || "—"],
    ["Data", ddmmaaaa(achado.data)],
    ["Tecnologia", achado.tecnologia_nome],
  ];

  return (
    <div className="space-y-5">
      <div>
        <Link
          href="/inspecoes/final"
          className="inline-flex items-center gap-1.5 text-xs font-medium text-fg-muted transition-colors hover:text-fg"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Voltar para Análise final
        </Link>
        <div className="mt-2 flex items-center gap-2">
          <h1 className="text-xl font-semibold tracking-tight text-fg">
            Análise <span className="font-mono text-fg-muted">#{achado.id}</span>
          </h1>
          {achado.confirmada ? (
            <Badge tone="success">Confirmada</Badge>
          ) : (
            <Badge tone="warning">Não confirmada</Badge>
          )}
        </div>
      </div>

      {/* Rastreabilidade (somente leitura) */}
      <Card>
        <h2 className="mb-3 text-sm font-semibold text-fg">Rastreabilidade</h2>
        <dl className="grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-4">
          {infos.map(([k, v]) => (
            <div key={k}>
              <dt className="text-[11px] font-medium uppercase tracking-wide text-fg-subtle">{k}</dt>
              <dd className="mt-0.5 truncate text-sm text-fg" title={v}>{v}</dd>
            </div>
          ))}
        </dl>
        <div className="mt-4 grid grid-cols-1 gap-4 border-t border-border pt-4 sm:grid-cols-2">
          <Field label="Número da OSP">
            <Input value={numeroOsp} maxLength={40} onChange={(e) => setNumeroOsp(e.target.value)} />
          </Field>
          <Field label="Condição">
            <Select value={condicao} onChange={(e) => setCondicao(e.target.value)}>
              <option value="">— condição —</option>
              {condicoes.map((c) => (
                <option key={c.id} value={c.id}>{c.nome}</option>
              ))}
            </Select>
          </Field>
        </div>
      </Card>

      {/* Campos editáveis da análise */}
      <Card>
        <h2 className="mb-4 text-sm font-semibold text-fg">Análise</h2>
        <AchadoCampos form={form} setForm={setForm} tipo={tipo} tecnologiaId={achado.tecnologia} mostrarGrauRisco />
      </Card>

      {/* Imagens */}
      <Card>
        <h2 className="mb-4 text-sm font-semibold text-fg">
          Imagens {tipo === "termografia" ? "(real + térmica)" : tipo === "vibracao" ? "(tendência + espectro + real)" : ""}
        </h2>
        <Imagens achado={achado} tipoTecnologia={tipo} onChange={carregar} />
      </Card>

      {msg && <Card><p className="text-sm text-danger-fg">{msg}</p></Card>}

      <div className="flex flex-wrap items-center justify-end gap-3 pb-2">
        <Button variant="secondary" onClick={() => router.push("/inspecoes/final")}>Cancelar</Button>
        <Button variant="secondary" onClick={() => salvar(false)} loading={salvando} icon={Save}>
          Salvar
        </Button>
        <Button onClick={() => salvar(true)} loading={salvando} icon={CheckCircle2}>
          Confirmar e publicar
        </Button>
      </div>
    </div>
  );
}
