import type { CSSProperties } from "react";
import type { DossieTransformador, ItemInspecaoVisual, Transformador } from "../tipos";
import {
  AZUL_TITULO, Campo, FolhaFicha, LINHA, Quadro, QuadroCliente, TINTA, TiposEnsaio, TOM,
} from "./transformador/folha";
import { data, kV, numero, numeroEnxuto, tensaoSecundaria } from "./transformador/formato";
import { criarModuloTransformador } from "./transformador/modulo";

/* Óleo isolante de transformador (2025-12_TRF-001_Óleo.pdf): registro da coleta
   com a inspeção visual OK/NC/NA e as fichas FQ, CR, PCB e 2-FAL. Carta
   (conteúdo, glossário, considerações e resumo do item 7) no backend:
   apps/ensaios/carta.py e relatorio.py. */

const ROTULOS_ENSAIO: Record<string, string> = {
  FQ: "FQ - Físico Químico", CR: "CR - Cromatográfico", PCB: "Teor PCB", "2FAL": "2-FAL",
};

const ESTADO_VISUAL: Record<ItemInspecaoVisual["estado"], CSSProperties> = {
  OK: { background: TOM.dentro.fundo },
  NC: { background: TOM.fora.fundo, fontWeight: 700 },
  NA: {},
};

function TabelaChecklist({ itens, linhas }: { itens: ItemInspecaoVisual[]; linhas: number }) {
  const vazias = Math.max(0, linhas - itens.length);
  const celula: CSSProperties = { border: LINHA, padding: "0.4mm 1.2mm", fontSize: "9.5pt", height: "5.6mm", boxSizing: "border-box" };
  return (
    <table style={{ width: "100%", borderCollapse: "collapse", tableLayout: "fixed" }}>
      <colgroup><col style={{ width: "9mm" }} /><col /></colgroup>
      <tbody>
        {itens.map((i) => (
          <tr key={i.item}>
            <td style={{ ...celula, textAlign: "center", ...ESTADO_VISUAL[i.estado] }}>{i.estado}</td>
            <td style={celula}>{i.item}</td>
          </tr>
        ))}
        {Array.from({ length: vazias }, (_, k) => (
          <tr key={`v${k}`}><td style={celula} /><td style={celula} /></tr>
        ))}
      </tbody>
    </table>
  );
}

function InspecaoVisual({ itens }: { itens: ItemInspecaoVisual[] }) {
  const geral = itens.filter((i) => i.grupo === "GERAL");
  const tanque = itens.filter((i) => i.grupo === "TANQUE_EXPANSAO");
  const observacoes = itens.filter((i) => i.observacao.trim() || i.foto);
  return (
    <>
      <h3 style={{ fontSize: "13pt", fontWeight: 700, color: AZUL_TITULO, margin: "7mm 0 3mm", lineHeight: 1.2 }}>
        INSPEÇÃO VISUAL{" "}
        <span style={{ fontSize: "7.5pt" }}>[OK - Condição Normal | NC - Não Conformidade | NA - Não Aplicável]</span>
      </h3>
      {itens.length === 0 ? (
        <p style={{ fontSize: "9pt", color: TINTA.suave }}>Inspeção visual não registrada.</p>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10mm", alignItems: "end" }}>
          <TabelaChecklist itens={geral} linhas={geral.length} />
          <div>
            <p style={{ fontSize: "9.5pt", fontWeight: 700, margin: "0 0 2mm", display: "flex", alignItems: "center", gap: "2mm" }}>
              <span aria-hidden style={{ color: AZUL_TITULO, fontSize: "12pt" }}>↓</span>
              Exclusivo para equipamentos com tanque de expansão
            </p>
            <TabelaChecklist itens={tanque} linhas={Math.max(tanque.length + 1, geral.length - 3)} />
          </div>
        </div>
      )}
      {observacoes.length > 0 && (
        <div style={{ marginTop: "4mm", fontSize: "9pt" }}>
          <p style={{ fontWeight: 700, marginBottom: "1mm" }}>Observações da inspeção visual</p>
          {observacoes.map((i) => (
            <div key={i.item} style={{ marginBottom: "2mm", display: "flex", gap: "3mm", alignItems: "flex-start" }}>
              {i.foto && (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={i.foto} alt={i.item} style={{ width: "40mm", height: "30mm", objectFit: "contain", border: LINHA }} />
              )}
              <p><b>{i.estado} · {i.item}:</b> {i.observacao}</p>
            </div>
          ))}
        </div>
      )}
    </>
  );
}

