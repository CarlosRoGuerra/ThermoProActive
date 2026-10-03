"use client";

import { FlaskConical } from "lucide-react";
import { Badge, Button, Card, CardHeader, Skeleton } from "@/components/ds";
import { data as fmtData, plural } from "@/lib/format";
import { rotuloEnsaio } from "./cartao-ensaio";
import type { ItemEnsaio, ModuloEnsaio } from "./tipos";

/**
 * Cartão da folha de campo, no painel do equipamento das rotas de ensaio
 * (transformador ou fluidos): o que já foi lançado (registro e laudos) e a
 * entrada para o lançamento completo.
 */
const TEXTOS: Record<ModuloEnsaio, { titulo: string; vazio: string; feito: string; registrar: string }> = {
  OLEO_ISOLANTE: {
    titulo: "Coleta de óleo e ensaios",
    vazio: "Registre a coleta da amostra, a inspeção visual e os ensaios solicitados.",
    feito: "Coleta registrada", registrar: "Registrar coleta",
  },
  ENSAIO_ELETRICO: {
    titulo: "Ensaios elétricos",
    vazio: "Registre o TAP, as temperaturas, os ensaios solicitados e as medições.",
    feito: "Ensaios registrados", registrar: "Registrar ensaios",
  },
  FLUIDO_LUBRIFICANTE: {
    titulo: "Coleta de fluido",
    vazio: "Registre a coleta da amostra: fluido, ponto de coleta, condição e os ensaios solicitados.",
    feito: "Coleta registrada", registrar: "Registrar coleta",
  },
};

export function ResumoEnsaiosCampo({
  modulo, resumo, carregando, podeEditar, onAbrir,
}: {
  modulo: ModuloEnsaio;
  resumo: ItemEnsaio | null;
  carregando: boolean;
  podeEditar: boolean;
  onAbrir: () => void;
}) {
  const t = TEXTOS[modulo];
  const solicitados = resumo?.ensaios.filter((e) => e.solicitado) ?? [];
  const descricao = !resumo?.registro
    ? t.vazio
    : `${t.feito} em ${fmtData(resumo.registro.data)}` +
      (resumo.pendentes ? ` · ${plural(resumo.pendentes, "ensaio sem laudo", "ensaios sem laudo")}` : " · laudos em dia");

  return (
    <Card>
      <CardHeader
        icon={FlaskConical}
        title={t.titulo}
        description={carregando ? undefined : descricao}
        actions={
          <Button size="sm" icon={FlaskConical} variant={resumo?.registro ? "secondary" : "primary"} onClick={onAbrir}>
            {!podeEditar ? "Ver ensaios" : resumo?.registro ? "Abrir ensaios" : t.registrar}
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
