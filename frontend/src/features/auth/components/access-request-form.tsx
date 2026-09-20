"use client";

import { FormEvent, useMemo, useState } from "react";
import Link from "next/link";
import { Check, ChevronLeft, ChevronRight, Send } from "lucide-react";
import { Alert, Button, Checkbox, Field, Input, Select } from "@/components/ds";
import { ApiError } from "@/lib/api";
import { enviarSolicitacaoAcesso, type PedidoAcesso } from "../api";

const PASSOS = ["Conta", "Empresa", "Responsável", "Concluir"];
const INICIAL: PedidoAcesso = {
  nome: "", email: "", telefone: "", razao_social: "", nome_fantasia: "", cnpj: "",
  segmento: "", telefone_empresa: "", email_empresa: "", quantidade_equipamentos: null,
  cargo: "", aceitou_termos: false, aceita_marketing: false,
};

function soNumeros(valor: string) { return valor.replace(/\D/g, ""); }
function formatarCnpj(valor: string) {
  return soNumeros(valor).slice(0, 14).replace(/^(\d{2})(\d)/, "$1.$2").replace(/^(\d{2})\.(\d{3})(\d)/, "$1.$2.$3").replace(/\.(\d{3})(\d)/, ".$1/$2").replace(/(\d{4})(\d)/, "$1-$2");
}

