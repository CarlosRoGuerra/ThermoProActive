"use client";

import { useParams } from "next/navigation";
import { PrestadorForm } from "../prestador-form";

export default function EditarPrestadorPage() {
  const params = useParams<{ id: string }>();
  return <PrestadorForm prestadorId={Number(params.id)} />;
}
