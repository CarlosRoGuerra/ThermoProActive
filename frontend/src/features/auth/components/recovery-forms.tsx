"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { CheckCircle2, Eye, EyeOff } from "lucide-react";
import { Alert, Button, Field, IconButton, Input } from "@/components/ds";
import { ApiError } from "@/lib/api";
import { redefinirSenha, solicitarRecuperacao, type ContextoAuth } from "../api";

export function ForgotPasswordForm({ contexto }: { contexto: ContextoAuth }) {
  const [email, setEmail] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [mensagem, setMensagem] = useState("");
  const [erro, setErro] = useState("");
  const portal = contexto === "portal";

  async function enviar(evento: FormEvent) {
    evento.preventDefault();
    setErro("");
    if (!email.includes("@")) { setErro("Informe um e-mail válido."); return; }
    setEnviando(true);
    try {
      const resposta = await solicitarRecuperacao(contexto, email.trim());
      setMensagem(resposta.detail);
    } catch (falha) {
      setErro(falha instanceof ApiError && falha.status === 429
        ? "Muitas solicitações. Aguarde antes de tentar novamente."
        : "Não foi possível enviar as instruções agora.");
    } finally { setEnviando(false); }
  }

  return (
    <div>
      <h1 className="text-2xl font-semibold text-fg">{portal ? "Recuperar acesso" : "Recuperar acesso administrativo"}</h1>
      <p className="mt-2 text-sm leading-relaxed text-fg-muted">
        {portal
          ? "Informe o e-mail associado à sua conta. Enviaremos as instruções para redefinir sua senha."
          : "Informe seu e-mail corporativo para receber as instruções de recuperação."}
      </p>
      {mensagem ? (
        <div className="mt-7 space-y-5">
          <Alert tone="success" icon={CheckCircle2}>{mensagem}</Alert>
          <Link href={`/${contexto}/login`} className="inline-flex h-10 w-full items-center justify-center rounded-lg bg-primary px-4 text-sm font-medium text-primary-fg hover:bg-primary-hover">
            Voltar para {portal ? "o login" : "a Área Administrativa"}
          </Link>
        </div>
      ) : (
        <form onSubmit={enviar} className="mt-7 space-y-5" noValidate>
          <Field label={portal ? "E-mail" : "E-mail corporativo"} obrigatorio erro={erro || null}>
            <Input type="email" inputMode="email" autoComplete="email" autoFocus value={email} onChange={(e) => setEmail(e.target.value)} />
          </Field>
          <Button type="submit" block size="lg" loading={enviando}>Enviar instruções</Button>
          <Link href={`/${contexto}/login`} className="block text-center text-sm font-medium text-primary hover:underline">
            Voltar para {portal ? "o login" : "a Área Administrativa"}
          </Link>
        </form>
      )}
    </div>
  );
}

export function ResetPasswordForm({ contexto }: { contexto: ContextoAuth }) {
  const params = useSearchParams();
  const token = params.get("token") ?? "";
  const [senha, setSenha] = useState("");
  const [confirmacao, setConfirmacao] = useState("");
  const [mostrar, setMostrar] = useState(false);
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [concluido, setConcluido] = useState(false);
  const portal = contexto === "portal";
  const forca = senha.length >= 20 ? "Forte" : senha.length >= 15 ? "Adequada" : "Use ao menos 15 caracteres";

  async function enviar(evento: FormEvent) {
    evento.preventDefault(); setErro("");
    if (!token) { setErro("Este link não é mais válido."); return; }
    if (senha.length < 15) { setErro("A nova senha precisa ter pelo menos 15 caracteres."); return; }
    if (senha !== confirmacao) { setErro("As senhas não coincidem."); return; }
    setEnviando(true);
    try { await redefinirSenha(token, senha); setConcluido(true); }
    catch { setErro("Este link não é mais válido. Solicite um novo link para redefinir sua senha."); }
    finally { setEnviando(false); }
  }

  if (concluido) return (
    <div className="text-center">
      <CheckCircle2 className="mx-auto h-12 w-12 text-success" aria-hidden="true" />
      <h1 className="mt-5 text-2xl font-semibold text-fg">{portal ? "Senha alterada com sucesso." : "Senha administrativa atualizada."}</h1>
      <Link href={`/${contexto}/login`} className="mt-7 inline-flex h-11 w-full items-center justify-center rounded-lg bg-primary px-5 text-base font-medium text-primary-fg hover:bg-primary-hover">
        Acessar {portal ? "Portal do Cliente" : "Área Administrativa"}
      </Link>
    </div>
  );

  return (
    <div>
      <h1 className="text-2xl font-semibold text-fg">Criar nova senha</h1>
      <p className="mt-2 text-sm text-fg-muted">Use uma frase longa e única. Espaços e gerenciadores de senha são bem-vindos.</p>
      <form onSubmit={enviar} className="mt-7 space-y-4" noValidate>
        <Field label="Nova senha" obrigatorio hint={forca}>
          <div className="relative">
            <Input type={mostrar ? "text" : "password"} autoComplete="new-password" value={senha} onChange={(e) => setSenha(e.target.value)} className="pr-11" />
            <IconButton icon={mostrar ? EyeOff : Eye} label={mostrar ? "Ocultar senha" : "Mostrar senha"} onClick={() => setMostrar(!mostrar)} className="absolute right-1 top-1/2 -translate-y-1/2" />
          </div>
        </Field>
        <Field label="Confirmar nova senha" obrigatorio>
          <Input type={mostrar ? "text" : "password"} autoComplete="new-password" value={confirmacao} onChange={(e) => setConfirmacao(e.target.value)} />
        </Field>
        {erro && <Alert tone="danger">{erro}</Alert>}
        <Button type="submit" block size="lg" loading={enviando}>{portal ? "Redefinir senha" : "Atualizar senha"}</Button>
      </form>
    </div>
  );
}
