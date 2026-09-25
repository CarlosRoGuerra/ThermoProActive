import { Fragment, type CSSProperties } from "react";
import type {
  Cabecalho, FichaIsolacao, FichaOhmica, FichaRelacao, LinhaOhmica, SerieIsolacao, Transformador,
} from "../../tipos";
import { ddmmaaaa } from "../../shell/formato";
import { CATEGORICAS_KPI } from "../../shell/kpis";
import { BlocoValores, CabecalhoLaudo, CELULA, FolhaFicha, MarcaConformidade, TINTA, TOM } from "./folha";
import { TextosFicha } from "./fichas-oleo";
import { numero } from "./formato";
import { CurvasIsolacao } from "./graficos";

/* ============================================================================
   Fichas dos ensaios elétricos (2025-12_TRF-001_ENDe.pdf, págs. 2 a 4):
   R×T — relação medida por fase e erro contra a nominal do TAP;
   R×I — resistência de isolação no tempo, por ligação, com IP/IA e curvas;
   R×O — resistência ôhmica medida, por fase (calculada) e corrigida a 75 °C.
   ========================================================================== */

const LINHAS_RXT = 6;
const LINHAS_RXO = 7;

const cabecalhoTabela: CSSProperties = { ...CELULA, fontWeight: 400, fontSize: "7.5pt", color: TINTA.secundaria, lineHeight: 1.25 };
const nota: CSSProperties = { fontSize: "7.5pt", color: TINTA.secundaria, marginTop: "2mm", lineHeight: 1.3 };

