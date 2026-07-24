"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Printer } from "lucide-react";
import { api } from "@/lib/api";
import { Button, Card, Spinner } from "@/components/ui";
import {
  AmplitudeGrafico,
  BarrasEmpilhadas,
  BarrasHorizontais,
  Legenda,
  LinhasComparativas,
  TabelaDados,
  type Fatia,
} from "./graficos";

/* ============================ Tipos do payload ============================ */
type Endereco = { formatado?: string; cep?: string; cidade_uf?: string };
type Parte = {
  nome: string;
  nome_fantasia?: string;
  cnpj: string;
  unidade_negocio?: string;
  endereco: Endereco;
  contato_gestor?: string;
  departamento?: string;
  contato?: string;
  logo?: string | null;
};
type LinhaAvaliacao = {
  rotulo: string;
  pred_qtd: string | null;
  pred_valor: string | null;
  emerg_qtd: string | null;
  emerg_valor: string | null;
};
type Osp = {
  numero: string;
  grau_risco: string;
  grau_risco_descricao: string;
  prazo_dias: number | null;
  area: string;
  setor: string;
  tag: string;
  equipamento: string;
  componente: string;
  anomalia: string;
  recomendacao: string;
  observacao: string;
  amplitude_velocidade: string | null;
  amplitude_aceleracao: string | null;
  avaliacao: {
    linhas: LinhaAvaliacao[];
    total_preditiva: string;
    total_emergencial: string;
    retorno_investimento: string;
  };
};
type Relatorio = {
  laudo: {
    numero: string;
    titulo: string;
    data_medicao_campo: string | null;
    data_upload_osps: string | null;
    data_upload_relatorio: string | null;
    responsavel: string;
    responsavel_cargo: string;
    responsavel_conselho: string;
  };
  inspecao: { tipo_analise_display: string; data: string };
  contratada: Parte;
  contratante: Parte;
  instrumentacao: {
    tipo: string; marca: string; modelo: string; numero_serie: string;
    data_ultima_calibracao: string | null; validade: string;
    entidade_calibracao: string; software_analise: string;
  }[];
  normas: { codigo: string; titulo: string; orgao: string }[];
  tabela_iso: {
    titulo: string; colunas: string[]; unidade: string;
    faixas: { zona: string; rotulo: string; cor: string; limites: string[] }[];
  } | null;
  definicao_tecnica: string;
  fluxo_trabalho: string[];
  glossario: { sigla: string; descricao: string }[];
  consideracoes: string[];
  secao_b: {
    resumo: {
      equipamentos_monitorados: number;
      anomalias_detectadas: number;
      osps_abertas: number;
      inspecoes_realizadas: number;
    };
    status_condicoes: Fatia[];
    graus_mensal: { mes: string; total: number; series: { gr: string; valor: number; cor: string }[] }[];
    componentes: Fatia[];
    anomalias: Fatia[];
    equipamentos_x_anomalias: { mes: string; equipamentos: number; anomalias: number }[];
    amplitude: Record<string, string | number | null>[];
    controle_osps: Fatia[];
    legenda_gr: { gr: string; cor: string }[];
  };
  secao_c: {
    total_equipamentos: number;
    areas: { area: string; setores: { setor: string; itens: { tag: string; equipamento: string; condicao: string }[] }[] }[];
  };
  secao_d: Osp[];
};

/* ============================ Helpers ============================ */
const CORES_GR: Record<string, string> = {
  "GR-0": "#22c55e",
  "GR-1": "#dc2626",
  "GR-2": "#f97316",
  "GR-3": "#f59e0b",
  "GR-4": "#eab308",
};

function data(v: string | null | undefined) {
  if (!v) return "—";
  const [a, m, d] = v.split("-");
  return `${d}/${m}/${a}`;
}

