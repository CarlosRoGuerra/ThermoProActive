"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Building2, Database, Lock, Pencil, Plus, Trash2 } from "lucide-react";
import {
  Alert,
  Badge,
  Button,
  Card,
  ConfirmDialog,
  DataTable,
  EmptyState,
  LoadingState,
  PageBody,
  PageHeader,
  SearchInput,
  SemDado,
  Toolbar,
  cn,
  useConfirmacao,
  useToast,
  type Coluna,
  type ItemMenu,
} from "@/components/ds";
import { api } from "@/lib/api";
import { useLista, useMutacao } from "@/lib/recurso";
import { useClienteAtivo } from "@/lib/cliente-ativo";
import { usePermissoes } from "@/lib/permissions";
import { plural } from "@/lib/format";
import { ExigeClienteAtivo } from "@/features/clientes/exige-cliente-ativo";
import {
  CATALOGOS,
  CATALOGOS_CLIENTE,
  CATALOGOS_SISTEMA,
  rotuloColuna,
  type CatalogDef,
} from "@/features/cadastros/catalogos";
import {
  FormularioCatalogo,
  type Opcao,
  type Registro,
} from "@/features/cadastros/formulario-catalogo";

/* ==========================================================================
   Dados de sistema e estrutura do cliente.
   --------------------------------------------------------------------------
   Uma tela genérica para ~16 tabelas de referência. A definição de cada uma
   vive em features/cadastros/catalogos.ts; aqui só existe a interface.

   Quem pode o quê (espelha o backend):
     • Áreas e Setores        → qualquer usuário interno (dado do cliente)
     • demais tabelas         → só o nível Master (MasterEditaDemaisVisualizam)
   Quem não pode editar continua consultando: a tela avisa por quê, em vez de
   simplesmente esconder os botões e deixar a pessoa sem saber.
   ========================================================================== */

export default function CadastrosPage() {
  return (
    <Suspense fallback={<LoadingState variante="tabela" linhas={8} colunas={4} />}>
      <Cadastros />
    </Suspense>
  );
}

