"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Paginated } from "@/lib/types";
import { Button, Field, Select } from "@/components/ds";

/**
 * Sugestões técnicas assistidas (Anexo I 2.4.2.4). Nunca aplica sozinho: o analista
 * escolhe aceitar, editar ou rejeitar. A escolha só vai ao achado quando a análise
 * for salva (o formulário pai faz o PATCH).
 */

type Sugestao = {
  origem: "REGRA" | "HISTORICO";
  recomendacao: { id: number; nome: string };
  regra: { id: number; nome: string; validacao: string } | null;
  contagem: number | null;
  total: number | null;
  justificativa: string;
  ja_selecionada: boolean;
};

type Resposta = { sugestoes: Sugestao[]; motivo: string };
type CatOpt = { id: number; nome: string };

const MOTIVO: Record<string, string> = {
  anomalia_nao_classificada: "Classifique a anomalia e salve para receber sugestões.",
  sem_condicao_classificada_e_sem_historico: "Sem medição classificada do equipamento e sem histórico comparável.",
  sem_regra_nem_historico: "Nenhuma regra cadastrada se aplica e não há histórico comparável deste cliente.",
};

export function SugestoesAchado({
  achadoId,
  onAplicar,
}: {
  achadoId: number;
  /** Leva a recomendação escolhida ao formulário; o analista salva a análise depois. */
  onAplicar: (recomendacaoId: number) => void;
}) {
  const [dados, setDados] = useState<Resposta | null>(null);
  const [todas, setTodas] = useState<CatOpt[]>([]);
  const [editando, setEditando] = useState<string | null>(null);
  const [alternativa, setAlternativa] = useState("");
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    api<Resposta>(`/preditiva/sugestoes/?achado=${achadoId}`)
      .then(setDados)
      .catch(() => setErro("Não foi possível carregar as sugestões."));
    api<Paginated<CatOpt>>("/tipos-recomendacao/?page_size=500")
      .then((d) => setTodas(d.results))
      .catch(() => setTodas([]));
  }, [achadoId]);

  async function decidir(s: Sugestao, decisao: "ACEITA" | "EDITADA" | "REJEITADA", finalId?: number) {
    setEnviando(true);
    setErro("");
    try {
      await api("/preditiva/aceitacoes-sugestao/", {
        method: "POST",
        body: {
          achado: achadoId,
          recomendacao_sugerida: s.recomendacao.id,
          origem: s.origem,
          decisao,
          recomendacao_final: decisao === "REJEITADA" ? null : finalId ?? s.recomendacao.id,
          justificativa: "",
        },
      });
      if (decisao !== "REJEITADA") onAplicar(finalId ?? s.recomendacao.id);
      setEditando(null);
    } catch {
      setErro("Não foi possível registrar a decisão. Recarregue as sugestões.");
    } finally {
      setEnviando(false);
    }
  }

  if (erro && !dados) return <p className="text-sm text-danger-fg">{erro}</p>;
  if (!dados) return null;

  return (
    <div className="space-y-3 rounded-lg border border-border p-4">
      <div>
        <p className="text-sm font-semibold text-fg">Sugestões técnicas</p>
        <p className="text-xs text-fg-muted">
          Orientação para revisão. Só entra no achado se você aceitar e salvar a análise.
        </p>
      </div>
      {dados.sugestoes.length === 0 && (
        <p className="text-sm text-fg-muted">{MOTIVO[dados.motivo] ?? "Sem sugestão para este achado."}</p>
      )}
      {dados.sugestoes.map((s) => {
        const chave = `${s.origem}-${s.recomendacao.id}`;
        return (
          <div key={chave} className="space-y-2 border-t border-border pt-3 first:border-t-0 first:pt-0">
            <p className="text-sm">
              <span className="font-medium">{s.recomendacao.nome}</span>{" "}
              <span className="text-xs text-fg-muted">
                ({s.origem === "REGRA" ? `regra: ${s.regra?.nome}` : `histórico: ${s.contagem} de ${s.total}`})
              </span>
            </p>
            <p className="text-xs text-fg-muted">{s.justificativa}</p>
            {editando === chave ? (
              <div className="flex flex-wrap items-end gap-2">
                <Field label="Recomendação final">
                  <Select value={alternativa} onChange={(e) => setAlternativa(e.target.value)}>
                    <option value="">— selecione —</option>
                    {todas.map((t) => (
                      <option key={t.id} value={t.id}>{t.nome}</option>
                    ))}
                  </Select>
                </Field>
                <Button
                  variant="primary"
                  size="sm"
                  disabled={!alternativa || Number(alternativa) === s.recomendacao.id || enviando}
                  onClick={() => decidir(s, "EDITADA", Number(alternativa))}
                >
                  Confirmar ajuste
                </Button>
                <Button variant="ghost" size="sm" onClick={() => setEditando(null)}>Cancelar</Button>
              </div>
            ) : (
              <div className="flex flex-wrap gap-2">
                <Button size="sm" disabled={enviando || s.ja_selecionada} onClick={() => decidir(s, "ACEITA")}>
                  {s.ja_selecionada ? "Já selecionada" : "Aceitar"}
                </Button>
                <Button variant="secondary" size="sm" disabled={enviando} onClick={() => { setAlternativa(""); setEditando(chave); }}>
                  Editar
                </Button>
                <Button variant="ghost" size="sm" disabled={enviando} onClick={() => decidir(s, "REJEITADA")}>
                  Rejeitar
                </Button>
              </div>
            )}
          </div>
        );
      })}
      {erro && <p className="text-sm text-danger-fg">{erro}</p>}
    </div>
  );
}
