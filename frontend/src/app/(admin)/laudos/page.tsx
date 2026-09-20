"use client";

import { ListaLaudos } from "@/features/laudos/lista-laudos";

export default function LaudosPage() {
  return <ListaLaudos baseHref="/laudos" ehCliente={false} />;
}
