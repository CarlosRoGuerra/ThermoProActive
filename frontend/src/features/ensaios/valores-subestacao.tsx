"use client";

import { Plus, Trash2 } from "lucide-react";
import { Button, IconButton, Input } from "@/components/ds";
import { numero } from "@/features/relatorio-inspecao/modulos/transformador/formato";
import { MSG_NUMERO_INVALIDO, paraApi, paraCampo } from "./numeros";
import { Conformidade } from "./valores";
import type { AvaliacaoSubestacao, EnsaioCatalogo, ParametroCatalogo, ValorApi } from "./tipos";

/* ==========================================================================
   Valores dos ensaios de subestação (TC, TP, DJ, CS, RP), por série — docs/25.

   MEDICAO: uma linha por série (fase, polo, núcleo ou função) e uma coluna por
   parâmetro digitado. As colunas calculadas (erro de relação, erro de pickup e de
   tempo) não se digitam: voltam do servidor na avaliação, com as mesmas regras do
   relatório.
   CURVA: uma linha por tensão de ensaio e uma coluna por núcleo, com a corrente de
   excitação; a tensão de joelho sai da avaliação.
   ========================================================================== */

type LinhaMedicao = { serie: string; valores: Record<string, string> };
type PontoCurva = { tensao: string; valores: string[] };

export type CamposSubestacao =
  | { tipo: "MEDICAO"; linhas: LinhaMedicao[] }
  | { tipo: "CURVA"; series: string[]; pontos: PontoCurva[] };

type ValorEnvio = Partial<ValorApi> & { parametro: number };

const lancados = (ensaio: EnsaioCatalogo) => ensaio.parametros.filter((p) => !p.calculado).sort((a, b) => a.ordem - b.ordem);
const calculados = (ensaio: EnsaioCatalogo) => ensaio.parametros.filter((p) => p.calculado).sort((a, b) => a.ordem - b.ordem);
const textual = (p: ParametroCatalogo) => p.tipo_limite === "QUALITATIVO";
const semRepetidos = (lista: string[]) => Array.from(new Set(lista));

/* ------------------------------ Estado inicial ------------------------------ */
export function camposSubestacaoIniciais(ensaio: EnsaioCatalogo, valores: ValorApi[]): CamposSubestacao {
  const series = semRepetidos(valores.map((v) => v.serie).filter(Boolean));
  const doParametro = (codigo: string) => ensaio.parametros.find((p) => p.codigo === codigo)?.id;
  if (ensaio.forma === "CURVA") {
    const corrente = doParametro("CORRENTE_EXCITACAO") ?? lancados(ensaio)[0]?.id;
    const medidos = valores.filter((v) => v.parametro === corrente && v.posicao != null);
    const tensoes = semRepetidos(medidos.map((v) => String(Number(v.posicao)))).sort((a, b) => Number(a) - Number(b));
    if (!series.length || !tensoes.length) return { tipo: "CURVA", series: [""], pontos: [{ tensao: "", valores: [""] }] };
    return {
      tipo: "CURVA",
      series,
      pontos: tensoes.map((t) => ({
        tensao: paraCampo(t),
        valores: series.map((s) => paraCampo(medidos.find((v) => v.serie === s && Number(v.posicao) === Number(t))?.valor)),
      })),
    };
  }
  const linhas = series.map((serie) => ({
    serie,
    valores: Object.fromEntries(lancados(ensaio).map((p) => {
      const v = valores.find((x) => x.parametro === p.id && x.serie === serie);
      return [p.codigo, textual(p) ? (v?.valor_texto ?? "") : paraCampo(v?.valor)];
    })),
  }));
  return { tipo: "MEDICAO", linhas: linhas.length ? linhas : [{ serie: "", valores: {} }] };
}

