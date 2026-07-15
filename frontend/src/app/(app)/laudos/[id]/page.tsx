"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Printer, ShieldCheck } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Laudo } from "@/lib/types";
import { Badge, Button, CriticidadeBadge, Spinner } from "@/components/ui";

export default function LaudoDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const router = useRouter();
  const [laudo, setLaudo] = useState<Laudo | null>(null);
  const [loading, setLoading] = useState(true);
  const [emitindo, setEmitindo] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function load() {
    setLaudo(await api<Laudo>(`/laudos/${id}/`));
  }

  useEffect(() => {
    load().finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function emitir() {
    setMsg(null);
    setEmitindo(true);
    try {
      await api(`/laudos/${id}/emitir/`, { method: "POST" });
      await load();
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "Erro ao emitir.");
    } finally {
      setEmitindo(false);
    }
  }

  if (loading) return <Spinner />;
  if (!laudo) return <p className="text-fg-muted">Laudo não encontrado.</p>;

  return (
    <div className="space-y-6">
      <header className="no-print flex items-center justify-between">
        <button
          onClick={() => router.back()}
          className="inline-flex items-center gap-1 text-sm text-fg-muted transition-colors hover:text-fg"
        >
          <ArrowLeft className="h-4 w-4" /> Voltar
        </button>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={() => window.print()} icon={Printer}>
            Imprimir / PDF
          </Button>
          {user?.is_interno && laudo.status === "RASCUNHO" && (
            <Button onClick={emitir} loading={emitindo} icon={ShieldCheck}>
              Emitir laudo
            </Button>
          )}
        </div>
      </header>

      {msg && (
        <div className="no-print rounded-lg bg-danger-subtle px-3 py-2 text-sm text-danger-fg">{msg}</div>
      )}

      {/* Documento do laudo (área imprimível) */}
      <div className="rounded-xl border border-border bg-surface p-8 shadow-xs">
        <div className="flex items-start justify-between border-b border-border pb-5">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent font-bold text-accent-fg">
              T
            </div>
            <div>
              <p className="text-base font-semibold text-fg">ThermoProActive</p>
              <p className="text-xs text-fg-muted">Laudo Técnico de Manutenção Preditiva</p>
            </div>
          </div>
          <div className="text-right text-sm">
            <p className="font-mono font-semibold text-fg">{laudo.numero}</p>
            <p className="text-fg-subtle">Versão {laudo.versao}</p>
            <div className="mt-1.5 flex justify-end">
              <Badge tone={laudo.status === "EMITIDO" ? "success" : "warning"}>{laudo.status_display}</Badge>
            </div>
          </div>
        </div>

        <div className="mt-6 grid grid-cols-2 gap-5 text-sm">
          <Info label="Título" value={laudo.titulo} />
          <Info label="Cliente" value={laudo.cliente_nome} />
          <Info
            label="Criticidade geral"
            value={laudo.criticidade_geral ? <CriticidadeBadge value={laudo.criticidade_geral} /> : "—"}
          />
          <Info
            label="Emissão"
            value={laudo.data_emissao ? new Date(laudo.data_emissao).toLocaleString("pt-BR") : "—"}
          />
        </div>

        <Section title="Diagnóstico Técnico">{laudo.diagnostico}</Section>
        <Section title="Recomendações">{laudo.recomendacoes}</Section>
        <Section title="Conclusão">{laudo.conclusao}</Section>

        <div className="mt-12 border-t border-border pt-6 text-sm">
          <div className="inline-block border-t border-border-strong px-10 pt-1.5 text-center">
            <p className="font-semibold text-fg">{laudo.responsavel_nome}</p>
            <p className="text-xs text-fg-muted">
              Responsável Técnico{laudo.responsavel_conselho ? ` — ${laudo.responsavel_conselho}` : ""}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

function Info({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <p className="text-xs uppercase tracking-wide text-fg-subtle">{label}</p>
      <p className="mt-1 font-medium text-fg">{value}</p>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mt-6">
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-accent">{title}</h3>
      <p className="whitespace-pre-line text-sm leading-relaxed text-fg">{children}</p>
    </div>
  );
}
