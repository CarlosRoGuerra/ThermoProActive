"use client";

import { FlaskConical } from "lucide-react";
import { PageBody, PageHeader } from "@/components/ds";
import { usePermissoes } from "@/lib/permissions";
import { EditorSubestacao } from "@/features/ensaios/editor-subestacao";

/** Escritório: registro, dados de placa, medições e laudo de cada ensaio do equipamento de subestação. */
export function EnsaiosSubestacaoPagina({ itemId }: { itemId: number }) {
  const { podeEditar } = usePermissoes();
  return (
    <PageBody>
      <PageHeader
        icon={FlaskConical}
        title="Ensaios elétricos de subestação"
        description="Registro de campo, dados de placa, medições por série, laudo, conclusão e recomendação de cada ensaio — o que sai nas fichas do relatório."
        trilha={[
          { label: "Inspeções", href: "/inspecoes/campo" },
          { label: "Análise final", href: "/inspecoes/final?visao=subestacao" },
          { label: "Ensaios de subestação" },
        ]}
      />
      <EditorSubestacao
        itemId={itemId}
        podeEditar={podeEditar}
        voltar={{ href: "/inspecoes/final?visao=subestacao", label: "Voltar para os ensaios de subestação" }}
      />
    </PageBody>
  );
}
