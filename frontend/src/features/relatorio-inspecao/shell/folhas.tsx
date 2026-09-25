import type { ReactNode } from "react";
import { Phone } from "lucide-react";
import type { Cabecalho } from "../tipos";

/* ============================================================================
   Folhas A4 físicas do relatório — comuns a qualquer tecnologia: capa,
   contracapa de seção e página interna com o papel timbrado. Medidas em mm
   conforme os gabaritos do cliente (AVSMD_Capa / Contra-Capa / osp).
   ========================================================================== */

/* Fonte do modelo do cliente (OSP). */
export const FONTE_RELATORIO = '"Segoe UI", system-ui, -apple-system, Roboto, Arial, sans-serif';

/* Telefone no padrão visual do gabarito: sem o prefixo internacional +55. */
export function telefoneModelo(telefone: string | null | undefined) {
  if (!telefone) return "";
  return telefone
    .trim()
    .replace(/^\+?55[\s.-]*/, "")
    .replace(/^\(?(\d{2})\)?[\s.-]*(\d{4,5})[\s.-]?(\d{4})$/, "$1-$2-$3");
}

/* Pequeno selo verde + telefone, reproduzindo o indicador de WhatsApp da
   capa/contracapas sem depender de um asset externo. */
function TelefoneWhatsApp({ telefone, fontSize = "16pt" }: { telefone: string | null | undefined; fontSize?: string }) {
  const exibicao = telefoneModelo(telefone);
  if (!exibicao) return null;
  return (
    <span style={{ display: "inline-flex", alignItems: "center", justifyContent: "flex-end", gap: "1mm", whiteSpace: "nowrap" }}>
      <span style={{ width: "4.6mm", height: "4.6mm", borderRadius: "1.1mm", background: "#25D366", display: "inline-flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
        <Phone style={{ width: "3mm", height: "3mm", color: "#fff", strokeWidth: 2.6 }} />
      </span>
      <span style={{ fontSize, fontWeight: 700, color: "#37459a" }}>{exibicao}</span>
    </span>
  );
}

/* Logo horizontal oficial (timbrado + contracapa final). Quando houver um arquivo
   dedicado, coloque-o em frontend/public/ e aponte aqui (ex.: "/thermoproactive-horizontal.png").
   Enquanto for null, usa a logomarca do cadastro (comportamento atual, sem quebrar). */
const LOGO_HORIZONTAL: string | null = null;

/* Logo do timbrado (páginas internas) — horizontal, SEM rotação, proporção
   preservada (object-fit: contain; height: auto). Largura-alvo 55mm. */
function LogoTimbrado({ marca }: { marca: string | null }) {
  if (!marca) return null;
  return (
    <div style={{ width: "62mm", height: "12mm", display: "flex", alignItems: "center", justifyContent: "flex-start", overflow: "hidden" }}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={marca}
        alt="Thermoproactive"
        style={{ width: "55mm", height: "auto", maxHeight: "11mm", objectFit: "contain", objectPosition: "left center", display: "block", margin: 0, padding: 0 }}
      />
    </div>
  );
}

/* Logo vertical da CAPA/CONTRACAPA — o próprio contêiner começa exatamente
   em X=15mm, conforme a cota física do gabarito do cliente. */
function LogoVerticalCapa({ marca }: { marca: string | null }) {
  if (!marca) return null;
  return (
    <div style={{ position: "absolute", left: "15mm", top: "10mm", width: "53.7mm", height: "277mm", overflow: "hidden" }}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={marca}
        alt="Thermoproactive"
        style={{ position: "absolute", left: "50%", top: "50%", width: "276mm", height: "auto", maxWidth: "none", transform: "translate(-50%, -50%) rotate(-90deg)", transformOrigin: "center", objectFit: "contain" }}
      />
    </div>
  );
}

/* Capa do relatório — folha A4 física ÚNICA (funde as antigas págs. 1 e 2),
   posicionamento em mm conforme o gabarito AVSMD_Capa. */
export function CapaRelatorio({ cab }: { cab: Cabecalho }) {
  return (
    <section className="pagina-capa evitar-quebra" style={{ position: "relative", width: "210mm", height: "297mm", boxSizing: "border-box", background: "#fff", fontFamily: FONTE_RELATORIO, fontWeight: 400, color: "#1f2937", overflow: "hidden", WebkitFontSmoothing: "antialiased", MozOsxFontSmoothing: "grayscale" }}>
      {/* Logo vertical Thermoproactive à esquerda */}
      <LogoVerticalCapa marca={cab.prestador?.logomarca ?? null} />

      {/* Ícone da tecnologia — 30×30mm, colado no topo/direita */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      {cab.tecnologia_imagem && (
        <img src={cab.tecnologia_imagem} alt={cab.tecnologia} style={{ position: "absolute", top: "10mm", right: "5mm", width: "30mm", height: "30mm", objectFit: "contain" }} />
      )}

      {/* Posições verticais calibradas sobre o PDF do cliente. */}

      {/* Título "Relatório Técnico" — topo visual calibrado em ~64mm */}
      <div style={{ position: "absolute", right: "5mm", top: "63.6mm", width: "120mm", textAlign: "right" }}>
        <p style={{ fontSize: "18pt", fontWeight: 700, color: "#64748b" }}>Relatório Técnico</p>
      </div>

      {/* Número do relatório — calibrado para o topo visual ~76,4mm */}
      <div style={{ position: "absolute", right: "5mm", top: "75.7mm", width: "120mm", textAlign: "right" }}>
        <p style={{ fontSize: "22pt", fontWeight: 700, color: "#37459a", whiteSpace: "nowrap" }}>{cab.numero}</p>
      </div>

      {/* Logo do cliente (50×50mm) — topo físico y = 123,5mm, colada à margem direita */}
      {cab.logomarca && (
        <div style={{ position: "absolute", right: "5mm", top: "123.5mm", width: "50mm", height: "50mm", display: "flex", alignItems: "center", justifyContent: "flex-end" }}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={cab.logomarca} alt={cab.empresa} style={{ maxWidth: "50mm", maxHeight: "50mm", objectFit: "contain" }} />
        </div>
      )}

      {/* Dados do cliente — calibrados para o topo visual ~185,4mm */}
      <div style={{ position: "absolute", right: "5mm", top: "184.7mm", width: "120mm", textAlign: "right" }}>
        <p style={{ fontSize: "20pt", fontWeight: 700, color: "#37459a" }}>{cab.empresa}</p>
        {cab.nome_fantasia && <p style={{ fontSize: "12pt", fontWeight: 400 }}>{cab.nome_fantasia}</p>}
        <div style={{ marginTop: "2mm", fontSize: "12pt", lineHeight: 1, fontWeight: 400 }}>
          {cab.cnpj && <p>CNPJ {cab.cnpj}</p>}
          {cab.endereco_linha1 && <p>{cab.endereco_linha1}</p>}
          {cab.endereco_linha2 && <p>{cab.endereco_linha2}</p>}
        </div>
        {cab.contato && <p style={{ marginTop: "3mm", fontSize: "12pt", fontWeight: 700 }}>A/C Sr(a). {cab.contato}</p>}
        {cab.departamento && <p style={{ fontSize: "10pt", fontWeight: 400 }}>{cab.departamento}</p>}
      </div>

      {/* Telefone/WhatsApp — canto inferior direito */}
      {cab.prestador?.telefone && (
        <div style={{ position: "absolute", right: "5mm", bottom: "10mm" }}>
          <TelefoneWhatsApp telefone={cab.prestador.telefone} fontSize="16pt" />
        </div>
      )}
    </section>
  );
}

/* Cabeçalho institucional (papel timbrado). Ele é posicionado de forma absoluta
   pela PaginaInterna para NÃO empurrar verticalmente o conteúdo técnico. */
function Timbrado({ cab }: { cab: Cabecalho }) {
  const p = cab.prestador;
  if (!p) return null;
  const logoHorizontal = LOGO_HORIZONTAL ?? p.logomarca;
  return (
    <div style={{ width: "190mm", boxSizing: "border-box", fontFamily: FONTE_RELATORIO }}>
      {/* ACIMA da linha: logo (esq.) + razão social / CNPJ / IE (dir.) — tudo em cinza.
          Texto alinhado ao RODAPÉ da faixa do logo p/ ficar rente à linha azul. */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end" }}>
        <LogoTimbrado marca={logoHorizontal} />
        <div style={{ textAlign: "right", fontSize: "7.5pt", lineHeight: 1.2, color: "#94a3b8" }}>
          <div style={{ fontSize: "9pt", fontWeight: 700, color: "#64748b" }}>{p.nome}</div>
          {p.cnpj && <div>{p.cnpj}{p.inscricao_estadual ? ` | IE ${p.inscricao_estadual}` : ""}</div>}
        </div>
      </div>
      {/* Linha azul logo abaixo da logomarca: y físico ~22,5mm. */}
      <div style={{ borderTop: "0.15mm solid #1d4ed8", marginTop: "0.5mm" }} />
      {/* ABAIXO da linha: endereço / contato (dir.) — cinza claro */}
      <div style={{ textAlign: "right", fontSize: "7.5pt", lineHeight: 1.25, color: "#94a3b8", marginTop: "1mm" }}>
        {p.endereco_linha1 && <div>{p.endereco_linha1}</div>}
        {p.endereco_linha2 && <div>{p.endereco_linha2}</div>}
        {p.telefone && <div>{telefoneModelo(p.telefone)}</div>}
        {p.email && <div>{p.email}</div>}
      </div>
    </div>
  );
}

/* Página interna A4 física. O timbrado fica absoluto e o conteúdo recebe
   coordenada Y própria, evitando que endereço/telefone do cabeçalho empurrem
   a OSP e a lista para baixo. */
export function PaginaInterna({
  cab, children, evitarQuebra = false, conteudoTopMm = 41.4,
}: {
  cab: Cabecalho; children: ReactNode; evitarQuebra?: boolean; conteudoTopMm?: number;
}) {
  return (
    <section
      className="pagina"
      style={{
        position: "relative", width: "210mm", minHeight: "297mm", boxSizing: "border-box",
        background: "#fff", fontFamily: FONTE_RELATORIO, fontWeight: 400, color: "#1f2937",
        WebkitFontSmoothing: "antialiased", MozOsxFontSmoothing: "grayscale",
        breakInside: evitarQuebra ? "avoid" : undefined, pageBreakInside: evitarQuebra ? "avoid" : undefined,
      }}
    >
      {/* Timbrado fixo na geometria da folha: X=15mm, Y=10mm, W=190mm.
          Como é absoluto, o conteúdo da OSP/lista pode começar antes do fim
          dos dados institucionais à direita, exatamente como no gabarito. */}
      <div style={{ position: "absolute", left: "15mm", top: "10mm", width: "190mm", zIndex: 0 }}>
        <Timbrado cab={cab} />
      </div>

      {/* O conteúdo usa coordenada vertical física própria.
          Default 41,4mm preserva Carta/KPIs. Seção C usa 34,9mm e OSP 23,5mm. */}
      <div
        style={{
          position: "relative", zIndex: 1, width: "190mm", marginLeft: "15mm",
          paddingTop: `${conteudoTopMm}mm`, paddingBottom: "10mm", boxSizing: "border-box",
          fontSize: "9pt",
        }}
      >
        {children}
      </div>
    </section>
  );
}

/* Contra-capa (divisória de seção) — MESMO modelo físico da capa (gabarito
   AVSMD_Contra-Capa): logo vertical do prestador (15mm), ícone da tecnologia
   (30×30mm, topo/direita), nome da seção à direita em Segoe UI 22pt negrito
   (margem 5mm) e telefone do prestador no rodapé. `titulo` aceita "\n" p/ 2 linhas. */
export function Contracapa({ cab, titulo }: { cab: Cabecalho; titulo: string }) {
  const marca = cab.prestador?.logomarca ?? null;
  const icone = cab.tecnologia_imagem;
  const telefone = cab.prestador?.telefone ?? null;
  return (
    <section className="pagina pagina-capa evitar-quebra" style={{ position: "relative", width: "210mm", height: "297mm", boxSizing: "border-box", background: "#fff", fontFamily: FONTE_RELATORIO, fontWeight: 400, color: "#1f2937", overflow: "hidden", WebkitFontSmoothing: "antialiased", MozOsxFontSmoothing: "grayscale" }}>
      <LogoVerticalCapa marca={marca} />
      {/* Ícone da tecnologia — 30×30mm, colado no topo/direita (10/5mm) */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      {icone && <img src={icone} alt={cab.tecnologia} style={{ position: "absolute", top: "10mm", right: "5mm", width: "30mm", height: "30mm", objectFit: "contain" }} />}
      {/* Nome da seção — direita, margem 5mm, Segoe UI 22pt negrito, ~centro vertical */}
      <div style={{ position: "absolute", right: "5mm", top: "138mm", width: "150mm", textAlign: "right" }}>
        <p style={{ fontSize: "22pt", fontWeight: 700, color: "#1d4ed8", lineHeight: 1.2, whiteSpace: "pre-line" }}>{titulo}</p>
      </div>
      {/* Telefone/WhatsApp do prestador — canto inferior direito */}
      {telefone && (
        <div style={{ position: "absolute", right: "5mm", bottom: "10mm" }}>
          <TelefoneWhatsApp telefone={telefone} fontSize="16pt" />
        </div>
      )}
    </section>
  );
}
