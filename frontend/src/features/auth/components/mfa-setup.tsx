"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { CheckCircle2, Copy, KeyRound } from "lucide-react";
import { Alert, Button, Field, Input } from "@/components/ds";
import { confirmarMfa, iniciarMfa, type ContextoAuth } from "../api";

export function MfaSetup({ contexto }: { contexto: ContextoAuth }) {
  const [segredo, setSegredo] = useState("");
  const [codigo, setCodigo] = useState("");
  const [codigos, setCodigos] = useState<string[]>([]);
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);
  useEffect(() => { iniciarMfa().then((r) => setSegredo(r.secret)).catch(() => setErro("Não foi possível iniciar a configuração.")); }, []);
  async function confirmar(evento: FormEvent) { evento.preventDefault(); setEnviando(true); setErro(""); try { const r = await confirmarMfa(codigo); setCodigos(r.recovery_codes); } catch { setErro("Código inválido ou expirado. Confira o horário do dispositivo."); } finally { setEnviando(false); } }
  if (codigos.length) return <div><CheckCircle2 className="h-12 w-12 text-success" /><h1 className="mt-5 text-2xl font-semibold text-fg">MFA ativado</h1><p className="mt-2 text-sm text-fg-muted">Guarde estes códigos em local seguro. Cada um funciona uma única vez.</p><div className="mt-5 grid grid-cols-2 gap-2 rounded-xl bg-surface-muted p-4 font-mono text-sm text-fg">{codigos.map((c) => <span key={c}>{c}</span>)}</div><Link href={contexto === "portal" ? "/portal/minha-conta/seguranca" : "/admin/seguranca"} className="mt-6 inline-flex h-10 items-center rounded-lg bg-primary px-4 font-medium text-primary-fg">Concluir</Link></div>;
  return <div><KeyRound className="h-10 w-10 text-primary" /><h1 className="mt-5 text-2xl font-semibold text-fg">Configurar autenticação em dois fatores</h1><p className="mt-2 text-sm text-fg-muted">No aplicativo autenticador, adicione uma conta com a chave abaixo. Depois informe o código de seis dígitos.</p><div className="mt-5 flex items-center gap-2 rounded-xl border border-border bg-surface-muted p-4"><code className="min-w-0 flex-1 break-all text-sm font-semibold text-fg">{segredo || "Gerando chave…"}</code><Button variant="ghost" size="sm" icon={Copy} onClick={() => navigator.clipboard.writeText(segredo)}>Copiar</Button></div><form onSubmit={confirmar} className="mt-5 space-y-4"><Field label="Código de autenticação" obrigatorio><Input inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={codigo} onChange={(e) => setCodigo(e.target.value.replace(/\D/g, ""))} /></Field>{erro && <Alert tone="danger">{erro}</Alert>}<Button type="submit" block loading={enviando} disabled={codigo.length !== 6}>Ativar MFA</Button></form></div>;
}