/* --------------------------------- R×T ----------------------------------- */
export function FichaRelacao({ cab, f, t, informacoes }: {
  cab: Cabecalho; f: FichaRelacao; t: Transformador; informacoes: string;
}) {
  const nomes = Array.from(new Set(f.campanhas.flatMap((c) => c.fases.map((x) => x.serie))));
  const fases = nomes.length ? nomes : ["Fase 1", "Fase 2", "Fase 3"];
  const linhas = [...f.campanhas, ...Array<null>(Math.max(0, LINHAS_RXT - f.campanhas.length)).fill(null)];
  const { inferior, superior, norma } = f.limite;
  const tolerancia = inferior != null && superior != null && Math.abs(inferior) === Math.abs(superior)
    ? `± ${numero(superior, 1)}`
    : `${numero(inferior, 1)} a ${numero(superior, 1)}`;
  const calculada = f.campanhas.some((c) => c.nominal_calculada);
  return (
    <FolhaFicha cab={cab} titulo={f.titulo}>
      <CabecalhoLaudo f={f} />
      <BlocoValores>
        <table style={{ width: "100%", borderCollapse: "collapse", tableLayout: "fixed" }}>
          <colgroup>
            <col style={{ width: "19mm" }} />
            <col style={{ width: "19mm" }} />
            {fases.map((n) => <Fragment key={n}><col /><col /></Fragment>)}
            <col style={{ width: "24mm" }} />
          </colgroup>
          <thead>
            <tr>
              <th rowSpan={2} style={CELULA} />
              <th rowSpan={2} style={cabecalhoTabela}>Relação<br />Nominal</th>
              {fases.map((n) => (
                <th key={n} colSpan={2} style={{ ...cabecalhoTabela, whiteSpace: "pre-line", height: "9mm" }}>{n.replace(" (", "\n(")}</th>
              ))}
              <th rowSpan={2} style={cabecalhoTabela}>Erro máximo admitido [%]<br />{norma}</th>
            </tr>
            <tr>
              {fases.map((n) => (
                <Fragment key={n}>
                  <th style={cabecalhoTabela}>Medido</th>
                  <th style={cabecalhoTabela}>Erro (%)</th>
                </Fragment>
              ))}
            </tr>
          </thead>
          <tbody>
            {linhas.map((c, k) => {
              const peso = c?.atual ? 700 : 400;
              return (
                <tr key={k}>
                  <td style={{ ...CELULA, fontSize: "8pt", fontWeight: peso }}>{c ? ddmmaaaa(c.data) : ""}</td>
                  <td style={{ ...CELULA, fontSize: "10pt", fontWeight: peso }}>
                    {c ? numero(c.nominal, 3) : ""}{c?.nominal_calculada ? <sup>1</sup> : null}
                  </td>
                  {fases.map((n) => {
                    const fase = c?.fases.find((x) => x.serie === n);
                    const tom = fase?.conforme == null ? undefined : fase.conforme ? TOM.dentro : TOM.fora;
                    return (
                      <Fragment key={n}>
                        <td style={{ ...CELULA, fontSize: "10pt", fontWeight: peso }}>{fase ? numero(fase.medido, 3) : ""}</td>
                        <td style={{ ...CELULA, fontSize: "10pt", fontWeight: peso, background: tom?.fundo }}>
                          {fase ? numero(fase.erro, 2) : ""}
                          {fase && <MarcaConformidade conforme={fase.conforme} />}
                        </td>
                      </Fragment>
                    );
                  })}
                  <td style={{ ...CELULA, fontSize: "10pt", fontWeight: 700 }}>{c?.atual ? tolerancia : ""}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </BlocoValores>
      {calculada && (
        <p style={nota}>
          <sup>1</sup> Relação nominal calculada pela tensão do TAP e pelas tensões de placa dos enrolamentos
          {t.cadastro.grupo_ligacao ? ` (ligação ${t.cadastro.grupo_ligacao})` : ""}.
        </p>
      )}
      <TextosFicha f={f} informacoes={informacoes} />
    </FolhaFicha>
  );
}

/* --------------------------------- R×I ----------------------------------- */
function Tensao({ s }: { s: SerieIsolacao }) {
  return <td style={{ ...CELULA, fontSize: "7.5pt", color: TINTA.secundaria }}>{numero(s.tensao, 0)}</td>;
}

export function FichaIsolacao({ cab, f, informacoes }: { cab: Cabecalho; f: FichaIsolacao; informacoes: string }) {
  const { series, tempos } = f;
  const criterio = f.criterio_ip.limite != null
    ? `IP conforme a partir de ${numero(f.criterio_ip.limite, 1)}${f.criterio_ip.norma ? ` (${f.criterio_ip.norma})` : ""}`
    : "";
  return (
    <FolhaFicha cab={cab} titulo={f.titulo}>
      <CabecalhoLaudo f={f} />
      <BlocoValores>
        {series.length === 0 ? (
          <p style={{ padding: "6mm", textAlign: "center", fontSize: "9pt", color: TINTA.suave }}>{f.status_rotulo}.</p>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse", tableLayout: "fixed" }}>
            <colgroup>
              <col style={{ width: "19mm" }} />
              {series.map((s) => <Fragment key={s.nome}><col style={{ width: "13mm" }} /><col /></Fragment>)}
            </colgroup>
            <thead>
              <tr>
                <th style={cabecalhoTabela}>Tempo [s]</th>
                {series.map((s, i) => (
                  <Fragment key={s.nome}>
                    <th style={cabecalhoTabela}>[V]</th>
                    <th style={cabecalhoTabela}>
                      <span style={{ display: "inline-block", width: "3.5mm", height: "0.6mm", background: CATEGORICAS_KPI[i % 3], verticalAlign: "middle", marginRight: "1.2mm" }} />
                      {s.nome} [MΩ]
                    </th>
                  </Fragment>
                ))}
              </tr>
            </thead>
            <tbody>
              {tempos.map((tempo) => {
                // 60 s em negrito, como na ficha de referência (base do IP e do IA).
                const peso = tempo === 60 ? 700 : 400;
                return (
                  <tr key={tempo}>
                    <td style={{ ...CELULA, fontSize: "9pt", fontWeight: peso, color: TINTA.secundaria }}>{numero(tempo, 0)}</td>
                    {series.map((s) => {
                      const p = s.pontos.find((x) => x.tempo === tempo);
                      return (
                        <Fragment key={s.nome}>
                          <Tensao s={s} />
                          <td style={{ ...CELULA, fontSize: "9.5pt", fontWeight: peso }}>{p ? numero(p.valor, 0) : ""}</td>
                        </Fragment>
                      );
                    })}
                  </tr>
                );
              })}
              <tr>
                <td style={{ ...CELULA, fontSize: "7.5pt", textAlign: "left" }}>IP [600 s/60 s]</td>
                {series.map((s) => {
                  const tom = s.ip_conforme == null ? undefined : s.ip_conforme ? TOM.dentro : TOM.fora;
                  return (
                    <Fragment key={s.nome}>
                      <td style={CELULA} />
                      <td style={{ ...CELULA, fontSize: "9.5pt", fontWeight: 700, background: tom?.fundo }}>
                        {numero(s.ip, 2)}<MarcaConformidade conforme={s.ip_conforme} />
                      </td>
                    </Fragment>
                  );
                })}
              </tr>
              <tr>
                <td style={{ ...CELULA, fontSize: "7.5pt", textAlign: "left" }}>IA [60 s/30 s]</td>
                {series.map((s) => (
                  <Fragment key={s.nome}>
                    <td style={CELULA} />
                    <td style={{ ...CELULA, fontSize: "9.5pt" }}>{numero(s.ia, 2)}</td>
                  </Fragment>
                ))}
              </tr>
            </tbody>
          </table>
        )}
        {series.length > 0 && (
          <div style={{ padding: "2mm 2mm 1mm" }}>
            <CurvasIsolacao series={series} tempos={tempos} />
          </div>
        )}
      </BlocoValores>
      {criterio && series.length > 0 && (
        <p style={nota}>IP = resistência aos 600 s ÷ resistência aos 60 s; IA = resistência aos 60 s ÷ resistência aos 30 s. {criterio}.</p>
      )}
      <TextosFicha f={f} informacoes={informacoes} />
    </FolhaFicha>
  );
}

/* --------------------------------- R×O ----------------------------------- */
type LinhaTabelaOhmica = { data: string | null; tap: string; linha: LinhaOhmica; destaque: boolean; suave: boolean };

export function FichaOhmica({ cab, f, t, informacoes }: {
  cab: Cabecalho; f: FichaOhmica; t: Transformador; informacoes: string;
}) {
  // Campanhas anteriores entram só com o valor corrigido (a tendência); a atual
  // traz corrigido (negrito), calculado e medido, como na ficha de referência.
  const linhas: LinhaTabelaOhmica[] = [];
  for (const c of f.campanhas) {
    for (const linha of c.linhas) {
      if (!c.atual && linha.tipo !== "Corrigido") continue;
      linhas.push({ data: c.data, tap: c.tap, linha, destaque: c.atual && linha.tipo === "Corrigido", suave: linha.tipo !== "Corrigido" });
    }
  }
  const vazias = Math.max(0, LINHAS_RXO - linhas.length);
  const atual = f.campanhas.find((c) => c.atual);
  const { temperatura_referencia_c: tRef, constante } = f.correcao;
  return (
    <FolhaFicha cab={cab} titulo={f.titulo}>
      <CabecalhoLaudo f={f} />
      <BlocoValores>
        <table style={{ width: "100%", borderCollapse: "collapse", tableLayout: "fixed" }}>
          <colgroup>
            <col style={{ width: "19mm" }} />
            <col style={{ width: "13mm" }} />
            {f.pares.map((p) => <col key={p.codigo} />)}
            <col style={{ width: "22mm" }} />
          </colgroup>
          <thead>
            <tr>
              <th style={cabecalhoTabela} />
              <th style={cabecalhoTabela}>TAP</th>
              {f.pares.map((p) => (
                <th key={p.codigo} style={cabecalhoTabela}>{p.nome} <span style={{ fontSize: "6.5pt" }}>[{p.unidade}]</span></th>
              ))}
              <th style={cabecalhoTabela}>Valor</th>
            </tr>
          </thead>
          <tbody>
            {linhas.map((l, k) => {
              const estilo: CSSProperties = {
                ...CELULA, fontSize: "10pt", fontWeight: l.destaque ? 700 : 400, color: l.suave ? TINTA.suave : TINTA.primaria,
              };
              return (
                <tr key={k}>
                  <td style={{ ...estilo, fontSize: "8pt", color: TINTA.primaria }}>{ddmmaaaa(l.data)}</td>
                  <td style={estilo}>{l.tap}</td>
                  {f.pares.map((p) => <td key={p.codigo} style={estilo}>{numero(l.linha.valores[p.codigo], p.casas)}</td>)}
                  <td style={estilo}>{l.linha.tipo}</td>
                </tr>
              );
            })}
            {Array.from({ length: vazias }, (_, k) => (
              <tr key={`v${k}`}>
                {Array.from({ length: f.pares.length + 3 }, (_, i) => <td key={i} style={CELULA} />)}
              </tr>
            ))}
          </tbody>
        </table>
      </BlocoValores>
      <p style={nota}>
        Medido: leitura entre terminais. Calculado: resistência por fase
        {t.cadastro.grupo_ligacao ? ` (ligação ${t.cadastro.grupo_ligacao})` : ""}. Corrigido: por fase, referida a {numero(tRef, 0)} °C —
        R × ({numero(constante, 1)} + {numero(tRef, 0)}) ÷ ({numero(constante, 1)} + temperatura do óleo
        {atual?.temperatura_oleo_c != null ? `, ${numero(atual.temperatura_oleo_c, 1)} °C` : ""}).
      </p>
      <TextosFicha f={f} informacoes={informacoes} />
    </FolhaFicha>
  );
}
