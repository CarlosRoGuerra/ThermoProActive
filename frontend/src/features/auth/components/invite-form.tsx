"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { CheckCircle2, Eye, EyeOff, LoaderCircle } from "lucide-react";
import { Alert, Button, Checkbox, Field, IconButton, Input } from "@/components/ds";
import { aceitarConvite, consultarConvite, type ContextoAuth } from "../api";

export function InviteForm({ contexto, token }: { contexto: ContextoAuth; token: string }) {
  const [convite, setConvite] = useState<{ nome: string; email: string } | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [invalido, setInvalido] = useState(false);
  const [senha, setSenha] = useState("");
  const [confirmacao, setConfirmacao] = useState("");
  const [mostrar, setMostrar] = useState(false);
  const [termos, setTermos] = useState(false);
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [concluido, setConcluido] = useState(false);

  useEffect(() => {
    consultarConvite(token)
      .then((dados) => {
        if (dados.tipo !== contexto) setInvalido(true);
        else setConvite({ nome: dados.nome, email: dados.email });
      })
      .catch(() => setInvalido(true))
      .finally(() => setCarregando(false));
  }, [contexto, token]);

  async function enviar(evento: FormEvent) {
    evento.preventDefault(); setErro("");
    if (senha.length < 15) { setErro("Use pelo menos 15 caracteres na senha."); return; }
    if (senha !== confirmacao) { setErro("As senhas não coincidem."); return; }
    if (!termos) { setErro("Aceite os Termos de Uso para continuar."); return; }
    setEnviando(true);
    try { await aceitarConvite(token, senha, termos); setConcluido(true); }
    catch { setErro("Este convite expirou ou já foi utilizado. Solicite um novo convite."); }
    finally { setEnviando(false); }
  }

  if (carregando) return <p role="status" className="flex items-center justify-center gap-2 py-16 text-sm text-fg-muted"><LoaderCircle className="h-4 w-4 animate-spin" /> Verificando convite…</p>;
  if (invalido) return <div><h1 className="text-2xl font-semibold text-fg">Este convite não é mais válido.</h1><p className="mt-3 text-sm text-fg-muted">Peça ao responsável pelo acesso para enviar um novo convite.</p><Link href={`/${contexto}/login`} className="mt-6 inline-block font-medium text-primary hover:underline">Voltar ao login</Link></div>;
  if (concluido) return <div className="text-center"><CheckCircle2 className="mx-auto h-12 w-12 text-success" /><h1 className="mt-5 text-2xl font-semibold text-fg">Seu acesso está pronto.</h1><p className="mt-2 text-sm text-fg-muted">Entre com seu e-mail e a senha que você acabou de criar.</p><Link href={`/${contexto}/login`} className="mt-7 inline-flex h-11 w-full items-center justify-center rounded-lg bg-primary font-medium text-primary-fg hover:bg-primary-hover">Acessar {contexto === "portal" ? "Portal do Cliente" : "Área Administrativa"}</Link></div>;

  return (
    <div>
      <p className="text-sm font-semibold text-primary">Primeiro acesso</p>
      <h1 className="mt-2 text-2xl font-semibold text-fg">Olá, {convite?.nome}</h1>
      <p className="mt-2 text-sm text-fg-muted">Confirme os dados e crie sua senha para acessar <strong>{convite?.email}</strong>.</p>
      <form onSubmit={enviar} className="mt-7 space-y-4" noValidate>
        <Field label="Criar senha" obrigatorio hint="Use 15 ou mais caracteres; espaços são permitidos.">
          <div className="relative"><Input type={mostrar ? "text" : "password"} autoComplete="new-password" value={senha} onChange={(e) => setSenha(e.target.value)} className="pr-11" /><IconButton icon={mostrar ? EyeOff : Eye} label={mostrar ? "Ocultar senha" : "Mostrar senha"} onClick={() => setMostrar(!mostrar)} className="absolute right-1 top-1/2 -translate-y-1/2" /></div>
        </Field>
        <Field label="Confirmar senha" obrigatorio><Input type={mostrar ? "text" : "password"} autoComplete="new-password" value={confirmacao} onChange={(e) => setConfirmacao(e.target.value)} /></Field>
        <Checkbox checked={termos} onChange={setTermos} label={<>Li e concordo com os <Link href="/termos" target="_blank" rel="noreferrer" className="font-medium text-primary hover:underline">Termos de Uso</Link> e a <Link href="/privacidade" target="_blank" rel="noreferrer" className="font-medium text-primary hover:underline">Política de Privacidade</Link>.</>} />
        {erro && <Alert tone="danger">{erro}</Alert>}
        <Button type="submit" block size="lg" loading={enviando}>Criar acesso</Button>
      </form>
    </div>
  );
}
