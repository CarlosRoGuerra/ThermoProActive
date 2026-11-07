"use client";

// Consulta da trilha de auditoria (Anexo I 3.1.22). Só Master interno — o backend recusa
// os demais (IsMaster em /api/auditoria/); o menu só mostra para quem tem `auditoria:ver`.

import { useState } from "react";
import { Alert, Badge, Card, DataTable, PageBody, PageHeader, Select, type Coluna } from "@/components/ds";
import { useLista } from "@/lib/recurso";
import { dataHora } from "@/lib/format";

type Registro = {
  id: number;
  criado_em: string;
  usuario: string | null;
  usuario_email: string;
  ip: string;
  metodo: string;
  caminho: string;
  acao: "CRIAR" | "ALTERAR" | "EXCLUIR";
  modelo: string;
  objeto_id: string;
  alteracoes: Record<string, [unknown, unknown] | unknown>;
};

const ROTULO_ACAO: Record<Registro["acao"], string> = {
  CRIAR: "Criação",
  ALTERAR: "Alteração",
  EXCLUIR: "Exclusão",
};

const TOM_ACAO: Record<Registro["acao"], "success" | "warning" | "danger"> = {
  CRIAR: "success",
  ALTERAR: "warning",
  EXCLUIR: "danger",
};

function resumoAlteracoes(alteracoes: Registro["alteracoes"]): string {
  const campos = Object.keys(alteracoes ?? {});
  if (campos.length === 0) return "—";
  return campos.slice(0, 4).join(", ") + (campos.length > 4 ? ` (+${campos.length - 4})` : "");
}

export function TelaAuditoria() {
  const [acao, setAcao] = useState("");
  const [modelo, setModelo] = useState("");
  const params = new URLSearchParams({ page_size: "200" });
  if (acao) params.set("acao", acao);
  if (modelo) params.set("modelo", modelo);
  const { itens, falha, carregando, recarregar } = useLista<Registro>(
    `/auditoria/?${params.toString()}`,
    "trilha de auditoria",
  );

  const colunas: Coluna<Registro>[] = [
    { chave: "quando", header: "Quando", celula: (r) => dataHora(r.criado_em), valor: (r) => r.criado_em },
    {
      chave: "quem",
      header: "Quem",
      celula: (r) => r.usuario_email || "Sistema",
      valor: (r) => r.usuario_email,
    },
    {
      chave: "acao",
      header: "Ação",
      celula: (r) => <Badge tone={TOM_ACAO[r.acao]}>{ROTULO_ACAO[r.acao]}</Badge>,
      valor: (r) => r.acao,
    },
    { chave: "modelo", header: "Modelo", celula: (r) => r.modelo, valor: (r) => r.modelo },
    { chave: "objeto", header: "Id", celula: (r) => r.objeto_id, valor: (r) => r.objeto_id },
    { chave: "campos", header: "Campos alterados", celula: (r) => resumoAlteracoes(r.alteracoes) },
    { chave: "ip", header: "IP", celula: (r) => r.ip || "—", valor: (r) => r.ip },
    { chave: "rota", header: "Rota", celula: (r) => `${r.metodo} ${r.caminho}`, valor: (r) => r.caminho },
  ];

  return (
    <PageBody>
      <PageHeader
        title="Auditoria"
        description="Quem criou, alterou ou excluiu dados de negócio, quando e de onde. Senhas e dados pessoais sensíveis não aparecem."
      />
      <Alert tone="info" title="Somente consulta">
        A trilha é append-only. Retenção configurada no servidor (AUDITORIA_RETENCAO_DIAS).
      </Alert>
      <Card>
        <div className="mb-4 grid gap-3 sm:grid-cols-2">
          <Select
            aria-label="Filtrar por ação"
            value={acao}
            onChange={(e) => setAcao(e.target.value)}
          >
            <option value="">Todas as ações</option>
            <option value="CRIAR">Criação</option>
            <option value="ALTERAR">Alteração</option>
            <option value="EXCLUIR">Exclusão</option>
          </Select>
          <Select
            aria-label="Filtrar por modelo"
            value={modelo}
            onChange={(e) => setModelo(e.target.value)}
          >
            <option value="">Todos os modelos</option>
            <option value="cadastros.Cliente">Cliente</option>
            <option value="cadastros.Equipamento">Equipamento</option>
            <option value="coletas.Inspecao">Inspeção</option>
            <option value="laudos.Laudo">Laudo</option>
            <option value="accounts.User">Usuário</option>
          </Select>
        </div>
        <DataTable
          itens={itens}
          colunas={colunas}
          getId={(r) => r.id}
          carregando={carregando}
          falha={falha}
          onRetry={recarregar}
          porPagina={25}
          vazio={"Nada registrado com esses filtros."}
        />
      </Card>
    </PageBody>
  );
}
