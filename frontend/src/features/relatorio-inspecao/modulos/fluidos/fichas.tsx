import type { CSSProperties, ReactNode } from "react";
import type { AmostraFluido, Cabecalho, CelulaFluido, DossieFluido, FichaFluido, GrauRisco, LinhaFluido } from "../../tipos";
import { STATUS_KPI } from "../../shell/kpis";
import {
  AZUL_TITULO, BlocoValores, CabecalhoLaudo, CaixaTexto, Campo, CELULA as CELULA_BASE, FolhaFicha, LINHA, LINHA_GRADE, Quadro, QuadroCliente,
  TINTA, TiposEnsaio, TOM,
} from "../transformador/folha";
import { data, numero } from "../transformador/formato";
import { CodigosIso, Tendencias } from "./graficos";

/* ============================================================================
   Fichas da análise de fluidos lubrificantes e hidráulicos — mesma folha,
   timbrado e quadros das fichas de óleo isolante (identidade do relatório);
   conteúdo próprio:

     Registro da coleta → FQ → EF → CP   (por equipamento da rota)

   FQ e EF: uma linha por parâmetro, uma coluna por coleta (até 6, a atual por
   último, em negrito), com a referência cadastrada e o estado na atual. Só saem
   os parâmetros que o laboratório informou em alguma coleta — nem todo
   laboratório analisa todos os elementos. CP: contagens por tamanho, o código
   ISO 4406 de cada coleta e a comparação com a meta, quando há meta.
   ========================================================================== */

const ROTULOS_ENSAIO: Record<string, string> = {
  FQ: "FQ - Físico-Química", EF: "EF - Espectrofotometria", CP: "CP - Contagem de Partículas",
};

const ESTADO: Record<string, { rotulo: string; cor: string; fundo?: string }> = {
  ROTINA: { rotulo: "Rotina", cor: STATUS_KPI.good },
  ALERTA: { rotulo: "Alerta", cor: "#9a6a00", fundo: "#fdf1d6" },
  CRITICA: { rotulo: "Crítica", cor: STATUS_KPI.critical, fundo: TOM.fora.fundo },
};
const ROTULO_ESTADO_VALOR: Record<string, string> = {
  ABAIXO_LD: "< LD", ABAIXO_LQ: "< LQ", NAO_DETECTADO: "N.D.", ACIMA_ESCALA: "> escala", INDISPONIVEL: "Indisp.",
};
const SETA = { SOBE: "↑", DESCE: "↓", ESTAVEL: "→" } as const;

const simNao = (v: boolean | null) => (v == null ? "" : v ? "Sim" : "Não");

function textoValor(l: LinhaFluido, c: CelulaFluido) {
  if (c.estado && c.estado !== "MEDIDO") return c.texto || ROTULO_ESTADO_VALOR[c.estado] || "";
  if (c.valor != null) return numero(c.valor, l.casas);
  return c.texto;
}

const temValor = (c: CelulaFluido) => c.valor != null || !!c.texto || (!!c.estado && c.estado !== "MEDIDO");

