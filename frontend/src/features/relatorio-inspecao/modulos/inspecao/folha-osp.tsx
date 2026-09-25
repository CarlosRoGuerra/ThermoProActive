import { Fragment, type ComponentType } from "react";
import type { Avaliacao, Cabecalho, DossieInspecao, ImagemOsp, OspD } from "../../tipos";
import { Contracapa, PaginaInterna } from "../../shell/folhas";
import { ddmmaaaa, moeda, num, qtd } from "../../shell/formato";
import { CorpoBalanceamento } from "../../corretiva-balanceamento";
import { CorpoCorretivaGenerico } from "../../corretiva-base";

/* ============================================================================
   Folha da OSP (Seção D) — uma por análise, geometria TRAVADA pelo gabarito do
   cliente (AVSMD_osp). O cabeçalho, o Grau de Risco, a foto, o Planejamento e o
   Retorno de Informação são da família; a tecnologia entra com o bloco de
   medições e os quadros de imagem da coluna direita (`TecnologiaInspecao`).
   ========================================================================== */

/** Quadro de imagem da coluna direita: `tipo` é o rótulo do tipo de imagem que o
 * backend manda (`AchadoImagem.get_tipo_display()`). */
export type QuadroImagem = { tipo: string; rotulo: string };

export type TecnologiaInspecao = {
  /** Mesma chave de `TecnologiaAnalise.modulo_tecnico`. */
  chave: string;
  /** Medições da análise, abaixo da foto (linhas de 5mm — ver LINHA_MEDICAO). */
  Medicoes: ComponentType<{ o: OspD }>;
  /** Quadros de imagem da coluna direita (80×60mm, 10mm entre eles). */
  quadros: QuadroImagem[];
  /** Tabela normativa do item 5 da carta. */
  Normatizacao?: ComponentType;
};

/** Linha do bloco de medições — módulo de 5mm do gabarito. */
export const LINHA_MEDICAO = { minHeight: "5mm", lineHeight: "5mm" } as const;

/* -------------------------- Normalizações de saída ------------------------- */
const temTexto = (v: string | null | undefined) => !!v?.trim();

/**
 * Número da OSP no relatório: "sequencial do cliente / sequencial global do BD"
 * (ex.: 6/42). Antes da barra reinicia por cliente; depois é a soma acumulada de
 * todas as OSPs do banco. Compat.: registros antigos vinham como "0006 | 42" —
 * nesse caso mostra só o trecho antes do pipe.
 */
const numeroOsp = (v: string) => {
  const s = (v || "").trim();
  if (!s || s === "—") return "—";
  return s.includes("|") ? (s.split("|")[0].trim() || "—") : s;
};

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
function imagensUnicas(imagens: ImagemOsp[]) {
  const vistos = new Set<string>();
  return imagens.filter((img) => {
    const chave = img.arquivo?.trim();
    if (!chave || vistos.has(chave)) return false;
    vistos.add(chave);
    return true;
  });
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

/** Normaliza a descrição do grau de risco para o padrão visual do cliente.
 * Exemplos:
 * "Grau de Risco BAIXO" -> "Risco Baixo"
 * "Grau de Risco IMINENTE" -> "Risco Iminente"
 * "INEXISTENTE" -> "Risco Inexistente"
 */
function descricaoRiscoModelo(v: string) {
  let s = (v || "").trim();
  if (!s) return "";

  s = s.replace(/^grau\s+de\s+risco\s*/i, "").trim();

  // Se o backend já devolver "Risco ...", apenas padroniza capitalização.
  const jaTemRisco = /^risco\s+/i.test(s);
  if (jaTemRisco) s = s.replace(/^risco\s+/i, "").trim();

  // Mantém siglas/números e transforma palavras em Title Case.
  const nome = s
    .toLocaleLowerCase("pt-BR")
    .replace(/(^|[\s\-/])([a-záàâãéèêíïóôõöúç])/g, (_, sep, ch) => sep + ch.toLocaleUpperCase("pt-BR"));

  return nome ? `Risco ${nome}` : "";
}

/* Slot de imagem da OSP (Foto do Eqpto / quadros da tecnologia): 80×60mm, imagem
   sem borda; caixa leve com rótulo quando não há imagem daquele tipo. */
function SlotImagem({ img, label }: { img?: ImagemOsp; label: string }) {
  return (
    <div style={{ width: "80mm", height: "60mm", boxSizing: "border-box", flexShrink: 0, overflow: "hidden" }}>
      {img ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={img.arquivo} alt={label} style={{ width: "100%", height: "100%", objectFit: "contain", display: "block" }} />
      ) : (
        <div style={{ width: "100%", height: "100%", boxSizing: "border-box", border: "0.2mm solid #cbd5e1", display: "flex", alignItems: "center", justifyContent: "center", color: "#94a3b8", fontSize: "12pt" }}>
          {label}
        </div>
      )}
    </div>
  );
}