/* ------------------------------- Para a API -------------------------------- */
/** Monta os `valores` do resultado. Erros por chave (linha-codigo, ponto-serie…). */
export function valoresSubestacaoParaApi(ensaio: EnsaioCatalogo, campos: CamposSubestacao) {
  const valores: ValorEnvio[] = [];
  const erros: Record<string, string> = {};

  if (campos.tipo === "MEDICAO") {
    campos.linhas.forEach((linha, i) => {
      const serie = linha.serie.trim();
      const preenchida = lancados(ensaio).some((p) => (linha.valores[p.codigo] ?? "").trim());
      if (!serie) {
        if (preenchida) erros[`${i}-serie`] = "Informe a série (fase, polo, núcleo ou função) desta linha.";
        return;
      }
      for (const p of lancados(ensaio)) {
        const texto = (linha.valores[p.codigo] ?? "").trim();
        if (!texto) continue;
        if (textual(p)) {
          valores.push({ parametro: p.id, serie, valor_texto: texto });
          continue;
        }
        const v = paraApi(texto);
        if (v === undefined) erros[`${i}-${p.codigo}`] = MSG_NUMERO_INVALIDO;
        else if (v != null) valores.push({ parametro: p.id, serie, valor: v });
      }
    });
    return { valores, erros };
  }

  const corrente = lancados(ensaio)[0];
  campos.series.forEach((s, k) => {
    if (!s.trim() && campos.pontos.some((pt) => (pt.valores[k] ?? "").trim())) erros[`serie${k}`] = "Informe o nome do núcleo.";
  });
  campos.pontos.forEach((ponto, i) => {
    const tensao = paraApi(ponto.tensao);
    const temValor = ponto.valores.some((v) => v.trim());
    if (!temValor) return;
    if (tensao == null || tensao === undefined || Number(tensao) < 0) {
      erros[`tensao${i}`] = ponto.tensao.trim() ? MSG_NUMERO_INVALIDO : "Informe a tensão do ponto.";
      return;
    }
    campos.series.forEach((s, k) => {
      const texto = (ponto.valores[k] ?? "").trim();
      if (!texto || !s.trim()) return;
      const v = paraApi(texto);
      if (v === undefined) erros[`ponto${i}-${k}`] = MSG_NUMERO_INVALIDO;
      else if (v != null && corrente) valores.push({ parametro: corrente.id, serie: s.trim(), posicao: tensao, valor: v });
    });
  });
  return { valores, erros };
}

/* --------------------------------- Peças --------------------------------- */
const rotuloUnidade = (p: ParametroCatalogo) => (p.unidade ? `(${p.unidade})` : "");

function Erro({ texto }: { texto?: string }) {
  return texto ? <p className="text-xs text-danger-fg">{texto}</p> : null;
}

