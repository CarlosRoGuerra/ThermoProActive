"use client";

import { ListaLaudos } from "@/features/laudos/lista-laudos";
import { useRegistrarVisita } from "@/features/portal/onboarding";

export default function PortalLaudosPage() {
  useRegistrarVisita("laudos");
  return <ListaLaudos baseHref="/portal/laudos" ehCliente />;
}