/* ------------------------------ Registro ------------------------------ */
function RegistroColetaFluido({ d, a }: { d: DossieFluido; a: AmostraFluido }) {
  const c = a.cadastro;
  const k = a.coleta;
  const complemento = k?.complemento_recente
    ? `Sim${k.volume_complemento_l != null ? ` (${numero(k.volume_complemento_l, 1)} L)` : ""}`
    : simNao(k?.complemento_recente ?? null);
  return (
    <FolhaFicha cab={d.cabecalho} titulo="REGISTRO DE DADOS DE COLETA DE AMOSTRA DE FLUIDO">
      <QuadroCliente d={d} />
      <Quadro colunas={4} style={{ marginTop: "4mm" }}>
        <Campo rotulo="Local da Instalação do Equipamento" span={2}>{c.local}</Campo>
        <Campo rotulo="Identificação do Equipamento" span={2}>{c.identificacao}</Campo>
        <Campo rotulo="Tipo de Equipamento" span={2}>{c.tipo_equipamento}</Campo>
        <Campo rotulo="Fabricante">{c.fabricante}</Campo>
        <Campo rotulo="Modelo">{c.modelo}</Campo>
        <Campo rotulo="Número de Série" span={2}>{c.numero_serie}</Campo>
        <Campo rotulo="Número de Patrimônio" span={2}>{c.numero_patrimonio}</Campo>
      </Quadro>
      <h3 style={{ fontSize: "10pt", fontWeight: 700, color: AZUL_TITULO, margin: "4mm 0 1.5mm" }}>Fluido</h3>
      <Quadro colunas={4}>
        <Campo rotulo="Aplicação">{k?.aplicacao_display}</Campo>
        <Campo rotulo="Fluido" span={2}>{k?.fluido}</Campo>
        <Campo rotulo="Grau de Viscosidade">{k?.grau_viscosidade}</Campo>
        <Campo rotulo="Fabricante do Fluido" span={2}>{k?.fabricante_fluido}</Campo>
        <Campo rotulo="Volume do Reservatório" unidade="L">{numero(k?.volume_reservatorio_l, 1)}</Campo>
        <Campo rotulo="Horas do Fluido" unidade="h">{numero(k?.horas_fluido, 0)}</Campo>
        <Campo rotulo="Última Troca do Fluido" span={2}>{data(k?.data_ultima_troca)}</Campo>
      </Quadro>
      <h3 style={{ fontSize: "10pt", fontWeight: 700, color: AZUL_TITULO, margin: "4mm 0 1.5mm" }}>Coleta</h3>
      <Quadro colunas={4}>
        <Campo rotulo="Data da Coleta">{data(k?.data)}</Campo>
        <Campo rotulo="Identificação da Amostra">{k?.identificacao_amostra}</Campo>
        <Campo rotulo="Amostrador" span={2}>{k?.amostrador}</Campo>
        <Campo rotulo="Ponto de Coleta" span={2}>{k?.ponto_coleta}</Campo>
        <Campo rotulo="Condição Operacional" span={2}>{k?.condicao_operacional}</Campo>
        <Campo rotulo="Temperatura do Fluido" unidade="°C">{numero(k?.temperatura_fluido_c, 1)}</Campo>
        <Campo rotulo="Temperatura Ambiente" unidade="°C">{numero(k?.temperatura_ambiente_c, 1)}</Campo>
        <Campo rotulo="Horas do Equipamento" unidade="h">{numero(k?.horas_equipamento, 0)}</Campo>
        <Campo rotulo="Complemento Recente">{complemento}</Campo>
        <Campo rotulo="Troca Recente de Filtro">{simNao(k?.troca_filtro_recente ?? null)}</Campo>
        <Campo rotulo="Intervenção / Manutenção Recente" span={3}>{k?.intervencao_recente}</Campo>
        <TiposEnsaio tipos={a.tipos_ensaio} rotulos={ROTULOS_ENSAIO} />
      </Quadro>
      {!k && <p style={{ fontSize: "9pt", color: TINTA.suave, marginTop: "3mm" }}>Coleta não registrada.</p>}
      {k?.observacoes && (
        <div style={{ border: LINHA, padding: "0.3mm 1.2mm 0.8mm", marginTop: "3mm" }}>
          <div style={{ fontSize: "6.5pt", color: TINTA.suave }}>Observações</div>
          <div style={{ fontSize: "10pt", whiteSpace: "pre-line" }}>{k.observacoes}</div>
        </div>
      )}
    </FolhaFicha>
  );
}

/* --------------------------- Tabela de parâmetros --------------------------- */
function Estado({ l }: { l: LinhaFluido }) {
  const e = l.status ? ESTADO[l.status] : null;
  const t = l.tendencia;
  return (
    <span style={{ display: "inline-flex", flexDirection: "column", alignItems: "center", lineHeight: 1.15 }}>
      <span style={{ fontWeight: 700, color: e?.cor ?? TINTA.suave, fontSize: "7.5pt" }}>
        {e ? e.rotulo : l.sem_referencia ? "Sem ref." : "—"}
      </span>
      {t && t.pct_anterior != null && (
        <span style={{ fontSize: "6.5pt", color: TINTA.secundaria }}>
          {SETA[t.direcao]} {t.pct_anterior > 0 ? "+" : ""}{numero(t.pct_anterior, 0)}%
        </span>
      )}
    </span>
  );
}

