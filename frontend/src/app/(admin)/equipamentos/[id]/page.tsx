"use client";

import { useParams } from "next/navigation";
import { EquipamentoForm } from "../equipamento-form";

export default function EditarEquipamentoPage() {
  const params = useParams<{ id: string }>();
  return <EquipamentoForm equipamentoId={Number(params.id)} />;
}
