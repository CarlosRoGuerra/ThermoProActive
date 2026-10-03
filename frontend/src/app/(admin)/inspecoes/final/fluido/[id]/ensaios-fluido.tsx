"use client";

import { Droplets } from "lucide-react";
import { PageBody, PageHeader } from "@/components/ds";
import { usePermissoes } from "@/lib/permissions";
import { EditorFluido } from "@/features/ensaios/editor-fluido";

/** Escritório: resultados do laboratório (FQ, EF, CP), conclusão e recomendação da amostra de fluido. */
export function EnsaiosFluidoPagina({ itemId }: { itemId: number }) {
  const { podeEditar } = usePermissoes();
  return (
    <PageBody>
      <PageHeader
        icon={Droplets}
        title="Análise de fluido"
        description="Coleta da amostra e os resultados do laboratório — FQ, EF e, quando pedida, CP — com a referência e o histórico de cada parâmetro."
        trilha={[
          { label: "Inspeções", href: "/inspecoes/campo" },
          { label: "Análise final", href: "/inspecoes/final?visao=fluidos" },
          { label: "Análise de fluido" },
        ]}
      />
      <EditorFluido
        itemId={itemId}
        podeEditar={podeEditar}
        voltar={{ href: "/inspecoes/final?visao=fluidos", label: "Voltar para os ensaios de fluidos" }}
      />
    </PageBody>
  );
}
