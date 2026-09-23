"use client";

import {
  ArrowRight,
  CheckCircle2,
  ChevronRight,
  ClipboardCheck,
  Send,
  TriangleAlert,
} from "lucide-react";
import {
  Alert,
  Badge,
  Button,
  Card,
  CardHeader,
  DescriptionList,
  SemDado,
  cn,
} from "@/components/ds";
import { data as fmtData, plural, texto } from "@/lib/format";
import type { Carregamento, ItemInspecao } from "@/lib/types";
import { proximoPendente } from "./navegador-equipamentos";
import { ROTULO_ESTADO, estadoDoItem, progressoDosItens } from "./progresso";

/* ==========================================================================
   Revisão e transferência.
   --------------------------------------------------------------------------
   A transferência é a passagem de bastão campo → escritório: depois dela a
   rota sai do celular do técnico e entra na fila da Análise final. Então esta
   tela existe para responder uma pergunta só: "posso transferir, e o que vai
   junto?".

   A regra de bloqueio é a do backend (`Carregamento.pode_transferir`: nenhum
   item sem condição). O que listamos como "atenção" — condição que exige ação
   sem nenhuma análise — NÃO bloqueia no servidor, e por isso aparece como
   aviso, não como impedimento. Inventar um bloqueio que o backend não tem
   deixaria a tela mentindo.
   ========================================================================== */

export function PainelPendencias({
  carregamento,
  itens,
  podeEditar,
  transferindo,
  onTransferir,
  onSelecionar,
}: {
  carregamento: Carregamento;
  itens: ItemInspecao[];
  podeEditar: boolean;
  transferindo: boolean;
  onTransferir: () => void;
  onSelecionar: (item: ItemInspecao) => void;
}) {
  const p = progressoDosItens(itens);
  const semCondicao = itens.filter((i) => estadoDoItem(i) === "PENDENTE");
  const semAnalise = itens.filter((i) => estadoDoItem(i) === "INCOMPLETO");
  const transferida = carregamento.status !== "EM_CAMPO";
  const liberada = semCondicao.length === 0 && itens.length > 0;
  const faltam = semCondicao.length + semAnalise.length;
  const proximo = proximoPendente(itens, null);

  return (
    <div className="space-y-4">
      {/* Esta é a tela de entrada da rota: o primeiro gesto é voltar ao trabalho.
          Fundo em vez de `Card tom`: as bordas com opacidade (border-primary/35)
          não são geradas sobre cores em var(--…) e o card sairia com borda cinza. */}
      {podeEditar && !transferida && proximo && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-primary-subtle px-4 py-3.5 shadow-xs sm:px-5">
          <div className="min-w-0">
            <p className="text-sm font-semibold text-fg">
              {faltam === 1 ? "Falta" : "Faltam"} {plural(faltam, "equipamento")}
            </p>
            <p className="truncate text-xs text-fg-muted">
              {p.concluidos === 0 ? "Comece por" : "Continue de onde parou:"}{" "}
              <span className="data font-medium text-fg">{proximo.equipamento_tag}</span> —{" "}
              {proximo.equipamento_nome}
            </p>
          </div>
          <Button iconRight={ChevronRight} onClick={() => onSelecionar(proximo)}>
            {p.concluidos === 0 ? "Começar" : "Continuar"}
          </Button>
        </div>
      )}

      <Card>
        <CardHeader
          title="Resumo desta coleta"
          description="O que segue para o escritório junto com a rota."
        />
        <DescriptionList
          colunas={3}
          items={[
            {
              label: "Relatório",
              value: carregamento.numero || <SemDado>Sem número</SemDado>,
              tecnico: true,
            },
            { label: "Rota", value: carregamento.rota_nome || <SemDado>Rota avulsa</SemDado> },
            { label: "Tecnologia", value: texto(carregamento.tecnologia_nome) },
            { label: "Analista", value: texto(carregamento.analista_nome) },
            {
              label: "Instrumento",
              value: carregamento.instrumento_nome || <SemDado />,
            },
            {
              label: "Data da coleta",
              value: fmtData(carregamento.data_coleta),
              tecnico: true,
            },
          ]}
        />
      </Card>

      {/* Balanço da rota — números derivados dos itens já carregados. */}
      <Card>
        <CardHeader title="Balanço da rota" />
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Placar label="Equipamentos" valor={p.total} />
          <Placar
            label="Com condição"
            valor={p.concluidos}
            tom={p.concluidos === p.total ? "success" : "warning"}
          />
          <Placar label="Com achado" valor={p.comAchado} tom={p.comAchado > 0 ? "danger" : "neutral"} />
          <Placar label="Análises registradas" valor={p.achados} />
        </div>
      </Card>

      {/* Pendências */}
      <Card>
        <CardHeader
          title="Pendências"
          description="O que ainda depende de você antes de encerrar a coleta."
        />

        {itens.length === 0 ? (
          <Alert tone="warning" icon={TriangleAlert} title="Esta rota não trouxe equipamentos">
            Sem equipamentos não há o que transferir. Verifique se a rota tem equipamentos
            selecionados no cadastro.
          </Alert>
        ) : semCondicao.length === 0 && semAnalise.length === 0 ? (
          <Alert tone="success" icon={CheckCircle2} title="Nenhuma pendência">
            Todos os equipamentos têm condição registrada e as condições que exigem ação já têm
            análise.
          </Alert>
        ) : (
          <div className="space-y-4">
            {semCondicao.length > 0 && (
              <ListaPendencia
                tom="danger"
                titulo={`${plural(semCondicao.length, "equipamento")} sem condição`}
                explicacao="Bloqueia a transferência: a condição é o registro de que o equipamento foi inspecionado."
                itens={semCondicao}
                onSelecionar={onSelecionar}
              />
            )}
            {semAnalise.length > 0 && (
              <ListaPendencia
                tom="warning"
                titulo={`${plural(semAnalise.length, "equipamento")} sem a análise que a condição pede`}
                explicacao="Não bloqueia a transferência, mas sem análise o equipamento não gera achado, OSP nem folha no relatório técnico."
                itens={semAnalise}
                onSelecionar={onSelecionar}
              />
            )}
          </div>
        )}
      </Card>

      {/* Transferência */}
      {!transferida && (
        <Card tom={liberada ? "success" : "neutral"}>
          <CardHeader
            title="Transferir para o escritório"
            description="Encerra a coleta em campo e abre a rota para a Análise final."
          />
          <ol className="mb-4 space-y-1.5 text-sm text-fg-muted">
            <li className="flex gap-2">
              <ArrowRight className="mt-0.5 h-3.5 w-3.5 shrink-0 text-fg-subtle" aria-hidden="true" />
              A rota passa a <strong className="font-medium text-fg">Transferida</strong> e deixa de
              aceitar edição em campo.
            </li>
            <li className="flex gap-2">
              <ArrowRight className="mt-0.5 h-3.5 w-3.5 shrink-0 text-fg-subtle" aria-hidden="true" />
              Os achados entram na <strong className="font-medium text-fg">Análise final</strong>,
              onde são revisados, confirmados e viram ordem de serviço.
            </li>
            <li className="flex gap-2">
              <ArrowRight className="mt-0.5 h-3.5 w-3.5 shrink-0 text-fg-subtle" aria-hidden="true" />
              Só depois de confirmados eles aparecem no{" "}
              <strong className="font-medium text-fg">relatório técnico</strong> e no portal do
              cliente.
            </li>
          </ol>

          {!liberada && semCondicao.length > 0 && (
            <div className="mb-3">
              <Alert tone="warning">
                Falta a condição de {plural(semCondicao.length, "equipamento")}. A transferência é
                liberada quando todos estiverem registrados.
              </Alert>
            </div>
          )}

          <Button
            icon={Send}
            onClick={onTransferir}
            loading={transferindo}
            disabled={!podeEditar || !liberada}
            title={
              !liberada
                ? "Preencha a condição de todos os equipamentos para liberar a transferência"
                : undefined
            }
          >
            Transferir para o escritório
          </Button>
        </Card>
      )}

      {transferida && (
        <Alert tone="info" icon={ClipboardCheck} title={`Rota ${carregamento.status_display}`}>
          {carregamento.transferido_em
            ? `Transferida em ${fmtData(carregamento.transferido_em)}. `
            : ""}
          A edição em campo está encerrada — o trabalho continua na Análise final.
        </Alert>
      )}
    </div>
  );
}

