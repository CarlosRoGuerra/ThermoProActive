import type { CSSProperties, ReactNode } from "react";
import type { Cabecalho, DossieTransformador, FichaEnsaio } from "../../tipos";
import { PaginaInterna } from "../../shell/folhas";
import { STATUS_KPI } from "../../shell/kpis";
import { data } from "./formato";

/* ============================================================================
   Peças das fichas de transformador — folha A4 do relatório (timbrado do
   shell) com o conteúdo das fichas de referência 2025-12_TRF-001: quadros de
   campos (rótulo pequeno em cima, valor embaixo), cabeçalho do laudo, bloco
   "Valores Obtidos na Análise" e quadros de texto.
   ========================================================================== */

export const AZUL_TITULO = "#1d4ed8"; // mesmo azul do título da OSP
export const TINTA = { primaria: "#0b0b0b", secundaria: "#52514e", suave: "#898781" };
export const LINHA = "0.2mm solid #64748b";
export const LINHA_GRADE = "0.15mm solid #cbd5e1";

/** Estado de um valor frente à referência — tom de fundo + marca, nunca só a cor. */
export const TOM = {
  dentro: { fundo: "#dcf3dc", marca: STATUS_KPI.good },
  fora: { fundo: "#fbe3e3", marca: STATUS_KPI.critical },
};

/** Folha de uma ficha: página interna do relatório + título da ficha. */
export function FolhaFicha({ cab, titulo, children }: { cab: Cabecalho; titulo: string; children: ReactNode }) {
  return (
    <PaginaInterna cab={cab} evitarQuebra>
      <h2 style={{ fontSize: "13pt", fontWeight: 700, color: AZUL_TITULO, margin: "0 0 4mm", lineHeight: 1.2 }}>{titulo}</h2>
      {children}
    </PaginaInterna>
  );
}

/** Quadro de campos: grade com bordas finas, `colunas` iguais. */
export function Quadro({ colunas = 4, children, style }: { colunas?: number; children: ReactNode; style?: CSSProperties }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: `repeat(${colunas}, minmax(0, 1fr))`, borderTop: LINHA, borderLeft: LINHA, ...style }}>
      {children}
    </div>
  );
}

/** Campo do quadro. Com `unidade`, o valor é numérico: centralizado, unidade em cinza à direita. */
export function Campo({
  rotulo, children, unidade, span = 1,
}: { rotulo: string; children?: ReactNode; unidade?: string; span?: number }) {
  const vazio = children == null || children === "";
  return (
    <div style={{ gridColumn: `span ${span}`, borderRight: LINHA, borderBottom: LINHA, padding: "0.3mm 1.2mm 0.5mm", boxSizing: "border-box", minWidth: 0 }}>
      <div style={{ fontSize: "6.5pt", color: TINTA.suave, lineHeight: 1.25 }}>{rotulo}</div>
      <div style={{ fontSize: "10pt", lineHeight: 1.35, display: "flex", gap: "2mm", minHeight: "4.7mm" }}>
        <span style={{ flex: 1, textAlign: unidade ? "center" : "left", overflowWrap: "anywhere" }}>{vazio ? " " : children}</span>
        {unidade && <span style={{ color: TINTA.suave, fontSize: "9pt" }}>{unidade}</span>}
      </div>
    </div>
  );
}

/** Quadro do cliente — igual nas fichas de registro do óleo e dos ensaios elétricos. */
export function QuadroCliente({ d }: { d: DossieTransformador }) {
  const cab = d.cabecalho;
  return (
    <Quadro colunas={4}>
      <Campo rotulo="Cliente" span={4}>{cab.cnpj ? `${cab.empresa} [${cab.cnpj}]` : cab.empresa}</Campo>
      <Campo rotulo="Endereço" span={4}>{cab.endereco}</Campo>
      <Campo rotulo="Contato">{cab.contato}</Campo>
      <Campo rotulo="Departamento">{cab.departamento}</Campo>
      <Campo rotulo="Telefone">{d.contato_cliente.telefone}</Campo>
      <Campo rotulo="E-mail"><span style={{ fontSize: "8pt" }}>{d.contato_cliente.email}</span></Campo>
    </Quadro>
  );
}

