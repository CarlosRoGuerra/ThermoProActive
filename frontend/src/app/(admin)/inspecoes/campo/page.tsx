"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ClipboardList, Plus, Send, TriangleAlert, Wrench } from "lucide-react";
import {
  Button,
  EmptyState,
  ErrorCard,
  Field,
  LoadingState,
  MetricCard,
  MetricGrid,
  PageBody,
  PageHeader,
  SearchInput,
  SegmentedControl,
  Select,
  Toolbar,
} from "@/components/ds";
import { useLista } from "@/lib/recurso";
import { useClienteAtivo } from "@/lib/cliente-ativo";
import { usePermissoes } from "@/lib/permissions";
import { normalizar, plural } from "@/lib/format";
import { ExigeClienteAtivo } from "@/features/clientes/exige-cliente-ativo";
import { CartaoAnalise } from "@/features/inspecoes/campo/cartao-analise";
import {
  ROTULO_VISAO,
  progressoDaLista,
  visaoDoCarregamento,
  type VisaoCampo,
} from "@/features/inspecoes/campo/progresso";
import type { CarregamentoLista } from "@/lib/types";

type Tecnologia = { id: number; nome: string };

/* ==========================================================================
   Central de Análise de Campo
   --------------------------------------------------------------------------
   A tela que o técnico abre ao chegar no cliente. Responde, nesta ordem:
     1. tenho rota travada por falta de condição?
     2. tem rota pronta para transferir ao escritório?
     3. onde eu parei?

   Por isso a lista é de CARTÕES com barra de progresso, e não uma tabela: o uso
   real é no celular, dentro da planta, e uma tabela de 11 colunas a 375px vira
   rolagem horizontal.

   As visões (Em andamento / Não iniciadas / Prontas para transferir /
   Transferidas) são recortes de UX sobre o status real do banco
   (EM_CAMPO · TRANSFERIDA · DESCARTADA) — não são status novos.

   As contagens vêm ANOTADAS pelo servidor, numa consulta para a página inteira:
   a tela não busca os itens de cada rota só para contá-los.
   ========================================================================== */