function moeda(v: string | null) {
  const n = Number(v ?? 0);
  return n.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function num(v: string | null) {
  return v == null || v === "" ? "—" : Number(v).toLocaleString("pt-BR");
}

/** Cabeçalho e rodapé repetidos em toda folha do documento. */
function Folha({
  children,
  contratada,
  secao,
  pagina,
}: {
  children: React.ReactNode;
  contratada: Parte;
  secao: string;
  pagina: string;
}) {
  return (
    <section className="folha">
      <header className="doc-topo">
        <div className="flex items-center gap-2">
          {contratada.logo && (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={contratada.logo} alt="" className="h-8 w-8 shrink-0 object-contain" />
          )}
          <div>
            <strong className="block text-[10pt] text-[color:var(--doc-accent)]">
              {contratada.nome}
            </strong>
            CNPJ {contratada.cnpj}
            {contratada.endereco?.formatado && <> · {contratada.endereco.formatado}</>}
          </div>
        </div>
        <div className="shrink-0 text-right font-semibold uppercase tracking-wide text-[color:var(--doc-accent)]">
          {secao}
        </div>
      </header>
      {children}
      <footer className="doc-rodape">
        <span>thermoproactive.com.br</span>
        <span>{pagina}</span>
      </footer>
    </section>
  );
}

export default function RelatorioTecnicoPage() {
  const params = useParams<{ id: string }>();
  const [r, setR] = useState<Relatorio | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    api<Relatorio>(`/laudos/${params.id}/relatorio-tecnico/`)
      .then(setR)
      .catch(() => setErro("Não foi possível montar o relatório deste laudo."));
  }, [params.id]);

  if (erro) {
    return (
      <Card>
        <p className="text-sm text-danger-fg">{erro}</p>
      </Card>
    );
  }
  if (!r) return <Spinner label="Montando o relatório…" />;

  const { contratada, contratante, laudo } = r;

  return (
    <>
      {/* Barra de ações — não sai na impressão */}
      <div className="no-print mb-4 flex flex-wrap items-center justify-between gap-3">
        <Link
          href={`/laudos/${params.id}`}
          className="inline-flex items-center gap-1.5 text-xs font-medium text-fg-muted transition-colors hover:text-fg"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Voltar para o laudo
        </Link>
        <div className="flex items-center gap-3">
          <span className="text-xs text-fg-subtle">
            Use “Salvar como PDF” na janela de impressão.
          </span>
          <Button icon={Printer} onClick={() => window.print()}>
            Imprimir / Salvar PDF
          </Button>
        </div>
      </div>

      <div className="doc">
        {/* ========================= CAPA ========================= */}
        <section className="folha">
          <div className="flex h-full flex-col">
            <div className="border-b-4 border-[color:var(--doc-accent)] pb-4">
              <p className="text-[9pt] uppercase tracking-[0.2em] text-[color:var(--doc-muted)]">
                {contratada.nome}
              </p>
              <h1 className="mt-1 text-[26pt] font-bold leading-tight">Relatório Técnico</h1>
              <p className="mt-1 font-mono text-[14pt] font-semibold text-[color:var(--doc-accent)]">
                {laudo.numero}
              </p>
            </div>

            <div className="mt-auto space-y-6 pb-10">
              {contratante.logo && (
                <img
                  src={contratante.logo}
                  alt={`Logomarca ${contratante.nome}`}
                  className="h-[130px] w-[130px] object-contain"
                />
              )}
              <div>
                <p className="text-[8pt] uppercase tracking-widest text-[color:var(--doc-muted)]">
                  Contratante
                </p>
                <p className="mt-1 text-[13pt] font-bold">{contratante.nome}</p>
                {contratante.nome_fantasia && (
                  <p className="text-[11pt]">{contratante.nome_fantasia}</p>
                )}
                <p className="text-[10pt]">CNPJ {contratante.cnpj}</p>
                {contratante.endereco?.formatado && (
                  <p className="text-[10pt]">{contratante.endereco.formatado}</p>
                )}
                {contratante.unidade_negocio && (
                  <p className="text-[10pt]">{contratante.unidade_negocio}</p>
                )}
              </div>

              {contratante.contato_gestor && (
                <div>
                  <p className="text-[8pt] uppercase tracking-widest text-[color:var(--doc-muted)]">
                    A/C
                  </p>
                  <p className="text-[11pt] font-semibold">{contratante.contato_gestor}</p>
                  {contratante.departamento && (
                    <p className="text-[10pt]">{contratante.departamento}</p>
                  )}
                </div>
              )}

              <div className="border-t border-[color:var(--doc-line)] pt-3 text-[9pt] text-[color:var(--doc-muted)]">
                <p>{r.inspecao.tipo_analise_display}</p>
                <p>Medições em campo: {data(laudo.data_medicao_campo)}</p>
              </div>
            </div>
          </div>
        </section>

        {/* ================= SEÇÃO A — CARTA AO CLIENTE ================= */}
        <Folha contratada={contratada} secao="Seção A — Carta ao Cliente" pagina="Página 1 A">
          <div className="space-y-5">
            <div>
              <p className="font-bold">{contratante.nome}</p>
              {contratante.endereco?.formatado && (
                <p className="italic">{contratante.endereco.formatado}</p>
              )}
              {contratante.contato_gestor && (
                <p className="mt-2 font-semibold">A/C.: {contratante.contato_gestor}</p>
              )}
              <p className="mt-3 bg-gray-100 px-3 py-1.5 text-center font-mono font-bold">
                {laudo.numero}
              </p>
            </div>

            <Bloco n="1" titulo="Objetivo do Relatório">
              <p>
                Este relatório técnico tem como objetivo apresentar os resultados das análises
                técnicas de:
              </p>
              <p className="italic">{r.inspecao.tipo_analise_display}</p>
            </Bloco>

            <Bloco n="2" titulo="Data(s) da(s) Execução(ões) da(s) Atividade(s)">
              <p>Medições em campo — {data(laudo.data_medicao_campo)}</p>
              <p>Upload das OSP&apos;s — {data(laudo.data_upload_osps)}</p>
              <p>Upload do relatório completo — {data(laudo.data_upload_relatorio)}</p>
            </Bloco>

            <Bloco n="3" titulo="Conteúdo do Relatório">
              <p>Seção A — Carta ao Cliente</p>
              <p>Seção C — Relação de Equipamentos Contemplados</p>
              <p>Seção D — Ordens de Serviços Preditivos [corretiva orientada pela preditiva]</p>
            </Bloco>

            <Bloco n="4" titulo="Instrumentação Utilizada">
              {r.instrumentacao.length === 0 ? (
                <p className="text-[color:var(--doc-muted)]">Nenhum instrumento vinculado.</p>
              ) : (
                r.instrumentacao.map((i, k) => (
                  <div key={k} className="mb-2 pl-3">
                    <p className="font-semibold">{i.tipo}</p>
                    {i.marca && <p>Marca: {i.marca}</p>}
                    {i.modelo && <p>Modelo: {i.modelo}</p>}
                    {i.numero_serie && <p>Serial #: {i.numero_serie}</p>}
                    {i.data_ultima_calibracao && (
                      <p>Data da última calibração: {data(i.data_ultima_calibracao)}</p>
                    )}
                    <p>Validade: {i.validade}</p>
                    {i.entidade_calibracao && <p>Entidade calibração: {i.entidade_calibracao}</p>}
                    {i.software_analise && (
                      <p className="mt-1">Software de análise: {i.software_analise}</p>
                    )}
                  </div>
                ))
              )}
            </Bloco>

            <Bloco n="5" titulo="Normatização">
              {r.normas.map((n, k) => (
                <p key={k}>
                  {n.codigo} — {n.titulo}
                </p>
              ))}
            </Bloco>
          </div>
        </Folha>

        {/* ---- Tabela ISO (só para vibração) ---- */}
        {r.tabela_iso && (
          <Folha contratada={contratada} secao="Seção A — Carta ao Cliente" pagina="Página 2 A">
            <h2 className="mb-3 text-center text-[12pt] font-bold">{r.tabela_iso.titulo}</h2>
            <table className="border border-[color:var(--doc-line)] text-[9pt]">
              <thead>
                <tr className="bg-gray-100">
                  <th className="border border-[color:var(--doc-line)] text-left">
                    Severidade
                  </th>
                  {r.tabela_iso.colunas.map((c) => (
                    <th key={c} className="border border-[color:var(--doc-line)]">
                      {c}
                    </th>
                  ))}
                </tr>
                <tr className="bg-gray-50 text-[8pt] text-[color:var(--doc-muted)]">
                  <th className="border border-[color:var(--doc-line)]">Zona ISO</th>
                  <th className="border border-[color:var(--doc-line)]" colSpan={4}>
                    {r.tabela_iso.unidade}
                  </th>
                </tr>
              </thead>
              <tbody>
                {r.tabela_iso.faixas.map((f) => (
                  <tr key={f.zona}>
                    <td
                      className="border border-[color:var(--doc-line)] text-center font-bold text-white"
                      style={{ background: f.cor }}
                    >
                      {f.zona} — {f.rotulo}
                    </td>
                    {f.limites.map((l, k) => (
                      <td key={k} className="border border-[color:var(--doc-line)] text-center font-mono">
                        {l}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>

            <Bloco n="6" titulo="Glossário Técnico" className="mt-6">
              {r.glossario.map((g) => (
                <p key={g.sigla} className="mb-1">
                  <strong>{g.sigla}</strong> — {g.descricao}
                </p>
              ))}
            </Bloco>
          </Folha>
        )}

        {/* ---- Definição da técnica + considerações + assinatura ---- */}
        <Folha contratada={contratada} secao="Seção A — Carta ao Cliente" pagina="Página 3 A">
          <div className="space-y-5">
            <Bloco n="7" titulo="Definição da Técnica">
              {r.definicao_tecnica.split("\n\n").map((p, k) => (
                <p key={k} className="mb-2 text-justify">
                  {p}
                </p>
              ))}
              <p className="mt-3 font-semibold">O fluxo de trabalho consiste em 03 etapas:</p>
              {r.fluxo_trabalho.map((f, k) => (
                <p key={k}>{f}</p>
              ))}
            </Bloco>

            <Bloco n="8" titulo="Considerações Importantes">
              {r.consideracoes.map((c, k) => (
                <p key={k} className="mb-2 text-justify">
                  {c}
                </p>
              ))}
            </Bloco>

            <div className="mt-10 text-center">
              <p className="mb-16 text-left">Atenciosamente,</p>
              <div className="mx-auto w-72 border-t border-[color:var(--doc-fg)] pt-1">
                <p className="font-bold">{laudo.responsavel}</p>
                <p className="text-[9pt]">{laudo.responsavel_cargo}</p>
                {laudo.responsavel_conselho && (
                  <p className="text-[9pt]">{laudo.responsavel_conselho}</p>
                )}
              </div>
            </div>
          </div>
        </Folha>

        {/* ============ SEÇÃO B — KPI's DASHBOARD ============ */}
        <Folha contratada={contratada} secao="Seção B — Gráficos Gerenciais" pagina="Página 1 B">
          <div className="mb-4 grid grid-cols-4 gap-3">
            {[
              ["Equipamentos monitorados", r.secao_b.resumo.equipamentos_monitorados],
              ["Anomalias detectadas", r.secao_b.resumo.anomalias_detectadas],
              ["OSPs em aberto", r.secao_b.resumo.osps_abertas],
              ["Inspeções realizadas", r.secao_b.resumo.inspecoes_realizadas],
            ].map(([rotulo, valor]) => (
              <div key={String(rotulo)} className="border border-[color:var(--doc-line)] p-2 text-center">
                <p className="font-mono text-[18pt] font-bold leading-none text-[color:var(--doc-accent)]">
                  {valor as number}
                </p>
                <p className="mt-1 text-[7.5pt] text-[color:var(--doc-muted)]">{rotulo as string}</p>
              </div>
            ))}
          </div>

          <Gr titulo="Status das Condições" nota="Distribuição atual dos equipamentos por condição.">
            <BarrasHorizontais dados={r.secao_b.status_condicoes} unidade="equipamentos" />
            <TabelaDados
              colunas={["Condição", "Qtde", "%"]}
              linhas={r.secao_b.status_condicoes.map((c) => [c.rotulo, c.valor, `${c.percentual}%`])}
            />
          </Gr>

          <Gr titulo="Status dos Graus de Risco" nota="Composição das anomalias abertas, mês a mês.">
            <BarrasEmpilhadas meses={r.secao_b.graus_mensal} />
            <Legenda itens={r.secao_b.legenda_gr.filter((g) => g.gr !== "GR-0").map((g) => ({ rotulo: g.gr, cor: g.cor }))} />
          </Gr>
        </Folha>

        <Folha contratada={contratada} secao="Seção B — Gráficos Gerenciais" pagina="Página 2 B">
          <Gr titulo="Status dos Componentes" nota="Componentes com maior incidência de anomalias.">
            <BarrasHorizontais dados={r.secao_b.componentes} />
          </Gr>
          <Gr titulo="Status das Anomalias" nota="Tipos de anomalia diagnosticados.">
            <BarrasHorizontais dados={r.secao_b.anomalias} />
          </Gr>
          <Gr titulo="Equipamentos Inspecionados × Anomalias Diagnosticadas" nota="Evolução mensal.">
            <LinhasComparativas dados={r.secao_b.equipamentos_x_anomalias} />
            <Legenda
              itens={[
                { rotulo: "Equipamentos inspecionados", cor: "#2a78d6" },
                { rotulo: "Anomalias diagnosticadas", cor: "#c9401f" },
              ]}
            />
          </Gr>
        </Folha>

        <Folha contratada={contratada} secao="Seção B — Gráficos Gerenciais" pagina="Página 3 B">
          <Gr
            titulo="Status da Amplitude Vibracional Global"
            nota="Pico medido por período, contra o limite aceitável da norma. Unidades separadas — velocidade e aceleração não compartilham eixo."
          >
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="mb-1 text-[8.5pt] font-semibold">Velocidade (mm/s)</p>
                <AmplitudeGrafico
                  dados={r.secao_b.amplitude}
                  campoPico="pico_velocidade"
                  campoLimite="limite_velocidade"
                  cor="#2a78d6"
                  unidade="mm/s"
                />
              </div>
              <div>
                <p className="mb-1 text-[8.5pt] font-semibold">Aceleração (g)</p>
                <AmplitudeGrafico
                  dados={r.secao_b.amplitude}
                  campoPico="pico_aceleracao"
                  campoLimite="limite_aceleracao"
                  cor="#eb6834"
                  unidade="g"
                />
              </div>
            </div>
          </Gr>

          <Gr titulo="Controle das O.S.P.'s" nota="Situação das ordens na reavaliação seguinte.">
            <BarrasHorizontais dados={r.secao_b.controle_osps} unidade="ordens de serviço" />
            <TabelaDados
              colunas={["Situação", "Qtde", "%"]}
              linhas={r.secao_b.controle_osps.map((c) => [c.rotulo, c.valor, `${c.percentual}%`])}
            />
          </Gr>
        </Folha>

        {/* ============ SEÇÃO C — EQUIPAMENTOS CONTEMPLADOS ============ */}
        <Folha
          contratada={contratada}
          secao="Seção C — Equipamentos Inspecionados"
          pagina="Página 1 C"
        >
          <div className="mb-4 flex items-baseline justify-between border-b border-[color:var(--doc-line)] pb-2">
            <p className="font-bold">Empresa: {contratante.nome}</p>
            <p className="font-bold">
              Total de equipamentos: {r.secao_c.total_equipamentos}
            </p>
          </div>

          {r.secao_c.areas.length === 0 ? (
            <p className="text-[color:var(--doc-muted)]">
              Nenhum equipamento medido nesta inspeção.
            </p>
          ) : (
            r.secao_c.areas.map((a) => (
              <div key={a.area} className="mb-5">
                <p className="text-[11pt] font-semibold">Área: {a.area}</p>
                {a.setores.map((s) => (
                  <div key={s.setor} className="mb-3 ml-2">
                    <p className="mb-1 text-[10pt]">Setor: {s.setor}</p>
                    <table className="text-[9pt]">
                      <thead>
                        <tr className="border-b border-[color:var(--doc-fg)] text-left">
                          <th className="w-20">Tag</th>
                          <th>Equipamento</th>
                          <th className="w-24 text-right">
                            {data(laudo.data_medicao_campo)}
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {s.itens.map((i, k) => (
                          <tr key={k} className={k % 2 ? "bg-gray-50" : ""}>
                            <td className="font-mono">{i.tag}</td>
                            <td>{i.equipamento}</td>
                            <td className="text-right font-semibold">{i.condicao}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ))}
              </div>
            ))
          )}
        </Folha>

        {/* ============ SEÇÃO D — ORDENS DE SERVIÇO ============ */}
        {r.secao_d.map((o, idx) => (
          <Folha
            key={o.numero}
            contratada={contratada}
            secao="Seção D — Ordem de Serviço"
            pagina={`Página ${idx + 1} D`}
          >
            <div className="flex items-start justify-between gap-6 border-b border-[color:var(--doc-line)] pb-3">
              <div className="text-[9.5pt] leading-relaxed">
                <p><strong>Empresa:</strong> {contratante.nome}</p>
                <p><strong>Data:</strong> {data(laudo.data_medicao_campo)}</p>
                <p><strong>Analista:</strong> {laudo.responsavel}</p>
                <p><strong>Área:</strong> {o.area}</p>
                <p><strong>Setor:</strong> {o.setor}</p>
                <p><strong>Tag:</strong> {o.tag}</p>
                <p><strong>Equipamento:</strong> {o.equipamento}</p>
                {o.componente && <p><strong>Componente:</strong> {o.componente}</p>}
              </div>
              <div className="shrink-0 text-center">
                <p className="font-mono text-[10pt] text-[color:var(--doc-accent)]">
                  O.S.P nº: {o.numero}
                </p>
                <p className="text-[9pt]">Grau de risco</p>
                <p
                  className="my-1 text-[40pt] font-black leading-none"
                  style={{ color: CORES_GR[o.grau_risco] ?? "#6b7280" }}
                >
                  {o.grau_risco || "—"}
                </p>
                <p className="text-[10pt]">{o.grau_risco_descricao}</p>
                {o.prazo_dias && (
                  <p className="text-[8pt] text-[color:var(--doc-muted)]">
                    Prazo: {o.prazo_dias} dias
                  </p>
                )}
              </div>
            </div>

            <div className="mt-3 space-y-2 text-[9.5pt]">
              {o.anomalia && <p><strong>Anomalia:</strong> {o.anomalia}</p>}
              {o.recomendacao && <p><strong>Recomendação:</strong> {o.recomendacao}</p>}
              {o.observacao && <p><strong>Observação:</strong> {o.observacao}</p>}
              <div className="flex gap-8 pt-1">
                {o.amplitude_velocidade && (
                  <p><strong>Amplitude Velocidade Global [mm/s]:</strong> {o.amplitude_velocidade}</p>
                )}
                {o.amplitude_aceleracao && (
                  <p><strong>Amplitude Aceleração Global [mm/s²]:</strong> {o.amplitude_aceleracao}</p>
                )}
              </div>
            </div>

            {/* Avaliação de Resultados */}
            <div className="mt-5">
              <p className="bg-[#7ab648] py-1 text-center text-[10pt] font-bold text-white">
                Avaliação de Resultados
              </p>
              <table className="border border-[color:var(--doc-line)] text-[8.5pt]">
                <thead>
                  <tr className="text-center">
                    <th className="border border-[color:var(--doc-line)]" />
                    <th className="border border-[color:var(--doc-line)]" colSpan={2}>
                      Manut. Orientada Preditiva
                    </th>
                    <th className="border border-[color:var(--doc-line)]" colSpan={2}>
                      Manut. Emergencial
                    </th>
                    <th className="border border-[color:var(--doc-line)]">
                      Retorno de Investimento
                    </th>
                  </tr>
                  <tr className="text-center text-[color:var(--doc-muted)]">
                    <th className="border border-[color:var(--doc-line)]" />
                    <th className="border border-[color:var(--doc-line)]">Qtde</th>
                    <th className="border border-[color:var(--doc-line)]">Valor</th>
                    <th className="border border-[color:var(--doc-line)]">Qtde</th>
                    <th className="border border-[color:var(--doc-line)]">Valor</th>
                    <th className="border border-[color:var(--doc-line)]">Resultados</th>
                  </tr>
                </thead>
                <tbody>
                  {o.avaliacao.linhas.map((l, k) => (
                    <tr key={k}>
                      <td className="border border-[color:var(--doc-line)] font-semibold">
                        {l.rotulo}
                      </td>
                      <td className="border border-[color:var(--doc-line)] text-center">
                        {l.pred_qtd === null ? "-" : num(l.pred_qtd)}
                      </td>
                      <td className="border border-[color:var(--doc-line)] text-right font-mono">
                        {moeda(l.pred_valor)}
                      </td>
                      <td className="border border-[color:var(--doc-line)] text-center">
                        {l.emerg_qtd === null ? "-" : num(l.emerg_qtd)}
                      </td>
                      <td className="border border-[color:var(--doc-line)] text-right font-mono">
                        {moeda(l.emerg_valor)}
                      </td>
                      <td className="border border-[color:var(--doc-line)]" />
                    </tr>
                  ))}
                  <tr className="bg-gray-100 font-bold">
                    <td className="border border-[color:var(--doc-line)]">Totais</td>
                    <td className="border border-[color:var(--doc-line)]" />
                    <td className="border border-[color:var(--doc-line)] text-right font-mono">
                      {moeda(o.avaliacao.total_preditiva)}
                    </td>
                    <td className="border border-[color:var(--doc-line)]" />
                    <td className="border border-[color:var(--doc-line)] text-right font-mono">
                      {moeda(o.avaliacao.total_emergencial)}
                    </td>
                    <td className="border border-[color:var(--doc-line)] text-right font-mono">
                      {moeda(o.avaliacao.retorno_investimento)}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            {/* Assinaturas das 3 etapas */}
            <div className="mt-6 text-[9pt]">
              <div className="mb-1 flex gap-4 pl-24 text-center text-[color:var(--doc-muted)]">
                <span className="flex-1">Data</span>
                <span className="flex-1">Responsável</span>
              </div>
              {["Planejamento", "Corretiva", "Finalização"].map((etapa) => (
                <div key={etapa} className="mb-3 flex items-end gap-4">
                  <span className="w-24 shrink-0">{etapa}</span>
                  <span className="flex-1 border-b border-[color:var(--doc-fg)]" />
                  <span className="flex-1 border-b border-[color:var(--doc-fg)]" />
                </div>
              ))}
            </div>
          </Folha>
        ))}
      </div>
    </>
  );
}

/** Bloco de gráfico: título, nota explicativa e o gráfico em si. */
function Gr({
  titulo,
  nota,
  children,
}: {
  titulo: string;
  nota: string;
  children: React.ReactNode;
}) {
  return (
    <div className="mb-5">
      <h2 className="text-[11pt] font-bold">{titulo}</h2>
      <p className="mb-1.5 text-[8pt] text-[color:var(--doc-muted)]">{nota}</p>
      {children}
    </div>
  );
}

function Bloco({
  n,
  titulo,
  children,
  className = "",
}: {
  n: string;
  titulo: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={className}>
      <p className="mb-1 font-bold">
        {n}. {titulo}
      </p>
      <div className="pl-4">{children}</div>
    </div>
  );
}