function TabelaFluido({ f, linhas }: { f: FichaFluido; linhas: LinhaFluido[] }) {
  const n = f.campanhas.length;
  // Compacta: o EF tem até 21 elementos e a ficha precisa caber numa A4 com diagnóstico e legenda.
  const CELULA: CSSProperties = { ...CELULA_BASE, height: "3.8mm", padding: "0.1mm 0.8mm", lineHeight: 1.15 };
  const cab: CSSProperties = { ...CELULA, fontWeight: 400, fontSize: "6.5pt", color: TINTA.secundaria, lineHeight: 1.15 };
  const grupoLinha = (g: string) => (
    <tr key={`g-${g}`}>
      <td colSpan={5 + n} style={{ ...CELULA, textAlign: "left", fontWeight: 700, fontSize: "7.5pt", background: "#f1f5f9" }}>{g}</td>
    </tr>
  );
  const corpo: ReactNode[] = [];
  let grupoAtual: string | null = null;
  for (const l of linhas) {
    if (f.grupos.length > 1 && l.grupo !== grupoAtual) {
      grupoAtual = l.grupo;
      if (l.grupo) corpo.push(grupoLinha(l.grupo));
    }
    const fundo = l.status ? ESTADO[l.status].fundo : undefined;
    corpo.push(
      <tr key={l.codigo}>
        <td style={{ ...CELULA, textAlign: "left", fontSize: "7.5pt" }}>
          {l.nome}{l.simbolo ? ` (${l.simbolo})` : ""}
        </td>
        <td style={{ ...CELULA, fontSize: "7pt", color: TINTA.secundaria }}>{l.unidade}</td>
        <td style={{ ...CELULA, fontSize: "6.5pt", color: TINTA.secundaria }}>{l.metodo || l.norma}</td>
        <td style={{ ...CELULA, fontSize: "6.5pt", color: TINTA.secundaria, lineHeight: 1.15 }}>
          {l.referencia ? l.referencia.texto : l.oleo_novo_texto || "—"}
        </td>
        {l.valores.map((c, i) => {
          const atual = f.campanhas[i]?.atual;
          return (
            <td key={i} style={{ ...CELULA, fontSize: "8pt", fontWeight: atual ? 700 : 400, background: atual ? fundo : undefined }}>
              {textoValor(l, c)}
            </td>
          );
        })}
        <td style={{ ...CELULA }}><Estado l={l} /></td>
      </tr>,
    );
  }
  return (
    <table style={{ width: "100%", borderCollapse: "collapse", tableLayout: "fixed" }}>
      <colgroup>
        <col style={{ width: "34mm" }} />
        <col style={{ width: "12mm" }} />
        <col style={{ width: "18mm" }} />
        <col style={{ width: "28mm" }} />
        {f.campanhas.map((_, i) => <col key={i} />)}
        <col style={{ width: "19mm" }} />
      </colgroup>
      <thead>
        <tr>
          <th style={{ ...cab, textAlign: "left" }}>Parâmetro</th>
          <th style={cab}>Unid.</th>
          <th style={cab}>Método</th>
          <th style={cab}>Referência</th>
          {f.campanhas.map((c, i) => (
            <th key={i} style={{ ...cab, fontWeight: c.atual ? 700 : 400, color: c.atual ? TINTA.primaria : TINTA.secundaria }}>
              {c.data ? data(c.data) : "—"}
            </th>
          ))}
          <th style={cab}>Estado</th>
        </tr>
      </thead>
      <tbody>{corpo}</tbody>
    </table>
  );
}

