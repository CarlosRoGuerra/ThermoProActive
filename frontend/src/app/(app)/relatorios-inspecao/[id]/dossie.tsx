"use client";

import { useCallback, useEffect, useState, type ReactNode } from "react";
import Link from "next/link";
import { ArrowLeft, Printer, Save } from "lucide-react";
import { api } from "@/lib/api";
import { tecnologiaTipo, type TecnologiaTipo } from "@/lib/inspecoes";
import { Button, Card, Field, Input, Spinner, Textarea } from "@/components/ui";

const ddmmaaaa = (iso: string | null) => (iso ? iso.split("-").reverse().join("/") : "—");

/* ------------------------------- Tipos ------------------------------------ */
type Instrumento = {
  tipo: string; marca: string; modelo: string; numero_serie: string;
  data_ultima_calibracao: string | null; proxima_calibracao: string | null;
  periodicidade: string; entidade_calibracao: string; software_analise: string;
};
type Norma = { codigo: string; nome: string; orgao: string };
type GlossTerm = { sigla: string; termo: string; descricao: string };
type Prestador = {
  nome: string; cnpj: string; inscricao_estadual: string; endereco: string; cidade_uf: string;
  endereco_linha1: string; endereco_linha2: string;
  email: string; telefone: string; site: string; logomarca: string | null;
};
type Cabecalho = {
  prestador: Prestador | null;
  empresa: string; nome_fantasia: string; cnpj: string; endereco: string; cidade_uf: string; contato: string; departamento: string;
  endereco_linha1: string; endereco_linha2: string;
  logomarca: string | null; numero: string; tecnologia: string; tecnologia_imagem: string | null; analistas: string[];
  definicao_tecnica: string; pontos_medicao_imagem: string | null;
  data_inicio: string | null; data_termino: string | null; data_finalizacao: string | null;
  instrumentos: Instrumento[]; normas: Norma[]; glossario: GlossTerm[]; consideracoes_finais: string;
};
type Dist = { rotulo: string; total: number };
type SecaoB = { condicoes: Dist[]; componentes: Dist[]; anomalias: Dist[]; equip_monitorados: number; anomalias_diagnosticadas: number };
type LinhaC = { tag: string; equipamento: string; condicao: string };
type GrupoC = { area: string; setor: string; linhas: LinhaC[] };
type AvalLinha = { rotulo: string; pred_q: string | null; pred_v: string | null; emerg_q: string | null; emerg_v: string | null };
type Avaliacao = { linhas: AvalLinha[]; total_preditiva: string; total_emergencial: string; retorno: string };
type OspD = {
  osp: string; area: string; setor: string; tag: string; equipamento: string; componente: string;
  anomalia: string; recomendacao: string; observacao: string; grau_risco: string; grau_risco_descricao: string;
  amplitude_velocidade: string | null; amplitude_aceleracao: string | null;
  temperatura_medida: string | null; temperatura_referencia: string | null; delta_t: string | null; carga_percentual: string | null;
  corrente: (string | null)[]; tensao: (string | null)[]; analista: string;
  imagens: { tipo: string; arquivo: string; legenda: string }[];
  avaliacao: Avaliacao | null;
};

const num = (v: string | null) => (v == null || v === "" ? 0 : Number(v));
const moeda = (v: string | number | null) => (v == null || v === "" ? "—" : num(String(v)).toLocaleString("pt-BR", { style: "currency", currency: "BRL" }));
const qtd = (v: string | null) => (v == null || v === "" ? "—" : String(num(v)));
export type Dossie = { cabecalho: Cabecalho; secao_b: SecaoB; secao_c: { total: number; grupos: GrupoC[] }; secao_d: OspD[] };

/* -------------------------- Normalizações de saída ------------------------- */
const temTexto = (v: string | null | undefined) => !!v?.trim();

/**
 * O backend deve idealmente devolver somente o número público da OSP.
 * Enquanto isso, evita expor IDs internos em valores como "0006 | 10".
 */
const numeroOspPublico = (v: string) => (v || "—").split("|")[0].trim() || "—";

/** Evita gerar uma folha inteira para registros sem conteúdo técnico. */
function temConteudoOsp(o: OspD) {
  const campos = [
    o.componente, o.anomalia, o.recomendacao, o.observacao,
    o.amplitude_velocidade, o.amplitude_aceleracao,
    o.temperatura_medida, o.temperatura_referencia, o.delta_t, o.carga_percentual,
  ];
  // A foto é EVIDÊNCIA de uma OSP, não motivo para criar uma OSP — por isso
  // imagens não entram nesta decisão (só conteúdo técnico).
  return (
    campos.some(temTexto) ||
    o.corrente.some(temTexto) ||
    o.tensao.some(temTexto)
  );
}

/** Remove fotos duplicadas pelo arquivo/URL sem alterar a ordem. */
function imagensUnicas(imagens: OspD["imagens"]) {
  const vistos = new Set<string>();
  return imagens.filter((img) => {
    const chave = img.arquivo?.trim();
    if (!chave || vistos.has(chave)) return false;
    vistos.add(chave);
    return true;
  });
}

function tamanhoNumeroRelatorio(numero: string) {
  if (numero.length >= 28) return 28;
  if (numero.length >= 24) return 30;
  if (numero.length >= 20) return 34;
  return 38;
}