/** Ficha 1 — Registro de dados de coleta de amostra de óleo (+ inspeção visual). */
function RegistroColeta({ d, t }: { d: DossieTransformador; t: Transformador }) {
  const c = t.cadastro;
  const coleta = t.coleta;
  return (
    <FolhaFicha cab={d.cabecalho} titulo="REGISTRO DE DADOS DE COLETA DE AMOSTRA DE ÓLEO">
      <QuadroCliente d={d} />
      <Quadro colunas={4} style={{ marginTop: "4mm" }}>
        <Campo rotulo="Local da Instalação do Equipamento" span={2}>{c.local}</Campo>
        <Campo rotulo="Identificação do Equipamento" span={2}>{c.identificacao}</Campo>
        <Campo rotulo="Número de Série" span={2}>{c.numero_serie}</Campo>
        <Campo rotulo="Número de Patrimônio" span={2}>{c.numero_patrimonio}</Campo>
        <Campo rotulo="Fabricante">{c.fabricante}</Campo>
        <Campo rotulo="Ano de Fabricação">{c.ano_fabricacao ?? ""}</Campo>
        <Campo rotulo="Tipo de Equipamento">{c.tipo_equipamento}</Campo>
        <Campo rotulo="Tipo">{c.modelo}</Campo>
        <Campo rotulo="Potência" unidade="kVA">{numeroEnxuto(c.potencia_kva, 1)}</Campo>
        <Campo rotulo="Tensão Primária" unidade="kV">{kV(c.tensao_primaria_v)}</Campo>
        <Campo rotulo="Temperatura da Amostra" unidade="°C">{numero(coleta?.temperatura_amostra_c, 1)}</Campo>
        <Campo rotulo="Temperatura Ambiente" unidade="°C">{numero(coleta?.temperatura_ambiente_c, 1)}</Campo>
        <Campo rotulo="Impedância" unidade="%">{numero(c.impedancia_pct, 2)}</Campo>
        <Campo rotulo="Tensão Secundária" unidade="V">{tensaoSecundaria(c)}</Campo>
        <Campo rotulo="Quantidade de Óleo" unidade="L">{numero(c.volume_oleo_l, 1)}</Campo>
        <Campo rotulo="Umidade Relativa do Ar" unidade="%">{numero(coleta?.umidade_relativa_pct, 1)}</Campo>
        <Campo rotulo="Data da Coleta">{data(coleta?.data)}</Campo>
        <Campo rotulo="Amostrador">{coleta?.amostrador}</Campo>
        <Campo rotulo="Ponto de Coleta">{coleta?.ponto_coleta}</Campo>
        <Campo rotulo="Tipo de Fluido">{coleta?.tipo_fluido}</Campo>
        <TiposEnsaio tipos={t.tipos_ensaio} rotulos={ROTULOS_ENSAIO} />
      </Quadro>
      <InspecaoVisual itens={t.inspecao_visual ?? []} />
    </FolhaFicha>
  );
}

export const MODULO_OLEO_ISOLANTE = criarModuloTransformador({
  chave: "OLEO_ISOLANTE",
  tituloFichas: "Fichas da Análise\ndo Óleo Isolante",
  Registro: RegistroColeta,
  informacoes: (f) => f.informacoes_adicionais,
});
