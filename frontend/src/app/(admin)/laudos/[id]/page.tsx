"use client";

import { useParams } from "next/navigation";
import { ShieldCheck } from "lucide-react";
import { Alert, Button, ConfirmDialog, useToast } from "@/components/ds";
import { LaudoDocumento } from "@/features/laudos/laudo-documento";
import { api } from "@/lib/api";
import { useRecurso, useMutacao } from "@/lib/recurso";
import { usePermissoes } from "@/lib/permissions";
import { useState } from "react";
import type { Laudo } from "@/lib/types";

/**
 * Laudo na visão da equipe interna: o mesmo documento do portal do cliente,
 * mais a ação de emitir.
 *
 * A emissão exige Conselho de Classe no cadastro do responsável (regra do
 * backend, Anexo I 3.1.2). Em vez de deixar o usuário clicar e receber um 400
 * seco, o botão é desabilitado com o motivo à vista.
 */
export default function LaudoInternoPage() {
  const { id } = useParams<{ id: string }>();
  const toast = useToast();
  const { pode, user } = usePermissoes();
  const [confirmando, setConfirmando] = useState(false);

  const recurso = useRecurso<Laudo>(`/laudos/${id}/`, "laudo técnico");
  const mutacao = useMutacao("emissão de laudo");
  const laudo = recurso.dados;

  const podeEmitir = pode("laudos:emitir");
  const podeAssinar = pode("laudos:assinar");
  const rascunho = laudo?.status === "RASCUNHO";

  async function emitir() {
    const r = await mutacao.executar(() => api(`/laudos/${id}/emitir/`, { method: "POST" }));
    setConfirmando(false);
    if (r.ok) {
      toast.sucesso("Laudo emitido", {
        descricao: "O documento já está disponível para o cliente no portal dele.",
      });
      recurso.recarregar();
    } else {
      toast.erro(r.falha.titulo, { descricao: r.falha.descricao });
    }
  }

  return (
    <>
      <LaudoDocumento
        laudoId={id}
        laudo={laudo}
        relatorioHref={`/laudos/${id}/relatorio`}
        trilha={[{ label: "Laudos técnicos", href: "/laudos" }, { label: laudo?.numero ?? `#${id}` }]}
        aviso={
          rascunho && podeEmitir && !podeAssinar ? (
            <Alert tone="warning" title="Você ainda não pode assinar laudos">
              Seu cadastro está sem o registro em Conselho de Classe (ex.: CREA), exigido para
              assinar o documento. Um usuário de nível Master pode completar isso em Usuários e
              acessos.
            </Alert>
          ) : undefined
        }
        acoes={
          rascunho && podeEmitir ? (
            <Button
              icon={ShieldCheck}
              onClick={() => setConfirmando(true)}
              disabled={!podeAssinar}
              title={
                podeAssinar
                  ? undefined
                  : "Cadastre seu Conselho de Classe para poder assinar laudos"
              }
            >
              Emitir laudo
            </Button>
          ) : undefined
        }
      />

      <ConfirmDialog
        aberto={confirmando}
        onFechar={() => setConfirmando(false)}
        onConfirmar={emitir}
        enviando={mutacao.enviando}
        tom="primary"
        icon={ShieldCheck}
        title="Emitir este laudo?"
        confirmarLabel="Emitir e publicar"
        mensagem={
          <>
            O laudo <strong>{laudo?.numero}</strong> será assinado como{" "}
            <strong>{user?.nome}</strong> e publicado no portal do cliente{" "}
            <strong>{laudo?.cliente_nome}</strong>.
          </>
        }
        detalhe="O cliente recebe a notificação de laudo concluído nos canais configurados."
        irreversivel
      />
    </>
  );
}
