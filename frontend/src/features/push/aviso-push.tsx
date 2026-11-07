"use client";

// Ativar/desativar o aviso no navegador deste dispositivo (Web Push, Anexo I 2.10.1.3).
// Vale para admin e portal: é a mesma API. Se o navegador não suporta ou o servidor não
// tem as chaves VAPID, a tela diz o motivo em vez de fingir que está ativo.

import { useEffect, useState } from "react";
import { BellRing, BellOff } from "lucide-react";
import { Alert, Button, Card } from "@/components/ds";
import { ativarPush, desativarPush, pushSuportado, type ResultadoPush } from "@/lib/push";
import { useToast } from "@/components/ds";

type Estado = "carregando" | "ativo" | "inativo" | "indisponivel";

export function AvisoPush() {
  const toast = useToast();
  const [estado, setEstado] = useState<Estado>("carregando");
  const [ocupado, setOcupado] = useState(false);
  const [aviso, setAviso] = useState<string | null>(null);

  useEffect(() => {
    let vivo = true;
    (async () => {
      if (!pushSuportado()) {
        if (vivo) setEstado("indisponivel");
        return;
      }
      const registro = await navigator.serviceWorker.getRegistration("/sw.js");
      const assinatura = await registro?.pushManager.getSubscription();
      if (vivo) setEstado(assinatura ? "ativo" : "inativo");
    })().catch(() => {
      if (vivo) setEstado("indisponivel");
    });
    return () => {
      vivo = false;
    };
  }, []);

  async function ativar() {
    setOcupado(true);
    setAviso(null);
    try {
      const resultado: ResultadoPush = await ativarPush();
      if (resultado === "ATIVO") {
        setEstado("ativo");
        toast.sucesso("Avisos ativados neste dispositivo.");
      } else if (resultado === "NEGADO") {
        setAviso("A permissão de notificações foi negada no navegador. Libere-a nas configurações do site.");
      } else if (resultado === "NAO_CONFIGURADO") {
        setAviso("O servidor ainda não tem as chaves de push configuradas. O aviso continua chegando pela tela.");
      } else {
        setEstado("indisponivel");
      }
    } catch {
      setAviso("Não foi possível ativar agora. Tente de novo em instantes.");
    } finally {
      setOcupado(false);
    }
  }

  async function desativar() {
    setOcupado(true);
    try {
      await desativarPush();
      setEstado("inativo");
      toast.sucesso("Avisos desativados neste dispositivo.");
    } catch {
      setAviso("Não foi possível desativar agora. Tente de novo.");
    } finally {
      setOcupado(false);
    }
  }

  if (estado === "carregando") return null;
  if (estado === "indisponivel") {
    return (
      <Alert tone="info" title="Avisos no navegador indisponíveis">
        Este navegador não suporta notificações em segundo plano. Os alertas continuam aparecendo nesta tela.
      </Alert>
    );
  }

  const ativo = estado === "ativo";
  return (
    <Card>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="font-medium text-fg">Avisos neste dispositivo</p>
          <p className="text-sm text-fg-muted">
            {ativo
              ? "Este dispositivo recebe os alertas mesmo com o site fechado."
              : "Receba os alertas como aviso do navegador, mesmo com o site fechado."}
          </p>
        </div>
        {ativo ? (
          <Button variant="secondary" icon={BellOff} onClick={desativar} loading={ocupado}>
            Desativar avisos
          </Button>
        ) : (
          <Button icon={BellRing} onClick={ativar} loading={ocupado}>
            Ativar avisos
          </Button>
        )}
      </div>
      {aviso && (
        <div className="mt-3">
          <Alert tone="warning">{aviso}</Alert>
        </div>
      )}
    </Card>
  );
}
