"use client";

import { useParams } from "next/navigation";
import { RetornoOsp } from "@/features/portal/retorno-osp";
import { PainelExecucaoOSP } from "@/features/osp/painel-execucao";

export default function PortalRetornoOspPage() {
  const { id } = useParams<{ id: string }>();
  // Cliente: retorno da execução + checklist/peças/fotos/horas só para leitura, e a assinatura.
  return (
    <>
      <RetornoOsp ospId={Number(id)} />
      <div className="mx-auto mt-6 max-w-5xl px-4 pb-10">
        <PainelExecucaoOSP ospId={Number(id)} modo="cliente" />
      </div>
    </>
  );
}
