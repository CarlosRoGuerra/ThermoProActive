"use client";

// Assinatura digital PAdES do laudo emitido (Anexo I 2.5.1.3). Quem assina é o responsável
// técnico do laudo, com o certificado A1 cadastrado no perfil. A assinatura é invisível: o
// PDF aprovado não muda. A verificação mostra se o conteúdo continua íntegro.

import { useEffect, useState, type FormEvent } from "react";
import { FileSignature, ShieldCheck } from "lucide-react";
import { Alert, Badge, Button, Card, Field, Input, useToast } from "@/components/ds";
import { api, ApiError, downloadFile } from "@/lib/api";

type Assinatura = {
  campo: string;
  intacto: boolean;
  valido: boolean;
  confiavel: boolean;
};

type Verificacao = {
  assinado: boolean;
  sha256_confere?: boolean;
  assinaturas?: Assinatura[];
  raiz_configurada?: boolean;
};

export function AssinaturaLaudo({
  laudoId,
  numero,
  emitido,
  ehResponsavel,
}: {
  laudoId: number;
  numero: string;
  emitido: boolean;
  ehResponsavel: boolean;
}) {
  const toast = useToast();
  const [verificacao, setVerificacao] = useState<Verificacao | null>(null);
  const [senha, setSenha] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  async function verificar() {
    try {
      setVerificacao(await api<Verificacao>(`/laudos/${laudoId}/verificar-assinatura/`));
    } catch {
      setVerificacao(null);
    }
  }

  useEffect(() => {
    if (emitido) verificar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [laudoId, emitido]);

  if (!emitido) return null;

  async function assinar(evento: FormEvent) {
    evento.preventDefault();
    if (!senha) {
      setErro("Informe a senha do certificado.");
      return;
    }
    setOcupado(true);
    setErro(null);
    try {
      await api(`/laudos/${laudoId}/assinar-digitalmente/`, { method: "POST", body: { senha } });
      setSenha("");
      toast.sucesso("Laudo assinado digitalmente.");
      await verificar();
    } catch (e) {
      // 409 SEM_CERTIFICADO: a aprovação eletrônica continua; a mensagem já diz isso.
      setErro(e instanceof ApiError ? e.message : "Não foi possível assinar agora.");
    } finally {
      setOcupado(false);
    }
  }

  const assinado = !!verificacao?.assinado;
  const integro = !!verificacao?.assinaturas?.every((a) => a.intacto) && verificacao?.sha256_confere !== false;

  return (
    <Card>
      <h2 className="mb-3 flex items-center gap-2 font-semibold text-fg">
        <ShieldCheck className="h-4 w-4" aria-hidden /> Assinatura digital
      </h2>
      {assinado ? (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={integro ? "success" : "danger"}>{integro ? "Íntegro desde a assinatura" : "Conteúdo alterado"}</Badge>
            {verificacao?.assinaturas?.map((a) => (
              <Badge key={a.campo} tone={a.confiavel ? "success" : "warning"}>
                {a.confiavel ? "Cadeia confiável" : "Cadeia não avaliada"}
              </Badge>
            ))}
          </div>
          {!verificacao?.raiz_configurada && (
            <p className="text-xs text-fg-muted">
              Nenhuma autoridade certificadora raiz configurada no servidor: a cadeia do certificado não foi avaliada.
            </p>
          )}
          <Button
            variant="secondary"
            onClick={() => downloadFile(`/laudos/${laudoId}/pdf-assinado/`, `${numero}-assinado.pdf`)}
          >
            Baixar PDF assinado
          </Button>
        </div>
      ) : ehResponsavel ? (
        <form onSubmit={assinar} className="space-y-3">
          <p className="text-sm text-fg-muted">
            Assina o PDF emitido com o seu certificado A1. A senha é usada só para assinar e não é guardada.
          </p>
          <Field label="Senha do certificado">
            <Input type="password" autoComplete="off" value={senha} onChange={(e) => setSenha(e.target.value)} />
          </Field>
          {erro && <Alert tone="warning">{erro}</Alert>}
          <Button type="submit" icon={FileSignature} loading={ocupado}>
            Assinar digitalmente
          </Button>
        </form>
      ) : (
        <p className="text-sm text-fg-muted">Este laudo ainda não foi assinado digitalmente.</p>
      )}
      {verificacao && verificacao.assinado && verificacao.assinaturas?.length === 0 && (
        <p className="mt-2 text-xs text-fg-muted">Sem assinaturas encontradas no PDF.</p>
      )}
    </Card>
  );
}