/** Origem das referências usadas na ficha — rastreabilidade dos limites impressos. */
function OrigemReferencias({ linhas }: { linhas: LinhaFluido[] }) {
  const grupos = new Map<string, string[]>();
  for (const l of linhas) {
    if (!l.referencia) continue;
    const r = l.referencia;
    const chave = [r.origem_display, r.escopo !== "Geral" ? `por ${r.escopo.toLowerCase()}` : "", r.fonte].filter(Boolean).join(" · ");
    grupos.set(chave, [...(grupos.get(chave) ?? []), l.simbolo || l.nome]);
  }
  if (!grupos.size) return null;
  return (
    <p style={{ fontSize: "7pt", color: TINTA.secundaria, margin: "1mm 1.2mm 0.8mm", lineHeight: 1.3 }}>
      <b>Referências:</b> {Array.from(grupos.entries()).map(([k, ps]) => `${ps.join(", ")} — ${k}`).join("; ")}.
    </p>
  );
}

/* --------------------- Diagnóstico e legenda (como no modelo) --------------------- */
const CHIP: Record<string, { rotulo: string; fundo: string; tinta: string; legenda: string }> = {
  ROTINA: { rotulo: "OK", fundo: "#00a651", tinta: "#fff", legenda: "Não necessita intervenção" },
  ALERTA: { rotulo: "ATENÇÃO", fundo: "#ffe600", tinta: "#000", legenda: "Intensificar monitoramento" },
  CRITICA: { rotulo: "INTERVIR", fundo: "#e30613", tinta: "#fff", legenda: "Atenção imediata" },
};
const FUNDO_GRAU: Record<string, { fundo: string; tinta: string }> = {
  "GR-0": { fundo: "#00a651", tinta: "#fff" }, "GR-1": { fundo: "#e30613", tinta: "#fff" },
  "GR-2": { fundo: "#e30613", tinta: "#fff" }, "GR-3": { fundo: "#f28c28", tinta: "#000" },
  "GR-4": { fundo: "#ffe600", tinta: "#000" },
};
const BARRA: CSSProperties = { background: "#0b1f5c", color: "#fff", fontWeight: 700, fontSize: "7.5pt", padding: "0.6mm 1.5mm" };

function Chip({ rotulo, fundo, tinta }: { rotulo: string; fundo: string; tinta: string }) {
  return (
    <span style={{ display: "inline-block", minWidth: "22mm", textAlign: "center", fontWeight: 700, fontSize: "8pt",
      background: fundo, color: tinta, padding: "0.4mm 2mm" }}>{rotulo}</span>
  );
}

/** STATUS do ensaio (OK / ATENÇÃO / INTERVIR), GR da amostra, observações geradas pelas referências e a legenda. */
function Diagnostico({ f, grau }: { f: FichaFluido; grau: GrauRisco | null }) {
  const chip = CHIP[f.status];
  const cor = grau ? FUNDO_GRAU[grau.sigla] : null;
  return (
    <div style={{ marginTop: "3mm", border: LINHA }}>
      <div style={{ ...BARRA, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span>DIAGNÓSTICO</span>
        <span style={{ display: "inline-flex", gap: "3mm", fontWeight: 400, fontSize: "6pt" }}>
          {Object.values(CHIP).map((c) => (
            <span key={c.rotulo} style={{ display: "inline-flex", alignItems: "center", gap: "1mm" }}>
              <span style={{ background: c.fundo, color: c.tinta, fontWeight: 700, padding: "0.1mm 1.8mm", fontSize: "6pt" }}>{c.rotulo}</span>
              {c.legenda}
            </span>
          ))}
        </span>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "auto auto 1fr", columnGap: "3mm", fontSize: "8pt", padding: "1mm 1.5mm", alignItems: "center" }}>
        <span><b>STATUS</b>{" "}{chip ? <Chip {...chip} /> : <span style={{ color: TINTA.secundaria }}>{f.status_rotulo}</span>}</span>
        <b>GRAU DE RISCO</b>
        <span>
          {grau && cor ? (
            <>
              <Chip rotulo={grau.rotulo} {...cor} />{" "}
              <span style={{ fontSize: "7.5pt", color: TINTA.secundaria }}>
                {grau.prazo_texto}
                {grau.origem === "ANALISTA" ? " (anomalia observada em campo)" : ` · ${grau.ensaios_com_anomalia} de ${grau.ensaios_avaliados} ensaio(s) com anomalia`}
              </span>
            </>
          ) : (
            <span style={{ color: TINTA.secundaria }}>Sem ensaio avaliado pelas referências</span>
          )}
        </span>
      </div>
      {(f.laboratorio || f.instrumento) && (
        <div style={{ fontSize: "7pt", color: TINTA.secundaria, padding: "0 1.5mm 1mm" }}>
          Laboratório: {[f.instrumento, f.laboratorio].filter(Boolean).join(" — ")}
        </div>
      )}
      {f.observacoes_geradas.length > 0 && (
        <>
          <div style={{ ...BARRA, background: "#e8ecf6", color: "#0b1f5c" }}>OBSERVAÇÕES ANALÍTICAS (pelas referências cadastradas)</div>
          <ul style={{ margin: 0, padding: "1mm 1.5mm 1mm 5mm", fontSize: "8pt", lineHeight: 1.3 }}>
            {f.observacoes_geradas.map((o) => <li key={o}>{o}</li>)}
          </ul>
        </>
      )}
    </div>
  );
}

