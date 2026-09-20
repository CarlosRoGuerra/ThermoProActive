"use client";

import { useParams } from "next/navigation";
import { EquipamentoForm } from "@/app/(admin)/equipamentos/equipamento-form";

export default function PortalEditarEquipamentoPage() {
  const { id } = useParams<{ id: string }>();
  return <EquipamentoForm equipamentoId={Number(id)} />;
}
