"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  AlertTriangle,
  Bell,
  CheckCheck,
  CheckCircle2,
  Clock,
  FileText,
  Wrench,
  type LucideIcon,
} from "lucide-react";
import { api } from "@/lib/api";
import type { Notificacao, Paginated } from "@/lib/types";
import { Button, Card, EmptyState, PageHeader, Spinner } from "@/components/ui";
import { Stagger, StaggerItem } from "@/components/motion";

const NIVEL_BORDER: Record<string, string> = {
  INFO: "border-l-accent",
  ALERTA: "border-l-warning",
  CRITICO: "border-l-danger",
};
const EVENTO_ICON: Record<string, LucideIcon> = {
  NOVA_OSP: Wrench,
  EQUIPAMENTO_CRITICO: AlertTriangle,
  LAUDO_CONCLUIDO: FileText,
  SLA_VENCENDO: Clock,
  APROVACAO_PENDENTE: CheckCircle2,
};
const ICON_TONE: Record<string, string> = {
  INFO: "bg-accent-subtle text-accent",
  ALERTA: "bg-warning-subtle text-warning-fg",
  CRITICO: "bg-danger-subtle text-danger-fg",
};

export default function NotificacoesPage() {
  const router = useRouter();
  const [itens, setItens] = useState<Notificacao[]>([]);
  const [loading, setLoading] = useState(true);

  async function reload() {
    const data = await api<Paginated<Notificacao>>("/notificacoes/");
    setItens(data.results);
  }

  useEffect(() => {
    reload().finally(() => setLoading(false));
  }, []);

  async function abrir(n: Notificacao) {
    if (!n.lida) {
      await api(`/notificacoes/${n.id}/lida/`, { method: "POST" });
      await reload();
    }
    if (n.url) router.push(n.url);
  }

  async function marcarTodas() {
    await api("/notificacoes/marcar-todas/", { method: "POST" });
    await reload();
  }

  const naoLidas = itens.filter((n) => !n.lida).length;

  return (
    <div className="space-y-6">
      <PageHeader
        icon={Bell}
        title="Notificações"
        description={`Eventos automáticos do sistema (Anexo I 2.10). ${naoLidas} não lida(s).`}
        actions={
          naoLidas > 0 ? (
            <Button variant="secondary" onClick={marcarTodas} icon={CheckCheck}>
              Marcar todas
            </Button>
          ) : undefined
        }
      />

      {loading ? (
        <Spinner />
      ) : itens.length === 0 ? (
        <Card>
          <EmptyState
            icon={Bell}
            title="Nenhuma notificação"
            description="Você será avisado aqui sobre equipamentos críticos, novas OSPs, laudos e SLAs."
          />
        </Card>
      ) : (
        <Stagger className="space-y-2" gap={0.04}>
          {itens.map((n) => {
            const Icon = EVENTO_ICON[n.evento] ?? Bell;
            return (
              <StaggerItem key={n.id}>
                <Card
                  interactive
                  padding={false}
                  className={`border-l-4 ${NIVEL_BORDER[n.nivel] ?? "border-l-border-strong"} ${
                    n.lida ? "opacity-65" : ""
                  }`}
                >
                  <button onClick={() => abrir(n)} className="flex w-full items-start gap-3.5 p-4 text-left">
                    <div
                      className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${
                        ICON_TONE[n.nivel] ?? "bg-surface-muted text-fg-subtle"
                      }`}
                    >
                      <Icon className="h-[18px] w-[18px]" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <p className="font-semibold text-fg">{n.titulo}</p>
                        {!n.lida && <span className="h-2 w-2 shrink-0 rounded-full bg-accent" />}
                      </div>
                      <p className="mt-0.5 text-sm text-fg-muted">{n.mensagem}</p>
                      <p className="mt-1.5 text-xs text-fg-subtle">
                        {n.evento_display} · {new Date(n.criado_em).toLocaleString("pt-BR")} · canais:{" "}
                        {n.canais_enviados.join(", ")}
                      </p>
                    </div>
                  </button>
                </Card>
              </StaggerItem>
            );
          })}
        </Stagger>
      )}
    </div>
  );
}
