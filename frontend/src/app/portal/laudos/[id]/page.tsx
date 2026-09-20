"use client";

import { useParams } from "next/navigation";
import { LaudoDocumento } from "@/features/laudos/laudo-documento";

/** Laudo aberto pelo cliente — somente leitura, sem ação de emissão. */
export default function PortalLaudoPage() {
  const { id } = useParams<{ id: string }>();
  return (
    <LaudoDocumento
      laudoId={id}
      trilha={[{ label: "Laudos técnicos", href: "/portal/laudos" }, { label: `#${id}` }]}
    />
  );
}
