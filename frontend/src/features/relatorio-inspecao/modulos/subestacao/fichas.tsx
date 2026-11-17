import { Fragment, type CSSProperties } from "react";
import type { Cabecalho } from "../../tipos";
import { CATEGORICAS_KPI } from "../../shell/kpis";
import { TextosFicha } from "../transformador/fichas-oleo";
import {
  BlocoValores, Campo, CabecalhoLaudo, CELULA, FolhaFicha, LINHA, MarcaConformidade, Quadro, QuadroCliente,
  TiposEnsaio, TINTA, TOM,
} from "../transformador/folha";
import { data, numero, numeroEnxuto } from "../transformador/formato";
import { CurvaExcitacao } from "../transformador/graficos";
import type {
  DossieSubestacao, EquipamentoSubestacao, FichaCurva, FichaMedicao, FichaSubestacao,
} from "./tipos";

/* ============================================================================
   Fichas dos ensaios elétricos de subestação — mesma folha, quadros, tabela de
   valores e textos das fichas do transformador (modulos/transformador). Duas formas:
   medição por série (uma linha por fase, polo, núcleo ou função; colunas calculadas
   quando há critério) e curva de excitação (tensão × corrente por núcleo).
   Cada ficha cabe numa folha A4; as linhas em branco mantêm a mesma altura.
   ========================================================================== */

const LINHAS_MEDICAO = 6;
const LINHAS_CURVA = 8;

const cabecalho: CSSProperties = { ...CELULA, fontWeight: 400, fontSize: "7.5pt", color: TINTA.secundaria, lineHeight: 1.25 };
const rotulo: CSSProperties = { ...CELULA, textAlign: "left", color: TINTA.suave, fontSize: "7pt" };
const miudo: CSSProperties = { ...CELULA, fontSize: "7pt", color: TINTA.suave, lineHeight: 1.2 };
const nota: CSSProperties = { fontSize: "7.5pt", color: TINTA.secundaria, marginTop: "2mm", lineHeight: 1.3 };

/** Informações do terceiro quadro: instrumento e informações adicionais, como na ficha de referência. */
const informacoesDa = (f: FichaSubestacao) => [f.instrumento, f.informacoes_adicionais].filter(Boolean).join("\n");

/* ------------------------------- Registro ------------------------------- */
/** Ficha 1 de cada equipamento: cadastro, dados de placa, condições do ensaio e ensaios solicitados. */
export function RegistroSubestacaoFicha({ d, e, titulo }: { d: DossieSubestacao; e: EquipamentoSubestacao; titulo: string }) {
  const c = e.cadastro;
  const r = e.registro;
  return (
    <FolhaFicha cab={d.cabecalho} titulo={titulo}>
      <QuadroCliente d={d} />
      <Quadro colunas={4} style={{ marginTop: "4mm" }}>
        <Campo rotulo="Local da Instalação do Equipamento" span={2}>{c.local}</Campo>
        <Campo rotulo="Identificação do Equipamento" span={2}>{c.identificacao}</Campo>
        <Campo rotulo="Número de Série" span={2}>{c.numero_serie}</Campo>
        <Campo rotulo="Número de Patrimônio" span={2}>{c.numero_patrimonio}</Campo>
        <Campo rotulo="Fabricante">{c.fabricante}</Campo>
        <Campo rotulo="Ano de Fabricação">{c.ano_fabricacao ?? ""}</Campo>
        <Campo rotulo="Tipo de Equipamento">{c.tipo_equipamento}</Campo>
        <Campo rotulo="Modelo">{c.modelo}</Campo>
        <Campo rotulo="Tensão Nominal" unidade="kV">{numeroEnxuto(c.tensao_nominal_kv, 3)}</Campo>
        <Campo rotulo="Corrente Nominal" unidade="A">{numeroEnxuto(c.corrente_nominal_a, 2)}</Campo>
        <Campo rotulo="Relação de Placa">{c.relacao_texto}</Campo>
        <Campo rotulo="Relação Nominal">{numeroEnxuto(c.relacao_transformacao, 4)}</Campo>
        <Campo rotulo="Classe de Exatidão">{c.classe_exatidao}</Campo>
        <Campo rotulo="Carga Nominal" unidade="VA">{numeroEnxuto(c.carga_nominal_va, 2)}</Campo>
        <Campo rotulo="Número de Núcleos">{c.numero_nucleos ?? ""}</Campo>
        <Campo rotulo="Polaridade">{c.polaridade}</Campo>
        <Campo rotulo="Número de Polos">{c.numero_polos ?? ""}</Campo>
        <Campo rotulo="Capacidade de Interrupção" unidade="kA">{numeroEnxuto(c.capacidade_interrupcao_ka, 2)}</Campo>
        <Campo rotulo="Mecanismo">{c.mecanismo}</Campo>
        {c.funcoes_protecao.length > 0 && (
          <Campo rotulo="Funções de Proteção do Relé" span={4}>{c.funcoes_protecao.join("  ·  ")}</Campo>
        )}
        <Campo rotulo="Data do Ensaio">{data(r?.data)}</Campo>
        <Campo rotulo="Analista">{r?.analista}</Campo>
        <Campo rotulo="Temperatura do Equipamento" unidade="°C">{numero(r?.temperatura_equipamento_c, 1)}</Campo>
        <Campo rotulo="Temperatura Ambiente" unidade="°C">{numero(r?.temperatura_ambiente_c, 1)}</Campo>
        <Campo rotulo="Umidade Relativa" unidade="%">{numero(r?.umidade_relativa_pct, 1)}</Campo>
        <TiposEnsaio tipos={e.tipos_ensaio} rotulos={{}} />
      </Quadro>
    </FolhaFicha>
  );
}

