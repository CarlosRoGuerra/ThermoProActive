"use client";

import { Badge, Input, SegmentedControl, Select, cn, type Tom } from "@/components/ds";
import type { LinhaFluido } from "@/features/relatorio-inspecao/tipos";
import { numero } from "@/features/relatorio-inspecao/modulos/transformador/formato";
import { ddmmaaaa } from "@/features/relatorio-inspecao/shell/formato";
import { paraCampo } from "./numeros";
import type { AvaliacaoFluido, EnsaioCatalogo, ParametroCatalogo } from "./tipos";
import { valoresParaApi, type CamposValores, type EstadoMedida } from "./valores";

/* ==========================================================================
   Valores de um ensaio de fluido (FQ, EF, CP) — a mesma tabela de parâmetros
   do motor de ensaios, mostrada como o analista precisa ler um laudo de óleo:
   agrupada (metais de desgaste, contaminantes, aditivos), e com a referência
   cadastrada, o estado e as coletas anteriores ao lado de cada parâmetro.

   O que é calculado (estado pela referência, tendência, código ISO 4406, meta)
   volta do servidor na `avaliacao`, com as regras do relatório.
   ========================================================================== */

const ESTADOS: { valor: EstadoMedida; label: string }[] = [
  { valor: "MEDIDO", label: "Medido" },
  { valor: "ABAIXO_LD", label: "< LD" },
  { valor: "ABAIXO_LQ", label: "< LQ" },
  { valor: "NAO_DETECTADO", label: "N.D." },
  { valor: "INDISPONIVEL", label: "Indisponível" },
];
const TOM_ESTADO: Record<string, Tom> = { ROTINA: "success", ALERTA: "warning", CRITICA: "danger" };
const ROTULO_ESTADO: Record<string, string> = { ROTINA: "Rotina", ALERTA: "Alerta", CRITICA: "Crítica" };
const SETA = { SOBE: "↑", DESCE: "↓", ESTAVEL: "→" } as const;

export type BaseContagem = "ML" | "100ML";

const digitados = (ensaio: EnsaioCatalogo) =>
  ensaio.parametros.filter((p) => !p.calculado).sort((a, b) => a.ordem - b.ordem);

/** `valores` para a API; na CP informada por 100 mL, converte para por mL e guarda o texto recebido. */
export function valoresFluidoParaApi(ensaio: EnsaioCatalogo, campos: CamposValores, base: BaseContagem) {
  const r = valoresParaApi(ensaio, campos);
  if (base !== "100ML" || ensaio.sigla !== "CP") return r;
  const contagens = new Set(ensaio.parametros.filter((p) => p.unidade === "part./mL").map((p) => p.id));
  return {
    erros: r.erros,
    valores: r.valores.map((v) => {
      if (!contagens.has(v.parametro) || v.valor == null) return v;
      const original = Number(v.valor);
      return { ...v, valor: (original / 100).toFixed(2), valor_texto: `${paraCampo(v.valor)} /100 mL` };
    }),
  };
}

function Historico({ linha, campanhas }: { linha: LinhaFluido; campanhas: AvaliacaoFluido["campanhas"] }) {
  const anteriores = linha.valores
    .map((c, i) => ({ c, i }))
    .filter(({ i }) => !campanhas[i]?.atual)
    .filter(({ c }) => c.valor != null || c.texto);
  if (!anteriores.length) return null;
  return (
    <p className="text-xs text-fg-subtle">
      Anteriores:{" "}
      {anteriores.map(({ c, i }) => (
        <span key={i} className="data mr-2" title={ddmmaaaa(campanhas[i]?.data ?? "")}>
          {c.valor != null ? numero(c.valor, linha.casas) : c.texto}
        </span>
      ))}
      {linha.tendencia && linha.tendencia.pct_anterior != null && (
        <span className="font-medium text-fg-muted">
          {SETA[linha.tendencia.direcao]} {linha.tendencia.pct_anterior > 0 ? "+" : ""}
          {numero(linha.tendencia.pct_anterior, 0)}% sobre a anterior
        </span>
      )}
    </p>
  );
}

