// Web Push (VAPID) do navegador — item 2.10.1.3. O polling do portal continua valendo
// como fallback: se o push não chegar, a lista ainda é atualizada a cada 60 s.
import { api } from "@/lib/api";

export type ResultadoPush = "ATIVO" | "NEGADO" | "INDISPONIVEL" | "NAO_CONFIGURADO";

export function pushSuportado(): boolean {
  return typeof window !== "undefined" && "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
}

function chaveParaBytes(base64Url: string): Uint8Array {
  const padding = "=".repeat((4 - (base64Url.length % 4)) % 4);
  const base64 = (base64Url + padding).replace(/-/g, "+").replace(/_/g, "/");
  const bruto = atob(base64);
  return Uint8Array.from(bruto, (c) => c.charCodeAt(0));
}

/** Pede permissão, registra o service worker e envia a assinatura deste dispositivo ao servidor. */
export async function ativarPush(): Promise<ResultadoPush> {
  if (!pushSuportado()) return "INDISPONIVEL";
  const chave = await api<{ chave: string; configurado: boolean }>("/notificacoes/push/chave/");
  if (!chave.configurado) return "NAO_CONFIGURADO";
  if ((await Notification.requestPermission()) !== "granted") return "NEGADO";
  const registro = await navigator.serviceWorker.register("/sw.js");
  const assinatura =
    (await registro.pushManager.getSubscription()) ??
    (await registro.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: chaveParaBytes(chave.chave) as BufferSource,
    }));
  const dados = assinatura.toJSON();
  await api("/notificacoes/push/assinatura/", {
    method: "POST",
    body: { endpoint: dados.endpoint, keys: dados.keys },
  });
  return "ATIVO";
}

/** Remove a assinatura deste dispositivo (no servidor e no navegador). */
export async function desativarPush(): Promise<void> {
  if (!pushSuportado()) return;
  const registro = await navigator.serviceWorker.getRegistration("/sw.js");
  const assinatura = await registro?.pushManager.getSubscription();
  if (!assinatura) return;
  await api("/notificacoes/push/assinatura/", { method: "DELETE", body: { endpoint: assinatura.endpoint } });
  await assinatura.unsubscribe();
}
