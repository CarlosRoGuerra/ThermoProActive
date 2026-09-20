"use client";

import { useEffect, useMemo, useState } from "react";
import { Building2, Check, ChevronDown, Clock } from "lucide-react";
import {
  Avatar,
  Button,
  Drawer,
  EmptyState,
  SearchInput,
  cn,
} from "@/components/ds";
import { useClienteAtivo, type ClienteAtivo } from "@/lib/cliente-ativo";
import { useClientes } from "@/lib/hierarquia";
import { cnpj as fmtCnpj, normalizar } from "@/lib/format";

/**
 * Seletor do cliente em atendimento — o "ambiente" de trabalho da equipe interna.
 *
 * Um chip na topbar mostra quem está sendo atendido; clicar abre um painel com
 * busca e os últimos acessados. Usa o `Drawer` do Design System, e não uma
 * sobreposição própria: assim herda Esc para fechar, aprisionamento de foco e
 * devolução do foco ao chip — que a versão anterior, feita à mão, não tinha.
 */
export function ClienteSwitcher() {
  const { clienteAtivo, recentes, ativar, limpar } = useClienteAtivo();
  const [aberto, setAberto] = useState(false);
  const [busca, setBusca] = useState("");
  // Só busca a lista completa quando o painel abre — são centenas de registros
  // que não têm por que viajar em cada carregamento de página.
  const { clientes, carregando } = useClientes(aberto);

  useEffect(() => {
    if (aberto) setBusca("");
  }, [aberto]);

  const resultados = useMemo(() => {
    const q = normalizar(busca).trim();
    if (!q) return [];
    return clientes
      .filter((c) =>
        normalizar([c.nome, c.nome_fantasia, c.cnpj, c.cidade_uf].join(" ")).includes(q)
      )
      .slice(0, 25);
  }, [clientes, busca]);

  function escolher(c: {
    id: number;
    nome: string;
    nome_fantasia: string;
    logomarca?: string | null;
  }) {
    ativar({ id: c.id, nome: c.nome, nome_fantasia: c.nome_fantasia, logomarca: c.logomarca });
    setAberto(false);
  }

  const titulo = clienteAtivo ? clienteAtivo.nome_fantasia || clienteAtivo.nome : "Escolher cliente";

  return (
    <>
      <button
        type="button"
        onClick={() => setAberto(true)}
        title="Trocar o cliente em atendimento"
        aria-haspopup="dialog"
        className={cn(
          "flex items-center gap-2 rounded-full border py-1 pl-1.5 pr-2.5 text-xs transition-colors",
          clienteAtivo
            ? "border-primary/30 bg-primary-subtle text-fg hover:bg-primary-subtle/70"
            : "border-dashed border-border-strong text-fg-muted hover:bg-surface-muted"
        )}
      >
        <span className="flex h-6 w-6 shrink-0 items-center justify-center overflow-hidden rounded-full bg-surface">
          {clienteAtivo?.logomarca ? (
            <Avatar nome={titulo} src={clienteAtivo.logomarca} tamanho="xs" />
          ) : (
            <Building2 className="h-3.5 w-3.5 text-primary" aria-hidden="true" />
          )}
        </span>
        <span className="hidden max-w-40 truncate font-medium sm:inline">{titulo}</span>
        <ChevronDown className="h-3.5 w-3.5 shrink-0 opacity-70" aria-hidden="true" />
      </button>

      <Drawer
        aberto={aberto}
        onFechar={() => setAberto(false)}
        title="Cliente em atendimento"
        description="Escolher um cliente filtra estrutura, equipamentos, rotas e inspeções por ele."
        largura="sm"
      >
        <div className="space-y-4">
          <SearchInput
            value={busca}
            onChange={setBusca}
            label="Buscar cliente"
            placeholder="Razão social, CNPJ, cidade…"
            autoFocus
          />

          {busca ? (
            carregando ? (
              <p className="py-6 text-center text-sm text-fg-subtle">Buscando…</p>
            ) : resultados.length === 0 ? (
              <EmptyState
                compacto
                icon={Building2}
                title="Nenhum cliente encontrado"
                description={`Nada corresponde a “${busca}”. Verifique a grafia ou busque pelo CNPJ.`}
              />
            ) : (
              <ul className="space-y-1">
                {resultados.map((c) => (
                  <LinhaCliente
                    key={c.id}
                    cliente={c}
                    ativo={clienteAtivo?.id === c.id}
                    onClick={() => escolher(c)}
                  />
                ))}
              </ul>
            )
          ) : (
            <>
              {clienteAtivo && (
                <section>
                  <h3 className="mb-1.5 text-2xs font-semibold uppercase tracking-wide text-fg-subtle">
                    Atendendo agora
                  </h3>
                  <ul>
                    <LinhaCliente cliente={clienteAtivo} ativo onClick={() => setAberto(false)} />
                  </ul>
                  <Button
                    variant="ghost"
                    size="sm"
                    block
                    className="mt-1 justify-start"
                    onClick={() => {
                      limpar();
                      setAberto(false);
                    }}
                  >
                    Sair do ambiente deste cliente
                  </Button>
                </section>
              )}

              <section>
                <h3 className="mb-1.5 flex items-center gap-1.5 text-2xs font-semibold uppercase tracking-wide text-fg-subtle">
                  <Clock className="h-3 w-3" aria-hidden="true" /> Últimos acessados
                </h3>
                {recentes.length === 0 ? (
                  <p className="py-3 text-sm text-fg-subtle">
                    Nenhum ainda. Use a busca acima para escolher um cliente.
                  </p>
                ) : (
                  <ul className="space-y-1">
                    {recentes.map((c) => (
                      <LinhaCliente
                        key={c.id}
                        cliente={c}
                        ativo={clienteAtivo?.id === c.id}
                        onClick={() => escolher(c)}
                      />
                    ))}
                  </ul>
                )}
              </section>
            </>
          )}
        </div>
      </Drawer>
    </>
  );
}

function LinhaCliente({
  cliente,
  ativo,
  onClick,
}: {
  cliente: {
    id: number;
    nome: string;
    nome_fantasia: string;
    cnpj?: string;
    logomarca?: string | null;
  };
  ativo: boolean;
  onClick: () => void;
}) {
  const principal = cliente.nome_fantasia || cliente.nome;
  const secundario = cliente.nome_fantasia
    ? cliente.nome
    : cliente.cnpj
    ? fmtCnpj(cliente.cnpj)
    : "";

  return (
    <li>
      <button
        type="button"
        onClick={onClick}
        aria-current={ativo ? "true" : undefined}
        className={cn(
          "flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-left transition-colors",
          ativo ? "bg-primary-subtle" : "hover:bg-surface-muted"
        )}
      >
        <Avatar nome={principal} src={cliente.logomarca} tamanho="sm" className="rounded-lg" />
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium text-fg">{principal}</span>
          {secundario && (
            <span className="block truncate text-xs text-fg-subtle">{secundario}</span>
          )}
        </span>
        {ativo && <Check className="h-4 w-4 shrink-0 text-primary" aria-hidden="true" />}
      </button>
    </li>
  );
}

export type { ClienteAtivo };