/* ------------------------------- Cores GR --------------------------------- */
const CORES: Record<string, { bg: string; fg: string }> = {
  GR0: { bg: "#16a34a", fg: "#fff" }, GR1: { bg: "#dc2626", fg: "#fff" },
  GR2: { bg: "#b91c1c", fg: "#fff" }, GR3: { bg: "#ea580c", fg: "#fff" },
  GR4: { bg: "#facc15", fg: "#1f2937" }, GR5: { bg: "#fde047", fg: "#1f2937" },
  OK: { bg: "#16a34a", fg: "#fff" },
};
function corCondicao(c: string) {
  return CORES[c.replace(/[^A-Za-z0-9]/g, "").toUpperCase()] ?? { bg: "#94a3b8", fg: "#fff" };
}

// 6.1 — abreviações fixas do glossário
const ABREVIACOES: [string, string][] = [
  ["O.S.P.", "Ordem de Serviço Preditivo gerada para correção de cada anomalia detectada."],
  ["G.R.", "Grau de Risco — determina o prazo de correção das anomalias detectadas."],
  ["LA", "Lado Acoplado."],
  ["LOA", "Lado Oposto ao Acoplado."],
];

/* ------------------------------- Barras ----------------------------------- */
function Barras({ dados, corFn, hue = "#3b6ea5" }: { dados: Dist[]; corFn?: (r: string) => string; hue?: string }) {
  if (dados.length === 0) return <p className="text-xs text-slate-400">Sem dados.</p>;
  const max = Math.max(1, ...dados.map((d) => d.total));
  return (
    <div className="space-y-1.5">
      {dados.map((d) => (
        <div key={d.rotulo} className="flex items-center gap-2 text-xs">
          <span className="w-44 shrink-0 whitespace-normal break-words leading-snug text-slate-600" title={d.rotulo}>{d.rotulo}</span>
          <div className="h-4 flex-1 overflow-hidden rounded bg-slate-100">
            <div className="h-4 rounded" style={{ width: `${(d.total / max) * 100}%`, background: corFn?.(d.rotulo) ?? hue }} />
          </div>
          <span className="w-6 shrink-0 text-right tabular-nums font-medium text-slate-700">{d.total}</span>
        </div>
      ))}
    </div>
  );
}

/* Fonte do modelo do cliente (OSP). */
const FONTE_OSP = '"Segoe UI", system-ui, -apple-system, Roboto, Arial, sans-serif';

/* Amplitudes/medições da OSP por tecnologia (modelo do cliente). */
function AmplitudesOSP({ o, tipo }: { o: OspD; tipo: TecnologiaTipo }) {
  if (tipo === "termografia") {
    return (
      <>
        <p style={{ fontWeight: 700 }}>Medições</p>
        <p><span style={{ fontWeight: 700 }}>Temp. medida [°C]:</span> {o.temperatura_medida ?? "—"}</p>
        <p><span style={{ fontWeight: 700 }}>Temp. referência [°C]:</span> {o.temperatura_referencia ?? "—"}</p>
        <p><span style={{ fontWeight: 700 }}>ΔT [°C]:</span> {o.delta_t ?? "—"}</p>
        <p><span style={{ fontWeight: 700 }}>Carga [%]:</span> {o.carga_percentual ?? "—"}</p>
      </>
    );
  }
  return (
    <>
      <p style={{ fontWeight: 700 }}>Amplitudes [valor global]</p>
      <p><span style={{ fontWeight: 700 }}>Aceleração [g&rsquo;s]:</span> {o.amplitude_aceleracao ?? "—"}</p>
      <p><span style={{ fontWeight: 700 }}>Velocidade [mm/s]:</span> {o.amplitude_velocidade ?? "—"}</p>
    </>
  );
}

/* Slot de imagem da OSP (Foto do Eqpto / Tendência / Espectro): 80×60mm, imagem
   sem borda; caixa leve com rótulo quando não há imagem daquele tipo. */
function SlotImagem({ img, label }: { img?: OspD["imagens"][number]; label: string }) {
  return (
    <div style={{ width: "80mm", height: "60mm", overflow: "hidden" }}>
      {img ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={img.arquivo} alt={label} style={{ width: "100%", height: "100%", objectFit: "contain" }} />
      ) : (
        <div style={{ width: "100%", height: "100%", border: "0.25mm solid #cbd5e1", display: "flex", alignItems: "center", justifyContent: "center", color: "#94a3b8", fontSize: "12pt" }}>
          {label}
        </div>
      )}
    </div>
  );
}