/** Linha "Tipos de Ensaios": ■ solicitado, □ não solicitado. */
export function TiposEnsaio({ tipos, rotulos }: {
  tipos: { sigla: string; nome: string; solicitado: boolean }[]; rotulos: Record<string, string>;
}) {
  return (
    <div style={{ gridColumn: "span 4", borderRight: LINHA, borderBottom: LINHA, padding: "0.3mm 1.2mm 0.6mm" }}>
      <div style={{ fontSize: "6.5pt", color: TINTA.suave, lineHeight: 1.25 }}>Tipos de Ensaios</div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, minmax(0, 1fr))", fontSize: "10pt", lineHeight: 1.35 }}>
        {tipos.map((t) => (
          <span key={t.sigla} style={{ display: "flex", alignItems: "center", gap: "2mm" }}>
            <span aria-label={t.solicitado ? "solicitado" : "não solicitado"} style={{ fontSize: "11pt", color: t.solicitado ? TINTA.primaria : TINTA.suave }}>
              {t.solicitado ? "■" : "□"}
            </span>
            {rotulos[t.sigla] ?? t.nome}
          </span>
        ))}
      </div>
    </div>
  );
}

/** Número do laudo, criticidade e datas — cabeçalho de toda ficha de ensaio. */
export function CabecalhoLaudo({ f }: { f: FichaEnsaio }) {
  return (
    <Quadro colunas={4}>
      <Campo rotulo="Número do Laudo">{f.numero_laudo}</Campo>
      <Campo rotulo="Criticidade">{f.criticidade}</Campo>
      <Campo rotulo="Data da Análise">{data(f.data_analise)}</Campo>
      <Campo rotulo={f.rotulos.proxima}>{data(f.data_proxima)}</Campo>
    </Quadro>
  );
}

/** Bloco "Valores Obtidos na Análise" (a tabela do ensaio vai dentro). */
export function BlocoValores({ children, titulo = "Valores Obtidos na Análise" }: { children: ReactNode; titulo?: string }) {
  return (
    <div style={{ border: LINHA, marginTop: "4mm" }}>
      <div style={{ background: "#f1f5f9", borderBottom: LINHA, fontSize: "8pt", fontWeight: 700, padding: "0.8mm 1.2mm" }}>{titulo}</div>
      {children}
    </div>
  );
}

/** Quadro de texto (Conclusão, Recomendação, Observações…). */
export function CaixaTexto({ rotulo, children }: { rotulo: string; children?: ReactNode }) {
  return (
    <div style={{ border: LINHA, padding: "0.3mm 1.2mm 0.8mm", marginTop: "3mm", boxSizing: "border-box" }}>
      <div style={{ fontSize: "6.5pt", color: TINTA.suave, lineHeight: 1.25 }}>{rotulo}</div>
      <div style={{ fontSize: "10pt", lineHeight: 1.35, whiteSpace: "pre-line", minHeight: "4.7mm" }}>{children || " "}</div>
    </div>
  );
}

/** Célula comum das tabelas de valores. */
export const CELULA: CSSProperties = {
  borderRight: LINHA_GRADE, borderBottom: LINHA_GRADE, padding: "0.5mm 0.8mm", textAlign: "center",
  verticalAlign: "middle", height: "5mm", boxSizing: "border-box",
};

/** Marca de conformidade ao lado do valor (✓ dentro / ✕ fora da referência). */
export function MarcaConformidade({ conforme }: { conforme: boolean | null }) {
  if (conforme == null) return null;
  const tom = conforme ? TOM.dentro : TOM.fora;
  return (
    <span aria-label={conforme ? "dentro da referência" : "fora da referência"} style={{ color: tom.marca, fontSize: "7pt", marginLeft: "0.8mm", fontWeight: 700 }}>
      {conforme ? "✓" : "✕"}
    </span>
  );
}