function Grafico({ children }: { children: ReactNode }) {
  return (
    <div style={{ border: LINHA, marginTop: "3mm", padding: "0.3mm 1.2mm 1mm" }}>
      <div style={{ fontSize: "6.5pt", color: TINTA.suave, lineHeight: 1.25, marginBottom: "0.5mm" }}>Tendência</div>
      {children}
    </div>
  );
}

function Notas({ f }: { f: FichaFluido }) {
  if (!f.notas.length) return null;
  return (
    <div style={{ fontSize: "7.5pt", color: TINTA.secundaria, marginTop: "2.5mm", lineHeight: 1.3, textAlign: "justify" }}>
      {f.notas.map((n) => <p key={n} style={{ margin: "0 0 1mm" }}>{n}</p>)}
    </div>
  );
}

/** Conclusão e Recomendação lado a lado; "Informações adicionais" só quando há texto (o laboratório vai no diagnóstico). */
function TextosFluido({ f }: { f: FichaFluido }) {
  return (
    <>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 2mm" }}>
        <CaixaTexto rotulo={f.rotulos.conclusao}>{f.conclusao}</CaixaTexto>
        <CaixaTexto rotulo="Recomendação">{f.recomendacao}</CaixaTexto>
      </div>
      {f.informacoes_adicionais && <CaixaTexto rotulo={f.rotulos.informacoes}>{f.informacoes_adicionais}</CaixaTexto>}
    </>
  );
}

function SemResultado({ f }: { f: FichaFluido }) {
  return (
    <p style={{ fontSize: "9pt", color: TINTA.secundaria, padding: "3mm 1.2mm" }}>
      {f.status_rotulo}.
    </p>
  );
}

/** FQ e EF. */
function FichaParametrosFluido({ cab, f, grau }: { cab: Cabecalho; f: FichaFluido; grau: GrauRisco | null }) {
  const linhas = f.linhas.filter((l) => l.valores.some(temValor));
  return (
    <FolhaFicha cab={cab} titulo={f.titulo}>
      <CabecalhoLaudo f={f} />
      <BlocoValores>
        {linhas.length ? <TabelaFluido f={f} linhas={linhas} /> : <SemResultado f={f} />}
        <OrigemReferencias linhas={linhas} />
      </BlocoValores>
      <Diagnostico f={f} grau={grau} />
      <TextosFluido f={f} />
      {linhas.length > 0 && (
        <Grafico><Tendencias linhas={linhas} campanhas={f.campanhas} maximo={4} altura={linhas.length > 14 ? 26 : 34} /></Grafico>
      )}
      <Notas f={f} />
    </FolhaFicha>
  );
}