/* Tabela "Retorno de Informação" (OSP), conforme modelo do cliente. */
function TabelaRetorno({ aval }: { aval: Avaliacao | null }) {
  return (
    <>
      <style>{`
        .tbl-ret { width: 190mm; border-collapse: collapse; font-size: 9pt; margin-top: 3mm; table-layout: fixed; break-inside: avoid; page-break-inside: avoid; }
        .tbl-ret th, .tbl-ret td { border: 0.2mm solid #b8b8b8; padding: 0 1mm; height: 5mm; }
        .tbl-ret .barra { height: 6mm; background: #16a34a; color: #fff; font-size: 12pt; font-weight: 700; text-align: center; border-color: #16a34a; }
      `}</style>
      <table className="tbl-ret">
        <colgroup>
          <col style={{ width: "40mm" }} />
          <col style={{ width: "25mm" }} />
          <col style={{ width: "25mm" }} />
          <col style={{ width: "25mm" }} />
          <col style={{ width: "25mm" }} />
          <col style={{ width: "25mm" }} />
          <col style={{ width: "25mm" }} />
        </colgroup>
        <thead>
          <tr><th className="barra" colSpan={7}>Retorno de Informação</th></tr>
          <tr>
            <th style={{ width: "40mm" }} />
            <th colSpan={2} style={{ fontWeight: 700, textAlign: "center" }}>Manutenção Preditiva</th>
            <th colSpan={2} style={{ fontWeight: 700, textAlign: "center" }}>Manutenção Emergencial</th>
            <th colSpan={2} style={{ fontWeight: 700, textAlign: "center" }}>Retorno de Investimento</th>
          </tr>
          <tr>
            <th />
            <th style={{ width: "25mm", fontWeight: 700, textAlign: "center" }}>Qtde.</th><th style={{ width: "25mm", fontWeight: 700, textAlign: "center" }}>Valor [$]</th>
            <th style={{ width: "25mm", fontWeight: 700, textAlign: "center" }}>Qtde.</th><th style={{ width: "25mm", fontWeight: 700, textAlign: "center" }}>Valor [$]</th>
            <th style={{ width: "25mm", fontWeight: 700, textAlign: "center" }}>Qtde.</th><th style={{ width: "25mm", fontWeight: 700, textAlign: "center" }}>Valor [$]</th>
          </tr>
        </thead>
        <tbody>
          {(aval?.linhas ?? []).map((l) => {
            const ret = num(l.emerg_v) - num(l.pred_v);
            // Célula vazia deve sair EM BRANCO (não "—"), como no modelo.
            const cq = (v: string | null) => (v && v.trim() ? qtd(v) : "");
            const cv = (v: string | null) => (v && v.trim() ? moeda(v) : "");
            return (
              <tr key={l.rotulo}>
                <td style={{ fontWeight: 700 }}>{l.rotulo}:</td>
                <td style={{ textAlign: "right" }}>{cq(l.pred_q)}</td>
                <td style={{ textAlign: "right" }}>{cv(l.pred_v)}</td>
                <td style={{ textAlign: "right" }}>{cq(l.emerg_q)}</td>
                <td style={{ textAlign: "right" }}>{cv(l.emerg_v)}</td>
                <td />
                <td style={{ textAlign: "right" }}>{ret ? moeda(ret) : ""}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </>
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
    <div style={{ width: "62mm", height: "20mm", display: "flex", alignItems: "center", justifyContent: "flex-start", overflow: "hidden" }}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={marca}
        alt="Thermoproactive"
        style={{ width: "55mm", height: "auto", maxHeight: "20mm", objectFit: "contain", objectPosition: "left center", display: "block", margin: 0, padding: 0 }}
      />
    </div>
  );
}

/* Logo horizontal grande da contracapa final — SEM rotação, sem distorcer. */
function LogoContracapa({ marca }: { marca: string | null }) {
  if (!marca) return null;
  return (
    <div style={{ width: "115mm", height: "28mm", display: "flex", alignItems: "center", justifyContent: "flex-start" }}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={marca}
        alt="Thermoproactive"
        style={{ width: "110mm", height: "auto", maxHeight: "26mm", objectFit: "contain", objectPosition: "left center", display: "block" }}
      />
    </div>
  );
}

/* Cabeçalho institucional (papel timbrado) EM FLUXO na página — sem position:fixed.
   190mm de largura, logo horizontal à esquerda, dados à direita, linha azul embaixo. */
function Timbrado({ cab }: { cab: Cabecalho }) {
  const p = cab.prestador;
  if (!p) return null;
  const logoHorizontal = LOGO_HORIZONTAL ?? p.logomarca;
  return (
    <div style={{ width: "190mm", minHeight: "22mm", display: "flex", alignItems: "center", justifyContent: "space-between", borderBottom: "0.3mm solid #1d4ed8", boxSizing: "border-box", fontFamily: FONTE_OSP }}>
      <LogoTimbrado marca={logoHorizontal} />
      <div style={{ width: "80mm", textAlign: "right", fontSize: "7.5pt", lineHeight: 1.1, color: "#64748b" }}>
        <p style={{ fontSize: "9pt", fontWeight: 700, color: "#334155" }}>{p.nome}</p>
        {p.cnpj && <p>{p.cnpj}{p.inscricao_estadual ? ` | IE ${p.inscricao_estadual}` : ""}</p>}
        {p.endereco_linha1 && <p>{p.endereco_linha1}</p>}
        {p.endereco_linha2 && <p>{p.endereco_linha2}</p>}
        {p.telefone && <p>{p.telefone}</p>}
        {p.email && <p>{p.email}</p>}
      </div>
    </div>
  );
}

/* Página interna como folha A4 física (210×297mm, margens 10/5/10/15mm),
   com o timbrado EM FLUXO no topo. Substitui o cabeçalho position:fixed.
   evitarQuebra: mantém a página inteira junta (usar na OSP, que é 1 folha). */
function PaginaInterna({ cab, children, evitarQuebra = false }: { cab: Cabecalho; children: ReactNode; evitarQuebra?: boolean }) {
  return (
    <section
      className="pagina"
      style={{
        width: "210mm", minHeight: "297mm", padding: "10mm 5mm 10mm 15mm", boxSizing: "border-box",
        background: "#fff", fontFamily: FONTE_OSP, color: "#1f2937",
        breakInside: evitarQuebra ? "avoid" : undefined, pageBreakInside: evitarQuebra ? "avoid" : undefined,
      }}
    >
      <Timbrado cab={cab} />
      <div style={{ width: "190mm", marginTop: "4mm", fontSize: "9pt" }}>{children}</div>
    </section>
  );
}

/* Bloco de cliente reutilizado na Capa e na Carta */
function BlocoCliente({ cab, semNumero = false }: { cab: Cabecalho; semNumero?: boolean }) {
  return (
    <div className="text-sm font-semibold text-slate-700">
      {!semNumero && <p className="font-mono text-[#1d4ed8]">{cab.numero}</p>}
      <p className={semNumero ? "" : "mt-1"}>{cab.empresa}</p>
      {cab.nome_fantasia && <p className="font-normal text-slate-600">{cab.nome_fantasia}</p>}
      {cab.cnpj && <p className="font-normal">CNPJ {cab.cnpj}</p>}
      {cab.endereco_linha1 ? (
        <>
          <p className="font-normal">{cab.endereco_linha1}</p>
          {cab.endereco_linha2 && <p className="font-normal">{cab.endereco_linha2}</p>}
        </>
      ) : cab.endereco && <p className="font-normal">{cab.endereco}</p>}
      {cab.contato && <p className="mt-1">A/C.: {cab.contato}</p>}
      {cab.departamento && <p className="font-normal text-slate-600">{cab.departamento}</p>}
    </div>
  );
}

/* Logomarca vertical (rotacionada) da capa/contracapa */
function LogoVertical({ marca }: { marca: string | null }) {
  if (!marca) return <div className="w-[150px] shrink-0" />;
  return (
    <div className="relative h-[660px] w-[150px] shrink-0 overflow-hidden">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={marca}
        alt=""
        style={{
          position: "absolute",
          top: "50%",
          left: "50%",
          width: 640,
          maxWidth: "none",
          transform: "translate(-50%, -50%) rotate(-90deg)",
        }}
      />
    </div>
  );
}

/* Contracapa (divisória) de cada seção */
function Contracapa({ titulo, subtitulo, imagem, tecnologia, marca }: {
  titulo: string; subtitulo?: string; imagem: string | null; tecnologia: string; marca: string | null;
}) {
  return (
    <section className="pagina pagina-capa evitar-quebra flex gap-6 bg-white p-8">
      <LogoVertical marca={marca} />
      <div className="flex flex-1 flex-col">
        <div className="flex justify-end">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          {imagem && <img src={imagem} alt={tecnologia} className="max-h-[180px] max-w-[180px] object-contain" />}
        </div>
        <div className="mt-auto text-right">
          <p className="text-4xl font-black leading-tight text-[#1d4ed8]">{titulo}</p>
          {subtitulo && <p className="mt-1 text-lg font-semibold text-slate-600">{subtitulo}</p>}
        </div>
      </div>
    </section>
  );
}

/* Contracapa final do relatório — sem cabeçalho/rodapé interno. */
function ContracapaFinal({ prestador }: { prestador: Prestador | null }) {
  return (
    <section className="pagina-capa evitar-quebra flex gap-6 bg-white p-8">
      <LogoContracapa marca={LOGO_HORIZONTAL ?? prestador?.logomarca ?? null} />
      <div className="flex flex-1 flex-col justify-end text-right text-slate-600">
        {prestador?.nome && <p className="text-base font-semibold text-slate-800">{prestador.nome}</p>}
        {prestador?.cnpj && <p className="mt-1 text-xs">CNPJ {prestador.cnpj}</p>}
        {prestador?.endereco_linha1 && <p className="mt-2 text-xs">{prestador.endereco_linha1}</p>}
        {prestador?.endereco_linha2 && <p className="text-xs">{prestador.endereco_linha2}</p>}
        {(prestador?.telefone || prestador?.email) && (
          <p className="mt-2 text-xs">{[prestador.telefone, prestador.email].filter(Boolean).join(" · ")}</p>
        )}
        {prestador?.site && <p className="mt-1 text-xs font-medium">{prestador.site}</p>}
      </div>
    </section>
  );
}

/* ------------------------------- Página ----------------------------------- */
export function RelatorioDossie({ relatorioId }: { relatorioId: number }) {
  const [d, setD] = useState<Dossie | null>(null);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const [dataFim, setDataFim] = useState("");
  const [consideracoes, setConsideracoes] = useState("");
  const [salvando, setSalvando] = useState(false);

  const carregar = useCallback(async () => {
    setLoading(true);
    try {
      const dossie = await api<Dossie>(`/relatorios-inspecao/${relatorioId}/dossie/`);
      setD(dossie);
      setDataFim(dossie.cabecalho.data_finalizacao ?? "");
      setConsideracoes(dossie.cabecalho.consideracoes_finais ?? "");
    } catch {
      setErro("Não foi possível carregar o relatório.");
    } finally {
      setLoading(false);
    }
  }, [relatorioId]);

  useEffect(() => { carregar(); }, [carregar]);

  async function salvarFinalizacao() {
    setSalvando(true);
    try {
      await api(`/relatorios-inspecao/${relatorioId}/`, {
        method: "PATCH",
        body: { data_finalizacao: dataFim || null, consideracoes_finais: consideracoes },
      });
      await carregar();
    } finally {
      setSalvando(false);
    }
  }

  if (loading) return <Card><Spinner label="Montando relatório…" /></Card>;
  if (!d) return <Card><p className="text-sm text-danger-fg">{erro ?? "Relatório não encontrado."}</p></Card>;

  const cab = d.cabecalho;

  function imprimir() {
    const nome = [cab.numero, cab.empresa, cab.nome_fantasia].filter(Boolean).join("_").replace(/[\\/:*?"<>|]/g, "-");
    const original = document.title;
    document.title = nome;
    const restaurar = () => { document.title = original; window.removeEventListener("afterprint", restaurar); };
    window.addEventListener("afterprint", restaurar);
    window.print();
  }

  return (
    <div className="space-y-4">
      <style>{`
        @media print {
          /* Margem 0: cada seção é uma folha A4 FÍSICA (210×297mm) com suas
             próprias margens internas (10/5/10/15mm) e o timbrado em fluxo. */
          @page { size: A4; margin: 0; }

          html, body { margin: 0 !important; padding: 0 !important; background: #fff !important; }

          body * { visibility: hidden; }
          .print-area, .print-area * { visibility: visible; }

          .print-area { position: absolute; inset: 0 auto auto 0; width: 100%; }
          .print-area > * { margin-top: 0 !important; }
          .no-print { display: none !important; }

          .print-area > section { break-after: page; page-break-after: always; }
          .print-area > section:last-child { break-after: auto; page-break-after: auto; }
          .evitar-quebra { break-inside: avoid; page-break-inside: avoid; }

          /* Capa/contracapas ocupam a folha inteira. */
          .pagina-capa { box-sizing: border-box; width: 210mm; min-height: 297mm; background: #fff !important; }
        }
      `}</style>

      <div className="no-print flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Link href="/relatorios-inspecao" className="inline-flex items-center gap-1.5 text-xs font-medium text-fg-muted transition-colors hover:text-fg">
            <ArrowLeft className="h-3.5 w-3.5" /> Voltar para Relatórios
          </Link>
          <span className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[10px] text-slate-500">build: logo-horizontal-v33</span>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" size="sm" icon={Printer} onClick={imprimir}>Impressão simples</Button>
          <Link
            href={`/imprimir/${relatorioId}`}
            className="inline-flex h-10 items-center gap-2 rounded-lg bg-accent px-4 text-sm font-medium text-accent-fg shadow-xs transition-colors hover:bg-accent-hover"
          >
            <Printer className="h-4 w-4" /> Imprimir / PDF (com nº de página)
          </Link>
        </div>
      </div>

      {/* Painel de finalização */}
      <Card className="no-print">
        <h2 className="mb-3 text-sm font-semibold text-fg">Finalização do relatório</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <Field label="Data de finalização do relatório">
            <Input type="date" value={dataFim} onChange={(e) => setDataFim(e.target.value)} />
          </Field>
          <Field label="Considerações finais / conclusões" className="sm:col-span-2">
            <Textarea rows={3} value={consideracoes} onChange={(e) => setConsideracoes(e.target.value)} placeholder="Conclusões da análise que saem no fim do relatório…" />
          </Field>
        </div>
        <div className="mt-3 flex justify-end">
          <Button icon={Save} loading={salvando} onClick={salvarFinalizacao}>Salvar</Button>
        </div>
      </Card>

      <RelatorioCorpo d={d} />
    </div>
  );
}

export function RelatorioCorpo({ d }: { d: Dossie }) {
  const { cabecalho: cab, secao_b: b, secao_c: c, secao_d: osps } = d;
  const tipoTec = tecnologiaTipo(cab.tecnologia);
  const temDef = !!(cab.definicao_tecnica?.trim() || cab.pontos_medicao_imagem);
  const ospsValidas = osps.filter(temConteudoOsp);
  
  return (
    <div className="print-area space-y-4 text-slate-800">
        {/* ===================== CAPA PRINCIPAL (pág. 1) ===================== */}
        <section className="pagina-capa evitar-quebra flex gap-6 bg-white p-8 relative">
          <LogoVertical marca={cab.prestador?.logomarca ?? null} />
          <div className="flex flex-1 flex-col">
            <div className="flex justify-end">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              {cab.tecnologia_imagem && <img src={cab.tecnologia_imagem} alt={cab.tecnologia} className="max-h-[180px] max-w-[180px] object-contain" />}
            </div>
            <div className="mt-auto text-right">
              {/* Texto "Relatório Técnico" menor e "Número" Maior, conforme exigido */}
              <p className="text-lg font-semibold uppercase tracking-widest text-slate-500">Relatório Técnico</p>
              <p
                className="mt-2 font-mono font-black leading-none text-[#1d4ed8]"
                style={{ fontSize: tamanhoNumeroRelatorio(cab.numero), whiteSpace: "nowrap", letterSpacing: "-0.04em" }}
              >
                {cab.numero}
              </p>
            </div>
          </div>
        </section>

        {/* ===================== CAPA CLIENTE (pág. 2) ===================== */}
        <section className="pagina pagina-capa evitar-quebra flex gap-6 bg-white p-8 relative">
          <LogoVertical marca={cab.prestador?.logomarca ?? null} />
          <div className="flex flex-1 flex-col justify-center">
            <div className="text-right">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              {cab.logomarca && <img src={cab.logomarca} alt="Logo do cliente" className="mb-6 ml-auto max-h-40 max-w-[280px] object-contain" />}
              <BlocoCliente cab={cab} semNumero />
            </div>
          </div>
        </section>

        {/* ========================= SEÇÃO A — CARTA ========================= */}
        <PaginaInterna cab={cab}>
          <div className="mb-4 flex items-start justify-between gap-4 border-b border-slate-200 pb-3">
            <p className="text-sm font-semibold text-rose-700">Seção A — Carta ao Cliente</p>
            <BlocoCliente cab={cab} />
          </div>

          <h3 className="text-sm font-bold text-slate-800">1. Objetivo do Relatório</h3>
          <p className="mb-3 text-justify text-sm text-slate-600">Apresentar os resultados das análises técnicas de: <em>{cab.tecnologia}</em>.</p>

          <h3 className="text-sm font-bold text-slate-800">2. Datas da Execução</h3>
          <ul className="mb-3 ml-4 list-disc text-sm text-slate-600">
            <li>Data de execução (medições em campo): {ddmmaaaa(cab.data_inicio)}{cab.data_inicio !== cab.data_termino ? ` a ${ddmmaaaa(cab.data_termino)}` : ""}</li>
            <li>Data de finalização do relatório: {ddmmaaaa(cab.data_finalizacao)}</li>
          </ul>

          <h3 className="text-sm font-bold text-slate-800">3. Conteúdo do Relatório</h3>
          <ul className="mb-3 ml-4 list-disc text-sm text-slate-600">
            <li>Seção A — Carta ao Cliente</li><li>Seção B — KPI’s Dashboard</li>
            <li>Seção C — Relação de Equipamentos Contemplados</li><li>Seção D — Ordens de Serviços Preditivos</li>
          </ul>

          <h3 className="text-sm font-bold text-slate-800">4. Instrumentação Utilizada</h3>
          {cab.instrumentos.length ? (
            <ul className="mb-3 ml-4 list-disc text-sm text-slate-600">
              {cab.instrumentos.map((i, k) => (
                <li key={k}>
                  {[i.tipo, i.marca, i.modelo].filter(Boolean).join(" · ")}
                  {i.numero_serie && ` · Serial ${i.numero_serie}`}
                  {i.software_analise && ` · Software ${i.software_analise}`}
                  <br />
                  <span className="text-xs text-slate-500">
                    Calibração: {ddmmaaaa(i.data_ultima_calibracao)}
                    {i.proxima_calibracao && ` · válida até ${ddmmaaaa(i.proxima_calibracao)}`}
                    {i.periodicidade && ` · ${i.periodicidade}`}
                    {i.entidade_calibracao && ` · Entidade: ${i.entidade_calibracao}`}
                  </span>
                </li>
              ))}
            </ul>
          ) : <p className="mb-3 text-sm text-slate-400">Não informada.</p>}

          <h3 className="text-sm font-bold text-slate-800">5. Normatização</h3>
          {cab.normas.length ? (
            <ul className="mb-3 ml-4 list-disc text-sm text-slate-600">
              {cab.normas.map((n, k) => <li key={k}>{[n.codigo, n.nome].filter(Boolean).join(" — ")}</li>)}
            </ul>
          ) : <p className="mb-3 text-sm text-slate-400">Não informada.</p>}

          <h3 className="text-sm font-bold text-slate-800">6. Glossário Técnico</h3>
          <p className="mt-1 text-sm font-semibold text-slate-700">6.1. Das abreviações</p>
          <dl className="mb-2 ml-2 text-sm text-slate-600">
            {ABREVIACOES.map(([sigla, desc], k) => (
              <div key={k} className="flex gap-2 py-0.5">
                <dt className="w-20 shrink-0 font-semibold text-slate-700">{sigla}</dt>
                <dd>{desc}</dd>
              </div>
            ))}
          </dl>

          <p className="mt-1 text-sm font-semibold text-slate-700">6.2. Das condições apropriadas</p>
          {cab.glossario.length ? (
            <dl className="mb-3 ml-2 text-sm text-slate-600">
              {cab.glossario.map((g, k) => (
                <div key={k} className="flex gap-2 py-0.5">
                  <dt className="w-20 shrink-0 font-semibold text-slate-700">{g.sigla}</dt>
                  <dd>{g.descricao}</dd>
                </div>
              ))}
            </dl>
          ) : <p className="mb-3 ml-2 text-sm text-slate-400">Sem condições no escopo deste relatório.</p>}

          {temDef && (
            <>
              <h3 className="text-sm font-bold text-slate-800">7. Definição da Técnica</h3>
              {cab.definicao_tecnica?.trim() && (
                <p className="mb-3 whitespace-pre-line text-justify text-sm text-slate-600">{cab.definicao_tecnica}</p>
              )}
              {cab.pontos_medicao_imagem && (
                <figure className="mb-3">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={cab.pontos_medicao_imagem} alt="Pontos de medição" className="mx-auto max-h-80 object-contain" />
                  <figcaption className="mt-1 text-center text-xs text-slate-500">Disposição dos pontos de medição.</figcaption>
                </figure>
              )}
            </>
          )}

          <h3 className="text-sm font-bold text-slate-800">{temDef ? "8" : "7"}. Considerações Importantes</h3>
          <p className="text-justify text-sm text-slate-600">
            Os critérios das análises são técnicos, associados à experiência do analista. Cada equipamento tem
            seu nível de criticidade para a planta, que deve ser considerado pelo planejamento da manutenção.
            Toda anomalia detectada deve ser corrigida o mais rápido possível; o prazo sugerido serve como referência.
          </p>
          {cab.consideracoes_finais.trim() && (
            <p className="mt-3 whitespace-pre-line text-justify text-sm text-slate-600">{cab.consideracoes_finais}</p>
          )}
          <div className="mt-10 text-right">
            <p className="text-sm text-slate-600">Atenciosamente,</p>
            <div className="mt-8 flex flex-wrap justify-end gap-8">
              {(cab.analistas.length ? cab.analistas : ["Analista"]).map((analista) => (
                <div key={analista} className="w-56 border-t border-slate-400 pt-1">
                  <p className="text-sm font-semibold text-slate-800">{analista}</p>
                  <p className="text-xs text-slate-500">Analista em Manutenção Preditiva</p>
                </div>
              ))}
            </div>
          </div>
        </PaginaInterna>

        {/* Contracapa da Seção B */}
        <Contracapa titulo="KPI’s DASHBOARD" imagem={cab.tecnologia_imagem} tecnologia={cab.tecnologia} marca={cab.prestador?.logomarca ?? null} />

        {/* ========================= SEÇÃO B — KPIs ========================= */}
        <PaginaInterna cab={cab}>
          <p className="mb-4 text-right text-sm font-semibold text-rose-700">Seção B — KPI’s Dashboard</p>
          <div className="grid grid-cols-1 gap-8 sm:grid-cols-2">
            <div>
              <h3 className="mb-2 text-sm font-bold text-slate-800">Status das Condições</h3>
              <Barras dados={b.condicoes} corFn={(r) => corCondicao(r).bg} />
            </div>
            <div>
              <h3 className="mb-2 text-sm font-bold text-slate-800">Equipamentos × Anomalias</h3>
              <div className="flex gap-4">
                <div className="flex-1 rounded-lg bg-slate-50 p-4 text-center">
                  <p className="text-3xl font-bold text-slate-800">{b.equip_monitorados}</p>
                  <p className="text-xs text-slate-500">Equipamentos monitorados</p>
                </div>
                <div className="flex-1 rounded-lg bg-slate-50 p-4 text-center">
                  <p className="text-3xl font-bold text-rose-700">{b.anomalias_diagnosticadas}</p>
                  <p className="text-xs text-slate-500">Anomalias diagnosticadas</p>
                </div>
              </div>
            </div>
            <div>
              <h3 className="mb-2 text-sm font-bold text-slate-800">Status dos Componentes</h3>
              <Barras dados={b.componentes} hue="#3b6ea5" />
            </div>
            <div>
              <h3 className="mb-2 text-sm font-bold text-slate-800">Status das Anomalias</h3>
              <Barras dados={b.anomalias} hue="#7c5cbf" />
            </div>
          </div>
        </PaginaInterna>

        {/* Contracapa da Seção C */}
        <Contracapa titulo="RELAÇÃO DE EQUIPAMENTOS CONTEMPLADOS" imagem={cab.tecnologia_imagem} tecnologia={cab.tecnologia} marca={cab.prestador?.logomarca ?? null} />

        {/* ========================= SEÇÃO C ========================= */}
        <PaginaInterna cab={cab}>
          <p style={{ fontSize: "9pt" }}><span style={{ fontWeight: 700 }}>Empresa:</span> {cab.empresa}</p>
          {c.grupos.length === 0 ? (
            <p style={{ fontSize: "9pt", textAlign: "center", padding: "12mm 0", color: "#64748b" }}>Nenhum equipamento inspecionado.</p>
          ) : (
            c.grupos.map((g, gi) => (
              <div key={gi} style={{ marginTop: "4mm", fontSize: "9pt" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                  <div>
                    <p><span style={{ fontWeight: 700 }}>Área:</span> {g.area}</p>
                    <p><span style={{ fontWeight: 700 }}>Setor:</span> {g.setor}</p>
                  </div>
                  {gi === 0 && <p><span style={{ fontWeight: 700 }}>Total de equipamentos:</span> {b.equip_monitorados}</p>}
                </div>
                <table style={{ width: "190mm", borderCollapse: "collapse", marginTop: "2mm", fontSize: "9pt", tableLayout: "fixed" }}>
                  <thead>
                    <tr style={{ borderBottom: "0.3mm solid #94a3b8", textAlign: "left" }}>
                      <th style={{ width: "30mm", fontWeight: 700, paddingBottom: "1mm" }}>TAG</th>
                      <th style={{ fontWeight: 700, paddingBottom: "1mm" }}>Equipamento</th>
                      <th style={{ width: "22mm", fontWeight: 700, textAlign: "right", paddingBottom: "1mm" }}>Condição</th>
                    </tr>
                  </thead>
                  <tbody>
                    {g.linhas.map((l, li) => {
                      const cor = corCondicao(l.condicao);
                      return (
                        <tr key={li} style={{ background: li % 2 ? "#eff6ff" : "#fff" }}>
                          <td style={{ fontFamily: "monospace", padding: "0.6mm 0" }}>{l.tag || "—"}</td>
                          <td style={{ padding: "0.6mm 0" }}>{l.equipamento}</td>
                          <td style={{ textAlign: "right", padding: "0.6mm 0" }}>
                            <span style={{ display: "inline-block", borderRadius: "1mm", padding: "0 2mm", fontWeight: 700, background: cor.bg, color: cor.fg }}>{l.condicao}</span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ))
          )}
        </PaginaInterna>

        {/* Contracapa da Seção D */}
        <Contracapa titulo="ORDENS DE SERVIÇOS PREDITIVOS" subtitulo="[corretiva orientada pela preditiva]" imagem={cab.tecnologia_imagem} tecnologia={cab.tecnologia} marca={cab.prestador?.logomarca ?? null} />

        {/* ========================= SEÇÃO D — OSPs ========================= */}
        {ospsValidas.map((o, i) => {
          const cor = corCondicao(o.grau_risco);
          const imgs = imagensUnicas(o.imagens);
          return (
            <PaginaInterna key={i} cab={cab} evitarQuebra>
              <p style={{ fontSize: "14pt", fontWeight: 700, color: "#1d4ed8", marginBottom: "0.5mm" }}>OSP nº. {numeroOspPublico(o.osp)}</p>

              {/* Dados (esq.) + Grau de Risco (dir.) */}
              <div style={{ display: "flex", justifyContent: "space-between", gap: "8.75mm" }}>
                <div style={{ width: "130.75mm", lineHeight: 1.15 }}>
                  {[
                    ["Empresa", cab.empresa], ["Data", ddmmaaaa(cab.data_termino)], ["Analista", o.analista],
                    ["Área", o.area], ["Setor", o.setor], ["TAG", o.tag], ["Equipamento", o.equipamento],
                    ["Componente", o.componente], ["Diagnóstico", o.anomalia], ["Observação", o.observacao],
                    ["Recomendação", o.recomendacao],
                  ].map(([k, v]) => (
                    <p key={k}><span style={{ fontWeight: 700 }}>{k}:</span> {v || "—"}</p>
                  ))}
                </div>
                <div style={{ width: "50.5mm", flexShrink: 0, alignSelf: "stretch", borderLeft: "0.3mm solid #94a3b8", textAlign: "center", padding: "0 2mm" }}>
                  <p style={{ fontSize: "16pt", fontWeight: 700 }}>Grau de Risco</p>
                  <p style={{ fontSize: "42pt", fontWeight: 800, lineHeight: 1, color: cor.bg }}>{o.grau_risco || "—"}</p>
                  <p style={{ fontSize: "12pt" }}>{o.grau_risco_descricao}</p>
                </div>
              </div>

              {/* Imagens em 2 colunas: esq = Foto do Eqpto + amplitudes/planejamento; dir = Tendência + Espectro */}
              <div style={{ display: "flex", gap: "10mm", marginTop: "3mm" }}>
                <div>
                  <SlotImagem img={imgs.find((im) => im.tipo === "Foto real")} label="Foto do Eqpto" />
                  <div style={{ marginTop: "3mm", lineHeight: 1.15 }}>
                    <AmplitudesOSP o={o} tipo={tipoTec} />
                    <table style={{ marginTop: "3mm", width: "80mm", fontSize: "9pt", borderCollapse: "collapse" }}>
                      <thead>
                        <tr>
                          <th />
                          <th style={{ fontWeight: 700, textAlign: "center", paddingBottom: "1mm" }}>Data</th>
                          <th style={{ fontWeight: 700, textAlign: "center", paddingBottom: "1mm" }}>Responsável</th>
                        </tr>
                      </thead>
                      <tbody>
                        {["Planejamento", "Corretiva Prog.", "Finalização OSP"].map((e) => (
                          <tr key={e}>
                            <td style={{ fontWeight: 700, whiteSpace: "nowrap", paddingRight: "2mm", paddingTop: "2mm" }}>{e}:</td>
                            <td style={{ borderBottom: "0.2mm solid #64748b", width: "22mm" }} />
                            <td style={{ borderBottom: "0.2mm solid #64748b" }} />
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
                <div>
                  <SlotImagem img={imgs.find((im) => im.tipo === "Linha de tendência")} label="Tendência" />
                  <div style={{ marginTop: "10mm" }}>
                    <SlotImagem img={imgs.find((im) => im.tipo === "Espectro")} label="Espectro" />
                  </div>
                </div>
              </div>

              <TabelaRetorno aval={o.avaliacao} />
            </PaginaInterna>
          );
        })}

        {ospsValidas.length === 0 && (
          <section className="pagina bg-white p-6">
            <p className="py-12 text-center text-sm text-slate-500">Nenhuma Ordem de Serviço Preditiva aplicável foi gerada para este relatório.</p>
          </section>
        )}

        {/* Contracapa final */}
        <ContracapaFinal prestador={cab.prestador} />

      </div>
  );
}