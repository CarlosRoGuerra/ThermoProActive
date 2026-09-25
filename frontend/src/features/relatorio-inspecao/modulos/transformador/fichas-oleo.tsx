import type { CSSProperties, ReactNode } from "react";
import type { Cabecalho, CelulaEnsaio, FichaEnsaio, FichaTabela, ParametroEnsaio, TipoLimite } from "../../tipos";
import { ddmmaaaa } from "../../shell/formato";
import {
  BlocoValores, CabecalhoLaudo, CaixaTexto, CELULA, FolhaFicha, LINHA, MarcaConformidade, TINTA, TOM,
} from "./folha";
import { numero } from "./formato";
import { GraficoReferencia } from "./graficos";

/* ============================================================================
   Fichas de resultado em tabela de parâmetros — FQ, CR, PCB e 2-FAL
   (2025-12_TRF-001_Óleo.pdf, págs. 2 a 5): grade de 9 colunas de parâmetro,
   linhas de unidade/norma/referência e uma linha por campanha (a atual em
   negrito, por último), textos do laudo, gráfico em % da referência e notas.
   ========================================================================== */

const COLUNAS_PARAMETRO = 9;
export const LINHAS_CAMPANHA = 6;

const TIPO_REFERENCIA: Record<TipoLimite, string> = {
  MAXIMO: "Máx.", MINIMO: "Mín.", FAIXA: "Faixa", QUALITATIVO: "", INFORMATIVO: "",
};
const ROTULO_ESTADO: Record<string, string> = {
  ABAIXO_LD: "< LD", ABAIXO_LQ: "< LQ", NAO_DETECTADO: "N.D.", ACIMA_ESCALA: "> escala", INDISPONIVEL: "Indisp.",
};

function referencia(p: ParametroEnsaio) {
  if (p.tipo_limite === "QUALITATIVO") return p.referencia_texto;
  if (p.tipo_limite === "INFORMATIVO") return "";
  if (p.tipo_limite === "FAIXA") return `${numero(p.limite, p.casas)} a ${numero(p.limite_superior, p.casas)}`;
  return numero(p.limite, p.casas);
}

/** Valor como a ficha imprime: número nas casas do catálogo, texto do laboratório ou estado (< LD…). */
function textoValor(p: ParametroEnsaio, c: CelulaEnsaio) {
  if (c.estado && c.estado !== "MEDIDO") return c.texto || ROTULO_ESTADO[c.estado] || "";
  if (c.valor != null) return numero(c.valor, p.casas) + (c.calculado ? "*" : "");
  return c.texto;
}

/** Observações, recomendação e o terceiro quadro (informações ou instrumentação). */
export function TextosFicha({ f, informacoes, complementoConclusao }: {
  f: FichaEnsaio; informacoes: string; complementoConclusao?: ReactNode;
}) {
  return (
    <>
      <CaixaTexto rotulo={f.rotulos.conclusao}>
        {f.conclusao}
        {complementoConclusao}
      </CaixaTexto>
      <CaixaTexto rotulo="Recomendação">{f.recomendacao}</CaixaTexto>
      <CaixaTexto rotulo={f.rotulos.informacoes}>{informacoes}</CaixaTexto>
    </>
  );
}

