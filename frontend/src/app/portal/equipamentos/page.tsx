"use client";

import { useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { Activity, Boxes, CornerDownRight, Pencil, Plus, Trash2 } from "lucide-react";
import {
  Badge,
  Button,
  ClasseAtivoBadge,
  ConfirmDialog,
  DataTable,
  EmptyState,
  EstadoBadge,
  LegendaEstados,
  MetricCard,
  MetricGrid,
  PageBody,
  PageHeader,
  SearchInput,
  SegmentedControl,
  SemDado,
  Toolbar,
  grauDe,
  pesoGravidade,
  useConfirmacao,
  useToast,
  type Coluna,
  type GrauMonitoramento,
  type ItemMenu,
} from "@/components/ds";
import { api } from "@/lib/api";
import { useLista, useMutacao, useRecurso } from "@/lib/recurso";
import { usePermissoes } from "@/lib/permissions";
import { dataHora, plural } from "@/lib/format";
import { useRegistrarVisita } from "@/features/portal/onboarding";
import type { Equipamento, EstadoEquipamento, PortalVisaoGeral } from "@/lib/types";

/* ==========================================================================
   Portal do Cliente — Meus equipamentos
   --------------------------------------------------------------------------
   A pergunta que esta tela responde: "como está cada máquina minha?".
   Por isso a primeira coluna depois da TAG é o ESTADO, e a ordenação padrão é
   por gravidade — o que precisa de decisão aparece primeiro, sem filtro nenhum.

   Honestidade do dado: equipamento sem coleta registrada aparece como
   "Sem medição", nunca como "Normal". O estado vem de /portal/visao-geral/,
   que consolida as três origens de medição no servidor.
   ========================================================================== */

type Filtro = "todos" | "atencao" | "sem-medicao";

export default function PortalEquipamentosPage() {
  useRegistrarVisita("equipamentos");
  const toast = useToast();
  const parametros = useSearchParams();
  const { pode } = usePermissoes();
  const podeGerenciar = pode("parque:gerenciar");
  const [busca, setBusca] = useState("");
  const [filtro, setFiltro] = useState<Filtro>(
    parametros?.get("estado") === "critico" ? "atencao" : "todos"
  );

  const lista = useLista<Equipamento>("/equipamentos/?page_size=500", "equipamentos do portal");
  const visao = useRecurso<PortalVisaoGeral>("/portal/visao-geral/", "estado dos equipamentos");
  const mutacao = useMutacao("remoção de equipamento");
  const remocao = useConfirmacao<Equipamento>();

  async function remover(eq: Equipamento) {
    const r = await mutacao.executar(() => api(`/equipamentos/${eq.id}/`, { method: "DELETE" }));
    if (r.ok) {
      toast.sucesso(`${eq.tag} removido`);
      lista.recarregar();
    } else {
      toast.erro(r.falha.titulo, { descricao: r.falha.descricao });
    }
  }

  const estados = visao.dados?.estado_equipamentos ?? {};
  const carregando = lista.carregando || visao.carregando;

  const comEstado = useMemo(
    () =>
      lista.itens.map((e) => {
        const estado: EstadoEquipamento | undefined = estados[e.tag];
        const grau: GrauMonitoramento =
          !estado || estado.medicoes === 0 ? "SEM_DADOS" : grauDe(estado.criticidade);
        return { equipamento: e, estado, grau };
      }),
    [lista.itens, estados]
  );

  const filtrados = useMemo(() => {
    const base =
      filtro === "atencao"
        ? comEstado.filter((l) => l.grau === "CRITICO" || l.grau === "ALERTA")
        : filtro === "sem-medicao"
        ? comEstado.filter((l) => l.grau === "SEM_DADOS")
        : comEstado;
    // Gravidade primeiro; dentro do mesmo grau, ordem natural da TAG.
    return [...base].sort(
      (a, b) =>
        pesoGravidade(a.grau) - pesoGravidade(b.grau) ||
        a.equipamento.tag.localeCompare(b.equipamento.tag, "pt-BR", { numeric: true })
    );
  }, [comEstado, filtro]);

  const totais = useMemo(() => {
    const conta = (g: GrauMonitoramento[]) => comEstado.filter((l) => g.includes(l.grau)).length;
    return {
      total: comEstado.length,
      intervencao: conta(["CRITICO"]),
      atencao: conta(["ALERTA"]),
      semMedicao: conta(["SEM_DADOS"]),
    };
  }, [comEstado]);

  type Linha = (typeof filtrados)[number];

  const colunas: Coluna<Linha>[] = [
    {
      chave: "tag",
      header: "TAG",
      mobile: "titulo",
      tecnico: true,
      valor: (l) => l.equipamento.tag,
      celula: (l) => (
        <span
          className="inline-flex items-center gap-1.5 font-semibold text-fg"
          style={{ paddingLeft: `${l.equipamento.nivel * 12}px` }}
        >
          {l.equipamento.is_subitem && (
            <CornerDownRight className="h-3 w-3 shrink-0 text-fg-subtle" aria-hidden="true" />
          )}
          {l.equipamento.tag}
        </span>
      ),
    },
    {
      chave: "estado",
      header: "Estado",
      mobile: "meta",
      valor: (l) => pesoGravidade(l.grau),
      celula: (l) => <EstadoBadge grau={l.grau} mostrarSignificado />,
    },
    {
      chave: "nome",
      header: "Equipamento",
      mobile: "subtitulo",
      valor: (l) => l.equipamento.nome,
      celula: (l) => (
        <span className="text-fg">
          {l.equipamento.nome}
          {l.equipamento.qtd_subitens > 0 && (
            <Badge tone="neutral" className="ml-2">
              {plural(l.equipamento.qtd_subitens, "sub-item", "sub-itens")}
            </Badge>
          )}
        </span>
      ),
    },
    {
      chave: "local",
      header: "Local",
      mobile: "meta",
      valor: (l) => `${l.equipamento.area_nome} ${l.equipamento.setor_nome}`,
      celula: (l) => (
        <span className="text-fg-muted">
          {l.equipamento.area_nome ? (
            <>
              {l.equipamento.area_nome}
              <span className="text-fg-subtle"> · </span>
              {l.equipamento.setor_nome}
            </>
          ) : (
            <SemDado />
          )}
        </span>
      ),
    },
    {
      chave: "ultima",
      header: "Última medição",
      mobile: "meta",
      valor: (l) => l.estado?.ultima_medicao ?? "",
      celula: (l) =>
        l.estado?.ultima_medicao ? (
          <span className="data text-xs">{dataHora(l.estado.ultima_medicao)}</span>
        ) : (
          <SemDado>Aguardando coleta</SemDado>
        ),
    },
    {
      chave: "classe",
      header: "Classe",
      mobile: "oculta",
      alinhamento: "centro",
      valor: (l) => l.equipamento.criticidade,
      celula: (l) => (
        <ClasseAtivoBadge value={l.equipamento.criticidade} label={l.equipamento.criticidade_display} />
      ),
    },
  ];

  return (
    <PageBody>
      <PageHeader
        icon={Activity}
        title="Meus equipamentos"
        description="O parque monitorado pela ThermoProActive, com o estado apurado na última coleta de cada máquina. Os equipamentos que exigem decisão aparecem no topo."
        trilha={[{ label: "Meus equipamentos" }]}
        actions={
          podeGerenciar ? (
            <Link href="/portal/equipamentos/novo">
              <Button icon={Plus}>Novo equipamento</Button>
            </Link>
          ) : undefined
        }
      />

      <MetricGrid colunas={4}>
        <MetricCard label="Equipamentos monitorados" value={totais.total} icon={Boxes} />
        <MetricCard
          label="Intervenção imediata"
          value={totais.intervencao}
          tone={totais.intervencao > 0 ? "danger" : "success"}
          contexto={totais.intervencao > 0 ? "acima do limite crítico" : "nenhum"}
        />
        <MetricCard
          label="Programar intervenção"
          value={totais.atencao}
          tone={totais.atencao > 0 ? "warning" : "neutral"}
          contexto={totais.atencao > 0 ? "acima do aceitável" : "nenhum"}
        />
        <MetricCard
          label="Sem medição ainda"
          value={totais.semMedicao}
          contexto="cadastrados, aguardando 1ª coleta"
        />
      </MetricGrid>

      <Toolbar
        busca={
          <SearchInput
            value={busca}
            onChange={setBusca}
            label="Buscar equipamento"
            placeholder="TAG, nome, fabricante, nº de série…"
          />
        }
        filtros={
          <SegmentedControl
            label="Filtrar por estado"
            tamanho="sm"
            valor={filtro}
            onMudar={setFiltro}
            opcoes={[
              { valor: "todos", label: "Todos" },
              { valor: "atencao", label: "Exigem ação" },
              { valor: "sem-medicao", label: "Sem medição" },
            ]}
          />
        }
        resumo={
          <span className="flex flex-wrap items-center gap-x-4 gap-y-1">
            <span>
              {filtrados.length === totais.total
                ? plural(totais.total, "equipamento")
                : `${filtrados.length} de ${totais.total} equipamentos`}
            </span>
            <LegendaEstados graus={["NORMAL", "ALERTA", "CRITICO", "SEM_DADOS"]} className="hidden xl:flex" />
          </span>
        }
      />

      <DataTable<Linha>
        itens={filtrados}
        colunas={colunas}
        getId={(l) => l.equipamento.id}
        busca={busca}
        camposBusca={(l) => [
          l.equipamento.fabricante,
          l.equipamento.modelo,
          l.equipamento.numero_serie,
          l.equipamento.tipo_equipamento_nome,
        ]}
        carregando={carregando}
        falha={lista.falha ?? visao.falha}
        onRetry={() => {
          lista.recarregar();
          visao.recarregar();
        }}
        tomDaLinha={(l) => (l.grau === "CRITICO" ? "danger" : undefined)}
        legenda="Equipamentos monitorados, com estado, localização e data da última medição"
        porPagina={15}
        acoes={
          podeGerenciar
            ? (l): ItemMenu[] => [
                {
                  label: "Editar",
                  icon: Pencil,
                  href: `/portal/equipamentos/editar/${l.equipamento.id}`,
                },
                {
                  label: "Remover",
                  icon: Trash2,
                  destrutivo: true,
                  onClick: () => remocao.pedir(l.equipamento),
                },
              ]
            : undefined
        }
        vazio={
          filtro !== "todos" ? (
            <EmptyState
              compacto
              icon={Activity}
              title={
                filtro === "atencao"
                  ? "Nenhum equipamento exige ação agora"
                  : "Todos os equipamentos já têm medição"
              }
              description={
                filtro === "atencao"
                  ? "Nenhuma máquina do seu parque está acima dos limites das normas na última coleta."
                  : "Todo o parque cadastrado já passou por pelo menos uma coleta."
              }
            />
          ) : (
            <EmptyState
              icon={Activity}
              title="Seu parque ainda não foi cadastrado"
              description={
                podeGerenciar
                  ? "Cadastre o primeiro equipamento, ou peça para a equipe técnica levantar o parque durante a próxima visita."
                  : "Os equipamentos são cadastrados pela equipe técnica no início do contrato, a partir do levantamento em campo, ou pelo Master da sua empresa."
              }
              action={
                podeGerenciar ? (
                  <Link href="/portal/equipamentos/novo">
                    <Button icon={Plus}>Cadastrar equipamento</Button>
                  </Link>
                ) : undefined
              }
              comoFunciona={[
                "A equipe faz o levantamento dos ativos na sua planta.",
                "Cada equipamento entra no sistema com TAG, área, setor e dados de placa.",
                "As rotas de inspeção são montadas e a coleta começa.",
              ]}
            />
          )
        }
      />

      <ConfirmDialog
        aberto={!!remocao.alvo}
        onFechar={remocao.cancelar}
        onConfirmar={() => remocao.executar(remover)}
        enviando={remocao.enviando}
        title="Remover este equipamento?"
        confirmarLabel="Remover"
        mensagem={
          <>
            <strong>{remocao.alvo?.tag}</strong> — {remocao.alvo?.nome} sai do seu parque
            monitorado.
          </>
        }
        detalhe="O histórico de medições e laudos já emitidos não é apagado."
        irreversivel
      />
    </PageBody>
  );
}