function Parametro({
  p, linha, campos, onMudar, erro, calc, campanhas, disabled,
}: {
  p: ParametroCatalogo;
  linha: { texto: string; estado: EstadoMedida };
  campos: Extract<CamposValores, { tipo: "TABELA" }>;
  onMudar: (c: CamposValores) => void;
  erro?: string;
  calc?: LinhaFluido;
  campanhas: AvaliacaoFluido["campanhas"];
  disabled: boolean;
}) {
  const mudar = (parcial: Partial<typeof linha>) =>
    onMudar({ ...campos, linhas: { ...campos.linhas, [p.codigo]: { ...linha, ...parcial } } });
  const qualitativo = p.tipo_limite === "QUALITATIVO";
  const rotulo = `${p.nome}${p.simbolo ? ` (${p.simbolo})` : ""}`;
  return (
    <li className="flex flex-wrap items-start gap-x-3 gap-y-2 px-3 py-2">
      <div className="min-w-[11rem] flex-1">
        <p className="text-sm font-medium text-fg">{rotulo}</p>
        <p className="text-xs text-fg-subtle">{[p.unidade, p.norma].filter(Boolean).join(" · ")}</p>
        {calc?.referencia ? (
          <p className="text-xs text-fg-muted" title={[calc.referencia.origem_display, calc.referencia.fonte].filter(Boolean).join(" · ")}>
            Ref.: {calc.referencia.texto} <span className="text-fg-subtle">({calc.referencia.origem_display})</span>
          </p>
        ) : calc?.sem_referencia ? (
          <p className="text-xs text-fg-subtle">Sem referência cadastrada para este equipamento/fluido</p>
        ) : null}
        {calc && <Historico linha={calc} campanhas={campanhas} />}
        {erro && <p className="text-xs text-danger-fg">{erro}</p>}
      </div>
      <div className="flex items-center gap-2">
        <Input
          className="w-28"
          inputMode={qualitativo ? "text" : "decimal"}
          tecnico={!qualitativo}
          aria-label={`Valor de ${rotulo}`}
          placeholder={linha.estado === "ABAIXO_LD" || linha.estado === "ABAIXO_LQ" ? "limite" : undefined}
          value={linha.texto}
          disabled={disabled || ["NAO_DETECTADO", "INDISPONIVEL"].includes(linha.estado)}
          onChange={(e) => mudar({ texto: e.target.value })}
        />
        {!qualitativo && (
          <Select className="w-28" aria-label={`Estado de ${rotulo}`} value={linha.estado} disabled={disabled}
            onChange={(e) => mudar({ estado: e.target.value as EstadoMedida })}>
            {ESTADOS.map((s) => <option key={s.valor} value={s.valor}>{s.label}</option>)}
          </Select>
        )}
        <span className="w-16 text-right">
          {calc?.status && <Badge tone={TOM_ESTADO[calc.status]}>{ROTULO_ESTADO[calc.status]}</Badge>}
        </span>
      </div>
    </li>
  );
}

export function EditorValoresFluido({
  ensaio, campos, onMudar, erros, avaliacao, disabled, base, onBase,
}: {
  ensaio: EnsaioCatalogo;
  campos: CamposValores;
  onMudar: (c: CamposValores) => void;
  erros: Record<string, string>;
  /** Avaliação da última gravação — só aparece quando os campos batem com ela. */
  avaliacao: AvaliacaoFluido | null;
  disabled: boolean;
  base: BaseContagem;
  onBase: (b: BaseContagem) => void;
}) {
  if (campos.tipo !== "TABELA") return null;
  const calc = new Map((avaliacao?.linhas ?? []).map((l) => [l.codigo, l]));
  const campanhas = avaliacao?.campanhas ?? [];
  const grupos = new Map<string, ParametroCatalogo[]>();
  for (const p of digitados(ensaio)) grupos.set(p.grupo, [...(grupos.get(p.grupo) ?? []), p]);
  const cp = ensaio.sigla === "CP";
  const atual = avaliacao?.codigos?.find((c) => c.atual);

  return (
    <div className="space-y-3">
      {cp && (
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-sm text-fg-muted">Contagens informadas pelo laboratório por</span>
          <SegmentedControl
            label="Base das contagens"
            tamanho="sm"
            valor={base}
            onMudar={onBase}
            opcoes={[{ valor: "ML", label: "mL" }, { valor: "100ML", label: "100 mL" }]}
          />
          {base === "100ML" && <span className="text-xs text-fg-subtle">O sistema guarda por mL (÷ 100) e o valor recebido.</span>}
        </div>
      )}
      {Array.from(grupos.entries()).map(([grupo, params]) => (
        <section key={grupo || "sem-grupo"}>
          {grupo && grupos.size > 1 && <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-fg-muted">{grupo}</h4>}
          <ul className={cn("divide-y divide-border rounded-lg border border-border")}>
            {params.map((p) => (
              <Parametro
                key={p.id}
                p={p}
                linha={campos.linhas[p.codigo] ?? { texto: "", estado: "MEDIDO" }}
                campos={campos}
                onMudar={onMudar}
                erro={erros[p.codigo]}
                calc={calc.get(p.codigo)}
                campanhas={campanhas}
                disabled={disabled}
              />
            ))}
          </ul>
        </section>
      ))}
      {cp && avaliacao && (
        <div className="flex flex-wrap items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm">
          <span className="text-fg-muted">Código ISO 4406:</span>
          <span className="data font-semibold text-fg">{atual?.codigo ?? "incompleto (faltam > 4, > 6 ou > 14 µm)"}</span>
          {avaliacao.meta && <span className="text-fg-muted">· meta {avaliacao.meta.referencia_texto}</span>}
          {avaliacao.situacao_meta === "FORA" && <Badge tone="danger">Fora da meta (+{avaliacao.excesso_meta})</Badge>}
          {avaliacao.situacao_meta === "DENTRO" && <Badge tone="success">Dentro da meta</Badge>}
          {avaliacao.situacao_meta === "SEM_META" && <Badge tone="neutral">Sem meta cadastrada</Badge>}
          {(avaliacao.codigos?.length ?? 0) > 1 && (
            <span className="text-xs text-fg-subtle">
              Anteriores: {avaliacao.codigos!.filter((c) => !c.atual).map((c) => c.codigo ?? "—").join(" · ")}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