export function AccessRequestForm() {
  const [passo, setPasso] = useState(0);
  const [dados, setDados] = useState(INICIAL);
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [concluido, setConcluido] = useState("");
  const alterar = <K extends keyof PedidoAcesso>(chave: K, valor: PedidoAcesso[K]) => setDados((atual) => ({ ...atual, [chave]: valor }));

  const valido = useMemo(() => {
    if (passo === 0) return dados.nome.trim().length >= 3 && dados.email.includes("@") && soNumeros(dados.telefone).length >= 10;
    if (passo === 1) return dados.razao_social.trim().length >= 3 && soNumeros(dados.cnpj).length === 14;
    if (passo === 2) return dados.cargo.trim().length >= 2;
    return dados.aceitou_termos;
  }, [passo, dados]);

  function avancar() {
    if (!valido) { setErro("Revise os campos obrigatórios antes de continuar."); return; }
    setErro(""); setPasso((atual) => Math.min(3, atual + 1));
  }

  async function enviar(evento: FormEvent) {
    evento.preventDefault();
    if (!valido) { setErro("Você precisa aceitar os Termos de Uso."); return; }
    setEnviando(true); setErro("");
    try {
      const resposta = await enviarSolicitacaoAcesso(dados);
      setConcluido(resposta.detail);
    } catch (falha) {
      setErro(falha instanceof ApiError ? falha.message : "Não foi possível enviar a solicitação.");
    } finally { setEnviando(false); }
  }

  if (concluido) return (
    <div className="text-center">
      <span className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-success-subtle text-success-fg"><Check className="h-7 w-7" /></span>
      <h1 className="mt-5 text-2xl font-semibold text-fg">Solicitação recebida</h1>
      <p className="mt-3 text-sm leading-relaxed text-fg-muted">{concluido}</p>
      <Link href="/portal/login" className="mt-7 inline-flex h-11 w-full items-center justify-center rounded-lg bg-primary px-5 font-medium text-primary-fg hover:bg-primary-hover">Voltar ao Portal do Cliente</Link>
    </div>
  );

  return (
    <div>
      <p className="text-sm font-semibold text-primary">Solicitar acesso</p>
      <h1 className="mt-2 text-2xl font-semibold text-fg">Conte um pouco sobre sua empresa</h1>
      <p className="mt-2 text-sm text-fg-muted">A criação de contas passa por análise para proteger os dados da sua organização.</p>

      <ol className="mt-7 grid grid-cols-4 gap-2" aria-label="Progresso do cadastro">
        {PASSOS.map((nome, indice) => (
          <li key={nome} aria-current={indice === passo ? "step" : undefined}>
            <span className={`block h-1 rounded-full ${indice <= passo ? "bg-primary" : "bg-border"}`} />
            <span className={`mt-2 block text-2xs ${indice === passo ? "font-semibold text-fg" : "text-fg-subtle"}`}>{indice + 1} {nome}</span>
          </li>
        ))}
      </ol>

      <form onSubmit={enviar} className="mt-7 space-y-4" noValidate>
        {passo === 0 && <>
          <Field label="Nome completo" obrigatorio><Input autoComplete="name" autoFocus value={dados.nome} onChange={(e) => alterar("nome", e.target.value)} /></Field>
          <Field label="E-mail profissional" obrigatorio><Input type="email" autoComplete="email" value={dados.email} onChange={(e) => alterar("email", e.target.value)} /></Field>
          <Field label="Telefone / celular" obrigatorio><Input type="tel" autoComplete="tel" inputMode="tel" value={dados.telefone} onChange={(e) => alterar("telefone", e.target.value)} /></Field>
          <Alert tone="info">Sua senha será criada somente depois que a solicitação for aprovada. Assim, não coletamos credenciais antes da hora.</Alert>
        </>}
        {passo === 1 && <>
          <Field label="Razão social" obrigatorio><Input autoFocus value={dados.razao_social} onChange={(e) => alterar("razao_social", e.target.value)} /></Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Nome fantasia"><Input value={dados.nome_fantasia} onChange={(e) => alterar("nome_fantasia", e.target.value)} /></Field>
            <Field label="CNPJ" obrigatorio><Input inputMode="numeric" value={dados.cnpj} onChange={(e) => alterar("cnpj", formatarCnpj(e.target.value))} placeholder="00.000.000/0000-00" /></Field>
          </div>
          <Field label="Segmento de atuação"><Select value={dados.segmento} onChange={(e) => alterar("segmento", e.target.value)}><option value="">Selecione</option><option>Indústria</option><option>Alimentos e bebidas</option><option>Papel e celulose</option><option>Logística</option><option>Outro</option></Select></Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Telefone empresarial"><Input type="tel" value={dados.telefone_empresa} onChange={(e) => alterar("telefone_empresa", e.target.value)} /></Field>
            <Field label="E-mail empresarial"><Input type="email" value={dados.email_empresa} onChange={(e) => alterar("email_empresa", e.target.value)} /></Field>
          </div>
        </>}
        {passo === 2 && <>
          <Alert tone="info">Usaremos os dados já informados para identificar o responsável pela solicitação.</Alert>
          <Field label="Responsável"><Input value={dados.nome} disabled /></Field>
          <Field label="Cargo / função" obrigatorio><Input autoFocus autoComplete="organization-title" value={dados.cargo} onChange={(e) => alterar("cargo", e.target.value)} /></Field>
          <Field label="Quantidade aproximada de equipamentos"><Input type="number" min={1} value={dados.quantidade_equipamentos ?? ""} onChange={(e) => alterar("quantidade_equipamentos", e.target.value ? Number(e.target.value) : null)} /></Field>
        </>}
        {passo === 3 && <>
          <div className="rounded-xl border border-border bg-surface-muted p-4 text-sm text-fg-muted">
            <p className="font-semibold text-fg">{dados.razao_social}</p><p className="mt-1">{dados.nome} · {dados.email}</p><p className="mt-1">CNPJ {dados.cnpj}</p>
          </div>
          <Checkbox checked={dados.aceitou_termos} onChange={(v) => alterar("aceitou_termos", v)} label={<>Li e concordo com os <Link href="/termos" target="_blank" rel="noreferrer" className="font-medium text-primary hover:underline">Termos de Uso</Link> e a <Link href="/privacidade" target="_blank" rel="noreferrer" className="font-medium text-primary hover:underline">Política de Privacidade</Link>.</>} />
          <Checkbox checked={dados.aceita_marketing} onChange={(v) => alterar("aceita_marketing", v)} label="Quero receber novidades e comunicações comerciais." hint="Opcional. Você pode cancelar quando quiser." />
        </>}
        {erro && <Alert tone="danger">{erro}</Alert>}
        <div className="flex items-center justify-between gap-3 pt-2">
          {passo > 0 ? <Button variant="secondary" icon={ChevronLeft} onClick={() => { setPasso(passo - 1); setErro(""); }}>Voltar</Button> : <Link href="/portal/login" className="text-sm font-medium text-primary hover:underline">Voltar ao login</Link>}
          {passo < 3 ? <Button iconRight={ChevronRight} onClick={avancar}>Continuar</Button> : <Button type="submit" icon={Send} loading={enviando}>Enviar solicitação</Button>}
        </div>
      </form>
    </div>
  );
}
