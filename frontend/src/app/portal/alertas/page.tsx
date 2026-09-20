"use client";

import { ListaAlertas } from "@/features/alertas/lista-alertas";
import { useRegistrarVisita } from "@/features/portal/onboarding";

export default function PortalAlertasPage() {
  useRegistrarVisita("alertas");
  return <ListaAlertas ehCliente />;
}
