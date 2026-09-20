"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Bell,
  CheckCheck,
  CircleCheck,
  Clock,
  FileText,
  OctagonAlert,
  TriangleAlert,
  Wrench,
  type LucideIcon,
} from "lucide-react";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorCard,
  LoadingState,
  PageBody,
  PageHeader,
  SegmentedControl,
  Toolbar,
  cn,
  useToast,
} from "@/components/ds";
import { api } from "@/lib/api";
import { useLista } from "@/lib/recurso";
import { tempoRelativo, dataHora, plural } from "@/lib/format";
import { destinoNoPortal } from "@/lib/permissions";
import type { Notificacao } from "@/lib/types";

/* ==========================================================================
   Alertas — compartilhado pelos dois portais.
   --------------------------------------------------------------------------
   A palavra "notificações" saiu da interface: para quem opera, isto é a caixa
   de alertas do parque. O nível (INFO/ALERTA/CRÍTICO) é comunicado por ícone,
   rótulo e faixa lateral — não só pela cor.

   Os canais de envio (e-mail, WhatsApp, push) aparecem só na área interna:
   para o cliente, "como o aviso saiu" é detalhe de bastidor.
   ========================================================================== */

const ICONE_EVENTO: Record<string, LucideIcon> = {
  NOVA_OSP: Wrench,
  EQUIPAMENTO_CRITICO: OctagonAlert,
  LAUDO_CONCLUIDO: FileText,
  SLA_VENCENDO: Clock,
  APROVACAO_PENDENTE: CircleCheck,
};

const NIVEL = {
  INFO: { faixa: "bg-info", fundo: "bg-info-subtle text-info-fg", icone: Bell, label: "Informação" },
  ALERTA: {
    faixa: "bg-warning",
    fundo: "bg-warning-subtle text-warning-fg",
    icone: TriangleAlert,
    label: "Alerta",
  },
  CRITICO: {
    faixa: "bg-danger",
    fundo: "bg-danger-subtle text-danger-fg",
    icone: OctagonAlert,
    label: "Crítico",
  },
} as const;

type Filtro = "todos" | "nao-lidos";

