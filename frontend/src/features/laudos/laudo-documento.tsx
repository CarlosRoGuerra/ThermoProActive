"use client";

import { CircleCheck, Download, FileText, Printer } from "lucide-react";
import { useState } from "react";
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
import { downloadFile } from "@/lib/api";
import { dataHora, texto } from "@/lib/format";
import type { DocumentoLaudo, Laudo, ConfiguracaoTemplateLaudo } from "@/lib/types";

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
  antesDocumento,
  depoisDocumento,
  templatePrevia,
  alteracoesNaoSalvas = false,
  revisaoDocumento = 0,
}: {
  laudoId: string | number;
  relatorioHref?: string;
  acoes?: React.ReactNode;
  trilha?: { label: string; href?: string }[];
  aviso?: React.ReactNode;
  /** Quando quem chama já tem o laudo carregado (evita buscar de novo). */
  laudo?: Laudo | null;
  antesDocumento?: React.ReactNode;
  depoisDocumento?: React.ReactNode;
  templatePrevia?: { configuracao: Partial<ConfiguracaoTemplateLaudo> };
  alteracoesNaoSalvas?: boolean;
  revisaoDocumento?: number;
}) {
  const recurso = useRecurso<Laudo>(
    laudoExterno ? null : `/laudos/${laudoId}/`,
    "laudo técnico"
  );
  const laudo = laudoExterno ?? recurso.dados;
  const documento = useRecurso<DocumentoLaudo>(laudo ? `/laudos/${laudo.id}/documento/?revisao=${revisaoDocumento}` : null, "conteúdo do documento");
  const [baixando, setBaixando] = useState(false);
  const [erroDownload, setErroDownload] = useState("");

  if (!laudoExterno && recurso.carregando) return <LoadingState variante="texto" linhas={8} />;
  if (!laudoExterno && recurso.falha)
    return <ErrorCard falha={recurso.falha} onRetry={recurso.recarregar} />;
  if (!laudo) return null;

  const emitido = laudo.status === "EMITIDO";
  const cancelado = laudo.status === "CANCELADO";
  const assinatura = laudo.assinatura;
  const config = templatePrevia?.configuracao ?? documento.dados?.template.configuracao;

  async function baixarPdf() {
    setBaixando(true); setErroDownload("");
    try { await downloadFile(`/laudos/${laudo!.id}/pdf/`, `${laudo!.numero}_v${laudo!.versao}.pdf`); }
    catch (e) { setErroDownload(e instanceof Error ? e.message : "Não foi possível baixar o PDF."); }
    finally { setBaixando(false); }
  }

  return (
    <PageBody>
      <div className="no-print">
        <PageHeader
          title={`Laudo ${laudo.numero}`}
          description={laudo.titulo}
          icon={FileText}
          trilha={trilha}
          selo={
            <Badge tone={cancelado ? "danger" : emitido ? "success" : "warning"} icon={emitido ? CircleCheck : undefined}>
              {laudo.status_display}
            </Badge>
          }
          actions={
            <>
              <Button variant="secondary" icon={Printer} onClick={() => window.print()}>
                {emitido ? "Imprimir cópia" : "Imprimir prévia"}
              </Button>
              {laudo.pdf_disponivel && <Button variant="secondary" icon={Download} loading={baixando} onClick={baixarPdf}>Baixar PDF emitido</Button>}
              {relatorioHref && !emitido && !cancelado && (
                <Link href={relatorioHref}>
                  <Button variant="secondary" icon={FileText}>
                    Consultar fonte
                  </Button>
                </Link>
              )}
              {acoes}
            </>
          }
        />
      </div>

      {aviso}
      {erroDownload && <div className="no-print"><Alert tone="danger" title="Download indisponível">{erroDownload}</Alert></div>}
      {documento.falha && <div className="no-print"><Alert tone="warning" title="Conteúdo complementar indisponível">{documento.falha.descricao}<Button variant="link" onClick={documento.recarregar}>Tentar novamente</Button></Alert></div>}
      {emitido && !laudo.pdf_disponivel && <div className="no-print"><Alert tone="warning" title="PDF emitido indisponível">O arquivo não está disponível para download. A equipe responsável deve verificar a geração do documento.</Alert></div>}
      {laudo.status === "RASCUNHO" && (
        <div className="no-print">
          <Alert tone="warning" title={alteracoesNaoSalvas ? "Prévia com alterações não salvas" : "Este laudo ainda é um rascunho"}>
            Revise o conteúdo e a fonte dos dados antes de solicitar a emissão pelo responsável técnico.
          </Alert>
        </div>
      )}

      {antesDocumento}
      {/* O estado permanece no papel; a impressão local não substitui o arquivo emitido. */}
      <Card className="laudo-impressao p-6 sm:p-8" as="article">
        <style>{`@media print { .laudo-impressao { color: #111; background: #fff; box-shadow: none; border: 0; } .laudo-impressao section { break-inside: avoid; } .laudo-impressao h2 { break-after: avoid; } .laudo-impressao header, .laudo-impressao footer { break-inside: avoid; } }`}</style>
        <header className="flex flex-wrap items-start justify-between gap-4 border-b border-border pb-5">
          <Logo tamanho="lg" mostrarDescritor={false} />
          <div className="text-right text-sm">
            <p className="data font-semibold text-fg">{laudo.numero}</p>
            <p className="text-xs text-fg-subtle">Versão {laudo.versao}</p>
            <p className="mt-1 text-xs font-semibold uppercase">{cancelado ? "CANCELADO" : emitido ? "EMITIDO — cópia de consulta" : "RASCUNHO — não emitido"}</p>
          </div>
        </header>
        {cancelado && <p className="mt-4 border border-danger p-3 text-sm font-semibold text-danger-fg">Documento cancelado{laudo.cancelado_em ? ` em ${dataHora(laudo.cancelado_em)}` : ""}. {laudo.motivo_cancelamento}</p>}
        {alteracoesNaoSalvas && <p className="mt-4 text-sm font-semibold">Prévia com alterações não salvas.</p>}
        <h1 className="mt-6 text-xl font-semibold text-fg">{config?.titulo_documento || "Laudo técnico"}</h1>

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
                  <SemDado>Pendente de avaliação técnica</SemDado>
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
        {documento.dados && (!config?.secoes || config.secoes.includes("evidencias")) && documento.dados.evidencias.length > 0 && <section className="mt-6">
          <h2 className="mb-3 text-2xs font-semibold uppercase tracking-wide text-primary">Evidências</h2>
          <div className="grid gap-4 sm:grid-cols-2">{documento.dados.evidencias.map((e) => <figure key={e.id} className="min-w-0">
            {urlImagemSegura(e.data_uri || e.url || "") && (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={e.data_uri || e.url} alt={e.legenda || e.nome} className="max-h-72 w-full object-contain" />
            )}
            <figcaption className="mt-2 break-words text-xs text-fg-muted">{e.legenda || e.nome}</figcaption>
          </figure>)}</div>
        </section>}
        {documento.dados && (!config?.secoes || config.secoes.includes("comparativos")) && documento.dados.graficos.length > 0 && <section className="mt-6">
          <h2 className="mb-3 text-2xs font-semibold uppercase tracking-wide text-primary">Comparativos</h2>
          {documento.dados.graficos.map((g, i) => <div key={`${g.titulo}-${i}`} className="mb-4 overflow-x-auto">
            <table className="w-full text-left text-sm"><caption className="mb-2 text-left font-semibold">{g.titulo}</caption>
              <thead><tr className="border-b border-border"><th className="py-2 pr-4">Data da medição</th><th className="py-2">Valor{g.unidade ? ` (${g.unidade})` : ""}</th></tr></thead>
              <tbody>{g.pontos.map((p, j) => <tr key={`${p.data}-${j}`} className="border-b border-border"><td className="py-2 pr-4">{dataHora(p.data)}</td><td className="py-2">{p.valor}</td></tr>)}</tbody>
            </table>
          </div>)}
        </section>}

        <footer className="mt-12 border-t border-border pt-6">
          <div className="inline-block border-t border-border-strong px-10 pt-1.5 text-center">
            <p className="text-sm font-semibold text-fg">{texto(assinatura?.nome || laudo.responsavel_nome)}</p>
            <p className="text-xs text-fg-muted">
              Responsável técnico
              {(assinatura?.conselho || laudo.responsavel_conselho) ? ` — ${assinatura?.conselho || laudo.responsavel_conselho}` : ""}
            </p>
          </div>
          {assinatura?.metodo === "APROVACAO_ELETRONICA_INTERNA" ? <div className="mt-4 text-xs text-fg-muted">
            <p className="font-semibold">Aprovação eletrônica interna registrada em {dataHora(assinatura.data_hora)}.</p>
            <p>Aprovação pela conta autenticada do responsável. Sem assinatura criptográfica ou certificado digital.</p>
          </div> : <p className="mt-4 text-xs text-fg-muted">Nenhuma aprovação eletrônica interna registrada para esta versão.</p>}
          {config?.rodape && <p className="mt-4 whitespace-pre-wrap text-xs text-fg-muted">{config.rodape}</p>}
        </footer>
      </Card>
      {depoisDocumento}
    </PageBody>
  );
}

function urlImagemSegura(url: string) {
  return /^https?:\/\//i.test(url) || /^\/(?!\/)/.test(url) || /^data:image\/(png|jpe?g|gif|webp);base64,/i.test(url);
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
