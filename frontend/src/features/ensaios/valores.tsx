"use client";

import { CircleCheck, CircleX } from "lucide-react";
import { Input, Select, cn } from "@/components/ds";
import type { FichaOhmica, FichaRelacao, FichaTabela } from "@/features/relatorio-inspecao/tipos";
import { numero } from "@/features/relatorio-inspecao/modulos/transformador/formato";
import { MSG_NUMERO_INVALIDO, paraApi, paraCampo } from "./numeros";
import { tipoDoEnsaio, type Avaliacao, type EnsaioCatalogo, type ParametroCatalogo, type ValorApi } from "./tipos";

/* ==========================================================================
   Valores de um ensaio: o estado dos campos, a conversão de/para a API e o
   editor de cada forma de ficha (tabela de parâmetros, R×T, R×I, R×O).
   O que é calculado (TG/TGC, erro, IP/IA, corrigidos) não se digita — volta do
   servidor na `avaliacao`, com as mesmas regras do relatório.
   ========================================================================== */

export type EstadoMedida = ValorApi["estado"];
type LinhaTabela = { texto: string; estado: EstadoMedida };

export type CamposValores =
  | { tipo: "TABELA"; linhas: Record<string, LinhaTabela> }
  | { tipo: "RXT"; fases: { serie: string; texto: string }[]; nominal: string }
  | { tipo: "RXI"; series: { nome: string; tensao: string }[]; tempos: number[]; grade: string[][] }
  | { tipo: "RXO"; pares: Record<string, string> };

// Configuração do relatório de referência (transformador Dyn1): nomes prontos, editáveis.
const FASES_PADRAO = ["Fase 1 (H1-H2/X0-X2)", "Fase 2 (H2-H3/X0-X3)", "Fase 3 (H3-H1/X0-X1)"];
const SERIES_RXI_PADRAO = ["AT-BT-Massa", "AT-Massa-BT", "BT-Massa-AT"];
const TEMPOS_RXI_PADRAO = [15, 30, 45, 60, 120, 180, 240, 300, 360, 420, 480, 540, 600];

const ESTADOS: { valor: EstadoMedida; label: string }[] = [
  { valor: "MEDIDO", label: "Medido" },
  { valor: "ABAIXO_LD", label: "< LD" },
  { valor: "ABAIXO_LQ", label: "< LQ" },
  { valor: "NAO_DETECTADO", label: "N.D." },
  { valor: "ACIMA_ESCALA", label: "> escala" },
  { valor: "INDISPONIVEL", label: "Indisponível" },
];

const parametrosDigitados = (ensaio: EnsaioCatalogo) =>
  ensaio.parametros.filter((p) => !p.calculado).sort((a, b) => a.ordem - b.ordem);
const porCodigo = (ensaio: EnsaioCatalogo, codigo: string) => ensaio.parametros.find((p) => p.codigo === codigo);

/* ------------------------------ Estado inicial ------------------------------ */
export function camposIniciais(ensaio: EnsaioCatalogo, valores: ValorApi[]): CamposValores {
  const tipo = tipoDoEnsaio(ensaio.sigla);
  const doParametro = (id: number | undefined) => valores.filter((v) => v.parametro === id);

  if (tipo === "RXT") {
    const medidas = doParametro(porCodigo(ensaio, "MEDIDA")?.id).sort((a, b) => a.serie.localeCompare(b.serie));
    const nominal = doParametro(porCodigo(ensaio, "NOMINAL")?.id)[0];
    return {
      tipo,
      fases: medidas.length
        ? medidas.map((v) => ({ serie: v.serie, texto: paraCampo(v.valor) }))
        : FASES_PADRAO.map((serie) => ({ serie, texto: "" })),
      nominal: paraCampo(nominal?.valor),
    };
  }
  if (tipo === "RXI") {
    const tensoes = doParametro(porCodigo(ensaio, "TENSAO")?.id);
    const leituras = doParametro(porCodigo(ensaio, "RESISTENCIA")?.id);
    const nomes = Array.from(new Set([...tensoes, ...leituras].map((v) => v.serie).filter(Boolean)));
    const ordem = (n: string) => (SERIES_RXI_PADRAO.includes(n) ? SERIES_RXI_PADRAO.indexOf(n) : 99);
    nomes.sort((a, b) => ordem(a) - ordem(b) || a.localeCompare(b));
    const series = (nomes.length ? nomes : SERIES_RXI_PADRAO).map((nome) => ({
      nome, tensao: paraCampo(tensoes.find((v) => v.serie === nome)?.valor),
    }));
    const tempos = Array.from(new Set([
      ...TEMPOS_RXI_PADRAO, ...leituras.map((v) => Number(v.posicao)).filter((t) => Number.isFinite(t)),
    ])).sort((a, b) => a - b);
    const grade = tempos.map((t) =>
      series.map((s) => paraCampo(leituras.find((v) => v.serie === s.nome && Number(v.posicao) === t)?.valor))
    );
    return { tipo, series, tempos, grade };
  }
  if (tipo === "RXO") {
    return {
      tipo,
      pares: Object.fromEntries(
        parametrosDigitados(ensaio).map((p) => [p.codigo, paraCampo(doParametro(p.id)[0]?.valor)])
      ),
    };
  }
  return {
    tipo,
    linhas: Object.fromEntries(parametrosDigitados(ensaio).map((p) => {
      const v = doParametro(p.id)[0];
      const abaixo = v?.estado === "ABAIXO_LD" || v?.estado === "ABAIXO_LQ";
      const texto = !v ? "" : p.tipo_limite === "QUALITATIVO"
        ? v.valor_texto
        : abaixo ? paraCampo(v.limite_deteccao) : paraCampo(v.valor);
      return [p.codigo, { texto, estado: v?.estado ?? "MEDIDO" }];
    })),
  };
}

