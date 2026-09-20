"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { CheckCircle2, MailCheck } from "lucide-react";
import { Alert, Button, Field, Input, LoadingState } from "@/components/ds";
import { AuthShell } from "@/features/auth/components/auth-shell";
import { reenviarVerificacao, verificarEmail } from "@/features/auth/api";

export default function VerifyEmailPage() {
  return <AuthShell contexto="portal"><Suspense><VerifyEmail /></Suspense></AuthShell>;
}

function VerifyEmail() {
  const token = useSearchParams().get("token") ?? "";
  const [estado, setEstado] = useState<"idle" | "loading" | "success" | "error">(token ? "loading" : "idle");
  const [email, setEmail] = useState("");
  const [mensagem, setMensagem] = useState("");
  useEffect(() => { if (token) verificarEmail(token).then((r) => { setMensagem(r.detail); setEstado("success"); }).catch(() => setEstado("error")); }, [token]);
  if (estado === "loading") return <LoadingState label="Confirmando seu e-mail…" />;
  if (estado === "success") return <div className="text-center"><CheckCircle2 className="mx-auto h-12 w-12 text-success" /><h1 className="mt-5 text-2xl font-semibold text-fg">{mensagem}</h1><Link href="/portal/login" className="mt-7 inline-flex h-11 w-full items-center justify-center rounded-lg bg-primary font-medium text-primary-fg">Acessar Portal do Cliente</Link></div>;
  return <div><MailCheck className="h-11 w-11 text-primary" /><h1 className="mt-5 text-2xl font-semibold text-fg">Confirme seu e-mail</h1><p className="mt-3 text-sm leading-relaxed text-fg-muted">{estado === "error" ? "Este link não é mais válido. Solicite uma nova confirmação." : "Use o link seguro enviado para o seu e-mail."}</p><div className="mt-6 space-y-4"><Field label="E-mail"><Input type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} /></Field><Button block disabled={!email.includes("@")} onClick={() => reenviarVerificacao(email).then((r) => setMensagem(r.detail))}>Reenviar confirmação</Button>{mensagem && <Alert tone="info">{mensagem}</Alert>}<Link href="/portal/login" className="block text-center text-sm font-medium text-primary hover:underline">Voltar ao login</Link></div></div>;
}
