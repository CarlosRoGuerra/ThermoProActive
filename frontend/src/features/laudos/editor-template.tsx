"use client";

import { useState } from "react";
import { Alert, Button, Field, Input, Modal, Select, Textarea } from "@/components/ds";
import { api } from "@/lib/api";
import { useMutacao } from "@/lib/recurso";
import type { ConfiguracaoTemplateLaudo, Laudo, TemplateLaudo } from "@/lib/types";

export const CONFIGURACAO_PADRAO: ConfiguracaoTemplateLaudo = {
  titulo_documento: "Laudo técnico", rodape: "",
  secoes: ["capa", "diagnostico", "recomendacoes", "conclusao", "evidencias", "comparativos"],
};

/** Personalização por dados: texto e seções conhecidas, sem código executável. */
export function EditorTemplate({ template, laudo, onFechar, onSalvo }: {
  template?: TemplateLaudo; laudo: Laudo; onFechar: () => void; onSalvo: (template: TemplateLaudo) => void;
}) {
  const [nome, setNome] = useState(template?.nome ?? "");
  const [cliente, setCliente] = useState(template?.cliente ? String(template.cliente) : "");
  const [tipo, setTipo] = useState(template?.tipo_analise ?? "");
  const [config, setConfig] = useState(template?.configuracao ?? CONFIGURACAO_PADRAO);
  const [erroNome, setErroNome] = useState("");
  const mutacao = useMutacao("template de laudo");

  async function salvar() {
    if (!nome.trim()) { setErroNome("Informe um nome para identificar o template."); return; }
    if (!config.titulo_documento.trim()) return;
    const resposta = await mutacao.executar(() => api<TemplateLaudo>(
      template ? `/templates-laudo/${template.id}/` : "/templates-laudo/",
      { method: template ? "PATCH" : "POST", body: {
        nome: nome.trim(), cliente: cliente ? Number(cliente) : null, tipo_analise: tipo,
        configuracao: config, ativo: template?.ativo ?? true,
      } },
    ));
    if (resposta.ok) onSalvo(resposta.dados);
  }

  return <Modal aberto onFechar={onFechar} title={template ? "Editar template" : "Novo template"}
    description="Personalize os textos nos espaços existentes. A sequência e o desenho das seções são preservados."
    tamanho="lg" footer={<><Button variant="secondary" onClick={onFechar} disabled={mutacao.enviando}>Cancelar</Button>
      <Button onClick={salvar} loading={mutacao.enviando} disabled={!config.titulo_documento.trim()}>Salvar template</Button></>}>
    <div className="space-y-4">
      {mutacao.falha && <Alert tone="danger" title={mutacao.falha.titulo}>{mutacao.falha.descricao}</Alert>}
      <Field label="Nome do template" obrigatorio erro={erroNome}><Input autoFocus value={nome} maxLength={120} onChange={(e) => { setNome(e.target.value); setErroNome(""); }} /></Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Aplicação por cliente"><Select value={cliente} onChange={(e) => setCliente(e.target.value)}>
          <option value="">Todos os clientes</option>
          {laudo.cliente_id && <option value={laudo.cliente_id}>{laudo.cliente_nome}</option>}
        </Select></Field>
        <Field label="Aplicação por tecnologia"><Select value={tipo} onChange={(e) => setTipo(e.target.value)}>
          <option value="">Todas as tecnologias</option>
          {laudo.tipo_analise && <option value={laudo.tipo_analise}>{laudo.tipo_analise.replaceAll("_", " ")}</option>}
        </Select></Field>
      </div>
      <Field label="Título do documento" obrigatorio><Input value={config.titulo_documento} maxLength={200} onChange={(e) => setConfig({ ...config, titulo_documento: e.target.value })} /></Field>
      <Field label="Rodapé" hint={laudo.relatorio_origem ? "O relatório modular preserva o timbrado original e não possui espaço para rodapé personalizado." : "Texto simples, até 100 caracteres, no espaço de rodapé existente."}><Textarea disabled={!!laudo.relatorio_origem} value={config.rodape} maxLength={100} onChange={(e) => setConfig({ ...config, rodape: e.target.value })} /></Field>
      <p className="text-sm text-fg-muted">A identificação, o diagnóstico, as recomendações, a conclusão, as evidências e os comparativos mantêm a ordem do documento original.</p>
      <section aria-label="Prévia do template" className="rounded border border-border bg-surface-muted p-4">
        <h3 className="font-semibold text-fg">{config.titulo_documento || "Título do documento"}</h3>
        <p className="my-3 text-sm text-fg-muted">Identificação · diagnóstico · recomendações · conclusão
          {config.secoes.includes("evidencias") ? " · evidências" : ""}{config.secoes.includes("comparativos") ? " · comparativos" : ""}</p>
        {config.rodape && <p className="whitespace-pre-wrap border-t border-border pt-3 text-xs text-fg-muted">{config.rodape}</p>}
      </section>
    </div>
  </Modal>;
}
