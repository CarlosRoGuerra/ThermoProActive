"use client";

// Certificado A1 do responsável técnico (Anexo I 2.5.1.3). O .pfx e a senha seguem para o
// servidor, que valida e cifra o arquivo; a senha NÃO é guardada em lugar nenhum.

import { useEffect, useState, type FormEvent } from "react";
import { ShieldCheck, Trash2, Upload } from "lucide-react";
import { Alert, Badge, Button, Card, CardHeader, DescriptionList, Input, Field } from "@/components/ds";
import { api, ApiError } from "@/lib/api";
import { dataHora } from "@/lib/format";
import { useToast } from "@/components/ds";

type Certificado = {
  titular: string;
  emissor: string;
  numero_serie: string;
  valido_ate: string;
  sha256_certificado: string;
  vencido: boolean;
};

export function CertificadoA1() {
  const toast = useToast();
  const [certificado, setCertificado] = useState<Certificado | null | undefined>(undefined);
  const [arquivo, setArquivo] = useState<File | null>(null);
  const [senha, setSenha] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  async function carregar() {
    try {
      const r = await api<{ certificado: null } | Certificado>("/auth/certificado-a1/");
      setCertificado("certificado" in r ? null : r);
    } catch {
      setCertificado(null);
    }
  }

  useEffect(() => {
    carregar();
  }, []);

  async function enviar(evento: FormEvent) {
    evento.preventDefault();
    if (!arquivo || !senha) {
      setErro("Escolha o arquivo do certificado e informe a senha.");
      return;
    }
    setOcupado(true);
    setErro(null);
    try {
      const dados = new FormData();
      dados.append("arquivo", arquivo);
      dados.append("senha", senha);
      const r = await api<Certificado>("/auth/certificado-a1/", { method: "POST", body: dados });
      setCertificado(r);
      setSenha("");
      setArquivo(null);
      toast.sucesso("Certificado cadastrado.");
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : "Não foi possível cadastrar o certificado.");
    } finally {
      setOcupado(false);
    }
  }

  async function remover() {
    setOcupado(true);
    try {
      await api("/auth/certificado-a1/", { method: "DELETE" });
      setCertificado(null);
      toast.sucesso("Certificado removido.");
    } catch {
      setErro("Não foi possível remover o certificado agora.");
    } finally {
      setOcupado(false);
    }
  }

  if (certificado === undefined) return null;

  return (
    <Card>
      <CardHeader title="Certificado digital A1" icon={ShieldCheck} />
      {certificado ? (
        <div className="space-y-4">
          <DescriptionList
            items={[
              { label: "Titular", value: certificado.titular },
              { label: "Emissor", value: certificado.emissor },
              { label: "Número de série", value: certificado.numero_serie },
              { label: "Válido até", value: dataHora(certificado.valido_ate) },
              {
                label: "Situação",
                value: certificado.vencido ? <Badge tone="danger">Vencido</Badge> : <Badge tone="success">Válido</Badge>,
              },
            ]}
          />
          <p className="text-xs text-fg-muted">SHA-256 do certificado: {certificado.sha256_certificado}</p>
          <Button variant="secondary" icon={Trash2} onClick={remover} loading={ocupado}>
            Remover certificado
          </Button>
        </div>
      ) : (
        <form onSubmit={enviar} className="space-y-4">
          <p className="text-sm text-fg-muted">
            Envie o arquivo .pfx/.p12 do seu certificado A1 para assinar digitalmente os laudos que você
            emite. A senha é usada só para validar o arquivo e não é guardada.
          </p>
          <Field label="Arquivo do certificado (.pfx ou .p12)">
            <input
              type="file"
              accept=".pfx,.p12,application/x-pkcs12"
              onChange={(e) => setArquivo(e.target.files?.[0] ?? null)}
              className="text-sm text-fg"
            />
          </Field>
          <Field label="Senha do certificado">
            <Input type="password" autoComplete="off" value={senha} onChange={(e) => setSenha(e.target.value)} />
          </Field>
          {erro && <Alert tone="warning">{erro}</Alert>}
          <Button type="submit" icon={Upload} loading={ocupado}>
            Cadastrar certificado
          </Button>
        </form>
      )}
    </Card>
  );
}