const SITUACAO_META = {
  DENTRO: { rotulo: "Dentro da meta", cor: STATUS_KPI.good },
  FORA: { rotulo: "Fora da meta", cor: STATUS_KPI.critical },
  SEM_META: { rotulo: "Sem meta cadastrada", cor: TINTA.suave },
} as const;

/** CP: contagens, código ISO 4406 por coleta e a meta de limpeza. */
function FichaContagem({ cab, f, grau }: { cab: Cabecalho; f: FichaFluido; grau: GrauRisco | null }) {
  const essenciais = new Set(["P4", "P6", "P14"]);
  const linhas = f.linhas.filter((l) => essenciais.has(l.codigo) || l.valores.some(temValor));
  const codigos = f.codigos ?? [];
  const atual = codigos.find((c) => c.atual);
  const metaEscalas = f.meta?.referencia_texto
    ? f.meta.referencia_texto.split("/").map((p) => (p === ">28" ? 29 : Number(p)))
    : null;
  const situacao = f.situacao_meta ? SITUACAO_META[f.situacao_meta] : null;
  return (
    <FolhaFicha cab={cab} titulo={f.titulo}>
      <CabecalhoLaudo f={f} />
      <BlocoValores>
        {f.situacao === "REALIZADO" ? (
          <>
            <TabelaFluido f={f} linhas={linhas} />
            <table style={{ width: "100%", borderCollapse: "collapse", tableLayout: "fixed" }}>
              <colgroup>
                <col style={{ width: "92mm" }} />
                {f.campanhas.map((_, i) => <col key={i} />)}
                <col style={{ width: "19mm" }} />
              </colgroup>
              <tbody>
                <tr>
                  <td style={{ ...CELULA_BASE, textAlign: "left", fontWeight: 700, fontSize: "8pt", borderTop: LINHA_GRADE }}>
                    Código ISO 4406 (&gt; 4 / &gt; 6 / &gt; 14 µm(c))
                  </td>
                  {codigos.map((c, i) => (
                    <td key={i} style={{ ...CELULA_BASE, fontWeight: c.atual ? 700 : 400, fontSize: "8.5pt" }}>{c.codigo ?? "—"}</td>
                  ))}
                  <td style={CELULA_BASE} />
                </tr>
              </tbody>
            </table>
          </>
        ) : (
          <SemResultado f={f} />
        )}
      </BlocoValores>
      {f.situacao === "REALIZADO" && (
        <Quadro colunas={4} style={{ marginTop: "3mm" }}>
          <Campo rotulo="Código Obtido">{atual?.codigo ?? ""}</Campo>
          <Campo rotulo="Meta de Limpeza">{f.meta?.referencia_texto ?? ""}</Campo>
          <Campo rotulo="Situação">
            {situacao && <span style={{ color: situacao.cor, fontWeight: 700 }}>{situacao.rotulo}</span>}
            {f.situacao_meta === "FORA" && f.excesso_meta ? ` (+${f.excesso_meta})` : ""}
          </Campo>
          <Campo rotulo="Origem da Meta">
            <span style={{ fontSize: "8pt" }}>{f.meta ? [f.meta.origem_display, f.meta.fonte].filter(Boolean).join(" · ") : ""}</span>
          </Campo>
        </Quadro>
      )}
      <Diagnostico f={f} grau={grau} />
      <TextosFluido f={f} />
      {f.situacao === "REALIZADO" && codigos.some((c) => c.codigo) && (
        <Grafico><CodigosIso codigos={codigos} meta={metaEscalas} /></Grafico>
      )}
      <Notas f={f} />
    </FolhaFicha>
  );
}

export function FichasAmostra({ d, a }: { d: DossieFluido; a: AmostraFluido }) {
  return (
    <>
      <RegistroColetaFluido d={d} a={a} />
      {a.ensaios.map((f) =>
        f.tipo === "CP"
          ? <FichaContagem key={f.sigla} cab={d.cabecalho} f={f} grau={a.grau_risco} />
          : <FichaParametrosFluido key={f.sigla} cab={d.cabecalho} f={f} grau={a.grau_risco} />,
      )}
    </>
  );
}
