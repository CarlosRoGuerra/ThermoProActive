"use client";

import { useEffect, useState } from "react";
import { ClipboardCheck } from "lucide-react";
import { Alert, Button, Modal, useToast } from "@/components/ds";
import { AchadoCampos } from "@/components/achado-campos";
import { api } from "@/lib/api";
import { useMutacao } from "@/lib/recurso";
import {
  formDeAchado,
  formVazio,
  payloadDeForm,
  tecnologiaTipo,
  type AchadoForm,
} from "@/lib/inspecoes";
import type { Achado, ItemInspecao } from "@/lib/types";

/**
 * Registro de uma análise (Achado) na folha de campo.
 *
 * Usa o `Modal` do Design System em vez da sobreposição feita à mão que existia
 * aqui: assim herda Esc para fechar, foco aprisionado e devolvido, e fundo sem
 * rolagem — o que a versão anterior não tinha.
 *
 * O formulário em si continua sendo o `AchadoCampos`, que se adapta à tecnologia
 * e lê os catálogos (TipoComponente, TipoAnomalia, TipoRecomendacao, Condicao).
 * Nada aqui é lista fixa no frontend.
 */
export function ModalAnalise({
  aberto,
  item,
  achado,
  tecnologiaNome,
  tecnologiaId,
  onFechar,
  onSalvo,
}: {
  aberto: boolean;
  item: ItemInspecao | null;
  /** `null` = nova análise. */
  achado: Achado | null;
  tecnologiaNome: string;
  tecnologiaId: number;
  onFechar: () => void;
  onSalvo: () => void | Promise<void>;
}) {
  const toast = useToast();
  const mutacao = useMutacao("análise de campo");
  const [form, setForm] = useState<AchadoForm>(formVazio());

  // Reabrir o modal sempre parte do estado certo: edição carrega o achado;
  // nova herda a condição já definida no item (reclassificável no escritório).
  useEffect(() => {
    if (!aberto || !item) return;
    setForm(
      achado
        ? formDeAchado(achado)
        : { ...formVazio(), condicao: item.condicao != null ? String(item.condicao) : "" }
    );
  }, [aberto, item, achado]);

  if (!item) return null;

  async function salvar() {
    const corpo = payloadDeForm(form);
    const r = await mutacao.executar(() =>
      achado
        ? api(`/achados/${achado.id}/`, { method: "PATCH", body: corpo })
        : api("/achados/", { method: "POST", body: { ...corpo, item: item!.id } })
    );
    if (r.ok) {
      toast.sucesso(achado ? "Análise atualizada" : "Análise registrada", {
        descricao: `${item!.equipamento_tag} — segue para a Análise final.`,
      });
      await onSalvo();
      return;
    }
    toast.erro(r.falha.titulo, { descricao: r.falha.descricao });
  }

  return (
    <Modal
      aberto={aberto}
      onFechar={onFechar}
      travarFundo
      tamanho="xl"
      title={achado ? "Editar análise" : "Nova análise"}
      description={`${item.equipamento_tag} — ${item.equipamento_nome} · ${tecnologiaNome}`}
      footer={
        <>
          <Button variant="secondary" size="sm" onClick={onFechar} disabled={mutacao.enviando}>
            Cancelar
          </Button>
          <Button size="sm" onClick={salvar} loading={mutacao.enviando} icon={ClipboardCheck}>
            {achado ? "Salvar análise" : "Adicionar análise"}
          </Button>
        </>
      }
    >
      {mutacao.falha?.tipo === "validacao" && (
        <div className="mb-4">
          <Alert tone="danger" title="Confira os dados da análise">
            {mutacao.falha.descricao}
          </Alert>
        </div>
      )}

      <AchadoCampos
        form={form}
        setForm={setForm}
        tipo={tecnologiaTipo(tecnologiaNome)}
        tecnologiaId={tecnologiaId}
      />
    </Modal>
  );
}
