"use client";

import { Suspense, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ClipboardCheck, Eye, FileCheck2, Trash2 } from "lucide-react";
import {
  Badge,
  ConfirmDialog,
  DataTable,
  EmptyState,
  Field,
  Input,
  LoadingState,
  PageBody,
  PageHeader,
  SearchInput,
  SegmentedControl,
  Select,
  SemDado,
  Toolbar,
  useConfirmacao,
  useToast,
  type Coluna,
  type ItemMenu,
} from "@/components/ds";
import { api } from "@/lib/api";
import { useLista, useMutacao } from "@/lib/recurso";
import { useClienteAtivo } from "@/lib/cliente-ativo";
import { usePermissoes } from "@/lib/permissions";
import { data as fmtData, plural, texto } from "@/lib/format";
import { ExigeClienteAtivo } from "@/features/clientes/exige-cliente-ativo";
import type { Achado } from "@/lib/types";

type Tecnologia = { id: number; nome: string };
type Situacao = "nao" | "sim" | "todas";

/**
 * Análise final — o refino no escritório do que veio do campo.
 *
 * A tela abre em "Não confirmadas" de propósito: é a fila de trabalho. Confirmar
 * uma análise publica o achado e gera a ordem de serviço, então o que já foi
 * confirmado sai do caminho.
 */
