"use client";

import { FlaskConical } from "lucide-react";
import { Badge, Button, Card, CardHeader, Skeleton } from "@/components/ds";
import { data as fmtData, plural } from "@/lib/format";
import { rotuloEnsaio } from "./cartao-ensaio";
import type { ModuloTransformador, TransformadorInspecao } from "./tipos";

/**
 * Cartão da folha de campo, no painel do transformador: o que já foi lançado
 * (registro e laudos) e a entrada para o lançamento completo.
 */
export function ResumoEnsaiosCampo({
  modulo, resumo, carregando, podeEditar, onAbrir,
}: {
  modulo: ModuloTransformador;
  resumo: TransformadorInspecao | null;
  carregando: boolean;
  podeEditar: boolean;
  onAbrir: () => void;
}) {
  const oleo = modulo === "OLEO_ISOLANTE";
  const solicitados = resumo?.ensaios.filter((e) => e.solicitado) ?? [];
  const descricao = !resumo?.registro
    ? oleo
      ? "Registre a coleta da amostra, a inspeção visual e os ensaios solicitados."
      : "Registre o TAP, as temperaturas, os ensaios solicitados e as medições."
    : `${oleo ? "Coleta registrada" : "Ensaios registrados"} em ${fmtData(resumo.registro.data)}` +
      (resumo.pendentes ? ` · ${plural(resumo.pendentes, "ensaio sem laudo", "ensaios sem laudo")}` : " · laudos em dia");

  return (
    <Card>
      <CardHeader
        icon={FlaskConical}
        title={oleo ? "Coleta de óleo e ensaios" : "Ensaios elétricos"}
        description={carregando ? undefined : descricao}
        actions={
          <Button size="sm" icon={FlaskConical} variant={resumo?.registro ? "secondary" : "primary"} onClick={onAbrir}>
            {!podeEditar ? "Ver ensaios" : resumo?.registro ? "Abrir ensaios" : oleo ? "Registrar coleta" : "Registrar ensaios"}
          </Button>
        }
      />
      {carregando ? (
        <Skeleton className="h-5 w-48" />
      ) : solicitados.length > 0 ? (
        <div className="flex flex-wrap gap-1.5">
          {solicitados.map((e) => (
            <Badge
              key={e.sigla}
              tone={e.situacao === "REALIZADO" ? "success" : e.situacao === "NAO_COLETADO" || e.situacao === "NAO_REALIZADO" ? "warning" : "neutral"}
            >
              {rotuloEnsaio(e.sigla)}
            </Badge>
          ))}
        </div>
      ) : (
        <p className="text-xs text-fg-subtle">Nenhum ensaio solicitado ainda.</p>
      )}
    </Card>
  );
}
