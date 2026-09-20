"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Eye, EyeOff, KeyRound, LockKeyhole } from "lucide-react";
import { Alert, Button, Checkbox, Field, IconButton, Input } from "@/components/ds";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { podeAcessarRota, rotaInicial } from "@/lib/permissions";
import type { ContextoAuth } from "../api";

export function LoginForm({ contexto }: { contexto: ContextoAuth }) {
  const { signIn } = useAuth();
  const router = useRouter();
  const params = useSearchParams();
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [codigo, setCodigo] = useState("");
  const [mfa, setMfa] = useState(false);
  const [mostrar, setMostrar] = useState(false);
  const [lembrar, setLembrar] = useState(false);
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);
  const portal = contexto === "portal";

  async function enviar(evento: FormEvent) {
    evento.preventDefault();
    setErro("");
    if (!email.trim() || !senha) {
      setErro("Informe seu e-mail e sua senha para continuar.");
      return;
    }
    setEnviando(true);
    try {
      const usuario = await signIn(contexto, email.trim(), senha, lembrar, codigo);
      if (usuario.mfa_obrigatorio && !usuario.mfa_ativo) {
        router.replace(`/${contexto}/mfa/setup`);
        return;
      }
      const proximo = params.get("proximo");
      router.replace(proximo && podeAcessarRota(usuario, proximo) ? proximo : rotaInicial(usuario));
    } catch (falha) {
      if (falha instanceof ApiError && falha.status === 428) {
        setMfa(true);
        setErro("Confirme sua identidade com o segundo fator.");
      } else if (falha instanceof ApiError && falha.status === 0) {
        setErro("Não foi possível conectar ao servidor. Verifique sua conexão e tente novamente.");
      } else {
        setErro("E-mail ou senha incorretos. Confira os dados e tente novamente.");
      }
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div>
      <div className="mb-7">
        {portal ? (
          <>
            <p className="text-sm font-semibold text-primary">Portal do Cliente</p>
            <h1 className="mt-2 text-2xl font-semibold text-fg">Bem-vindo ao Pred Ativos</h1>
            <p className="mt-2 text-sm leading-relaxed text-fg-muted">
              Acesse sua conta para acompanhar equipamentos, monitoramentos, alertas e relatórios.
            </p>
          </>
        ) : (
          <>
            <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl bg-primary-subtle text-primary-subtle-fg lg:hidden">
              <LockKeyhole className="h-5 w-5" aria-hidden="true" />
            </div>
            <h1 className="text-2xl font-semibold text-fg">Área Administrativa</h1>
            <p className="mt-2 text-sm text-fg-muted">Acesso exclusivo para colaboradores autorizados.</p>
          </>
        )}
      </div>

      <form onSubmit={enviar} className="space-y-4" noValidate>
        <Field label={portal ? "E-mail" : "E-mail corporativo"} obrigatorio htmlFor={`${contexto}-email`}>
          <Input
            id={`${contexto}-email`}
            type="email"
            inputMode="email"
            autoComplete="email"
            autoFocus
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="nome@empresa.com.br"
          />
        </Field>
        <Field label="Senha" obrigatorio htmlFor={`${contexto}-senha`}>
          <div className="relative">
            <Input
              id={`${contexto}-senha`}
              type={mostrar ? "text" : "password"}
              autoComplete="current-password"
              value={senha}
              onChange={(e) => setSenha(e.target.value)}
              className="pr-11"
            />
            <IconButton
              icon={mostrar ? EyeOff : Eye}
              label={mostrar ? "Ocultar senha" : "Mostrar senha"}
              onClick={() => setMostrar((valor) => !valor)}
              className="absolute right-1 top-1/2 -translate-y-1/2"
              size="sm"
            />
          </div>
        </Field>
        {mfa && (
          <Field label="Código de autenticação" obrigatorio hint="Use o aplicativo autenticador ou um código de recuperação.">
            <Input
              value={codigo}
              onChange={(e) => setCodigo(e.target.value)}
              inputMode="numeric"
              autoComplete="one-time-code"
              iconeEsquerda={<KeyRound className="h-4 w-4" />}
            />
          </Field>
        )}
        <div className="flex items-center justify-between gap-4">
          {portal ? (
            <Checkbox checked={lembrar} onChange={setLembrar} label="Manter conectado" />
          ) : <span />}
          <Link href={`/${contexto}/esqueci-senha`} className="text-sm font-medium text-primary hover:underline">
            Esqueci minha senha
          </Link>
        </div>
        {erro && <Alert tone={mfa ? "info" : "danger"}>{erro}</Alert>}
        <Button type="submit" size="lg" block loading={enviando}>
          {portal ? "Entrar" : "Acessar painel"}
        </Button>
      </form>

      {portal && (
        <p className="mt-6 text-center text-sm text-fg-muted">
          Sua empresa ainda não tem acesso?{" "}
          <Link href="/portal/cadastro" className="font-semibold text-primary hover:underline">
            Solicitar acesso
          </Link>
        </p>
      )}
    </div>
  );
}
