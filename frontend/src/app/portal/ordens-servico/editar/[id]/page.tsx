"use client";

import { useParams } from "next/navigation";
import { OspForm } from "@/app/(admin)/osps/osp-form";

export default function PortalEditarOspPage() {
  const { id } = useParams<{ id: string }>();
  return <OspForm ospId={Number(id)} />;
}