/* ------------------------------ Para a API ------------------------------ */
type ValorEnvio = Partial<ValorApi> & { parametro: number };

/** Monta os `valores` do resultado. Erros por chave de campo (texto inválido). */
export function valoresParaApi(ensaio: EnsaioCatalogo, campos: CamposValores) {
  const valores: ValorEnvio[] = [];
  const erros: Record<string, string> = {};
  const numeroDe = (chave: string, texto: string) => {
    const v = paraApi(texto);
    if (v === undefined) erros[chave] = MSG_NUMERO_INVALIDO;
    return v ?? null;
  };

  if (campos.tipo === "TABELA") {
    for (const p of parametrosDigitados(ensaio)) {
      const { texto, estado } = campos.linhas[p.codigo] ?? { texto: "", estado: "MEDIDO" };
      if (p.tipo_limite === "QUALITATIVO") {
        if (texto.trim()) valores.push({ parametro: p.id, valor_texto: texto.trim() });
        continue;
      }
      if (estado === "MEDIDO") {
        const v = numeroDe(p.codigo, texto);
        if (v != null) valores.push({ parametro: p.id, valor: v });
      } else {
        // Abaixo do LD/LQ: o número digitado é o limite do método ("< 2,0" na ficha).
        const limite = texto.trim() ? numeroDe(p.codigo, texto) : null;
        const abaixo = estado === "ABAIXO_LD" || estado === "ABAIXO_LQ";
        valores.push({
          parametro: p.id, valor: null, estado,
          limite_deteccao: abaixo ? limite : null,
          valor_texto: abaixo && limite != null ? `< ${paraCampo(limite)}` : "",
        });
      }
    }
  } else if (campos.tipo === "RXT") {
    const medida = porCodigo(ensaio, "MEDIDA")!;
    campos.fases.forEach((f, i) => {
      const v = numeroDe(`fase${i}`, f.texto);
      if (v != null) valores.push({ parametro: medida.id, serie: f.serie.trim(), valor: v });
    });
    const nominal = numeroDe("nominal", campos.nominal);
    if (nominal != null) valores.push({ parametro: porCodigo(ensaio, "NOMINAL")!.id, valor: nominal });
  } else if (campos.tipo === "RXI") {
    const tensao = porCodigo(ensaio, "TENSAO")!;
    const resistencia = porCodigo(ensaio, "RESISTENCIA")!;
    campos.series.forEach((s, j) => {
      const v = numeroDe(`tensao${j}`, s.tensao);
      if (v != null) valores.push({ parametro: tensao.id, serie: s.nome.trim(), valor: v });
    });
    campos.tempos.forEach((t, i) =>
      campos.series.forEach((s, j) => {
        const v = numeroDe(`r${i}-${j}`, campos.grade[i]?.[j] ?? "");
        if (v != null) valores.push({ parametro: resistencia.id, serie: s.nome.trim(), posicao: String(t), valor: v });
      })
    );
  } else {
    for (const p of parametrosDigitados(ensaio)) {
      const v = numeroDe(p.codigo, campos.pares[p.codigo] ?? "");
      if (v != null) valores.push({ parametro: p.id, valor: v });
    }
  }
  return { valores, erros };
}

