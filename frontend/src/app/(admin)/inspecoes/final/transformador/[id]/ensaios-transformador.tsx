"use client";

import { FlaskConical } from "lucide-react";
import { PageBody, PageHeader } from "@/components/ds";
import { usePermissoes } from "@/lib/permissions";
import { EditorTransformador } from "@/features/ensaios/editor";

/** Escritório: laudos do laboratório, conclusão e recomendação de cada ensaio do transformador. */
export function EnsaiosTransformadorPagina({ itemId }: { itemId: number }) {
  const { podeEditar } = usePermissoes();
  return (
    <PageBody>
      <PageHeader
        icon={FlaskConical}
        title="Ensaios do transformador"
        description="Registro de campo, valores, laudo, conclusão e recomendação de cada ensaio — o que sai nas fichas do relatório."
        trilha={[
          { label: "Inspeções", href: "/inspecoes/campo" },
          { label: "Análise final", href: "/inspecoes/final?visao=ensaios" },
          { label: "Ensaios do transformador" },
        ]}
      />
      <EditorTransformador
        itemId={itemId}
        podeEditar={podeEditar}
        voltar={{ href: "/inspecoes/final?visao=ensaios", label: "Voltar para os ensaios de transformador" }}
      />
    </PageBody>
  );
}
