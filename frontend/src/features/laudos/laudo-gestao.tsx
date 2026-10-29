"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { CircleX, History, Pencil, ShieldCheck } from "lucide-react";
import { Alert, Badge, Button, Card, Field, Modal, Textarea, useToast } from "@/components/ds";
import { api } from "@/lib/api";
import { dataHora } from "@/lib/format";
import { usePermissoes } from "@/lib/permissions";
import { useMutacao, useRecurso } from "@/lib/recurso";
import type { EventoLaudo, Laudo, Paginated, TemplateLaudo } from "@/lib/types";
import { EditorRascunho } from "./editor-rascunho";
import { LaudoDocumento } from "./laudo-documento";
import { AnexosLaudo } from "./anexos-laudo";

function itens<T>(dados: T[] | Paginated<T> | null): T[] {
  return Array.isArray(dados) ? dados : dados?.results ?? [];
}

export function LaudoGestao({ laudoId }: { laudoId: string }) {
  const router = useRouter();
  const toast = useToast();
  const { user, interno } = usePermissoes();
  const recurso = useRecurso<Laudo>(`/laudos/${laudoId}/`, "laudo técnico");
  const versoes = useRecurso<Laudo[] | Paginated<Laudo>>(`/laudos/${laudoId}/versoes/`, "versões do laudo");
  const eventos = useRecurso<EventoLaudo[] | Paginated<EventoLaudo>>(`/laudos/${laudoId}/eventos/`, "histórico do laudo");
  const laudo = recurso.dados;
  const template = useRecurso<TemplateLaudo>(laudo?.status === "RASCUNHO" && laudo.template ? `/templates-laudo/${laudo.template}/` : null, "template do documento");
  const [editando, setEditando] = useState(false);
  const [previa, setPrevia] = useState<Partial<Laudo> | null>(null);
  const [templatePrevia, setTemplatePrevia] = useState<TemplateLaudo | undefined>(undefined);
  const [acao, setAcao] = useState<"emitir" | "revisar" | "cancelar" | null>(null);
  const [motivo, setMotivo] = useState("");
  const [erroMotivo, setErroMotivo] = useState("");
  const [revisaoDocumento, setRevisaoDocumento] = useState(0);
  const mutacao = useMutacao("operação do laudo");
  const rascunho = laudo?.status === "RASCUNHO";
  const responsavel = user?.id === laudo?.responsavel;
  const podeAprovar = interno && responsavel && !!user?.is_active && !!user.conselho_classe?.trim();
  const podeGerenciar = interno && (responsavel || user?.is_master);

  function abrirAcao(nova: "emitir" | "revisar" | "cancelar") {
    setMotivo(""); setErroMotivo(""); mutacao.limparFalha(); setAcao(nova);
  }

  function encerrarEdicao() { setEditando(false); setPrevia(null); setTemplatePrevia(undefined); }

  async function executarAcao() {
    if (!acao || !laudo) return;
    if (acao !== "emitir" && !motivo.trim()) { setErroMotivo("Informe o motivo para registrar esta decisão no histórico."); return; }
    const resultado = await mutacao.executar(() => api<Laudo>(`/laudos/${laudo.id}/${acao}/`, {
      method: "POST", body: acao === "emitir" ? {} : { motivo: motivo.trim() },
    }));
    if (!resultado.ok) return;
    const anteriorAcao = acao;
    setAcao(null);
    toast.sucesso(anteriorAcao === "emitir" ? "Laudo emitido" : anteriorAcao === "revisar" ? "Revisão aberta" : "Laudo cancelado");
    if (anteriorAcao === "revisar") { router.push(`/laudos/${resultado.dados.id}`); return; }
    recurso.definirDados(resultado.dados); versoes.recarregar(); eventos.recarregar();
    setRevisaoDocumento((n) => n + 1);
  }

  return <>
    <LaudoDocumento laudoId={laudoId} laudo={laudo ? { ...laudo, ...previa } : undefined}
      relatorioHref={laudo?.relatorio_origem ? `/relatorios-inspecao/${laudo.relatorio_origem}` : `/laudos/${laudoId}/relatorio`}
      templatePrevia={previa ? templatePrevia : template.dados ?? undefined} alteracoesNaoSalvas={!!previa}
      revisaoDocumento={revisaoDocumento}
      trilha={[{ label: "Laudos técnicos", href: "/laudos" }, { label: laudo?.numero ?? `#${laudoId}` }]}
      aviso={rascunho && !podeAprovar && interno ? <div className="no-print"><Alert tone="warning" title="Emissão pelo responsável técnico">
        {!responsavel ? `A emissão deve ser aprovada pela conta de ${laudo?.responsavel_nome}.` : "Complete o registro do Conselho de Classe no cadastro do responsável antes de emitir."}
      </Alert></div> : undefined}
      acoes={<>
        {rascunho && interno && !editando && <Button variant="secondary" icon={Pencil} onClick={() => setEditando(true)}>Editar rascunho</Button>}
        {rascunho && <Button icon={ShieldCheck} onClick={() => abrirAcao("emitir")} disabled={!podeAprovar || editando}>Emitir laudo</Button>}
        {laudo?.status === "EMITIDO" && podeGerenciar && <Button variant="secondary" icon={History} onClick={() => abrirAcao("revisar")}>Criar revisão</Button>}
        {laudo && laudo.status !== "CANCELADO" && podeGerenciar && <Button variant="ghost" icon={CircleX} onClick={() => abrirAcao("cancelar")} disabled={editando}>Cancelar laudo</Button>}
      </>}
      antesDocumento={editando && laudo && user ? <><EditorRascunho key={laudo.id} laudo={laudo} user={user}
        onPrevia={(conteudo, selecionado) => { setPrevia(conteudo); setTemplatePrevia(selecionado); }} onCancelar={encerrarEdicao}
        onSalvo={(salvo) => { recurso.definirDados(salvo); encerrarEdicao(); eventos.recarregar(); toast.sucesso("Rascunho salvo"); }} />
        <AnexosLaudo laudoId={laudo.id} onAlterado={() => { eventos.recarregar(); setRevisaoDocumento((n) => n + 1); }} /></> : undefined}
      depoisDocumento={laudo ? <div className="no-print grid gap-4 lg:grid-cols-2">
        <Card><h2 className="mb-3 font-semibold text-fg">Versões do documento</h2>
          {versoes.falha ? <Alert tone="warning" title="Versões indisponíveis">{versoes.falha.descricao}<Button variant="link" onClick={versoes.recarregar}>Tentar novamente</Button></Alert> :
            <ol className="space-y-3">{itens(versoes.dados).map((v) => <li key={v.id} className="flex flex-wrap items-center justify-between gap-2 border-b border-border pb-3 last:border-0">
              <div>{v.id === laudo.id ? <span className="font-semibold">Versão {v.versao} · atual nesta tela</span> : <Link className="font-semibold text-primary underline-offset-4 hover:underline" href={`/laudos/${v.id}`}>Versão {v.versao}</Link>}
                <p className="text-xs text-fg-muted">{v.numero}{v.data_emissao ? ` · ${dataHora(v.data_emissao)}` : ""}</p></div>
              <Badge tone={v.status === "EMITIDO" ? "success" : v.status === "CANCELADO" ? "danger" : "warning"}>{v.status_display}</Badge>
            </li>)}</ol>}
        </Card>
        <Card><h2 className="mb-3 font-semibold text-fg">Histórico de decisões</h2>
          {eventos.falha ? <Alert tone="warning" title="Histórico indisponível">{eventos.falha.descricao}<Button variant="link" onClick={eventos.recarregar}>Tentar novamente</Button></Alert> :
            <ol className="space-y-3">{itens(eventos.dados).map((e) => <li key={e.id} className="border-l-2 border-border pl-3">
              <p className="text-sm font-medium">{e.tipo_display || e.tipo.replaceAll("_", " ")}</p>
              <p className="text-xs text-fg-muted">{dataHora(e.criado_em)}{e.usuario_nome ? ` · ${e.usuario_nome}` : ""}</p>
              {e.motivo && <p className="mt-1 whitespace-pre-wrap text-sm text-fg-muted">{e.motivo}</p>}
            </li>)}</ol>}
        </Card>
      </div> : undefined} />
    <Modal aberto={!!acao} onFechar={() => { if (!mutacao.enviando) setAcao(null); }}
      title={acao === "emitir" ? "Emitir e aprovar este laudo?" : acao === "revisar" ? "Criar uma nova revisão?" : "Cancelar este laudo?"}
      footer={<><Button variant="secondary" disabled={mutacao.enviando} onClick={() => setAcao(null)}>Voltar</Button>
        <Button variant={acao === "cancelar" ? "destructive" : "primary"} loading={mutacao.enviando} onClick={executarAcao}>
          {acao === "emitir" ? "Emitir e aprovar" : acao === "revisar" ? "Abrir revisão" : "Confirmar cancelamento"}
        </Button></>}>
      <div className="space-y-4">
        {mutacao.falha && <Alert tone="danger" title={mutacao.falha.titulo}>{mutacao.falha.descricao}</Alert>}
        {acao === "emitir" ? <><p className="text-sm text-fg">O conteúdo desta versão será preservado e publicado para {laudo?.cliente_nome}. A aprovação será registrada como {user?.nome}, {user?.conselho_classe}.</p>
          <p className="text-sm text-fg-muted">Este mecanismo registra uma aprovação interna pela conta autenticada; não utiliza assinatura criptográfica nem certificado digital.</p></> : <>
          <p className="text-sm text-fg-muted">{acao === "revisar" ? "A versão emitida será preservada. As alterações serão feitas em um novo rascunho." : "O documento e o motivo permanecerão no histórico. O cancelamento não apaga os registros."}</p>
          <Field label="Motivo" obrigatorio erro={erroMotivo}><Textarea rows={4} value={motivo} onChange={(e) => { setMotivo(e.target.value); setErroMotivo(""); }} /></Field>
        </>}
      </div>
    </Modal>
  </>;
}
