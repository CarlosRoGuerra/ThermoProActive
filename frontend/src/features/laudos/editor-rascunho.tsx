"use client";

import { useState } from "react";
import { FilePlus, Pencil, Save } from "lucide-react";
import { Alert, Button, Card, Field, Input, Select, Textarea } from "@/components/ds";
import { api } from "@/lib/api";
import { useLista, useMutacao } from "@/lib/recurso";
import type { Laudo, TemplateLaudo, User } from "@/lib/types";
import { EditorTemplate } from "./editor-template";

type Conteudo = Pick<Laudo, "titulo" | "diagnostico" | "recomendacoes" | "conclusao" | "responsavel"> & { template: number | null };

export function EditorRascunho({ laudo, user, onPrevia, onCancelar, onSalvo }: {
  laudo: Laudo; user: User; onPrevia: (conteudo: Partial<Laudo>, template?: TemplateLaudo) => void;
  onCancelar: () => void; onSalvo: (laudo: Laudo) => void;
}) {
  const [form, setForm] = useState<Conteudo>({
    titulo: laudo.titulo, diagnostico: laudo.diagnostico, recomendacoes: laudo.recomendacoes,
    conclusao: laudo.conclusao,
    responsavel: laudo.responsavel, template: laudo.template ?? null,
  });
  const [templateEditando, setTemplateEditando] = useState<TemplateLaudo | "novo" | null>(null);
  const [erroTitulo, setErroTitulo] = useState("");
  const templates = useLista<TemplateLaudo>("/templates-laudo/?page_size=200", "templates de laudo");
  const usuarios = useLista<User>(user.is_master ? "/usuarios/?is_active=true&page_size=200" : null, "responsáveis técnicos");
  const mutacao = useMutacao("edição do rascunho");
  const aplicaveis = templates.itens.filter((t) => t.ativo && (!t.cliente || t.cliente === laudo.cliente_id)
    && (!t.tipo_analise || t.tipo_analise === laudo.tipo_analise)
    && !(laudo.relatorio_origem && t.configuracao.rodape?.trim()));
  const escolhido = templates.itens.find((t) => t.id === form.template);

  function mudar<K extends keyof Conteudo>(campo: K, valor: Conteudo[K]) {
    const proximo = { ...form, [campo]: valor };
    setForm(proximo);
    onPrevia(proximo, templates.itens.find((t) => t.id === proximo.template));
  }

  async function salvar() {
    if (!form.titulo.trim()) { setErroTitulo("Informe o título do laudo."); return; }
    const resposta = await mutacao.executar(() => api<Laudo>(`/laudos/${laudo.id}/`, {
      method: "PATCH", body: form,
    }));
    if (resposta.ok) onSalvo(resposta.dados);
  }

  return <Card className="no-print p-5 sm:p-6">
    <div className="mb-4"><h2 className="font-semibold text-fg">Editar rascunho</h2>
      <p className="mt-1 text-sm text-fg-muted">A prévia abaixo acompanha sua edição. Salve as alterações antes de emitir.</p></div>
    <div className="space-y-4">
      {mutacao.falha && <Alert tone="danger" title={mutacao.falha.titulo}>{mutacao.falha.descricao}</Alert>}
      <Field label="Título do laudo" obrigatorio erro={erroTitulo}><Input value={form.titulo} maxLength={200} onChange={(e) => { mudar("titulo", e.target.value); setErroTitulo(""); }} /></Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <div><p className="label">Criticidade da análise de origem</p><p className="text-sm text-fg">{laudo.criticidade_geral || "Pendente de avaliação técnica"}</p></div>
        <Field label="Responsável técnico">
          {user.is_master ? <Select value={form.responsavel} onChange={(e) => mudar("responsavel", Number(e.target.value))}>
            {!usuarios.itens.some((u) => u.id === form.responsavel) && <option value={form.responsavel}>{laudo.responsavel_nome}</option>}
            {usuarios.itens.filter((u) => u.is_interno && u.is_active).map((u) => <option key={u.id} value={u.id}>{u.nome}{u.conselho_classe ? ` — ${u.conselho_classe}` : " — sem conselho cadastrado"}</option>)}
          </Select> : <div className="space-y-2"><p className="text-sm text-fg">{form.responsavel === user.id ? user.nome : laudo.responsavel_nome}</p>
            {form.responsavel !== user.id && <Button variant="secondary" size="sm" onClick={() => mudar("responsavel", user.id)}>Definir-me responsável</Button>}
          </div>}
        </Field>
      </div>
      <Field label="Template do documento" hint="Templates são aplicados conforme cliente e tecnologia.">
        <Select value={form.template ?? ""} onChange={(e) => mudar("template", e.target.value ? Number(e.target.value) : null)}>
          <option value="">Padrão do sistema</option>
          {aplicaveis.map((t) => <option key={t.id} value={t.id}>{t.nome} · versão {t.versao}</option>)}
        </Select>
      </Field>
      {templates.falha && <Alert tone="warning" title="Templates indisponíveis">{templates.falha.descricao}<Button variant="link" onClick={templates.recarregar}>Tentar novamente</Button></Alert>}
      {user.is_master && <div className="flex flex-wrap gap-2">
        <Button variant="secondary" size="sm" icon={FilePlus} onClick={() => setTemplateEditando("novo")}>Novo template</Button>
        {escolhido && <Button variant="ghost" size="sm" icon={Pencil} onClick={() => setTemplateEditando(escolhido)}>Editar template selecionado</Button>}
      </div>}
      <Field label="Diagnóstico técnico"><Textarea rows={5} value={form.diagnostico} onChange={(e) => mudar("diagnostico", e.target.value)} /></Field>
      <Field label="Recomendações"><Textarea rows={4} value={form.recomendacoes} onChange={(e) => mudar("recomendacoes", e.target.value)} /></Field>
      <Field label="Conclusão"><Textarea rows={4} value={form.conclusao} onChange={(e) => mudar("conclusao", e.target.value)} /></Field>
      <div className="flex flex-wrap justify-end gap-2 border-t border-border pt-4">
        <Button variant="secondary" onClick={onCancelar} disabled={mutacao.enviando}>Descartar alterações</Button>
        <Button icon={Save} onClick={salvar} loading={mutacao.enviando}>Salvar rascunho</Button>
      </div>
    </div>
    {templateEditando && <EditorTemplate template={templateEditando === "novo" ? undefined : templateEditando} laudo={laudo}
      onFechar={() => setTemplateEditando(null)} onSalvo={(t) => {
        setTemplateEditando(null); templates.recarregar(); setForm({ ...form, template: t.id });
        onPrevia({ ...form, template: t.id }, t);
      }} />}
  </Card>;
}