function Cadastros() {
  const toast = useToast();
  const parametros = useSearchParams();
  const { user, podeExcluir } = usePermissoes();
  const { clienteAtivo } = useClienteAtivo();

  const itemUrl = parametros?.get("item");
  const [catalogo, setCatalogo] = useState<CatalogDef>(
    () => CATALOGOS.find((c) => c.key === itemUrl) ?? CATALOGOS[0]
  );
  const [busca, setBusca] = useState("");
  const [emEdicao, setEmEdicao] = useState<Registro | null | "novo">(null);
  const [opcoes, setOpcoes] = useState<Record<string, Opcao[]>>({});

  // O submenu da barra lateral escolhe o catálogo pela URL (?item=).
  useEffect(() => {
    const alvo = CATALOGOS.find((c) => c.key === itemUrl);
    if (alvo && alvo.key !== catalogo.key) setCatalogo(alvo);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [itemUrl]);

  // Trocar de catálogo zera o contexto da tela.
  useEffect(() => {
    setBusca("");
    setEmEdicao(null);
  }, [catalogo.key]);

  const ehDoCliente = !!catalogo.escopoCliente;
  const precisaCliente = ehDoCliente && !clienteAtivo;

  const podeEditar =
    catalogo.permissao === "interno"
      ? !!user?.is_interno
      : !!user?.pode_curar_dados_sistema;

  const escopo =
    catalogo.escopoCliente && clienteAtivo
      ? `&${catalogo.escopoCliente.param}=${clienteAtivo.id}`
      : "";

  const lista = useLista<Registro>(
    precisaCliente ? null : `/${catalogo.endpoint}/?page_size=500${escopo}`,
    catalogo.label
  );
  const mutacao = useMutacao("remoção de registro");
  const remocao = useConfirmacao<Registro>();

  // Opções dos campos relacionais (tecnologias, áreas…), por endpoint.
  useEffect(() => {
    const relacionais = catalogo.fields.filter(
      (f) => (f.type === "multiref" || f.type === "ref") && f.optionsEndpoint
    );
    if (relacionais.length === 0) return;
    const controle = new AbortController();
    for (const f of relacionais) {
      const endpoint = f.optionsEndpoint!;
      const query =
        f.escopoClienteAtivo && clienteAtivo
          ? `?cliente=${clienteAtivo.id}&page_size=500`
          : "?page_size=500";
      api<{ results: Opcao[] }>(`/${endpoint}/${query}`, { signal: controle.signal })
        .then((d) => setOpcoes((atual) => ({ ...atual, [endpoint]: d.results })))
        .catch(() => {
          /* opção indisponível: o campo fica vazio e o Field mostra o vazio */
        });
    }
    return () => controle.abort();
  }, [catalogo, clienteAtivo]);

  async function remover(r: Registro) {
    const res = await mutacao.executar(() =>
      api(`/${catalogo.endpoint}/${r.id}/`, { method: "DELETE" })
    );
    if (res.ok) {
      toast.sucesso("Registro removido");
      lista.removerItem((x) => x.id === r.id);
    } else {
      toast.erro(res.falha.titulo, { descricao: res.falha.descricao });
    }
  }

  /** Nome legível de um registro, para as mensagens de confirmação. */
  function rotulo(r: Registro | null): string {
    if (!r) return "";
    return String(r.nome ?? r.codigo ?? r.sigla ?? `#${r.id}`);
  }

  const colunas: Coluna<Registro>[] = useMemo(
    () =>
      catalogo.columns.map((c, i) => ({
        chave: c,
        header: rotuloColuna(c),
        mobile: i === 0 ? "titulo" : i === 1 ? "subtitulo" : "meta",
        valor: (r) => {
          const v = r[c];
          if (Array.isArray(v)) return (v as Opcao[]).map((o) => o.nome).join(" ");
          if (typeof v === "boolean") return v ? 1 : 0;
          return v == null ? "" : String(v);
        },
        celula: (r) => {
          const v = r[c];
          if (c === "cor")
            return (
              <span className="inline-flex items-center gap-2">
                <span
                  className="h-4 w-4 rounded-full ring-1 ring-border"
                  style={{ background: String(v ?? "") }}
                  aria-hidden="true"
                />
                <span className="data text-xs">{String(v ?? "")}</span>
              </span>
            );
          if (typeof v === "boolean")
            return <Badge tone={v ? "warning" : "neutral"}>{v ? "Sim" : "Não"}</Badge>;
          if (Array.isArray(v))
            return (v as Opcao[]).length ? (
              <span className="flex flex-wrap gap-1">
                {(v as Opcao[]).map((o) => (
                  <Badge key={o.id} tone="primary">
                    {o.nome}
                  </Badge>
                ))}
              </span>
            ) : (
              <SemDado />
            );
          const texto = v == null || v === "" ? null : String(v);
          return texto ? (
            <span className={i === 0 ? "font-medium text-fg" : undefined}>{texto}</span>
          ) : (
            <SemDado />
          );
        },
      })),
    [catalogo]
  );

  const acoes = (r: Registro): ItemMenu[] => {
    if (!podeEditar) return [];
    const itens: ItemMenu[] = [
      { label: "Editar registro", onClick: () => setEmEdicao(r), icon: Pencil },
    ];
    if (podeExcluir)
      itens.push({
        label: "Remover registro",
        icon: Trash2,
        destrutivo: true,
        onClick: () => remocao.pedir(r),
      });
    return itens;
  };

  const grupoAtual = ehDoCliente ? CATALOGOS_CLIENTE : CATALOGOS_SISTEMA;

  return (
    <PageBody>
      {ehDoCliente ? (
        <PageHeader
          icon={Building2}
          title="Estrutura do cliente"
          description={
            clienteAtivo
              ? `Áreas e setores de ${clienteAtivo.nome_fantasia || clienteAtivo.nome}. É esta estrutura que organiza os equipamentos e as rotas.`
              : "As áreas e os setores pertencem a um cliente. Escolha quem você está atendendo para gerenciá-los."
          }
          trilha={[{ label: "Clientes", href: "/clientes" }, { label: catalogo.label }]}
        />
      ) : (
        <PageHeader
          icon={Database}
          title="Dados de sistema"
          description="As tabelas de referência que alimentam os campos do sistema: normas, tipos, criticidades e instrumentação. A curadoria é do nível Master, para manter a padronização."
          trilha={[{ label: "Dados de sistema" }, { label: catalogo.label }]}
        />
      )}

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[15rem_1fr] lg:gap-6">
        {/* Índice dos catálogos — no celular vira uma faixa rolável. */}
        <Card padding={false} className="h-fit p-1.5">
          <nav aria-label={ehDoCliente ? "Estrutura do cliente" : "Tabelas de referência"}>
            <ul className="flex gap-1 overflow-x-auto lg:flex-col lg:overflow-visible [&::-webkit-scrollbar]:hidden">
              {grupoAtual.map((c) => (
                <li key={c.key} className="shrink-0 lg:shrink">
                  <button
                    type="button"
                    onClick={() => setCatalogo(c)}
                    aria-current={catalogo.key === c.key ? "page" : undefined}
                    className={cn(
                      "block w-full whitespace-nowrap rounded-lg px-3 py-2 text-left text-sm font-medium transition-colors duration-fast",
                      catalogo.key === c.key
                        ? "bg-primary-subtle text-primary-subtle-fg"
                        : "text-fg-muted hover:bg-surface-muted hover:text-fg"
                    )}
                  >
                    {c.label}
                  </button>
                </li>
              ))}
            </ul>
          </nav>
        </Card>

        <div className="min-w-0 space-y-4">
          {precisaCliente ? (
            <ExigeClienteAtivo oQue="As áreas e os setores" />
          ) : (
            <>
              {!podeEditar && (
                <Alert tone="info" icon={Lock} title="Você está consultando">
                  A criação e a edição das tabelas de referência são restritas ao nível{" "}
                  <strong>Master</strong>, para que os catálogos não fiquem divergentes. Peça a
                  inclusão a quem tem esse acesso.
                </Alert>
              )}

              <Toolbar
                busca={
                  <SearchInput
                    value={busca}
                    onChange={setBusca}
                    label={`Buscar em ${catalogo.label}`}
                    placeholder={`Buscar em ${catalogo.label.toLowerCase()}…`}
                  />
                }
                acoes={
                  podeEditar ? (
                    <Button icon={Plus} onClick={() => setEmEdicao("novo")}>
                      Novo · {catalogo.label}
                    </Button>
                  ) : undefined
                }
                resumo={
                  lista.itens.length > 0
                    ? plural(lista.itens.length, "registro")
                    : undefined
                }
              />

              <DataTable<Registro>
                itens={lista.itens}
                colunas={colunas}
                getId={(r) => r.id}
                busca={busca}
                carregando={lista.carregando}
                falha={lista.falha}
                onRetry={lista.recarregar}
                onLinhaClick={podeEditar ? (r) => setEmEdicao(r) : undefined}
                acoes={podeEditar ? acoes : undefined}
                ordenacaoInicial={{ chave: catalogo.columns[0], direcao: "asc" }}
                legenda={`${catalogo.label}: ${catalogo.columns.map(rotuloColuna).join(", ")}`}
                vazio={
                  <EmptyState
                    icon={ehDoCliente ? Building2 : Database}
                    title={`Nenhum registro em ${catalogo.label}`}
                    description={
                      podeEditar
                        ? "Adicione o primeiro registro — ele passa a aparecer como opção nos formulários do sistema."
                        : "Esta tabela ainda está vazia. Peça ao nível Master para incluir os registros."
                    }
                    action={
                      podeEditar ? (
                        <Button icon={Plus} onClick={() => setEmEdicao("novo")}>
                          Adicionar o primeiro
                        </Button>
                      ) : undefined
                    }
                  />
                }
              />
            </>
          )}
        </div>
      </div>

      <FormularioCatalogo
        aberto={emEdicao !== null}
        catalogo={catalogo}
        registro={emEdicao === "novo" ? null : emEdicao}
        opcoes={opcoes}
        onFechar={() => setEmEdicao(null)}
        onSalvo={() => {
          setEmEdicao(null);
          lista.recarregar();
        }}
      />

      <ConfirmDialog
        aberto={!!remocao.alvo}
        onFechar={remocao.cancelar}
        onConfirmar={() => remocao.executar(remover)}
        enviando={mutacao.enviando}
        title="Remover este registro?"
        confirmarLabel="Remover"
        mensagem={
          <>
            <strong>{rotulo(remocao.alvo)}</strong> sai de {catalogo.label.toLowerCase()}.
          </>
        }
        detalhe="Ele deixa de aparecer como opção nos formulários. Registros que já o utilizam mantêm o valor; se estiver em uso e não puder sair, o sistema recusa a remoção."
        irreversivel
      />
    </PageBody>
  );
}
