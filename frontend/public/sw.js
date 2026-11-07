// Service worker do Web Push (item 2.10.1.3). Só exibe o aviso que o servidor envia;
// o payload é texto curto (título, mensagem, id) — nada sensível vai no push.

self.addEventListener("push", (event) => {
  let dados = {};
  try {
    dados = event.data ? event.data.json() : {};
  } catch (_erro) {
    dados = { mensagem: event.data ? event.data.text() : "" };
  }
  event.waitUntil(
    self.registration.showNotification(dados.titulo || "Pred Ativos", {
      body: dados.mensagem || "",
      tag: dados.id || undefined,
      data: { url: "/" },
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((janelas) => {
      for (const janela of janelas) {
        if ("focus" in janela) return janela.focus();
      }
      return self.clients.openWindow(event.notification.data.url);
    }),
  );
});