function AnaliseFinalConteudo() {
  const router = useRouter();
  const parametros = useSearchParams();
  const toast = useToast();
  const { podeEditar, podeExcluir } = usePermissoes();
  const { clienteAtivo } = useClienteAtivo();

  const [busca, setBusca] = useState("");
  const [tecFiltro, setTecFiltro] = useState("");
  const [dataIni, setDataIni] = useState("");
  const [dataFim, setDataFim] = useState("");
  // Ao voltar de "Confirmar e publicar", a URL pede a visão "Confirmadas".
  const situacaoInicial = parametros?.get("situacao");
  const [situacao, setSituacao] = useState<Situacao>(
    situacaoInicial === "sim" || situacaoInicial === "todas" ? situacaoInicial : "nao"
  );

  const tecnologias = useLista<Tecnologia>("/tecnologias-analise/?page_size=500", "tecnologias");
  const lista = useLista<Achado>(
    clienteAtivo
      ? `/achados/?item__carregamento__cliente=${clienteAtivo.id}&item__carregamento__status=TRANSFERIDA&page_size=500`
      : null,
    "análises transferidas"
  );
  const mutacao = useMutacao("remoção de análise");
  const remocao = useConfirmacao<Achado>();

  async function remover(a: Achado) {
    const r = await mutacao.executar(() => api(`/achados/${a.id}/`, { method: "DELETE" }));
    if (r.ok) {
      toast.sucesso("Análise removida");
      lista.removerItem((x) => x.id === a.id);
    } else {
      toast.erro(r.falha.titulo, { descricao: r.falha.descricao });
    }
  }

  const nomeTecnologia = tecnologias.itens.find((t) => String(t.id) === tecFiltro)?.nome;

  const filtrados = useMemo(
    () =>
      lista.itens.filter((a) => {
        if (situacao === "nao" && a.confirmada) return false;
        if (situacao === "sim" && !a.confirmada) return false;
        if (tecFiltro && a.tecnologia_nome !== nomeTecnologia) return false;
        if (dataIni && (a.data ?? "") < dataIni) return false;
        if (dataFim && (a.data ?? "") > dataFim) return false;
        return true;
      }),
    [lista.itens, situacao, tecFiltro, nomeTecnologia, dataIni, dataFim]
  );

  const naoConfirmadas = lista.itens.filter((a) => !a.confirmada).length;

  const colunas: Coluna<Achado>[] = [
    {
      chave: "osp",
      header: "OSP",
      mobile: "titulo",
      tecnico: true,
      valor: (a) => a.numero_osp ?? "",
      celula: (a) =>
        a.numero_osp ? (
          <span className="font-semibold text-fg">{a.numero_osp}</span>
        ) : (
          <SemDado>#{a.id}</SemDado>
        ),
    },
    {
      chave: "equipamento",
      header: "Equipamento",
      mobile: "subtitulo",
      valor: (a) => `${a.equipamento_tag} ${a.equipamento_nome}`,
      celula: (a) => (
        <span>
          <span className="data font-medium text-fg">{a.equipamento_tag}</span>
          <span className="block truncate text-xs text-fg-muted">{texto(a.equipamento_nome)}</span>
        </span>
      ),
    },
    {
      chave: "data",
      header: "Data",
      mobile: "meta",
      tecnico: true,
      valor: (a) => a.data ?? "",
      celula: (a) => fmtData(a.data),
    },
    {
      chave: "componente",
      header: "Componente",
      mobile: "meta",
      valor: (a) => a.tipo_componente_nome || a.componente_texto || "",
      celula: (a) => texto(a.tipo_componente_nome || a.componente_texto),
    },
    {
      chave: "condicao",
      header: "Condição",
      mobile: "meta",
      valor: (a) => a.condicao_sigla || a.condicao_nome || "",
      celula: (a) =>
        a.condicao_sigla || a.condicao_nome ? (
          <Badge tone="warning" title={a.condicao_nome ?? undefined}>
            {a.condicao_sigla || a.condicao_nome}
          </Badge>
        ) : (
          <SemDado />
        ),
    },
    {
      chave: "tecnologia",
      header: "Tecnologia",
      mobile: "oculta",
      valor: (a) => a.tecnologia_nome,
      celula: (a) => texto(a.tecnologia_nome),
    },
    {
      chave: "situacao",
      header: "Situação",
      mobile: "meta",
      valor: (a) => (a.confirmada ? 1 : 0),
      celula: (a) =>
        a.confirmada ? (
          <Badge tone="success">Confirmada</Badge>
        ) : (
          <Badge tone="warning">Aguardando confirmação</Badge>
        ),
    },
  ];

  const acoes = (a: Achado): ItemMenu[] => {
    const itens: ItemMenu[] = [
      { label: "Abrir análise", href: `/inspecoes/final/${a.id}`, icon: Eye },
    ];
    if (podeExcluir)
      itens.push({
        label: "Remover análise",
        icon: Trash2,
        destrutivo: true,
        onClick: () => remocao.pedir(a),
      });
    return itens;
  };

  return (
    <PageBody>
      <PageHeader
        icon={FileCheck2}
        title="Análise final"
        description={
          clienteAtivo
            ? `Refino no escritório do que foi coletado em ${clienteAtivo.nome_fantasia || clienteAtivo.nome}. Confirmar uma análise publica o achado e abre a ordem de serviço.`
            : "Refinamento no escritório das análises trazidas do campo."
        }
        trilha={[{ label: "Inspeções", href: "/inspecoes/campo" }, { label: "Análise final" }]}
        selo={
          naoConfirmadas > 0 ? (
            <Badge tone="warning">{naoConfirmadas} aguardando confirmação</Badge>
          ) : undefined
        }
      />

      {!clienteAtivo ? (
        <ExigeClienteAtivo oQue="As análises transferidas do campo" />
      ) : (
        <>
          <Toolbar
            busca={
              <SearchInput
                value={busca}
                onChange={setBusca}
                label="Buscar análise"
                placeholder="OSP, equipamento, componente…"
              />
            }
            filtros={
              <>
                <SegmentedControl
                  label="Situação da análise"
                  tamanho="sm"
                  valor={situacao}
                  onMudar={setSituacao}
                  opcoes={[
                    { valor: "nao", label: "A confirmar" },
                    { valor: "sim", label: "Confirmadas" },
                    { valor: "todas", label: "Todas" },
                  ]}
                />
                <div className="w-44">
                  <Field label="Tecnologia">
                    <Select value={tecFiltro} onChange={(e) => setTecFiltro(e.target.value)}>
                      <option value="">Todas</option>
                      {tecnologias.itens.map((t) => (
                        <option key={t.id} value={t.id}>
                          {t.nome}
                        </option>
                      ))}
                    </Select>
                  </Field>
                </div>
                <div className="flex gap-2">
                  <Field label="De">
                    <Input type="date" value={dataIni} onChange={(e) => setDataIni(e.target.value)} />
                  </Field>
                  <Field label="Até">
                    <Input type="date" value={dataFim} onChange={(e) => setDataFim(e.target.value)} />
                  </Field>
                </div>
              </>
            }
            resumo={
              lista.itens.length > 0
                ? `${filtrados.length} de ${plural(lista.itens.length, "análise", "análises")} transferidas`
                : undefined
            }
          />

          {lista.carregando ? (
            <LoadingState variante="tabela" linhas={8} colunas={6} label="Carregando análises…" />
          ) : (
            <DataTable<Achado>
              itens={filtrados}
              colunas={colunas}
              getId={(a) => a.id}
              busca={busca}
              camposBusca={(a) => [a.anomalia_texto, a.tipo_anomalia_nome, String(a.id)]}
              falha={lista.falha}
              onRetry={lista.recarregar}
              onLinhaClick={(a) => router.push(`/inspecoes/final/${a.id}`)}
              acoes={podeEditar ? acoes : undefined}
              ordenacaoInicial={{ chave: "data", direcao: "desc" }}
              porPagina={15}
              legenda="Análises transferidas do campo, com OSP, equipamento, componente, condição e situação"
              vazio={
                situacao !== "todas" || tecFiltro || dataIni || dataFim ? (
                  <EmptyState
                    compacto
                    icon={FileCheck2}
                    title={
                      situacao === "nao"
                        ? "Nenhuma análise aguardando confirmação"
                        : "Nada corresponde aos filtros"
                    }
                    description={
                      situacao === "nao"
                        ? "Toda a fila de refino deste cliente está em dia."
                        : "Ajuste a situação, a tecnologia ou o período."
                    }
                  />
                ) : (
                  <EmptyState
                    icon={ClipboardCheck}
                    title="Nenhuma análise transferida deste cliente"
                    description="As análises chegam aqui quando a folha de campo é transferida para o escritório."
                    comoFunciona={[
                      "Carregue uma rota em Análise de campo e registre as condições.",
                      "Lance as análises dos equipamentos que exigem ação.",
                      "Transfira a rota — as análises aparecem nesta fila para refino.",
                    ]}
                  />
                )
              }
            />
          )}
        </>
      )}

      <ConfirmDialog
        aberto={!!remocao.alvo}
        onFechar={remocao.cancelar}
        onConfirmar={() => remocao.executar(remover)}
        enviando={mutacao.enviando}
        title="Remover esta análise?"
        confirmarLabel="Remover análise"
        mensagem={
          <>
            A análise do equipamento <strong>{remocao.alvo?.equipamento_tag}</strong>
            {remocao.alvo?.numero_osp ? (
              <>
                {" "}
                (OSP <strong>{remocao.alvo.numero_osp}</strong>)
              </>
            ) : null}{" "}
            será apagada.
          </>
        }
        detalhe={
          remocao.alvo?.confirmada
            ? "Esta análise já foi confirmada e publicada — remover pode deixar a ordem de serviço sem origem."
            : "Ela sai da fila de refino e não gera ordem de serviço."
        }
        irreversivel
      />
    </PageBody>
  );
}

export default function AnaliseFinalPage() {
  return (
    <Suspense fallback={<LoadingState variante="tabela" linhas={8} colunas={6} />}>
      <AnaliseFinalConteudo />
    </Suspense>
  );
}
