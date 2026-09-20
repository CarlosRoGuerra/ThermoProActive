"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Eye, Gauge, Plus, Wrench } from "lucide-react";
import {
  Badge,
  Button,
  CriticidadeBadge,
  DataTable,
  EmptyState,
  Field,
  MetricCard,
  MetricGrid,
  PageBody,
  PageHeader,
  SearchInput,
  SectionHeader,
  SegmentedControl,
  SemDado,
  Toolbar,
  type Coluna,
} from "@/components/ds";
import { Combobox } from "@/components/combobox";
import { qs } from "@/lib/api";
import { useLista } from "@/lib/recurso";
import { useClienteAtivo } from "@/lib/cliente-ativo";
import { useClientes } from "@/lib/hierarquia";
import { usePermissoes } from "@/lib/permissions";
import { data as fmtData, percentual, plural, texto } from "@/lib/format";
import type { AtividadeCorretiva, ServicoCampoLista } from "@/lib/types";

/* ==========================================================================
   Manutenção corretiva — balanceamento, alinhamento e afins.
   --------------------------------------------------------------------------
   A tela tem dois assuntos que antes disputavam o mesmo espaço: as ATIVIDADES
   (rotas carregadas, ainda em execução) e os SERVIÇOS (o que já foi executado e
   medido). Viraram duas visões de um seletor, em vez de duas tabelas empilhadas
   com títulos soltos — assim a página abre no que está em andamento.
   ========================================================================== */

type Visao = "atividades" | "servicos";

