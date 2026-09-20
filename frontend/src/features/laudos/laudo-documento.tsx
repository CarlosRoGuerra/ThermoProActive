"use client";

import { CircleCheck, FileText, Printer } from "lucide-react";
import Link from "next/link";
import {
  Alert,
  Badge,
  Button,
  Card,
  CriticidadeBadge,
  DescriptionList,
  ErrorCard,
  LoadingState,
  Logo,
  PageBody,
  PageHeader,
  SemDado,
} from "@/components/ds";
import { useRecurso } from "@/lib/recurso";
import { dataHora, texto } from "@/lib/format";
import type { Laudo } from "@/lib/types";

/* ==========================================================================
   Documento do laudo — compartilhado pelos dois portais.
   --------------------------------------------------------------------------
   A equipe interna abre em /laudos/:id (e pode emitir); o cliente abre em
   /portal/laudos/:id (só leitura). O documento é o MESMO — o que muda são as
   ações no topo. Antes esta marcação vivia dentro da página de admin e o
   cliente não tinha como ver o laudo depois da separação dos portais.
   ========================================================================== */

export function LaudoDocumento({
  laudoId,
  /** Rota do Relatório Técnico completo. Sem ela, o botão não aparece. */
  relatorioHref,
  /** Ações específicas da área (ex.: "Emitir laudo" no portal interno). */
  acoes,
  trilha,
  /** Aviso extra no topo (ex.: rascunho não vale como documento). */
  aviso,
  laudo: laudoExterno,
}: {
  laudoId: string | number;
  relatorioHref?: string;
  acoes?: React.ReactNode;
  trilha?: { label: string; href?: string }[];
  aviso?: React.ReactNode;
  /** Quando quem chama já tem o laudo carregado (evita buscar de novo). */
  laudo?: Laudo | null;
}) {
  const recurso = useRecurso<Laudo>(
    laudoExterno ? null : `/laudos/${laudoId}/`,
    "laudo técnico"
  );
  const laudo = laudoExterno ?? recurso.dados;

  if (!laudoExterno && recurso.carregando) return <LoadingState variante="texto" linhas={8} />;
  if (!laudoExterno && recurso.falha)
    return <ErrorCard falha={recurso.falha} onRetry={recurso.recarregar} />;
  if (!laudo) return null;

  const emitido = laudo.status === "EMITIDO";

  return (
    <PageBody>
      <div className="no-print">
        <PageHeader
          title={`Laudo ${laudo.numero}`}
          description={laudo.titulo}
          icon={FileText}
          trilha={trilha}
          selo={
            <Badge tone={emitido ? "success" : "warning"} icon={emitido ? CircleCheck : undefined}>
              {laudo.status_display}
            </Badge>
          }
          actions={
            <>
              <Button variant="secondary" icon={Printer} onClick={() => window.print()}>
                Imprimir / PDF
              </Button>
              {relatorioHref && (
                <Link href={relatorioHref}>
                  <Button variant="secondary" icon={FileText}>
                    Relatório completo
                  </Button>
                </Link>
              )}
              {acoes}
            </>
          }
        />
      </div>

      {aviso}
      {!emitido && (
        <div className="no-print">
          <Alert tone="warning" title="Este laudo ainda é um rascunho">
            O documento só tem validade técnica depois de emitido e assinado pelo responsável.
          </Alert>
        </div>
      )}

      {/* --- Área imprimível --- */}
      <Card className="p-6 sm:p-8">
        <header className="flex flex-wrap items-start justify-between gap-4 border-b border-border pb-5">
          <Logo tamanho="lg" mostrarDescritor={false} />
          <div className="text-right text-sm">
            <p className="data font-semibold text-fg">{laudo.numero}</p>
            <p className="text-xs text-fg-subtle">Versão {laudo.versao}</p>
          </div>
        </header>

        <div className="mt-6">
          <DescriptionList
            colunas={2}
            items={[
              { label: "Título", value: texto(laudo.titulo) },
              { label: "Cliente", value: texto(laudo.cliente_nome) },
              {
                label: "Criticidade geral",
                value: laudo.criticidade_geral ? (
                  <CriticidadeBadge value={laudo.criticidade_geral} />
                ) : (
                  <SemDado />
                ),
              },
              {
                label: "Emissão",
                value: laudo.data_emissao ? dataHora(laudo.data_emissao) : <SemDado>Não emitido</SemDado>,
                tecnico: true,
              },
            ]}
          />
        </div>

        <Secao titulo="Diagnóstico técnico">{laudo.diagnostico}</Secao>
        <Secao titulo="Recomendações">{laudo.recomendacoes}</Secao>
        <Secao titulo="Conclusão">{laudo.conclusao}</Secao>

        <footer className="mt-12 border-t border-border pt-6">
          <div className="inline-block border-t border-border-strong px-10 pt-1.5 text-center">
            <p className="text-sm font-semibold text-fg">{texto(laudo.responsavel_nome)}</p>
            <p className="text-xs text-fg-muted">
              Responsável técnico
              {laudo.responsavel_conselho ? ` — ${laudo.responsavel_conselho}` : ""}
            </p>
          </div>
        </footer>
      </Card>
    </PageBody>
  );
}

function Secao({ titulo, children }: { titulo: string; children?: string }) {
  return (
    <section className="mt-6">
      <h2 className="mb-2 text-2xs font-semibold uppercase tracking-wide text-primary">{titulo}</h2>
      {children ? (
        <p className="whitespace-pre-line text-sm leading-relaxed text-fg">{children}</p>
      ) : (
        <p className="text-sm text-fg-subtle">Sem conteúdo registrado nesta seção.</p>
      )}
    </section>
  );
}