function Placar({
  label,
  valor,
  tom = "neutral",
}: {
  label: string;
  valor: number;
  tom?: "neutral" | "success" | "warning" | "danger";
}) {
  return (
    <div className="rounded-lg bg-surface-muted/60 px-3 py-2.5">
      <p
        className={cn(
          "data text-xl font-semibold",
          tom === "success" && "text-success-fg",
          tom === "warning" && "text-warning-fg",
          tom === "danger" && "text-danger-fg",
          tom === "neutral" && "text-fg"
        )}
      >
        {valor}
      </p>
      <p className="mt-0.5 text-2xs uppercase tracking-wide text-fg-subtle">{label}</p>
    </div>
  );
}

function ListaPendencia({
  tom,
  titulo,
  explicacao,
  itens,
  onSelecionar,
}: {
  tom: "danger" | "warning";
  titulo: string;
  explicacao: string;
  itens: ItemInspecao[];
  onSelecionar: (item: ItemInspecao) => void;
}) {
  return (
    <div>
      <div className="mb-2 flex items-start gap-2">
        <TriangleAlert
          className={cn(
            "mt-0.5 h-4 w-4 shrink-0",
            tom === "danger" ? "text-danger" : "text-warning"
          )}
          aria-hidden="true"
        />
        <div>
          <p className="text-sm font-medium text-fg">{titulo}</p>
          <p className="text-xs text-fg-muted">{explicacao}</p>
        </div>
      </div>
      <ul className="divide-y divide-border overflow-hidden rounded-lg border border-border">
        {itens.map((item) => (
          <li key={item.id}>
            {/* Clicar leva direto ao equipamento: pendência sem atalho é lista de reclamação. */}
            <button
              type="button"
              onClick={() => onSelecionar(item)}
              className="flex w-full items-center justify-between gap-3 px-3 py-2.5 text-left transition-colors hover:bg-surface-muted"
            >
              <span className="min-w-0">
                <span className="data block truncate text-sm font-medium text-fg">
                  {item.equipamento_tag}
                </span>
                <span className="block truncate text-xs text-fg-muted">
                  {item.equipamento_nome} · {item.area_nome} / {item.setor_nome}
                </span>
              </span>
              <span className="flex shrink-0 items-center gap-1.5">
                <Badge tone={tom}>{ROTULO_ESTADO[estadoDoItem(item)]}</Badge>
                <ChevronRight className="h-4 w-4 text-fg-subtle" aria-hidden="true" />
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