export default function AnaliseCampoPage() {
  const { podeEditar } = usePermissoes();
  const { clienteAtivo } = useClienteAtivo();

  const [visao, setVisao] = useState<VisaoCampo>("em_andamento");
  const [busca, setBusca] = useState("");
  const [tecFiltro, setTecFiltro] = useState("");

  const tecnologias = useLista<Tecnologia>("/tecnologias-analise/?page_size=500", "tecnologias");
  const lista = useLista<CarregamentoLista>(
    clienteAtivo
      ? `/carregamentos/?cliente=${clienteAtivo.id}&ordering=-data_coleta&page_size=300`
      : null,
    "análises de campo"
  );

  const porVisao = useMemo(() => {
    const mapa: Record<VisaoCampo, CarregamentoLista[]> = {
      em_andamento: [],
      nao_iniciadas: [],
      concluidas: [],
      transferidas: [],
    };
    for (const c of lista.itens) mapa[visaoDoCarregamento(c)].push(c);
    return mapa;
  }, [lista.itens]);

  // Abre na visão que tem trabalho — quem entra quer continuar de onde parou.
  // Só na primeira carga; depois a escolha é do usuário.
  const [visaoDefinida, setVisaoDefinida] = useState(false);
  useEffect(() => {
    if (lista.carregando || visaoDefinida) return;
    if (porVisao.em_andamento.length) setVisao("em_andamento");
    else if (porVisao.concluidas.length) setVisao("concluidas");
    else if (porVisao.nao_iniciadas.length) setVisao("nao_iniciadas");
    else if (porVisao.transferidas.length) setVisao("transferidas");
    setVisaoDefinida(true);
  }, [lista.carregando, visaoDefinida, porVisao]);

  const visiveis = useMemo(() => {
    const q = normalizar(busca).trim();
    return porVisao[visao].filter((c) => {
      if (tecFiltro && String(c.tecnologia) !== tecFiltro) return false;
      if (!q) return true;
      return normalizar(
        [c.numero, c.rota_nome, c.analista_nome, c.tecnologia_nome, c.cliente_nome].join(" ")
      ).includes(q);
    });
  }, [porVisao, visao, tecFiltro, busca]);

  // Indicadores: cada um responde a uma decisão. Nenhum é enfeite.
  const indicadores = useMemo(() => {
    const emCampo = lista.itens.filter((c) => c.status === "EM_CAMPO");
    return {
      emCampo: emCampo.length,
      pendentes: emCampo.reduce((s, c) => s + (c.qtd_pendentes ?? 0), 0),
      achados: emCampo.reduce((s, c) => s + (c.qtd_achados ?? 0), 0),
      analisados: emCampo.reduce((s, c) => s + progressoDaLista(c).concluidos, 0),
      prontas: porVisao.concluidas.length,
    };
  }, [lista.itens, porVisao.concluidas.length]);

  const opcoesVisao = (["em_andamento", "nao_iniciadas", "concluidas", "transferidas"] as const).map(
    (v) => ({ valor: v, label: `${ROTULO_VISAO[v]} (${porVisao[v].length})` })
  );

  return (
    <PageBody>
      <PageHeader
        icon={ClipboardList}
        title="Análise de campo"
        description="Gerencie coletas, rotas e inspeções em andamento. Registre a condição de cada equipamento e transfira a rota ao escritório quando terminar."
        trilha={[{ label: "Inspeções" }, { label: "Análise de campo" }]}
        actions={
          podeEditar && clienteAtivo ? (
            <Link href="/inspecoes/campo/nova">
              <Button icon={Plus}>Carregar rota</Button>
            </Link>
          ) : undefined
        }
      />

      {!clienteAtivo ? (
        <ExigeClienteAtivo oQue="As rotas de coleta" />
      ) : (
        <>
          <MetricGrid colunas={4}>
            <MetricCard
              label="Análises em campo"
              value={indicadores.emCampo}
              icon={ClipboardList}
              contexto={`${plural(indicadores.analisados, "equipamento")} já registrados`}
            />
            <MetricCard
              label="Equipamentos pendentes"
              value={indicadores.pendentes}
              tone={indicadores.pendentes > 0 ? "warning" : "success"}
              icon={TriangleAlert}
              contexto={
                indicadores.pendentes > 0
                  ? "sem condição — travam a transferência"
                  : "nenhuma pendência"
              }
              dica="A rota só pode ser transferida quando todos os equipamentos dela têm condição informada."
            />
            <MetricCard
              label="Achados registrados"
              value={indicadores.achados}
              icon={Wrench}
              contexto="nas rotas ainda em campo"
            />
            <MetricCard
              label="Prontas para transferir"
              value={indicadores.prontas}
              tone={indicadores.prontas > 0 ? "success" : "neutral"}
              icon={Send}
              contexto={
                indicadores.prontas > 0
                  ? "aguardando envio ao escritório"
                  : "nenhuma completa ainda"
              }
            />
          </MetricGrid>

          <Toolbar
            busca={
              <SearchInput
                value={busca}
                onChange={setBusca}
                label="Buscar análise de campo"
                placeholder="Relatório, rota, analista…"
              />
            }
            filtros={
              <div className="w-56">
                <Field label="Tecnologia">
                  <Select value={tecFiltro} onChange={(e) => setTecFiltro(e.target.value)}>
                    <option value="">Todas as tecnologias</option>
                    {tecnologias.itens.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.nome}
                      </option>
                    ))}
                  </Select>
                </Field>
              </div>
            }
          />

          <div className="-mt-1 overflow-x-auto pb-1">
            <SegmentedControl
              label="Situação das análises"
              tamanho="sm"
              valor={visao}
              onMudar={setVisao}
              opcoes={opcoesVisao}
            />
          </div>

          {lista.carregando ? (
            <LoadingState variante="cartoes" linhas={3} label="Carregando análises de campo…" />
          ) : lista.falha ? (
            <ErrorCard falha={lista.falha} onRetry={lista.recarregar} />
          ) : visiveis.length === 0 ? (
            <VazioDaVisao
              visao={visao}
              temAlguma={lista.itens.length > 0}
              filtrando={!!busca || !!tecFiltro}
              podeEditar={podeEditar}
            />
          ) : (
            <>
              <p className="text-xs text-fg-subtle">
                {plural(visiveis.length, "análise", "análises")} em{" "}
                {ROTULO_VISAO[visao].toLowerCase()}
              </p>
              <ul className="grid grid-cols-1 gap-3 xl:grid-cols-2">
                {visiveis.map((c) => (
                  <CartaoAnalise key={c.id} carregamento={c} />
                ))}
              </ul>
            </>
          )}
        </>
      )}
    </PageBody>
  );
}

function VazioDaVisao({
  visao,
  temAlguma,
  filtrando,
  podeEditar,
}: {
  visao: VisaoCampo;
  temAlguma: boolean;
  filtrando: boolean;
  podeEditar: boolean;
}) {
  if (filtrando) {
    return (
      <EmptyState
        compacto
        icon={ClipboardList}
        title="Nada corresponde aos filtros"
        description="Ajuste a busca ou a tecnologia para ver as análises desta visão."
      />
    );
  }

  if (temAlguma) {
    const textos: Record<VisaoCampo, string> = {
      em_andamento: "Nenhuma rota em andamento no momento.",
      nao_iniciadas: "Todas as rotas carregadas já têm pelo menos um equipamento registrado.",
      concluidas: "Nenhuma rota pronta para transferir — ainda há equipamentos sem condição.",
      transferidas: "Nenhuma rota transferida para o escritório ainda.",
    };
    return (
      <EmptyState
        compacto
        icon={ClipboardList}
        title={ROTULO_VISAO[visao]}
        description={textos[visao]}
      />
    );
  }

  return (
    <EmptyState
      icon={ClipboardList}
      title="Nenhuma rota carregada para este cliente"
      description="Carregar uma rota cria a folha de campo com os equipamentos dela, pronta para registrar as condições."
      action={
        podeEditar ? (
          <Link href="/inspecoes/campo/nova">
            <Button icon={Plus}>Carregar rota</Button>
          </Link>
        ) : undefined
      }
      comoFunciona={[
        "Escolha o relatório (novo número ou existente), a rota e o instrumento.",
        "Percorra os equipamentos registrando a condição e as análises necessárias.",
        "Transfira a rota — o que exige ação segue para a Análise final.",
      ]}
    />
  );
}
