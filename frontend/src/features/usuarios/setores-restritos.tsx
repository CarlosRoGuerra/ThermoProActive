"use client";

// Restrição de usuário de cliente a setores do próprio cliente (Anexo I 2.1.1.6).
// Sem nenhum setor marcado o usuário vê o cliente inteiro; com algum marcado, só esses.
// Quem configura: Master interno (aba na edição do usuário) ou o Master do próprio cliente
// (Minha Equipe). O backend é a autoridade; a tela só reflete o que ele devolve.

import { useEffect, useState } from "react";
import { Alert, Button, Checkbox, useToast } from "@/components/ds";
import { api, ApiError } from "@/lib/api";
import type { Paginated } from "@/lib/types";

type SetorOpcao = { id: number; identificacao: string; area_nome: string; nome: string };

export function SetoresRestritos({
  alvoId,
  clienteId,
  pelaEquipe,
}: {
  /** id do usuário de cliente que está sendo restringido. */
  alvoId: number;
  clienteId: number | null;
  /** true = Minha Equipe (Master do cliente); false = edição de usuário (Master interno). */
  pelaEquipe: boolean;
}) {
  const toast = useToast();
  const [setores, setSetores] = useState<SetorOpcao[] | null>(null);
  const [marcados, setMarcados] = useState<Set<number>>(new Set());
  const [original, setOriginal] = useState<Set<number>>(new Set());
  const [erro, setErro] = useState<string | null>(null);
  const [salvando, setSalvando] = useState(false);
  const base = pelaEquipe ? `/minha-equipe/${alvoId}/setores/` : `/usuarios/${alvoId}/setores/`;

  useEffect(() => {
    let vivo = true;
    (async () => {
      try {
        const [lista, atual] = await Promise.all([
          clienteId
            ? api<Paginated<SetorOpcao>>(`/setores/?area__cliente=${clienteId}&page_size=500`)
            : Promise.resolve({ count: 0, results: [] as SetorOpcao[] }),
          api<{ restrito: boolean; setores: number[] }>(base),
        ]);
        if (!vivo) return;
        setSetores(lista.results);
        const ids = new Set(atual.setores);
        setMarcados(ids);
        setOriginal(new Set(atual.setores));
      } catch (e) {
        if (vivo) setErro(e instanceof ApiError ? e.message : "Não foi possível carregar os setores.");
      }
    })();
    return () => {
      vivo = false;
    };
  }, [base, clienteId]);

  function alternar(id: number, ligado: boolean) {
    setMarcados((atual) => {
      const novo = new Set(atual);
      if (ligado) novo.add(id);
      else novo.delete(id);
      return novo;
    });
  }

  async function salvar() {
    setSalvando(true);
    setErro(null);
    try {
      const r = await api<{ restrito: boolean; setores: number[] }>(base, {
        method: "PUT",
        body: { setores: [...marcados] },
      });
      setOriginal(new Set(r.setores));
      setMarcados(new Set(r.setores));
      toast.sucesso(r.restrito ? "Acesso restrito aos setores marcados." : "Acesso ao cliente inteiro.");
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : "Não foi possível salvar os setores.");
    } finally {
      setSalvando(false);
    }
  }

  if (erro && !setores) return <Alert tone="warning">{erro}</Alert>;
  if (!setores) return <p className="text-sm text-fg-muted">Carregando setores…</p>;

  const mudou = original.size !== marcados.size || [...marcados].some((id) => !original.has(id));
  return (
    <div className="space-y-3">
      <p className="text-sm text-fg-muted">
        {marcados.size === 0
          ? "Sem setor marcado, o usuário vê o cliente inteiro."
          : `Restrito a ${marcados.size} setor(es): ele só vê equipamentos, medições e laudos desses setores.`}
      </p>
      {mudou && (
        <p className="text-xs font-medium text-warning-fg">
          Alteração ainda não aplicada: clique em “Salvar setores”.
        </p>
      )}
      {setores.length === 0 ? (
        <Alert tone="info">Este cliente ainda não tem setores cadastrados.</Alert>
      ) : (
        <ul className="grid gap-2 sm:grid-cols-2">
          {setores.map((s) => (
            <li key={s.id}>
              <Checkbox
                checked={marcados.has(s.id)}
                onChange={(ligado) => alternar(s.id, ligado)}
                label={s.identificacao || `${s.area_nome} — ${s.nome}`}
              />
            </li>
          ))}
        </ul>
      )}
      {erro && <Alert tone="warning">{erro}</Alert>}
      <div className="flex justify-end gap-2">
        {marcados.size > 0 && (
          <Button variant="secondary" size="sm" onClick={() => setMarcados(new Set())} disabled={salvando}>
            Liberar cliente inteiro
          </Button>
        )}
        <Button size="sm" onClick={salvar} disabled={!mudou} loading={salvando}>
          Salvar setores
        </Button>
      </div>
    </div>
  );
}
