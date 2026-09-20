"use client";

// Mesmo formulário do admin (/osps/nova) — o campo "Cliente" se auto-preenche
// e trava na própria empresa quando quem preenche é o Master do Portal.
import { OspForm } from "@/app/(admin)/osps/osp-form";

export default function PortalNovaOspPage() {
  return <OspForm />;
}