export function ListaAlertas({ ehCliente }: { ehCliente: boolean }) {
  const router = useRouter();
  const toast = useToast();
  const [filtro, setFiltro] = useState<Filtro>("todos");
  const [marcandoTodos, setMarcandoTodos] = useState(false);

  const { itens, carregando, falha, recarregar, definirDados } = useLista<Notificacao>(
    "/notificacoes/?page_size=100",
    "alertas"
  );

  const naoLidas = useMemo(() => itens.filter((n) => !n.lida).length, [itens]);
  const visiveis = filtro === "nao-lidos" ? itens.filter((n) => !n.lida) : itens;

  async function abrir(n: Notificacao) {
    if (!n.lida) {
      // Marca como lida de forma otimista: a lista responde na hora, e se o
      // servidor recusar o próximo carregamento devolve a verdade.
      definirDados((atual) =>
        atual
          ? { ...atual, results: atual.results.map((i) => (i.id === n.id ? { ...i, lida: true } : i)) }
          : atual
      );
      try {
        await api(`/notificacoes/${n.id}/lida/`, { method: "POST" });
      } catch {
        recarregar();
      }
    }
    if (n.url) router.push(ehCliente ? destinoNoPortal(n.url) : n.url);
  }

  async function marcarTodas() {
    setMarcandoTodos(true);
    try {
      await api("/notificacoes/marcar-todas/", { method: "POST" });
      toast.sucesso(`${plural(naoLidas, "alerta")} marcado${naoLidas > 1 ? "s" : ""} como lido`);
      recarregar();
    } catch (e) {
      toast.falha(e, "Não foi possível marcar os alertas como lidos.");
    } finally {
      setMarcandoTodos(false);
    }
  }

  return (
    <PageBody>
      <PageHeader
        icon={Bell}
        title="Alertas"
        description={
          ehCliente
            ? "Tudo que exige a sua atenção: equipamentos em condição crítica, novas ordens de serviço e laudos publicados. Os mesmos avisos chegam por e-mail."
            : "Eventos automáticos do sistema — equipamento crítico, nova OSP, laudo concluído, SLA vencendo e aprovação pendente (Anexo I 2.10)."
        }
        trilha={[{ label: "Alertas" }]}
        selo={naoLidas > 0 ? <Badge tone="danger">{naoLidas} não lidos</Badge> : undefined}
        actions={
          naoLidas > 0 ? (
            <Button variant="secondary" icon={CheckCheck} onClick={marcarTodas} loading={marcandoTodos}>
              Marcar todos como lidos
            </Button>
          ) : undefined
        }
      />

      {itens.length > 0 && (
        <Toolbar
          filtros={
            <SegmentedControl
              label="Filtrar alertas"
              tamanho="sm"
              valor={filtro}
              onMudar={setFiltro}
              opcoes={[
                { valor: "todos", label: `Todos (${itens.length})` },
                { valor: "nao-lidos", label: `Não lidos (${naoLidas})` },
              ]}
            />
          }
        />
      )}

      {carregando ? (
        <LoadingState variante="cartoes" linhas={4} label="Carregando alertas…" />
      ) : falha ? (
        <ErrorCard falha={falha} onRetry={recarregar} />
      ) : visiveis.length === 0 ? (
        <Card padding={false}>
          {filtro === "nao-lidos" ? (
            <EmptyState
              compacto
              icon={CircleCheck}
              title="Nenhum alerta pendente"
              description="Você já leu todos os avisos."
              action={
                <Button variant="secondary" size="sm" onClick={() => setFiltro("todos")}>
                  Ver o histórico
                </Button>
              }
            />
          ) : (
            <EmptyState
              icon={Bell}
              title="Nenhum alerta até agora"
              description={
                ehCliente
                  ? "Você será avisado aqui — e por e-mail — quando algo do seu parque precisar de decisão."
                  : "Os alertas são disparados automaticamente pelos eventos do sistema."
              }
              comoFunciona={[
                "Uma medição fora do limite marca o equipamento como crítico.",
                "O sistema abre a ordem de serviço e avisa os responsáveis.",
                "Quando o laudo é emitido, o aviso de conclusão é enviado.",
              ]}
            />
          )}
        </Card>
      ) : (
        <ul className="space-y-2">
          {visiveis.map((n) => {
            const nivel = NIVEL[n.nivel] ?? NIVEL.INFO;
            const Icone = ICONE_EVENTO[n.evento] ?? nivel.icone;
            return (
              <li key={n.id}>
                <Card padding={false} className={cn("overflow-hidden", n.lida && "opacity-70")}>
                  <button
                    type="button"
                    onClick={() => abrir(n)}
                    className="flex w-full items-start gap-0 text-left transition-colors hover:bg-surface-muted/60"
                  >
                    {/* Faixa de nível: pista de gravidade que sobrevive ao P&B. */}
                    <span className={cn("w-1 shrink-0 self-stretch", nivel.faixa)} aria-hidden="true" />
                    <span className="flex flex-1 items-start gap-3.5 p-4">
                      <span
                        className={cn(
                          "flex h-9 w-9 shrink-0 items-center justify-center rounded-lg",
                          nivel.fundo
                        )}
                        aria-hidden="true"
                      >
                        <Icone className="h-[1.125rem] w-[1.125rem]" />
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="flex flex-wrap items-center gap-2">
                          <span className="font-semibold text-fg">{n.titulo}</span>
                          {!n.lida && <Badge tone="primary">Novo</Badge>}
                        </span>
                        <span className="mt-0.5 block text-sm text-fg-muted">{n.mensagem}</span>
                        <span className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-fg-subtle">
                          <span>{nivel.label}</span>
                          <span aria-hidden="true">·</span>
                          <span>{n.evento_display}</span>
                          <span aria-hidden="true">·</span>
                          <time dateTime={n.criado_em} title={dataHora(n.criado_em)}>
                            {tempoRelativo(n.criado_em)}
                          </time>
                          {!ehCliente && n.canais_enviados.length > 0 && (
                            <>
                              <span aria-hidden="true">·</span>
                              <span>enviado por {n.canais_enviados.join(", ")}</span>
                            </>
                          )}
                        </span>
                      </span>
                    </span>
                  </button>
                </Card>
              </li>
            );
          })}
        </ul>
      )}
    </PageBody>
  );
}
