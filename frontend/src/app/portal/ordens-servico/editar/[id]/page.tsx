"use client";

import { useParams } from "next/navigation";
import { RetornoOsp } from "@/features/portal/retorno-osp";

export default function PortalRetornoOspPage() {
  const { id } = useParams<{ id: string }>();
  return <RetornoOsp ospId={Number(id)} />;
}