/* ------------------------------- Medições ------------------------------- */
function Notas({ f }: { f: FichaSubestacao }) {
  return (
    <>
      {f.status === "SEM_CRITERIO" && (
        <p style={nota}>Sem critério de aceitação definido para este ensaio: os valores são informativos.</p>
      )}
      {f.notas.length > 0 && (
        <div style={{ ...nota, textAlign: "justify" }}>
          {f.notas.map((n) => <p key={n} style={{ margin: "0 0 1mm" }}>{n}</p>)}
        </div>
      )}
    </>
  );
}

function FichaMedicaoView({ cab, f }: { cab: Cabecalho; f: FichaMedicao }) {
  const linhas = [...f.linhas, ...Array<null>(Math.max(0, LINHAS_MEDICAO - f.linhas.length)).fill(null)];
  const { criterio, indicadores } = f;
  const simultaneidades = [
    indicadores.simultaneidade_abertura_ms != null && `na abertura ${numero(indicadores.simultaneidade_abertura_ms, 1)} ms`,
    indicadores.simultaneidade_fechamento_ms != null && `no fechamento ${numero(indicadores.simultaneidade_fechamento_ms, 1)} ms`,
  ].filter(Boolean);
  return (
    <FolhaFicha cab={cab} titulo={f.titulo}>
      <CabecalhoLaudo f={f} />
      <BlocoValores>
        <table style={{ width: "100%", borderCollapse: "collapse", tableLayout: "fixed" }}>
          <colgroup>
            <col style={{ width: "26mm" }} />
            {f.colunas.map((c) => <col key={c.codigo} />)}
          </colgroup>
          <thead>
            <tr>
              <th style={{ ...CELULA, height: "11mm", fontSize: "7.5pt", color: TINTA.secundaria }}>Série</th>
              {f.colunas.map((c) => (
                <th key={c.codigo} style={{ ...cabecalho, whiteSpace: "pre-line" }}>
                  {c.nome}{c.calculado ? "\n(calculado)" : ""}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr>
              <td style={rotulo}>Unidades</td>
              {f.colunas.map((c) => <td key={c.codigo} style={miudo}>{c.unidade ? `(${c.unidade})` : ""}</td>)}
            </tr>
            <tr>
              <td style={rotulo}>Norma</td>
              {f.colunas.map((c) => <td key={c.codigo} style={{ ...miudo, fontSize: "6.5pt" }}>{c.norma}</td>)}
            </tr>
            {linhas.map((l, k) => (
              <tr key={k}>
                <td style={{ ...CELULA, fontSize: "8pt", textAlign: "left" }}>{l?.serie ?? ""}</td>
                {f.colunas.map((c) => {
                  const cel = l?.celulas[c.codigo];
                  const tom = cel?.conforme == null ? undefined : cel.conforme ? TOM.dentro : TOM.fora;
                  return (
                    <td key={c.codigo} style={{ ...CELULA, fontSize: "10pt", background: tom?.fundo }}>
                      {cel ? (cel.texto || numero(cel.valor, c.casas)) : ""}
                      {cel && cel.conforme != null && <MarcaConformidade conforme={cel.conforme} />}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </BlocoValores>
      {criterio && (
        <p style={nota}>
          {criterio.admissivel != null
            ? `Erro admitido ± ${numero(criterio.admissivel, 2)} % pela classe ${criterio.classe} (${criterio.norma}).`
            : `Classe ${criterio.classe || "não informada"} sem critério na tabela de ${criterio.norma}: erro sem critério definido.`}
          {criterio.relacao_nominal != null && ` Relação nominal da placa: ${numeroEnxuto(criterio.relacao_nominal, 4)}.`}
        </p>
      )}
      {simultaneidades.length > 0 && (
        <p style={nota}>Simultaneidade entre polos: {simultaneidades.join(" · ")} (critério do fabricante).</p>
      )}
      <TextosFicha f={f} informacoes={informacoesDa(f)} />
      <Notas f={f} />
    </FolhaFicha>
  );
}

/* ---------------------------------- Curva ---------------------------------- */
function FichaCurvaView({ cab, f }: { cab: Cabecalho; f: FichaCurva }) {
  const linhas = [...f.tabela, ...Array<null>(Math.max(0, LINHAS_CURVA - f.tabela.length)).fill(null)];
  const joelhos = Object.entries(f.joelhos);
  return (
    <FolhaFicha cab={cab} titulo={f.titulo}>
      <CabecalhoLaudo f={f} />
      <BlocoValores>
        {f.series.length === 0 ? (
          <p style={{ padding: "6mm", textAlign: "center", fontSize: "9pt", color: TINTA.suave }}>{f.status_rotulo}.</p>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse", tableLayout: "fixed" }}>
            <colgroup>
              <col style={{ width: "26mm" }} />
              {f.series.map((s) => <col key={s} />)}
            </colgroup>
            <thead>
              <tr>
                <th style={cabecalho}>Tensão [V]</th>
                {f.series.map((s, i) => (
                  <th key={s} style={cabecalho}>
                    <span style={{ display: "inline-block", width: "3.5mm", height: "0.6mm", background: CATEGORICAS_KPI[i % CATEGORICAS_KPI.length], verticalAlign: "middle", marginRight: "1.2mm" }} />
                    {s} [mA]
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {linhas.map((l, k) => (
                <tr key={k}>
                  <td style={{ ...CELULA, fontSize: "9pt" }}>{l ? numero(l.tensao, 0) : ""}</td>
                  {f.series.map((s) => (
                    <td key={s} style={{ ...CELULA, fontSize: "9.5pt" }}>{l ? numero(l.correntes[s], 2) : ""}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </BlocoValores>
      <div style={{ border: LINHA, marginTop: "3mm", padding: "0.3mm 1.2mm 1mm" }}>
        <div style={{ fontSize: "6.5pt", color: TINTA.suave, lineHeight: 1.25 }}>Curva de excitação</div>
        <CurvaExcitacao series={f.grafico} />
      </div>
      {joelhos.length > 0 && (
        <p style={nota}>
          Tensão de joelho (IEEE C57.13 — 10 % a mais de tensão exige 50 % a mais de corrente): {joelhos.map(([nome, v]) => (
            <span key={nome} style={{ marginRight: "4mm" }}>{nome}: {v != null ? `${numero(v, 0)} V` : "não atingido"}</span>
          ))}
        </p>
      )}
      <TextosFicha f={f} informacoes={informacoesDa(f)} />
      <Notas f={f} />
    </FolhaFicha>
  );
}

/** Ficha de um ensaio: medição por série ou curva, conforme a forma do ensaio no catálogo. */
export function FichaEnsaioSubestacao({ cab, f }: { cab: Cabecalho; f: FichaSubestacao }) {
  return f.tipo === "CURVA" ? <FichaCurvaView cab={cab} f={f} /> : <FichaMedicaoView cab={cab} f={f} />;
}
