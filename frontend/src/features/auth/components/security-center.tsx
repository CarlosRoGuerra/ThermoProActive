"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { Clock3, KeyRound, Laptop, LockKeyhole, ShieldCheck } from "lucide-react";
import { Alert, Button, Card, CardHeader, Field, Input, LoadingState } from "@/components/ds";
import {
  alterarSenha,
  encerrarOutrasSessoes,
  obterSeguranca,
  type ContextoAuth,
  type Evento,
  type ResumoSeguranca,
  type Sessao,
} from "../api";

export function SecurityCenter({ contexto }: { contexto: ContextoAuth }) {
  const [resumo, setResumo] = useState<ResumoSeguranca | null>(null);
  const [sessoes, setSessoes] = useState<Sessao[]>([]);
  const [eventos, setEventos] = useState<Evento[]>([]);
  const [erro, setErro] = useState("");
  const [mensagem, setMensagem] = useState("");
  const [atual, setAtual] = useState("");
  const [nova, setNova] = useState("");
  const [confirmacao, setConfirmacao] = useState("");
  const [salvando, setSalvando] = useState(false);

  function carregar() {
    obterSeguranca().then(([r, s, e]) => { setResumo(r); setSessoes(s); setEventos(e); }).catch(() => setErro("Não foi possível carregar a segurança da conta."));
  }
  useEffect(carregar, []);

  async function trocarSenha(evento: FormEvent) {
    evento.preventDefault(); setErro(""); setMensagem("");
    if (nova.length < 15) { setErro("A nova senha precisa ter pelo menos 15 caracteres."); return; }
    if (nova !== confirmacao) { setErro("As senhas não coincidem."); return; }
    setSalvando(true);
    try { const r = await alterarSenha(atual, nova); setMensagem(r.detail); setAtual(""); setNova(""); setConfirmacao(""); carregar(); }
    catch { setErro("Não foi possível alterar a senha. Confira a senha atual."); }
    finally { setSalvando(false); }
  }

  async function encerrar() {
    await encerrarOutrasSessoes(); setMensagem("As outras sessões foram encerradas."); carregar();
  }

  if (!resumo && !erro) return <LoadingState label="Carregando segurança da conta…" />;

  return (
    <div className="space-y-6">
      <div><p className="text-sm font-semibold text-primary">Conta e acesso</p><h1 className="mt-1 text-2xl font-semibold text-fg">Segurança</h1><p className="mt-2 text-sm text-fg-muted">Gerencie senha, segundo fator e dispositivos conectados.</p></div>
      {erro && <Alert tone="danger">{erro}</Alert>}{mensagem && <Alert tone="success">{mensagem}</Alert>}
      <div className="grid gap-5 xl:grid-cols-2">
        <Card>
          <CardHeader title="Alterar senha" description="A mudança encerra automaticamente as outras sessões." />
          <form onSubmit={trocarSenha} className="space-y-4 p-5 pt-0">
            <Field label="Senha atual" obrigatorio><Input type="password" autoComplete="current-password" value={atual} onChange={(e) => setAtual(e.target.value)} /></Field>
            <Field label="Nova senha" obrigatorio hint="Use pelo menos 15 caracteres."><Input type="password" autoComplete="new-password" value={nova} onChange={(e) => setNova(e.target.value)} /></Field>
            <Field label="Confirmar nova senha" obrigatorio><Input type="password" autoComplete="new-password" value={confirmacao} onChange={(e) => setConfirmacao(e.target.value)} /></Field>
            <Button type="submit" loading={salvando} icon={LockKeyhole}>Atualizar senha</Button>
          </form>
        </Card>
        <Card>
          <CardHeader title="Autenticação em dois fatores" description="Protege a conta mesmo se a senha for descoberta." />
          <div className="p-5 pt-0">
            <div className="flex items-center gap-3 rounded-xl bg-surface-muted p-4"><ShieldCheck className={`h-6 w-6 ${resumo?.mfa_ativo ? "text-success" : "text-fg-subtle"}`} /><div><p className="font-semibold text-fg">{resumo?.mfa_ativo ? "MFA ativado" : "MFA ainda não ativado"}</p><p className="text-xs text-fg-muted">Aplicativo autenticador compatível com TOTP.</p></div></div>
            {!resumo?.mfa_ativo && <Link href={`/${contexto}/mfa/setup`} className="mt-4 inline-flex h-10 items-center rounded-lg bg-primary px-4 text-sm font-medium text-primary-fg hover:bg-primary-hover"><KeyRound className="mr-2 h-4 w-4" />Configurar MFA</Link>}
          </div>
        </Card>
      </div>
      <Card>
        <CardHeader title="Sessões ativas" description={`${resumo?.sessoes_ativas ?? 0} dispositivo(s) conectado(s).`} actions={<Button variant="secondary" size="sm" onClick={encerrar}>Encerrar outras sessões</Button>} />
        <div className="divide-y divide-border px-5 pb-5">
          {sessoes.map((sessao) => <div key={sessao.id} className="flex items-start gap-3 py-4"><Laptop className="mt-0.5 h-5 w-5 text-fg-subtle" /><div className="min-w-0"><p className="truncate text-sm font-medium text-fg">{sessao.dispositivo}</p><p className="mt-1 text-xs text-fg-muted">Ativa desde {new Date(sessao.criado_em).toLocaleString("pt-BR")} {sessao.atual && <strong className="text-success-fg">· esta sessão</strong>}</p></div></div>)}
        </div>
      </Card>
      <Card>
        <CardHeader title="Atividade recente" description="Eventos de segurança da sua conta." />
        <div className="divide-y divide-border px-5 pb-5">
          {eventos.map((evento, indice) => <div key={`${evento.criado_em}-${indice}`} className="flex items-center gap-3 py-3 text-sm"><Clock3 className="h-4 w-4 text-fg-subtle" /><span className="flex-1 text-fg">{evento.evento.replaceAll("_", " ").toLocaleLowerCase("pt-BR")}</span><time className="text-xs text-fg-muted">{new Date(evento.criado_em).toLocaleString("pt-BR")}</time></div>)}
        </div>
      </Card>
    </div>
  );
}