/* ----------------------------- Editor por forma ----------------------------- */
export function EditorValoresSubestacao({
  ensaio, campos, onMudar, erros, avaliacao, disabled,
}: {
  ensaio: EnsaioCatalogo;
  campos: CamposSubestacao;
  onMudar: (c: CamposSubestacao) => void;
  erros: Record<string, string>;
  /** Avaliação da última gravação — só aparece quando os campos batem com ela. */
  avaliacao: AvaliacaoSubestacao | null;
  disabled: boolean;
}) {
  if (campos.tipo === "CURVA") {
    const corrente = lancados(ensaio)[0];
    const mudarSerie = (k: number, nome: string) =>
      onMudar({ ...campos, series: campos.series.map((s, j) => (j === k ? nome : s)) });
    const mudarCelula = (i: number, k: number, texto: string) =>
      onMudar({
        ...campos,
        pontos: campos.pontos.map((pt, a) => (a === i ? { ...pt, valores: pt.valores.map((v, b) => (b === k ? texto : v)) } : pt)),
      });
    const mudarTensao = (i: number, texto: string) =>
      onMudar({ ...campos, pontos: campos.pontos.map((pt, a) => (a === i ? { ...pt, tensao: texto } : pt)) });
    return (
      <div className="space-y-3">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[32rem] text-sm">
            <thead>
              <tr className="text-left text-xs text-fg-muted">
                <th className="py-1.5 pr-2 font-medium">Tensão do ensaio {corrente && `· ${corrente.nome} ${rotuloUnidade(corrente)}`}</th>
                {campos.series.map((s, k) => (
                  <th key={k} className="px-1 py-1.5 align-bottom font-normal">
                    <div className="flex items-center gap-1">
                      <Input aria-label={`Nome do núcleo ${k + 1}`} value={s} disabled={disabled} placeholder="Núcleo"
                        onChange={(e) => mudarSerie(k, e.target.value)} />
                      {!disabled && campos.series.length > 1 && (
                        <IconButton icon={Trash2} label={`Remover o núcleo ${k + 1}`} size="xs"
                          onClick={() => onMudar({
                            ...campos,
                            series: campos.series.filter((_, j) => j !== k),
                            pontos: campos.pontos.map((pt) => ({ ...pt, valores: pt.valores.filter((_, b) => b !== k) })),
                          })} />
                      )}
                    </div>
                    <Erro texto={erros[`serie${k}`]} />
                  </th>
                ))}
                <th />
              </tr>
            </thead>
            <tbody>
              {campos.pontos.map((pt, i) => (
                <tr key={i} className="border-t border-border">
                  <td className="py-1 pr-2">
                    <Input className="w-32" inputMode="decimal" tecnico sufixo="V" aria-label={`Tensão do ponto ${i + 1}`}
                      value={pt.tensao} disabled={disabled} onChange={(e) => mudarTensao(i, e.target.value)} />
                    <Erro texto={erros[`tensao${i}`]} />
                  </td>
                  {campos.series.map((_, k) => (
                    <td key={k} className="px-1 py-1">
                      <Input className="w-28" inputMode="decimal" tecnico sufixo="mA" aria-label={`Corrente no ponto ${i + 1}, núcleo ${k + 1}`}
                        value={pt.valores[k] ?? ""} disabled={disabled} onChange={(e) => mudarCelula(i, k, e.target.value)} />
                      <Erro texto={erros[`ponto${i}-${k}`]} />
                    </td>
                  ))}
                  <td className="py-1 text-right">
                    {!disabled && campos.pontos.length > 1 && (
                      <IconButton icon={Trash2} label={`Remover o ponto ${i + 1}`} size="xs"
                        onClick={() => onMudar({ ...campos, pontos: campos.pontos.filter((_, a) => a !== i) })} />
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="flex flex-wrap gap-2">
          {!disabled && (
            <>
              <Button size="sm" variant="secondary" icon={Plus}
                onClick={() => onMudar({ ...campos, pontos: [...campos.pontos, { tensao: "", valores: campos.series.map(() => "") }] })}>
                Adicionar tensão
              </Button>
              <Button size="sm" variant="secondary" icon={Plus}
                onClick={() => onMudar({
                  ...campos,
                  series: [...campos.series, ""],
                  pontos: campos.pontos.map((pt) => ({ ...pt, valores: [...pt.valores, ""] })),
                })}>
                Adicionar núcleo
              </Button>
            </>
          )}
        </div>
        {avaliacao?.joelhos && Object.keys(avaliacao.joelhos).length > 0 && (
          <p className="text-sm text-fg-muted">
            Tensão de joelho (IEEE C57.13):{" "}
            {Object.entries(avaliacao.joelhos).map(([nome, v]) => (
              <span key={nome} className="data mr-3 font-medium text-fg">
                {nome}: {v != null ? `${numero(v, 0)} V` : "não atingido"}
              </span>
            ))}
          </p>
        )}
      </div>
    );
  }

  const digitados = lancados(ensaio);
  const colunasCalc = calculados(ensaio);
  const mudarLinha = (i: number, parcial: Partial<LinhaMedicao>) =>
    onMudar({ tipo: "MEDICAO", linhas: campos.linhas.map((l, a) => (a === i ? { ...l, ...parcial } : l)) });
  const calcDaSerie = (serie: string) => avaliacao?.linhas?.find((l) => l.serie === serie.trim())?.celulas ?? null;
  return (
    <div className="space-y-3">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[36rem] text-sm">
          <thead>
            <tr className="text-left text-xs text-fg-muted">
              <th className="py-1.5 pr-3 font-medium">Série</th>
              {digitados.map((p) => (
                <th key={p.id} className="px-1 py-1.5 font-medium">
                  <span className="block text-fg">{p.nome}</span>
                  <span className="block font-normal">{[p.unidade && `(${p.unidade})`, p.norma].filter(Boolean).join(" ")}</span>
                </th>
              ))}
              {colunasCalc.map((p) => (
                <th key={p.id} className="px-1 py-1.5 font-medium">
                  <span className="block text-fg">{p.nome}</span>
                  <span className="block font-normal">{p.unidade ? `(${p.unidade}) · calculado` : "calculado"}</span>
                </th>
              ))}
              <th />
            </tr>
          </thead>
          <tbody>
            {campos.linhas.map((linha, i) => {
              const calc = calcDaSerie(linha.serie);
              return (
                <tr key={i} className="border-t border-border align-top">
                  <td className="py-1.5 pr-3">
                    <Input className="w-36" aria-label={`Série da linha ${i + 1}`} value={linha.serie} disabled={disabled}
                      placeholder="Fase, polo, núcleo…" onChange={(e) => mudarLinha(i, { serie: e.target.value })} />
                    <Erro texto={erros[`${i}-serie`]} />
                  </td>
                  {digitados.map((p) => (
                    <td key={p.id} className="px-1 py-1.5">
                      <Input className="w-28" inputMode={textual(p) ? "text" : "decimal"} tecnico={!textual(p)}
                        aria-label={`${p.nome} — ${linha.serie || `linha ${i + 1}`}`} value={linha.valores[p.codigo] ?? ""}
                        disabled={disabled}
                        onChange={(e) => mudarLinha(i, { valores: { ...linha.valores, [p.codigo]: e.target.value } })} />
                      <Erro texto={erros[`${i}-${p.codigo}`]} />
                    </td>
                  ))}
                  {colunasCalc.map((p) => {
                    const cel = calc?.[p.codigo];
                    return (
                      <td key={p.id} className="px-1 py-1.5">
                        <span className="data inline-flex items-center gap-1.5 font-medium">
                          {cel?.valor != null ? numero(cel.valor, p.casas_decimais) : "—"}
                          <Conformidade conforme={cel?.conforme} />
                        </span>
                      </td>
                    );
                  })}
                  <td className="py-1.5 text-right">
                    {!disabled && campos.linhas.length > 1 && (
                      <IconButton icon={Trash2} label={`Remover a linha ${i + 1}`} size="xs"
                        onClick={() => onMudar({ tipo: "MEDICAO", linhas: campos.linhas.filter((_, a) => a !== i) })} />
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {!disabled && (
        <Button size="sm" variant="secondary" icon={Plus}
          onClick={() => onMudar({ tipo: "MEDICAO", linhas: [...campos.linhas, { serie: "", valores: {} }] })}>
          Adicionar linha
        </Button>
      )}
      {avaliacao?.criterio && (
        <p className="text-xs text-fg-muted">
          {avaliacao.criterio.admissivel != null
            ? `Erro admitido ± ${numero(avaliacao.criterio.admissivel, 2)} % pela classe ${avaliacao.criterio.classe} (${avaliacao.criterio.norma}).`
            : `Classe ${avaliacao.criterio.classe || "não informada"} sem critério na tabela de ${avaliacao.criterio.norma}: erro sem critério definido.`}
        </p>
      )}
      {avaliacao?.indicadores && Object.values(avaliacao.indicadores).some((v) => v != null) && (
        <p className="text-sm text-fg-muted">
          Calculado:{" "}
          {avaliacao.indicadores.simultaneidade_abertura_ms != null && (
            <span className="data mr-3 font-medium text-fg">
              simultaneidade na abertura = {numero(avaliacao.indicadores.simultaneidade_abertura_ms, 1)} ms
            </span>
          )}
          {avaliacao.indicadores.simultaneidade_fechamento_ms != null && (
            <span className="data mr-3 font-medium text-fg">
              simultaneidade no fechamento = {numero(avaliacao.indicadores.simultaneidade_fechamento_ms, 1)} ms
            </span>
          )}
        </p>
      )}
    </div>
  );
}
