"use client";

import Link from "next/link";
import {
  CalendarDays,
  ChevronRight,
  ClipboardCheck,
  Map,
  Send,
  TriangleAlert,
  User,
} from "lucide-react";
import { Badge, Button, Card, ProgressBar, SemDado, cn } from "@/components/ds";
import { data as fmtData, plural, texto } from "@/lib/format";
import type { CarregamentoLista } from "@/lib/types";
import { progressoDaLista, visaoDoCarregamento } from "./progresso";

/**
 * Uma análise de campo na listagem.
 *
 * Cartão, não linha de tabela: o técnico abre isto no celular, dentro da planta,
 * e precisa bater o olho no progresso e tocar em "Continuar". Uma tabela de 11
 * colunas não sobrevive a 375px — viraria rolagem horizontal, que é justamente
 * o que a folha de campo não pode ter.
 */
export function CartaoAnalise({ carregamento }: { carregamento: CarregamentoLista }) {
  const p = progressoDaLista(carregamento);
  const visao = visaoDoCarregamento(carregamento);
  const emCampo = carregamento.status === "EM_CAMPO";
  const prontaParaTransferir = visao === "concluidas";

  const tom = prontaParaTransferir ? "success" : "neutral";

  return (
    <Card as="li" padding={false} tom={tom} className="overflow-hidden">
      <div className="p-4 sm:p-5">
        {/* Identificação */}
        <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
          <div className="min-w-0">
            <p className="data text-sm font-semibold text-fg">
              {carregamento.numero || `Carregamento #${carregamento.id}`}
            </p>
            <p className="mt-0.5 truncate text-sm text-fg-muted">
              {texto(carregamento.cliente_nome)}
            </p>
          </div>
          <div className="flex shrink-0 flex-wrap items-center gap-1.5">
            <Badge tone="primary">{carregamento.tecnologia_nome}</Badge>
            {carregamento.tipo_corretiva && <Badge tone="warning">Corretiva</Badge>}
            {prontaParaTransferir ? (
              <Badge tone="success" icon={Send}>
                Pronta para transferir
              </Badge>
            ) : emCampo ? (
              <Badge tone="warning">Em campo</Badge>
            ) : (
              <Badge tone="neutral">{carregamento.status_display}</Badge>
            )}
          </div>
        </div>

        {/* Contexto da coleta */}
        <dl className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-1.5 text-xs text-fg-muted">
          <div className="inline-flex items-center gap-1.5">
            <Map className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            <dt className="sr-only">Rota</dt>
            <dd>{carregamento.rota_nome || <SemDado>Rota avulsa</SemDado>}</dd>
          </div>
          <div className="inline-flex items-center gap-1.5">
            <User className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            <dt className="sr-only">Analista</dt>
            <dd>{texto(carregamento.analista_nome)}</dd>
          </div>
          <div className="inline-flex items-center gap-1.5">
            <CalendarDays className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            <dt className="sr-only">Data da coleta</dt>
            <dd className="data">{fmtData(carregamento.data_coleta)}</dd>
          </div>
          {p.achados > 0 && (
            <div className="inline-flex items-center gap-1.5">
              <ClipboardCheck className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
              <dt className="sr-only">Análises registradas</dt>
              <dd>{plural(p.achados, "achado")}</dd>
            </div>
          )}
        </dl>

        {/* Progresso — a informação que decide se dá para transferir */}
        <div className="mt-4">
          <div className="mb-1.5 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
            <span className="text-xs text-fg-muted">
              <span className="data font-semibold text-fg">
                {p.concluidos}/{p.total}
              </span>{" "}
              equipamentos concluídos
            </span>
            <span
              className={cn(
                "text-xs font-semibold",
                p.percentual === 100 ? "text-success-fg" : "text-fg-muted"
              )}
            >
              {p.percentual}%
            </span>
          </div>
          <ProgressBar
            valor={p.concluidos}
            max={Math.max(1, p.total)}
            label={`Progresso da análise ${carregamento.numero ?? carregamento.id}`}
          />
          {p.pendentes > 0 && emCampo && (
            <p className="mt-2 inline-flex items-center gap-1.5 text-xs text-warning-fg">
              <TriangleAlert className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
              {plural(p.pendentes, "equipamento")} sem condição definida
            </p>
          )}
        </div>
      </div>

      {/* Ação principal — alvo grande, o técnico está de luva */}
      <div className="border-t border-border bg-surface-muted/40 px-4 py-3 sm:px-5">
        <Link href={`/inspecoes/campo/${carregamento.id}`} className="block">
          <Button
            block
            variant={emCampo ? "primary" : "secondary"}
            iconRight={ChevronRight}
            className="sm:w-auto"
          >
            {emCampo ? "Continuar análise" : "Abrir folha de campo"}
          </Button>
        </Link>
      </div>
    </Card>
  );
}