/* Rótulos fixos da tabela "Retorno de Informação": SEMPRE exibidos como formulário,
   mesmo sem avaliação preenchida. Devem casar exatamente com os do backend
   (_avaliacao_osp em coletas/relatorio_tecnico/inspecao.py) para herdar os valores por rótulo. */
const ROTULOS_RETORNO = [
  "Mão de Obra [h]", "M.O. Terceirizada [h]", "Material Reparo [$]",
  "Produção [h|Ton.]", "Outros [$]",
] as const;

/* Tabela "Retorno de Informação" (OSP), conforme modelo do cliente. */
function TabelaRetorno({ aval }: { aval: Avaliacao | null }) {
  return (
    <>
      <style>{`
        .tbl-ret { width: 190mm; border-collapse: collapse; font-size: 9pt; margin-top: 4.5mm; table-layout: fixed; break-inside: avoid; page-break-inside: avoid; }
        .tbl-ret th, .tbl-ret td { box-sizing: border-box; border: 0.2mm solid #b8b8b8; padding: 0 1mm; height: 5mm; line-height: 5mm; }
        .tbl-ret .linha-barra, .tbl-ret .linha-barra th { height: 6mm !important; min-height: 6mm; max-height: 6mm; }
        .tbl-ret .barra { box-sizing: border-box; height: 6mm !important; min-height: 6mm; max-height: 6mm; padding: 0 1mm !important; line-height: 6mm !important; background: #16a34a; color: #fff; font-size: 12pt; font-weight: 700; text-align: center; border-color: #16a34a; vertical-align: middle; }
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
          <tr className="linha-barra"><th className="barra" colSpan={7}>Retorno de Informação</th></tr>
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
          {/* As 5 linhas SEMPRE aparecem (formulário). Quando há avaliação, os valores
              são casados pelo rótulo; sem avaliação, saem em branco. */}
          {ROTULOS_RETORNO.map((rot) => {
            const l = aval?.linhas.find((x) => x.rotulo === rot);
            const ret = l ? num(l.emerg_v) - num(l.pred_v) : 0;
            // Célula vazia deve sair EM BRANCO (não "—"), como no modelo.
            const cq = (v: string | null | undefined) => (v && v.trim() ? qtd(v) : "");
            const cv = (v: string | null | undefined) => (v && v.trim() ? moeda(v) : "");
            return (
              <tr key={rot}>
                <td style={{ fontWeight: 700 }}>{rot}:</td>
                <td style={{ textAlign: "right" }}>{cq(l?.pred_q)}</td>
                <td style={{ textAlign: "right" }}>{cv(l?.pred_v)}</td>
                <td style={{ textAlign: "right" }}>{cq(l?.emerg_q)}</td>
                <td style={{ textAlign: "right" }}>{cv(l?.emerg_v)}</td>
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

function FolhaOsp({ cab, o, tecnologia }: { cab: Cabecalho; o: OspD; tecnologia: TecnologiaInspecao }) {
  const cor = corCondicao(o.grau_risco);
  const imgs = imagensUnicas(o.imagens);
  const { Medicoes } = tecnologia;
  // A metade inferior da folha muda quando a intervenção é uma corretiva já
  // executada: Planejamento/quadros da tecnologia/Retorno descrevem uma OSP a
  // fazer, não uma que foi feita. Qualquer `tipo_corretiva` não-vazio é
  // corretiva — nunca cai de volta no layout preditivo por falta de layout
  // específico. Só o balanceamento tem apresentação própria; outros tipos
  // (ex.: alinhamento a laser, com regras técnicas ainda em discussão com o
  // cliente) usam o corpo neutro comum, sem inventar campo nenhum.
  const foto = <SlotImagem img={imgs.find((im) => im.tipo === "Foto real")} label="Foto do Eqpto" />;
  const corpoCorretivo =
    o.tipo_corretiva === "BALANCEAMENTO" && o.corretiva ? (
      <CorpoBalanceamento corretiva={o.corretiva} foto={foto} />
    ) : o.tipo_corretiva ? (
      <CorpoCorretivaGenerico
        tipoDisplay={o.tipo_corretiva_display || o.tipo_corretiva}
        economia={o.corretiva?.economia ?? null}
        foto={foto}
      />
    ) : null;
  return (
    <PaginaInterna cab={cab} evitarQuebra conteudoTopMm={23.5}>
      <p style={{ fontSize: "14pt", fontWeight: 700, color: "#1d4ed8", marginBottom: "0.5mm" }}>OSP nº. {numeroOsp(o.osp)}</p>

      {/* Dados (esq.) + Grau de Risco (dir.).
          O bloco textual usa passo vertical de 4,2mm, conforme o gabarito.
          A caixa do risco é independente: começa ~39,5mm no Y físico,
          mede 50,5mm de largura e 35mm de altura. */}
      <div style={{ display: "flex", justifyContent: "space-between", marginTop: "-2.4mm" }}>
        <div style={{ width: "130.75mm" }}>
          {[
            ["Empresa", cab.empresa], ["Data", ddmmaaaa(cab.data_termino)], ["Analista", o.analista],
            ["Área", o.area], ["Setor", o.setor], ["TAG", o.tag], ["Equipamento", o.equipamento],
            ["Componente", o.componente], ["Diagnóstico", o.anomalia], ["Observação", o.observacao],
            ["Recomendação", o.recomendacao],
          ].map(([k, v]) => (
            <div key={k} style={{ minHeight: "4.2mm", lineHeight: "4.2mm" }}>
              <span style={{ fontWeight: 700 }}>{k}:</span> {v || "—"}
            </div>
          ))}
        </div>

        <div
          style={{
            width: "50.5mm",
            height: "35mm",
            boxSizing: "border-box",
            flexShrink: 0,
            marginTop: "10.4mm",
            borderLeft: "0.3mm solid #94a3b8",
            textAlign: "center",
            padding: "3.2mm 2mm 0",
            overflow: "hidden",
          }}
        >
          <p style={{ margin: 0, fontSize: "16pt", fontWeight: 700, lineHeight: 1 }}>
            Grau de Risco
          </p>
          <p
            style={{
              margin: "2mm 0 0",
              fontSize: "48pt",
              fontWeight: 800,
              lineHeight: 0.92,
              color: cor.bg,
            }}
          >
            {o.grau_risco || "—"}
          </p>
          <p style={{ margin: "1.2mm 0 0", fontSize: "12pt", lineHeight: 1.05 }}>
            {descricaoRiscoModelo(o.grau_risco_descricao)}
          </p>
        </div>
      </div>

      {corpoCorretivo ? (
        corpoCorretivo
      ) : (
        <>
          {/* GRID físico 90 + 10 + 80 + 10 = 190mm.
              Esquerda (90mm): FOTO deslocada 10mm da margem (10→90), mas Medições
              e Planejamento ALINHADOS À MARGEM ESQUERDA (0mm), como os campos acima;
              as linhas de Planejamento terminam a 90mm (borda direita da foto).
              Direita (100→180mm): quadros da tecnologia, 10mm entre eles. */}
          <div style={{ width: "190mm", display: "grid", gridTemplateColumns: "90mm 10mm 80mm 10mm", alignItems: "start", marginTop: "14.2mm" }}>
            <div style={{ width: "90mm" }}>
              <div style={{ marginLeft: "10mm", width: "80mm" }}>{foto}</div>
              <div style={{ height: "10mm" }} />
              <Medicoes o={o} />
              <table style={{ marginTop: "3mm", width: "90mm", fontSize: "9pt", borderCollapse: "collapse" }}>
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
                      <td style={{ borderBottom: "0.2mm solid #64748b", width: "25mm" }} />
                      <td style={{ borderBottom: "0.2mm solid #64748b" }} />
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div />
            <div style={{ width: "80mm" }}>
              {tecnologia.quadros.map((q, qi) => (
                <Fragment key={q.tipo}>
                  {qi > 0 && <div style={{ height: "10mm" }} />}
                  <SlotImagem img={imgs.find((im) => im.tipo === q.tipo)} label={q.rotulo} />
                </Fragment>
              ))}
            </div>
            <div />
          </div>

          <TabelaRetorno aval={o.avaliacao} />
        </>
      )}
    </PaginaInterna>
  );
}

/** Seção D: contracapa + uma folha por análise com conteúdo técnico. */
export function FichasOsp({ d, tecnologia }: { d: DossieInspecao; tecnologia: TecnologiaInspecao }) {
  const cab = d.cabecalho;
  const ospsValidas = d.secao_d.filter(temConteudoOsp);
  return (
    <>
      <Contracapa cab={cab} titulo={"Ordens de Serviços\nOrientadas pela Preditiva"} />

      {ospsValidas.map((o, i) => (
        <FolhaOsp key={i} cab={cab} o={o} tecnologia={tecnologia} />
      ))}

      {ospsValidas.length === 0 && (
        <section className="pagina bg-white p-6">
          <p className="py-12 text-center text-sm text-slate-500">Nenhuma Ordem de Serviço Preditiva aplicável foi gerada para este relatório.</p>
        </section>
      )}

      {/* A última página do relatório é a última OSP — a Carta ao Cliente
          só aparece no início (Seção A), não se repete aqui no final. */}
    </>
  );
}