/* --------------------------------- Peças --------------------------------- */
function Conformidade({ conforme }: { conforme: boolean | null | undefined }) {
  if (conforme == null) return <span className="inline-block w-4" aria-hidden="true" />;
  return conforme ? (
    <CircleCheck className="h-4 w-4 shrink-0 text-success" aria-label="Dentro da referência" />
  ) : (
    <CircleX className="h-4 w-4 shrink-0 text-danger" aria-label="Fora da referência" />
  );
}

function referencia(p: ParametroCatalogo) {
  const n = (v: string | null) => (v == null ? "" : numero(Number(v), p.casas_decimais));
  const unidade = p.unidade ? ` ${p.unidade}` : "";
  if (p.tipo_limite === "MAXIMO") return `Máx. ${n(p.limite)}${unidade}`;
  if (p.tipo_limite === "MINIMO") return `Mín. ${n(p.limite)}${unidade}`;
  if (p.tipo_limite === "FAIXA") return `${n(p.limite)} a ${n(p.limite_superior)}${unidade}`;
  if (p.tipo_limite === "QUALITATIVO") return p.referencia_texto;
  return p.unidade ? `Em ${p.unidade}` : "Informativo";
}

/* ----------------------------- Editor por tipo ----------------------------- */
export function EditorValores({
  ensaio, campos, onMudar, erros, avaliacao, disabled,
}: {
  ensaio: EnsaioCatalogo;
  campos: CamposValores;
  onMudar: (c: CamposValores) => void;
  erros: Record<string, string>;
  /** Avaliação da última gravação — só aparece quando os campos batem com ela. */
  avaliacao: Avaliacao | null;
  disabled: boolean;
}) {
  if (campos.tipo === "TABELA") {
    const campanha = avaliacao?.campanhas?.[0] as FichaTabela["campanhas"][number] | undefined;
    return (
      <div className="space-y-2">
        <ul className="divide-y divide-border rounded-lg border border-border">
          {parametrosDigitados(ensaio).map((p) => {
            const linha = campos.linhas[p.codigo] ?? { texto: "", estado: "MEDIDO" as EstadoMedida };
            const mudar = (parcial: Partial<LinhaTabela>) =>
              onMudar({ ...campos, linhas: { ...campos.linhas, [p.codigo]: { ...linha, ...parcial } } });
            const qualitativo = p.tipo_limite === "QUALITATIVO";
            return (
              <li key={p.id} className="flex flex-wrap items-center gap-x-3 gap-y-2 px-3 py-2">
                <div className="min-w-[12rem] flex-1">
                  <p className="text-sm font-medium text-fg">{p.nome}</p>
                  <p className="text-xs text-fg-subtle">{[referencia(p), p.norma.replace(" | ", " · ")].filter(Boolean).join(" · ")}</p>
                  {erros[p.codigo] && <p className="text-xs text-danger-fg">{erros[p.codigo]}</p>}
                </div>
                <div className="flex items-center gap-2">
                  <Input
                    className="w-32"
                    inputMode={qualitativo ? "text" : "decimal"}
                    tecnico={!qualitativo}
                    aria-label={`Valor de ${p.nome}`}
                    placeholder={linha.estado === "ABAIXO_LD" || linha.estado === "ABAIXO_LQ" ? "limite" : undefined}
                    value={linha.texto}
                    disabled={disabled || ["NAO_DETECTADO", "ACIMA_ESCALA", "INDISPONIVEL"].includes(linha.estado)}
                    onChange={(e) => mudar({ texto: e.target.value })}
                  />
                  {!qualitativo && (
                    <Select
                      className="w-32"
                      aria-label={`Estado de ${p.nome}`}
                      value={linha.estado}
                      disabled={disabled}
                      onChange={(e) => mudar({ estado: e.target.value as EstadoMedida })}
                    >
                      {ESTADOS.map((s) => <option key={s.valor} value={s.valor}>{s.label}</option>)}
                    </Select>
                  )}
                  <Conformidade conforme={campanha?.valores[p.codigo]?.conforme} />
                </div>
              </li>
            );
          })}
        </ul>
        {avaliacao?.indicadores && Object.keys(avaliacao.indicadores).length > 0 && (
          <p className="text-sm text-fg-muted">
            Calculado:{" "}
            {Object.entries(avaliacao.indicadores).map(([k, v]) => (
              <span key={k} className="data mr-3 font-medium text-fg">{k} = {numero(v, 0)}</span>
            ))}
          </p>
        )}
        {avaliacao?.gp_estimado && (
          <p className="text-xs text-fg-muted">Grau de polimerização estimado pelo 2-furfural (De Pablo).</p>
        )}
      </div>
    );
  }

  if (campos.tipo === "RXT") {
    const campanha = avaliacao?.campanhas?.[0] as FichaRelacao["campanhas"][number] | undefined;
    const limite = avaliacao?.limite;
    return (
      <div className="space-y-3">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[32rem] text-sm">
            <thead>
              <tr className="text-left text-xs text-fg-muted">
                <th className="py-1.5 pr-3 font-medium">Fase</th>
                <th className="py-1.5 pr-3 font-medium">Relação medida</th>
                <th className="py-1.5 font-medium">Erro</th>
              </tr>
            </thead>
            <tbody>
              {campos.fases.map((f, i) => {
                const calc = campanha?.fases.find((x) => x.serie === f.serie.trim());
                const mudar = (parcial: Partial<{ serie: string; texto: string }>) =>
                  onMudar({ ...campos, fases: campos.fases.map((x, k) => (k === i ? { ...x, ...parcial } : x)) });
                return (
                  <tr key={i} className="border-t border-border">
                    <td className="py-1.5 pr-3">
                      <Input aria-label={`Nome da fase ${i + 1}`} value={f.serie} disabled={disabled}
                        onChange={(e) => mudar({ serie: e.target.value })} />
                    </td>
                    <td className="py-1.5 pr-3">
                      <Input className="w-32" inputMode="decimal" tecnico aria-label={`Relação medida na ${f.serie}`}
                        value={f.texto} disabled={disabled} onChange={(e) => mudar({ texto: e.target.value })} />
                      {erros[`fase${i}`] && <p className="text-xs text-danger-fg">{erros[`fase${i}`]}</p>}
                    </td>
                    <td className="py-1.5">
                      <span className="data inline-flex items-center gap-1.5">
                        {calc?.erro != null ? `${numero(calc.erro, 2)} %` : "—"}
                        <Conformidade conforme={calc?.conforme} />
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <div className="flex flex-wrap items-end gap-x-6 gap-y-2">
          <div>
            <label className="label" htmlFor={`nominal-${ensaio.id}`}>Relação nominal informada</label>
            <Input id={`nominal-${ensaio.id}`} className="w-40" inputMode="decimal" tecnico placeholder="calculada"
              value={campos.nominal} disabled={disabled} onChange={(e) => onMudar({ ...campos, nominal: e.target.value })} />
            {erros.nominal && <p className="text-xs text-danger-fg">{erros.nominal}</p>}
          </div>
          {campanha && (
            <p className="text-sm text-fg-muted">
              Relação nominal usada:{" "}
              <span className="data font-medium text-fg">{campanha.nominal != null ? numero(campanha.nominal, 3) : "—"}</span>
              {campanha.nominal_calculada && " (calculada pelo TAP e pela placa)"}
              {limite?.superior != null && ` · erro admitido ± ${numero(limite.superior, 1)} % (${limite.norma})`}
            </p>
          )}
        </div>
        {campanha && campanha.nominal == null && (
          <p className="text-xs text-warning-fg">
            Sem relação nominal: informe a tensão do TAP no registro e a placa do transformador (tensão secundária e
            grupo de ligação) no cadastro, ou digite a relação nominal.
          </p>
        )}
      </div>
    );
  }

  if (campos.tipo === "RXI") {
    const series = avaliacao?.series ?? [];
    const mudarSerie = (j: number, parcial: Partial<{ nome: string; tensao: string }>) =>
      onMudar({ ...campos, series: campos.series.map((s, k) => (k === j ? { ...s, ...parcial } : s)) });
    const mudarCelula = (i: number, j: number, texto: string) =>
      onMudar({ ...campos, grade: campos.grade.map((linha, a) => (a === i ? linha.map((c, b) => (b === j ? texto : c)) : linha)) });
    return (
      <div className="overflow-x-auto">
        <table className="w-full min-w-[34rem] text-sm">
          <thead>
            <tr>
              <th className="py-1.5 pr-2 text-left text-xs font-medium text-fg-muted">Tempo [s]</th>
              {campos.series.map((s, j) => (
                <th key={j} className="px-1 py-1.5 text-left align-bottom font-normal">
                  <Input aria-label={`Ligação ${j + 1}`} value={s.nome} disabled={disabled}
                    onChange={(e) => mudarSerie(j, { nome: e.target.value })} />
                  <Input className="mt-1" inputMode="decimal" tecnico sufixo="V" placeholder="tensão"
                    aria-label={`Tensão de ensaio de ${s.nome}`} value={s.tensao} disabled={disabled}
                    onChange={(e) => mudarSerie(j, { tensao: e.target.value })} />
                  {erros[`tensao${j}`] && <p className="text-xs text-danger-fg">{erros[`tensao${j}`]}</p>}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {campos.tempos.map((t, i) => (
              <tr key={t} className={cn("border-t border-border", t === 60 && "font-semibold")}>
                <td className="data py-1 pr-2 text-fg-muted">{t}</td>
                {campos.series.map((s, j) => (
                  <td key={j} className="px-1 py-1">
                    <Input inputMode="decimal" tecnico sufixo="MΩ" aria-label={`${s.nome} aos ${t} s`}
                      value={campos.grade[i]?.[j] ?? ""} disabled={disabled}
                      onChange={(e) => mudarCelula(i, j, e.target.value)} />
                    {erros[`r${i}-${j}`] && <p className="text-xs text-danger-fg">{erros[`r${i}-${j}`]}</p>}
                  </td>
                ))}
              </tr>
            ))}
            {series.length > 0 && (
              <>
                <tr className="border-t-2 border-border">
                  <td className="py-1.5 pr-2 text-xs text-fg-muted">IP [600/60 s]</td>
                  {campos.series.map((s, j) => {
                    const calc = series.find((x) => x.nome === s.nome.trim());
                    return (
                      <td key={j} className="px-1 py-1.5">
                        <span className="data inline-flex items-center gap-1.5 font-medium">
                          {calc?.ip != null ? numero(calc.ip, 2) : "—"}
                          <Conformidade conforme={calc?.ip_conforme} />
                        </span>
                      </td>
                    );
                  })}
                </tr>
                <tr>
                  <td className="py-1.5 pr-2 text-xs text-fg-muted">IA [60/30 s]</td>
                  {campos.series.map((s, j) => {
                    const calc = series.find((x) => x.nome === s.nome.trim());
                    return <td key={j} className="data px-1 py-1.5">{calc?.ia != null ? numero(calc.ia, 2) : "—"}</td>;
                  })}
                </tr>
              </>
            )}
          </tbody>
        </table>
      </div>
    );
  }

  // R×O
  const campanha = avaliacao?.campanhas?.[0] as FichaOhmica["campanhas"][number] | undefined;
  const linha = (tipo: "Corrigido" | "Calculado") => campanha?.linhas.find((l) => l.tipo === tipo)?.valores ?? {};
  const corrigido = linha("Corrigido");
  const calculado = linha("Calculado");
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[32rem] text-sm">
        <thead>
          <tr className="text-left text-xs text-fg-muted">
            <th className="py-1.5 pr-3 font-medium">Terminais</th>
            <th className="py-1.5 pr-3 font-medium">Medido</th>
            <th className="py-1.5 pr-3 font-medium">Por fase</th>
            <th className="py-1.5 font-medium">Corrigido a 75 °C</th>
          </tr>
        </thead>
        <tbody>
          {parametrosDigitados(ensaio).map((p) => (
            <tr key={p.id} className="border-t border-border">
              <td className="py-1.5 pr-3 font-medium text-fg">{p.nome}</td>
              <td className="py-1.5 pr-3">
                <Input className="w-36" inputMode="decimal" tecnico sufixo={p.unidade} aria-label={`${p.nome} medido`}
                  value={campos.pares[p.codigo] ?? ""} disabled={disabled}
                  onChange={(e) => onMudar({ ...campos, pares: { ...campos.pares, [p.codigo]: e.target.value } })} />
                {erros[p.codigo] && <p className="text-xs text-danger-fg">{erros[p.codigo]}</p>}
              </td>
              <td className="data py-1.5 pr-3">
                {calculado[p.codigo] != null ? numero(calculado[p.codigo], p.casas_decimais) : campanha ? "= medido" : "—"}
              </td>
              <td className="data py-1.5 font-medium">
                {corrigido[p.codigo] != null ? `${numero(corrigido[p.codigo], p.casas_decimais)} ${p.unidade}` : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
