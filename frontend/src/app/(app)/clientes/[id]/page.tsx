"use client";

import { useParams } from "next/navigation";
import { ClienteForm } from "../cliente-form";

export default function EditarClientePage() {
  const params = useParams<{ id: string }>();
  return <ClienteForm clienteId={Number(params.id)} />;
}
