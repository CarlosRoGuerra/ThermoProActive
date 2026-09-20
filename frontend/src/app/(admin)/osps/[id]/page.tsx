"use client";

import { useParams } from "next/navigation";
import { OspForm } from "../osp-form";

export default function EditarOspPage() {
  const params = useParams<{ id: string }>();
  return <OspForm ospId={Number(params.id)} />;
}