export default function ServicosPage() {
  const router = useRouter();
  const { podeEditar } = usePermissoes();
  const { opcoes: opcoesClientes } = useClientes();
  const { clienteAtivo } = useClienteAtivo();

  const [cliente, setCliente] = useState<number | "">(clienteAtivo?.id ?? "");
  const [visao, setVisao] = useState<Visao>("atividades");
  const [busca, setBusca] = useState("");

  useEffect(() => {
    if (clienteAtivo) setCliente(clienteAtivo.id);
  }, [clienteAtivo]);

  const filtro = qs({ ordering: "-data_coleta", page_size: 300, cliente });
  const atividades = useLista<AtividadeCorretiva>(
    `/atividades-corretivas/${filtro}`,
    "atividades corretivas"
  );
  const servicos = useLista<ServicoCampoLista>(
    `/servicos/${qs({ ordering: "-data_execucao", page_size: 300, cliente })}`,
    "serviços corretivos"
  );

  // Abre na visão que tem conteúdo: quem entra quer ver o que está em andamento,
  // mas se não há atividade aberta, o histórico é mais útil que uma tela vazia.
  useEffect(() => {
    if (!atividades.carregando && atividades.itens.length === 0 && servicos.itens.length > 0) {
      setVisao("servicos");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [atividades.carregando, atividades.itens.length, servicos.itens.length]);

  useEffect(() => setBusca(""), [visao]);

  const reducaoMedia = useMemo(() => {
    const valores = servicos.itens
      .map((s) => (s.reducao_media_pct == null ? null : Number(s.reducao_media_pct)))
      .filter((v): v is number => v !== null && Number.isFinite(v));
    if (valores.length === 0) return null;
    return valores.reduce((a, b) => a + b, 0) / valores.length;
  }, [servicos.itens]);

  const colunasAtividades: Coluna<AtividadeCorretiva>[] = [
    {
      chave: "numero",
      header: "Relatório",
      mobile: "titulo",
      tecnico: true,
      valor: (a) => a.numero,
      celula: (a) => (
        <span>
          <span className="font-semibold text-fg">{a.numero}</span>
          <span className="block truncate text-xs text-fg-muted">{a.cliente_nome}</span>
        </span>
      ),
    },
    {
      chave: "rota",
      header: "Rota",
      mobile: "subtitulo",
      valor: (a) => a.rota_nome,
      celula: (a) => texto(a.rota_nome),
    },
    {
      chave: "tecnologia",
      header: "Tecnologia",
      mobile: "meta",
      valor: (a) => a.tecnologia_nome,
      celula: (a) => <Badge tone="primary">{a.tecnologia_nome}</Badge>,
    },
    {
      chave: "data",
      header: "Data do ensaio",
      mobile: "meta",
      tecnico: true,
      valor: (a) => a.data_coleta,
      celula: (a) => fmtData(a.data_coleta),
    },
    {
      chave: "itens",
      header: "Equipamentos",
      mobile: "meta",
      alinhamento: "direita",
      tecnico: true,
      valor: (a) => a.qtd_itens,
      celula: (a) => a.qtd_itens,
    },
  ];

  const colunasServicos: Coluna<ServicoCampoLista>[] = [
    {
      chave: "equipamento",
      header: "Equipamento",
      mobile: "titulo",
      tecnico: true,
      valor: (s) => s.equipamento_tag,
      celula: (s) => (
        <span>
          <span className="font-semibold text-fg">{s.equipamento_tag}</span>
          <span className="block truncate text-xs text-fg-muted">{s.cliente_nome}</span>
        </span>
      ),
    },
    {
      chave: "tipo",
      header: "Tipo de serviço",
      mobile: "subtitulo",
      valor: (s) => s.tipo_display,
      celula: (s) => <Badge tone="neutral">{s.tipo_display}</Badge>,
    },
    {
      chave: "data",
      header: "Execução",
      mobile: "meta",
      tecnico: true,
      valor: (s) => s.data_execucao ?? "",
      celula: (s) => fmtData(s.data_execucao),
    },
    {
      chave: "rotacao",
      header: "Rotação",
      mobile: "meta",
      alinhamento: "direita",
      tecnico: true,
      valor: (s) => s.rotacao_rpm ?? 0,
      celula: (s) => (s.rotacao_rpm ? `${s.rotacao_rpm} RPM` : <SemDado />),
    },
    {
      chave: "planos",
      header: "Planos",
      mobile: "oculta",
      alinhamento: "direita",
      tecnico: true,
      valor: (s) => s.numero_planos ?? 0,
      celula: (s) => s.numero_planos || <SemDado />,
    },
    {
      chave: "reducao",
      header: "Redução da vibração",
      mobile: "meta",
      alinhamento: "direita",
      tecnico: true,
      valor: (s) => (s.reducao_media_pct == null ? -1 : Number(s.reducao_media_pct)),
      celula: (s) =>
        s.reducao_media_pct == null ? (
          <SemDado />
        ) : (
          <span className="font-medium text-success-fg">{percentual(s.reducao_media_pct)}</span>
        ),
    },
    {
      chave: "condicao",
      header: "Condição final",
      mobile: "meta",
      valor: (s) => s.criticidade_final,
      celula: (s) => <CriticidadeBadge value={s.criticidade_final} />,
    },
  ];

  return (
    <PageBody>
      <PageHeader
        icon={Wrench}
        title="Manutenção corretiva"
        description="Balanceamento de rotores, alinhamento a laser e demais trabalhos corretivos executados em campo, com o resultado medido antes e depois."
        trilha={[{ label: "Inspeções", href: "/inspecoes/campo" }, { label: "Manutenção corretiva" }]}
        actions={
          podeEditar ? (
            <Button icon={Plus} onClick={() => router.push("/servicos/novo")}>
              Nova atividade
            </Button>
          ) : undefined
        }
      />

      <MetricGrid colunas={3}>
        <MetricCard
          label="Atividades em rota"
          value={atividades.itens.length}
          icon={Wrench}
          contexto="carregadas para execução"
        />
        <MetricCard
          label="Serviços executados"
          value={servicos.itens.length}
          icon={Gauge}
          contexto="com medição registrada"
        />
        <MetricCard
          label="Redução média da vibração"
          value={reducaoMedia == null ? "—" : percentual(reducaoMedia)}
          tone={reducaoMedia != null && reducaoMedia > 0 ? "success" : "neutral"}
          contexto={
            reducaoMedia == null
              ? "sem serviço medido ainda"
              : `média de ${plural(servicos.itens.length, "serviço")}`
          }
          dica="Queda percentual da amplitude de vibração entre a medição de referência e a final."
        />
      </MetricGrid>

      <Toolbar
        busca={
          <SearchInput
            value={busca}
            onChange={setBusca}
            label="Buscar"
            placeholder={
              visao === "atividades" ? "Relatório, rota, tecnologia…" : "TAG, cliente, tipo…"
            }
          />
        }
        filtros={
          <>
            <div className="w-56">
              <Field label="Cliente">
                <Combobox
                  value={cliente}
                  onChange={setCliente}
                  options={opcoesClientes}
                  placeholder="Todos os clientes"
                  limparLabel="Todos os clientes"
                />
              </Field>
            </div>
            <SegmentedControl
              label="O que mostrar"
              tamanho="sm"
              valor={visao}
              onMudar={setVisao}
              opcoes={[
                { valor: "atividades", label: `Em rota (${atividades.itens.length})` },
                { valor: "servicos", label: `Executados (${servicos.itens.length})` },
              ]}
            />
          </>
        }
      />

      {visao === "atividades" ? (
        <DataTable<AtividadeCorretiva>
          itens={atividades.itens}
          colunas={colunasAtividades}
          getId={(a) => a.id}
          busca={busca}
          carregando={atividades.carregando}
          falha={atividades.falha}
          onRetry={atividades.recarregar}
          onLinhaClick={(a) => router.push(`/servicos/atividades/${a.id}`)}
          acoes={(a) => [
            { label: "Abrir atividade", href: `/servicos/atividades/${a.id}`, icon: Eye },
          ]}
          ordenacaoInicial={{ chave: "data", direcao: "desc" }}
          legenda="Atividades corretivas carregadas por rota"
          vazio={
            <EmptyState
              icon={Wrench}
              title="Nenhuma atividade corretiva em rota"
              description="A atividade corretiva nasce do carregamento de uma rota com tecnologia corretiva (balanceamento, alinhamento)."
              action={
                podeEditar ? (
                  <Button icon={Plus} onClick={() => router.push("/servicos/novo")}>
                    Carregar rota corretiva
                  </Button>
                ) : undefined
              }
              comoFunciona={[
                "Monte uma rota com a tecnologia corretiva e os equipamentos alvo.",
                "Carregue a rota — cada equipamento vira um item para analisar.",
                "Registre as medições de referência, teste e correção em campo.",
              ]}
            />
          }
        />
      ) : (
        <DataTable<ServicoCampoLista>
          itens={servicos.itens}
          colunas={colunasServicos}
          getId={(s) => s.id}
          busca={busca}
          carregando={servicos.carregando}
          falha={servicos.falha}
          onRetry={servicos.recarregar}
          onLinhaClick={(s) =>
            router.push(
              s.atividade ? `/servicos/atividades/${s.atividade}?item=${s.item}` : `/servicos/${s.id}`
            )
          }
          ordenacaoInicial={{ chave: "data", direcao: "desc" }}
          legenda="Serviços corretivos executados, com rotação, planos, redução de vibração e condição final"
          vazio={
            <EmptyState
              icon={Gauge}
              title="Nenhum serviço corretivo executado"
              description="Os balanceamentos e alinhamentos concluídos aparecem aqui com o resultado medido."
            />
          }
        />
      )}

      {/* Roteiro acordado com o cliente — informa o que ainda não existe, sem
          disputar espaço com os dados reais da tela. */}
      <SectionHeader
        title="Tecnologias corretivas cobertas"
        description="O que já está disponível nesta área e o que entra nas próximas etapas."
      />
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {[
          { titulo: "Balanceamento de rotores", situacao: "Disponível", tom: "success" as const },
          { titulo: "Alinhamento a laser", situacao: "Registro agrupado", tom: "warning" as const },
          { titulo: "Outros trabalhos corretivos", situacao: "Próxima etapa", tom: "neutral" as const },
        ].map((t) => (
          <div
            key={t.titulo}
            className="rounded-xl border border-border bg-surface px-4 py-3 shadow-xs"
          >
            <p className="text-sm font-medium text-fg">{t.titulo}</p>
            <Badge tone={t.tom} className="mt-1.5">
              {t.situacao}
            </Badge>
          </div>
        ))}
      </div>
    </PageBody>
  );
}