function TabelaParametros({ f }: { f: FichaTabela }) {
  const colunas: (ParametroEnsaio | null)[] = [
    ...f.parametros, ...Array<null>(Math.max(0, COLUNAS_PARAMETRO - f.parametros.length)).fill(null),
  ];
  const linhas = [...f.campanhas, ...Array<null>(Math.max(0, LINHAS_CAMPANHA - f.campanhas.length)).fill(null)];
  const rotulo: CSSProperties = { ...CELULA, textAlign: "left", color: TINTA.suave, fontSize: "7pt" };
  const miudo: CSSProperties = { ...CELULA, fontSize: "7pt", color: TINTA.suave, lineHeight: 1.2 };
  return (
    <table style={{ width: "100%", borderCollapse: "collapse", tableLayout: "fixed" }}>
      <colgroup>
        <col style={{ width: "19mm" }} />
        {colunas.map((_, i) => <col key={i} />)}
      </colgroup>
      <thead>
        <tr>
          <th style={{ ...CELULA, height: "11mm" }} />
          {colunas.map((p, i) => (
            <th key={i} style={{ ...CELULA, fontWeight: 400, fontSize: "7pt", color: TINTA.secundaria, lineHeight: 1.2 }}>{p?.nome}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        <tr>
          <td style={rotulo}>Unidades</td>
          {colunas.map((p, i) => <td key={i} style={miudo}>{p?.unidade ? `(${p.unidade})` : ""}</td>)}
        </tr>
        <tr>
          <td style={rotulo}>Norma</td>
          {colunas.map((p, i) => (
            <td key={i} style={{ ...miudo, fontSize: "6.5pt" }}>
              {p?.norma.split(" | ").map((n) => <div key={n}>{n}</div>)}
            </td>
          ))}
        </tr>
        <tr>
          <td style={rotulo}>Referência</td>
          {colunas.map((p, i) => (
            <td key={i} style={{ ...CELULA, fontSize: "9.5pt", color: TINTA.secundaria }}>{p ? referencia(p) : ""}</td>
          ))}
        </tr>
        <tr>
          <td style={rotulo} />
          {colunas.map((p, i) => <td key={i} style={miudo}>{p ? TIPO_REFERENCIA[p.tipo_limite] : ""}</td>)}
        </tr>
        {linhas.map((c, k) => (
          <tr key={k}>
            <td style={{ ...CELULA, fontSize: "8pt", fontWeight: c?.atual ? 700 : 400 }}>{c ? ddmmaaaa(c.data) : ""}</td>
            {colunas.map((p, i) => {
              const cel = c && p ? c.valores[p.codigo] : undefined;
              const fora = cel?.conforme === false;
              return (
                <td key={i} style={{ ...CELULA, fontSize: "10pt", fontWeight: c?.atual ? 700 : 400, background: fora ? TOM.fora.fundo : undefined }}>
                  {cel && p ? textoValor(p, cel) : ""}
                  {fora && <MarcaConformidade conforme={false} />}
                </td>
              );
            })}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** Ficha de resultado de um ensaio do óleo (FQ, CR, PCB, 2-FAL). */
export function FichaParametros({ cab, f, informacoes }: { cab: Cabecalho; f: FichaTabela; informacoes: string }) {
  // CR: TG e TGC calculados saem ao fim da conclusão, como na ficha de referência.
  const indicadores = Object.entries(f.indicadores).filter(([, v]) => v != null);
  return (
    <FolhaFicha cab={cab} titulo={f.titulo}>
      <CabecalhoLaudo f={f} />
      <BlocoValores>
        <TabelaParametros f={f} />
      </BlocoValores>
      <TextosFicha
        f={f}
        informacoes={informacoes}
        complementoConclusao={indicadores.length > 0 && (
          <em>{`${f.conclusao ? " " : ""}[${indicadores.map(([k, v]) => `${k} = ${numero(v, 0)}`).join(" | ")}]`}</em>
        )}
      />
      <div style={{ border: LINHA, marginTop: "3mm", padding: "0.3mm 1.2mm 1mm" }}>
        <div style={{ fontSize: "6.5pt", color: TINTA.suave, lineHeight: 1.25 }}>Gráfico</div>
        <GraficoReferencia barras={f.grafico} />
      </div>
      {f.gp_estimado && (
        <p style={{ fontSize: "7.5pt", color: TINTA.secundaria, marginTop: "2mm" }}>
          * Grau de Polimerização estimado pelo teor de 2-Furfural (equação de De Pablo).
        </p>
      )}
      {f.notas.length > 0 && (
        <div style={{ fontSize: "7.5pt", color: TINTA.secundaria, marginTop: "2.5mm", lineHeight: 1.3, textAlign: "justify" }}>
          {f.notas.map((n) => <p key={n} style={{ margin: "0 0 1mm" }}>{n}</p>)}
        </div>
      )}
    </FolhaFicha>
  );
}
