"use client";

import { Droplets } from "lucide-react";
import { PageBody, PageHeader } from "@/components/ds";
import { HistoricoFluidos } from "@/features/ensaios/historico-fluidos";

/* Portal do Cliente — Análise de fluidos: a tendência de cada parâmetro (FQ, EF)
   e do código de limpeza (CP) por equipamento, só dos relatórios finalizados. */
export default function PortalFluidosPage() {
  return (
    <PageBody>
      <PageHeader
        icon={Droplets}
        title="Análise de fluidos"
        description="Evolução dos resultados de óleo lubrificante e hidráulico por equipamento, com a referência e o estado de cada parâmetro."
      />
      <HistoricoFluidos />
    </PageBody>
  );
}
