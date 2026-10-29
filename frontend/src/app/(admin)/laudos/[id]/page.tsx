"use client";

import { useParams } from "next/navigation";
import { LaudoGestao } from "@/features/laudos/laudo-gestao";

export default function LaudoInternoPage() {
  const { id } = useParams<{ id: string }>();
  return <LaudoGestao key={id} laudoId={id} />;
}