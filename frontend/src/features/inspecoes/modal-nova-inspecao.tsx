"use client";

import { useEffect, useState } from "react";
import { Alert, Button, Field, Input, Modal, Select, useToast } from "@/components/ds";
import { Combobox } from "@/components/combobox";
import { api } from "@/lib/api";
import { useClienteAtivo } from "@/lib/cliente-ativo";
import { useClientes } from "@/lib/hierarquia";
import { useMutacao } from "@/lib/recurso";
import { usePermissoes } from "@/lib/permissions";

/**
 * "Nova inspeção" — coleta direta, sem carregar rota. Compartilhada por
 * /inspecoes (admin) e /portal/inspecoes: mesma modal, mesma validação, os
 * dois só decidem se a mostram (equipe interna sempre; cliente só o Master).
 *
 * Extraída para fora de um `page.tsx` de propósito — o App Router só aceita
 * exports específicos ("default", "metadata"...) num arquivo de página; um
 * componente nomeado ali quebra a checagem de tipos das rotas.
 */
export const TIPOS_ANALISE = [
  { valor: "VIBRACAO", texto: "Análise de vibração" },
  { valor: "TERMOGRAFIA", texto: "Termografia" },
  { valor: "ENSAIO_ELETRICO", texto: "Ensaios elétricos" },
  { valor: "FLUIDOS", texto: "Análise de fluidos" },
  { valor: "ULTRASSOM", texto: "Ultrassom" },
  { valor: "ESPESSURA", texto: "Medição de espessura" },
  { valor: "QUALIDADE_ENERGIA", texto: "Qualidade de energia" },
  { valor: "CORRETIVA", texto: "Manutenção corretiva" },
  { valor: "SENSITIVA", texto: "Inspeção sensitiva" },
];

export function ModalNovaInspecao({
  aberto,
  clienteSugerido,
  onFechar,
  onCriada,
}: {
  aberto: boolean;
  clienteSugerido: number | "";
  onFechar: () => void;
  onCriada: (id: number) => void;
}) {
  const toast = useToast();
  const { ehCliente } = usePermissoes();
  const { clienteAtivo } = useClienteAtivo();
  const { opcoes: opcoesClientes } = useClientes(aberto);
  const mutacao = useMutacao("criação de inspeção");

  const [cliente, setCliente] = useState<number | "">(clienteSugerido);
  const [tipo, setTipo] = useState("VIBRACAO");
  const [dataColeta, setDataColeta] = useState(() => new Date().toISOString().slice(0, 10));

  // Reabrir já vem com o cliente em atendimento e a data de hoje.
  useEffect(() => {
    if (!aberto) return;
    setCliente(clienteSugerido);
    setDataColeta(new Date().toISOString().slice(0, 10));
  }, [aberto, clienteSugerido]);

  async function criar() {
    if (!cliente) return;
    const r = await mutacao.executar(() =>
      api<{ id: number }>("/inspecoes/", {
        method: "POST",
        body: { cliente, data: dataColeta, tipo_analise: tipo },
      })
    );
    if (r.ok) onCriada(r.dados.id);
    else toast.erro(r.falha.titulo, { descricao: r.falha.descricao });
  }

  return (
    <Modal
      aberto={aberto}
      onFechar={onFechar}
      travarFundo
      title="Nova inspeção"
      description="A inspeção agrupa as medições de uma coleta. As medições são lançadas na tela dela."
      footer={
        <>
          <Button variant="secondary" size="sm" onClick={onFechar} disabled={mutacao.enviando}>
            Cancelar
          </Button>
          <Button size="sm" onClick={criar} loading={mutacao.enviando} disabled={!cliente}>
            Criar e lançar medições
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        {ehCliente ? (
          <Field label="Cliente" hint="Sua empresa — não muda.">
            <Input value={clienteAtivo?.nome_fantasia || clienteAtivo?.nome || ""} disabled readOnly />
          </Field>
        ) : (
          <Field
            label="Cliente"
            obrigatorio
            hint="Define de quem são os equipamentos que você poderá medir."
          >
            <Combobox
              value={cliente}
              onChange={setCliente}
              options={opcoesClientes}
              placeholder="Buscar cliente…"
              permiteLimpar={false}
            />
          </Field>
        )}

        <Field label="Tecnologia de análise" obrigatorio>
          <Select value={tipo} onChange={(e) => setTipo(e.target.value)}>
            {TIPOS_ANALISE.map((t) => (
              <option key={t.valor} value={t.valor}>
                {t.texto}
              </option>
            ))}
          </Select>
        </Field>

        <Field label="Data da coleta" obrigatorio>
          <Input type="date" value={dataColeta} onChange={(e) => setDataColeta(e.target.value)} />
        </Field>

        <Alert tone="info">
          Para coletar uma rota inteira com folha de campo e transferência para o escritório, use{" "}
          <strong>Inspeções → Análise de campo</strong>.
        </Alert>
      </div>
    </Modal>
  );
}
