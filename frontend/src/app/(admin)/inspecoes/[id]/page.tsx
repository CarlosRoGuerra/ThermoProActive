"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ClipboardList, FileText, FlaskConical, Gauge, Plus, Thermometer } from "lucide-react";
import { api } from "@/lib/api";
import { data as fmtData, dataHora } from "@/lib/format";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { usePermissoes } from "@/lib/permissions";
import type { ClassificacaoMedicao, Equipamento, Inspecao, Laudo, Paginated } from "@/lib/types";
import {
  Alert,
  Badge,
  Button,
  Card,
  CriticidadeBadge,
  EmptyState,
  Field,
  Input,
  LoadingState,
  PageBody,
  PageHeader,
  Select,
  Table,
  TBody,
  TD,
  TH,
  THead,
  TR,
} from "@/components/ds";

const DIRECOES = [
  { v: "H", label: "Horizontal" },
  { v: "V", label: "Vertical" },
  { v: "A", label: "Axial" },
];
const SISTEMAS = [
  { v: "ELETRICO", label: "Sistemas Elétricos" },
  { v: "MEC_DINAMICO", label: "Mecânicos Dinâmicos" },
  { v: "MEC_ESTATICO", label: "Mecânicos Estáticos" },
  { v: "PROCESSO", label: "Processos Industriais" },
];

import { mensagemDeErro } from "@/lib/erros";
import {
  decimalColeta, ensaiosDoFluido, grandezasDaColeta,
  SUBTIPOS_TECNICOS, SUBTIPOS_VIBRACAO,
} from "@/features/inspecoes/coleta-tecnica";

type InstrumentoColeta = { id: number; tipo: string; marca: string; modelo: string; numero_serie: string };
type ClassificacaoColeta = { criticidade: string; classificacao_status?: string };
function Classificacao({ medicao }: { medicao: ClassificacaoColeta }) {
  if (medicao.classificacao_status === "LEGADO") return <span className="inline-flex flex-wrap gap-1">{medicao.criticidade && <CriticidadeBadge value={medicao.criticidade} />}<Badge>Classificação histórica</Badge></span>;
  if (medicao.classificacao_status === "PENDENTE" || !medicao.criticidade)
    return <Badge tone="warning">Pendente de avaliação</Badge>;
  return <CriticidadeBadge value={medicao.criticidade} />;
}

type ContextoColeta = ClassificacaoMedicao & {
  data_hora: string;
  parametros?: Record<string, unknown>;
  aceleracao_rms?: string | null;
  deslocamento_pp?: string | null;
  temperatura?: string | null;
  temperatura_ambiente?: string | null;
  emissividade?: string;
  carga_percentual?: string | null;
  valor_referencia?: string | null;
};

function DadosColeta({ medicao }: { medicao: ContextoColeta }) {
  const detalhes = [
    ["Data/hora", dataHora(medicao.data_hora)],
    ["Instrumento", medicao.instrumento ? `#${medicao.instrumento}` : null],
    ["Autor da coleta", medicao.coletado_por ? `#${medicao.coletado_por}` : null],
    ["Aceleração RMS (g)", medicao.aceleracao_rms],
    ["Deslocamento pico a pico (µm)", medicao.deslocamento_pp],
    ["Temperatura no ponto (°C)", medicao.temperatura],
    ["Temperatura ambiente (°C)", medicao.temperatura_ambiente],
    ["Emissividade", medicao.emissividade],
    ["Carga (%)", medicao.carga_percentual],
    ["Referência informada", medicao.valor_referencia],
    ["Frequência (Hz)", medicao.parametros?.frequencia_hz],
    ["Fase (°)", medicao.parametros?.fase_graus],
    ["Observação", medicao.parametros?.observacao],
  ].filter(([, valor]) => valor != null && valor !== "");
  return <details className="mt-2 text-xs text-fg-muted">
    <summary className="cursor-pointer py-1">Dados da coleta</summary>
    <dl className="mt-1 space-y-1">
      {detalhes.map(([label, valor]) => <div key={String(label)}><dt className="inline font-medium">{String(label)}: </dt><dd className="inline">{String(valor)}</dd></div>)}
    </dl>
    {!!medicao.historico_classificacao?.length && <p className="mt-2">{medicao.historico_classificacao.length} versão(ões) anterior(es) preservada(s) no histórico.</p>}
  </details>;
}

export default function InspecaoDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const { pode } = usePermissoes();
  const router = useRouter();
  // Master do cliente também lança medições aqui (decisão de 2026-09-19) —
  // "Gerar laudo" continua exclusivo da equipe interna: emitir laudo é
  // responsabilidade técnica do profissional (`laudos:emitir`), não gestão
  // do próprio parque.
  const podeEditar = pode("parque:gerenciar");
  const [insp, setInsp] = useState<Inspecao | null>(null);
  const [equipamentos, setEquipamentos] = useState<Equipamento[]>([]);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [erros, setErros] = useState<Record<string, string>>({});
  const resumoErros = useRef<HTMLDivElement>(null);
  const [instrumentos, setInstrumentos] = useState<InstrumentoColeta[]>([]);
  const [instrumento, setInstrumento] = useState("");

  const tipo = insp?.tipo_analise ?? "";
  const isVib = tipo === "VIBRACAO";
  const isTermo = tipo === "TERMOGRAFIA";
  const isTec = !!insp && !isVib && !isTermo;
  const isSensitiva = tipo === "SENSITIVA";


  const [vib, setVib] = useState({
    equipamento: "" as number | "", componente: "" as number | "", ponto_medicao: "",
    subtipo: "MEC_DINAMICO", direcao: "H", rotacao_rpm: "", velocidade_rms: "", fator_crista: "",
    aceleracao_rms: "", deslocamento_pp: "", temperatura: "", frequencia_hz: "", fase_graus: "",
  });
  const [termo, setTermo] = useState({
    equipamento: "" as number | "", ponto_medicao: "", sistema: "ELETRICO",
    temperatura_ponto: "", temperatura_referencia: "", carga_percentual: "",
    temperatura_ambiente: "", emissividade: "",
  });
  const [tec, setTec] = useState({
    equipamento: "" as number | "", ponto_medicao: "", grandezaIdx: 0,
    subtipo: "", ensaio: "FQ", grandeza_livre: "", unidade_livre: "",
    valor: "", valor_referencia: "", criticidade: "", observacao: "",
  });

  const subtipoTecnico = tec.subtipo || SUBTIPOS_TECNICOS[tipo]?.[0]?.valor || "";
  const grandezas = grandezasDaColeta(tipo, subtipoTecnico, tec.ensaio);

  async function load() {
    const data = await api<Inspecao>(`/inspecoes/${id}/`);
    setInsp(data);
    if (podeEditar) {
      const eqs = await api<Paginated<Equipamento>>(
        `/equipamentos/?setor__area__cliente=${data.cliente}`
      );
      setEquipamentos(eqs.results);
    }
  }

  useEffect(() => {
    load().catch((e) => setMsg(mensagemDeErro(e))).finally(() => setLoading(false));
    if (podeEditar) api<Paginated<InstrumentoColeta>>("/instrumentos/?page_size=500")
      .then((d) => setInstrumentos(d.results))
      .catch((e) => setMsg(mensagemDeErro(e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, user, podeEditar]);

  const equipSel = equipamentos.find((e) => e.id === vib.equipamento);
  const grandezaSel = grandezas[tec.grandezaIdx];

  async function salvar(endpoint: string, body: Record<string, unknown>, limpar: () => void) {
    setSaving(true);
    setMsg(null);
    try {
      await api(endpoint, { method: "POST", body: { ...body, instrumento: instrumento ? Number(instrumento) : null } });
      limpar();
      await load();
    } catch (e) {
      if (e && typeof e === "object" && "data" in e && e.data && typeof e.data === "object") {
        const campos = Object.fromEntries(Object.entries(e.data).map(([chave, valor]) =>
          [chave, Array.isArray(valor) ? valor.join(" ") : String(valor)]));
        setErros(campos);
        setTimeout(() => resumoErros.current?.focus(), 0);
      }
      setMsg(mensagemDeErro(e));
    } finally {
      setSaving(false);
    }
  }

  function validar(campos: Record<string, string>, obrigatorios: string[]) {
    const falhas: Record<string, string> = {};
    const valores: Record<string, string | null> = {};
    for (const [chave, texto] of Object.entries(campos)) {
      const n = decimalColeta(texto);
      if (n === undefined) falhas[chave] = "Informe um número com vírgula ou ponto decimal, sem separador de milhar.";
      else valores[chave] = n;
    }
    const estado = isVib ? vib : isTermo ? termo : tec;
    if (!estado.equipamento) falhas.equipamento = "Selecione o equipamento.";
    if (!estado.ponto_medicao.trim()) falhas.ponto_medicao = "Informe o ponto de medição.";
    for (const chave of obrigatorios)
      if (!campos[chave]?.trim()) falhas[chave] = "Preencha este campo para registrar a leitura.";
    if (grandezaSel?.livre && isTec && !tec.grandeza_livre.trim())
      falhas.grandeza_livre = "Informe a grandeza identificada pelo laboratório.";
    if (isVib) {
      if (vib.subtipo !== "MEC_DINAMICO" && !["velocidade_rms", "aceleracao_rms", "deslocamento_pp"].some((chave) => valores[chave] != null))
        falhas.velocidade_rms = "Informe ao menos uma amplitude medida: velocidade, aceleração ou deslocamento.";
      for (const chave of ["velocidade_rms", "aceleracao_rms", "deslocamento_pp", "fator_crista", "rotacao_rpm", "frequencia_hz"])
        if (valores[chave] != null && Number(valores[chave]) < 0) falhas[chave] = "Informe um valor maior ou igual a zero.";
      if (valores.rotacao_rpm != null && !Number.isInteger(Number(valores.rotacao_rpm)))
        falhas.rotacao_rpm = "Informe a rotação em RPM inteiros.";
      if (valores.fase_graus != null && (Number(valores.fase_graus) < 0 || Number(valores.fase_graus) >= 360))
        falhas.fase_graus = "Informe uma fase de 0 até menos de 360 graus.";
    }
    if (isTermo && valores.emissividade != null && (Number(valores.emissividade) <= 0 || Number(valores.emissividade) > 1))
      falhas.emissividade = "A emissividade deve ser maior que zero e até 1.";
    if (isTermo && valores.carga_percentual != null && Number(valores.carga_percentual) < 0)
      falhas.carga_percentual = "A carga não pode ser negativa.";
    setErros(falhas);
    if (Object.keys(falhas).length) {
      setTimeout(() => resumoErros.current?.focus(), 0);
      return null;
    }
    return valores;
  }

  function salvarVibracao() {
    const n = validar({ velocidade_rms: vib.velocidade_rms, aceleracao_rms: vib.aceleracao_rms,
      deslocamento_pp: vib.deslocamento_pp, fator_crista: vib.fator_crista,
      temperatura: vib.temperatura, rotacao_rpm: vib.rotacao_rpm,
      ...(vib.subtipo === "ODS" ? { frequencia_hz: vib.frequencia_hz, fase_graus: vib.fase_graus } : {}),
    }, vib.subtipo === "MEC_DINAMICO" ? ["velocidade_rms"] : []);
    if (!n) return;
    const { frequencia_hz, fase_graus, ...medidas } = n;
    return salvar("/medicoes-vibracao/", {
      inspecao: Number(id), equipamento: vib.equipamento, componente: vib.componente || null,
      ponto_medicao: vib.ponto_medicao, direcao: vib.direcao, subtipo: vib.subtipo, ...medidas,
      parametros: vib.subtipo === "ODS" ? { frequencia_hz, fase_graus } : {},
    }, () => setVib({ ...vib, ponto_medicao: "", velocidade_rms: "", fator_crista: "",
      aceleracao_rms: "", deslocamento_pp: "", temperatura: "", frequencia_hz: "", fase_graus: "" }));
  }

  function salvarTermografia() {
    const n = validar({ temperatura_ponto: termo.temperatura_ponto,
      temperatura_referencia: termo.temperatura_referencia, temperatura_ambiente: termo.temperatura_ambiente,
      emissividade: termo.emissividade,
      ...(termo.sistema === "ELETRICO" ? { carga_percentual: termo.carga_percentual } : {}),
    }, ["temperatura_ponto", "temperatura_referencia", "emissividade"]);
    if (!n) return;
    return salvar("/medicoes-termografia/", {
      inspecao: Number(id), equipamento: termo.equipamento, ponto_medicao: termo.ponto_medicao,
      sistema: termo.sistema, carga_percentual: null, ...n,
    }, () => setTermo({ ...termo, ponto_medicao: "", temperatura_ponto: "", temperatura_referencia: "" }));
  }

  function salvarTecnica() {
    const n = validar(isSensitiva ? {} : { valor: tec.valor, valor_referencia: tec.valor_referencia }, isSensitiva ? [] : ["valor"]);
    if (!n) return;
    return salvar("/medicoes-tecnicas/", {
      inspecao: Number(id), equipamento: tec.equipamento, tipo, subtipo: subtipoTecnico,
      ponto_medicao: tec.ponto_medicao,
      grandeza: grandezaSel?.livre ? tec.grandeza_livre : grandezaSel?.label ?? "",
      unidade: grandezaSel?.livre ? tec.unidade_livre : grandezaSel?.unidade ?? "",
      valor: isSensitiva ? null : n.valor, valor_referencia: n.valor_referencia ?? null,
      parametros: { ...(tipo === "FLUIDOS" ? { ensaio: tec.ensaio } : {}),
        ...(isSensitiva ? { criticidade: tec.criticidade } : {}), observacao: tec.observacao },
    }, () => setTec({ ...tec, ponto_medicao: "", valor: "", valor_referencia: "", criticidade: "", observacao: "" }));
  }

  async function gerarLaudo() {
    setMsg(null);
    try {
      const laudo = await api<Laudo>("/laudos/gerar/", { method: "POST", body: { inspecao: Number(id) } });
      router.push(`/laudos/${laudo.id}`);
    } catch (e) {
      setMsg(mensagemDeErro(e));
    }
  }

  if (loading) return <LoadingState variante="formulario" linhas={4} label="Carregando a inspeção…" />;
  if (!insp)
    return (
      <Card padding={false}>
        <EmptyState
          icon={ClipboardList}
          title="Inspeção não encontrada"
          description="Ela pode ter sido removida, ou o endereço está incorreto."
          action={
            <Link href="/inspecoes">
              <Button variant="secondary" size="sm">
                Voltar para inspeções
              </Button>
            </Link>
          }
        />
      </Card>
    );

  const Icon = isVib ? Gauge : isTermo ? Thermometer : FlaskConical;

  return (
    <PageBody>
      <PageHeader
        icon={Icon}
        title={`Inspeção #${insp.id}`}
        description={`${insp.tipo_analise_display} · coletada em ${fmtData(insp.data)} por ${insp.tecnico_nome} · ${insp.cliente_nome}`}
        trilha={[{ label: "Inspeções", href: "/inspecoes" }, { label: `#${insp.id}` }]}
        selo={insp.criticidade_maxima ? <CriticidadeBadge value={insp.criticidade_maxima} /> : <Badge tone="warning">Pendente de avaliação</Badge>}
        actions={
          user?.is_interno && insp.qtd_medicoes > 0 ? (
            <Button onClick={gerarLaudo} icon={FileText}>
              Gerar laudo
            </Button>
          ) : undefined
        }
      />

      {msg && (
        <Alert tone="danger" title="Não foi possível concluir" onClose={() => setMsg(null)}>
          {msg}
        </Alert>
      )}

      {Object.keys(erros).length > 0 && (
        <div ref={resumoErros} tabIndex={-1} role="alert" className="rounded-lg border border-danger p-4 text-sm text-danger-fg">
          <p className="font-semibold">Confira os campos indicados antes de salvar.</p>
          <ul className="mt-2 list-inside list-disc">
            {Object.entries(erros).map(([campo, erro]) => (
              <li key={campo}><a className="underline" href={`#coleta-${campo}`}>{erro}</a></li>
            ))}
          </ul>
        </div>
      )}

      {podeEditar && (
        <Card>
          <Field label="Instrumento utilizado" erro={erros.instrumento} htmlFor="coleta-instrumento" hint="Vinculado à leitura; informe o instrumento realmente utilizado.">
            <Select value={instrumento} onChange={(e) => setInstrumento(e.target.value)} disabled={saving}>
              <option value="">Não informado</option>
              {instrumentos.map((i) => <option key={i.id} value={i.id}>{i.tipo} · {i.marca} {i.modelo} · {i.numero_serie}</option>)}
            </Select>
          </Field>
        </Card>
      )}

      {/* ---------- Formulário de Vibração ---------- */}
      {podeEditar && isVib && (
        <Card>
          <h2 className="mb-4 text-sm font-semibold text-fg">Registrar medição de vibração</h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Field label="Modalidade" obrigatorio erro={erros.subtipo} htmlFor="coleta-subtipo">
              <Select value={vib.subtipo} onChange={(e) => { setVib({ ...vib, subtipo: e.target.value }); setErros({}); }}>
                {SUBTIPOS_VIBRACAO.map((s) => <option key={s.valor} value={s.valor}>{s.label}</option>)}
              </Select>
            </Field>
            <Field label="Equipamento" obrigatorio erro={erros.equipamento} htmlFor="coleta-equipamento">
              <Select
                value={vib.equipamento}
                onChange={(e) => setVib({ ...vib, equipamento: e.target.value ? Number(e.target.value) : "", componente: "" })}
              >
                <option value="">Selecione…</option>
                {equipamentos.map((eq) => (
                  <option key={eq.id} value={eq.id}>{eq.tag} — {eq.nome} (Classe {eq.classe_iso})</option>
                ))}
              </Select>
            </Field>
            <Field label="Componente">
              <Select value={vib.componente} onChange={(e) => setVib({ ...vib, componente: e.target.value ? Number(e.target.value) : "" })} disabled={!equipSel}>
                <option value="">—</option>
                {equipSel?.componentes.map((c) => <option key={c.id} value={c.id}>{c.nome}</option>)}
              </Select>
            </Field>
            <Field label="Ponto de medição" htmlFor="coleta-ponto_medicao" erro={erros.ponto_medicao} obrigatorio>
              <Input value={vib.ponto_medicao} onChange={(e) => setVib({ ...vib, ponto_medicao: e.target.value })} placeholder="Ex.: Mancal LA" />
            </Field>
            <Field label="Direção">
              <Select value={vib.direcao} onChange={(e) => setVib({ ...vib, direcao: e.target.value })}>
                {DIRECOES.map((d) => <option key={d.v} value={d.v}>{d.label}</option>)}
              </Select>
            </Field>
            <Field label="Rotação (RPM)" htmlFor="coleta-rotacao_rpm" erro={erros.rotacao_rpm}>
              <Input inputMode="decimal" value={vib.rotacao_rpm} onChange={(e) => setVib({ ...vib, rotacao_rpm: e.target.value })} />
            </Field>
            <Field label="Velocidade RMS (mm/s)" obrigatorio={vib.subtipo === "MEC_DINAMICO"} htmlFor="coleta-velocidade_rms" erro={erros.velocidade_rms} hint={vib.subtipo !== "MEC_DINAMICO" ? "Informe velocidade, aceleração ou deslocamento medido." : undefined}>
              <Input inputMode="decimal" value={vib.velocidade_rms} onChange={(e) => setVib({ ...vib, velocidade_rms: e.target.value })} />
            </Field>
            <Field label="Fator de crista" htmlFor="coleta-fator_crista" erro={erros.fator_crista}>
              <Input inputMode="decimal" value={vib.fator_crista} onChange={(e) => setVib({ ...vib, fator_crista: e.target.value })} />
            </Field>
            <Field label="Aceleração RMS (g)" erro={erros.aceleracao_rms} htmlFor="coleta-aceleracao_rms">
              <Input inputMode="decimal" value={vib.aceleracao_rms} onChange={(e) => setVib({ ...vib, aceleracao_rms: e.target.value })} />
            </Field>
            <Field label="Deslocamento pico a pico (µm)" erro={erros.deslocamento_pp} htmlFor="coleta-deslocamento_pp" hint="Não equivale ao deslocamento RMS.">
              <Input inputMode="decimal" value={vib.deslocamento_pp} onChange={(e) => setVib({ ...vib, deslocamento_pp: e.target.value })} />
            </Field>
            <Field label="Temperatura no ponto (°C)" erro={erros.temperatura} htmlFor="coleta-temperatura">
              <Input inputMode="decimal" value={vib.temperatura} onChange={(e) => setVib({ ...vib, temperatura: e.target.value })} />
            </Field>
            {vib.subtipo === "ODS" && <>
              <Field label="Frequência (Hz)" erro={erros.frequencia_hz} htmlFor="coleta-frequencia_hz">
                <Input inputMode="decimal" value={vib.frequencia_hz} onChange={(e) => setVib({ ...vib, frequencia_hz: e.target.value })} />
              </Field>
              <Field label="Fase (°)" erro={erros.fase_graus} htmlFor="coleta-fase_graus" hint="Leitura angular de 0 até menos de 360°; sem diagnóstico automático.">
                <Input inputMode="decimal" value={vib.fase_graus} onChange={(e) => setVib({ ...vib, fase_graus: e.target.value })} />
              </Field>
            </>}
            <div className="flex items-end">
              <Button onClick={salvarVibracao} loading={saving} disabled={saving} icon={Plus} className="w-full">Adicionar</Button>
            </div>
          </div>
          <p className="mt-3 text-xs text-fg-subtle">A classificação depende do subtipo e de um critério aplicável. ODS e sistemas estáticos ficam pendentes de avaliação técnica. O registro pontual de ODS não substitui o estudo completo de formas de deflexão.</p>
        </Card>
      )}

      {/* ---------- Formulário de Termografia ---------- */}
      {podeEditar && isTermo && (
        <Card>
          <h2 className="mb-4 text-sm font-semibold text-fg">Registrar medição de termografia</h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Field label="Equipamento" obrigatorio erro={erros.equipamento} htmlFor="coleta-equipamento">
              <Select value={termo.equipamento} onChange={(e) => setTermo({ ...termo, equipamento: e.target.value ? Number(e.target.value) : "" })}>
                <option value="">Selecione…</option>
                {equipamentos.map((eq) => <option key={eq.id} value={eq.id}>{eq.tag} — {eq.nome}</option>)}
              </Select>
            </Field>
            <Field label="Sistema">
              <Select value={termo.sistema} onChange={(e) => setTermo({ ...termo, sistema: e.target.value })}>
                {SISTEMAS.map((s) => <option key={s.v} value={s.v}>{s.label}</option>)}
              </Select>
            </Field>
            <Field label="Ponto de medição" htmlFor="coleta-ponto_medicao" erro={erros.ponto_medicao} obrigatorio>
              <Input value={termo.ponto_medicao} onChange={(e) => setTermo({ ...termo, ponto_medicao: e.target.value })} placeholder="Ex.: Conexão fase R" />
            </Field>
            {termo.sistema === "ELETRICO" && <Field label="Carga (%)" erro={erros.carga_percentual} htmlFor="coleta-carga_percentual">
              <Input inputMode="decimal" value={termo.carga_percentual} onChange={(e) => setTermo({ ...termo, carga_percentual: e.target.value })} />
            </Field>}
            <Field label="Emissividade" obrigatorio erro={erros.emissividade} htmlFor="coleta-emissividade" hint="Informe o ajuste utilizado no instrumento; valor maior que 0 e até 1.">
              <Input inputMode="decimal" value={termo.emissividade} onChange={(e) => setTermo({ ...termo, emissividade: e.target.value })} />
            </Field>
            <Field label="Temperatura ambiente (°C)" erro={erros.temperatura_ambiente} htmlFor="coleta-temperatura_ambiente">
              <Input inputMode="decimal" value={termo.temperatura_ambiente} onChange={(e) => setTermo({ ...termo, temperatura_ambiente: e.target.value })} />
            </Field>
            <Field label="Temp. do ponto (°C)" obrigatorio htmlFor="coleta-temperatura_ponto" erro={erros.temperatura_ponto}>
              <Input inputMode="decimal" value={termo.temperatura_ponto} onChange={(e) => setTermo({ ...termo, temperatura_ponto: e.target.value })} />
            </Field>
            <Field label="Temp. de referência (°C)" obrigatorio htmlFor="coleta-temperatura_referencia" erro={erros.temperatura_referencia}>
              <Input inputMode="decimal" value={termo.temperatura_referencia} onChange={(e) => setTermo({ ...termo, temperatura_referencia: e.target.value })} />
            </Field>
            <div className="flex items-end lg:col-span-2">
              <Button onClick={salvarTermografia} loading={saving} disabled={saving} icon={Plus} className="w-full">Adicionar</Button>
            </div>
          </div>
          <p className="mt-3 text-xs text-fg-subtle">ΔT é a diferença entre a temperatura medida e a de referência. A classificação aguarda critério validado para o sistema inspecionado.</p>
        </Card>
      )}

      {/* ---------- Formulário Técnico genérico ---------- */}
      {podeEditar && isTec && (
        <Card>
          <h2 className="mb-4 text-sm font-semibold text-fg">Registrar medição — {insp.tipo_analise_display}</h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Field label="Modalidade" obrigatorio erro={erros.subtipo} htmlFor="coleta-subtipo">
              <Select value={subtipoTecnico} onChange={(e) => { setTec({ ...tec, subtipo: e.target.value, ensaio: "FQ", grandezaIdx: 0, valor: "", valor_referencia: "" }); setErros({}); }}>
                {(SUBTIPOS_TECNICOS[tipo] ?? []).map((s) => <option key={s.valor} value={s.valor}>{s.label}</option>)}
              </Select>
            </Field>
            {tipo === "FLUIDOS" && <Field label="Ensaio" obrigatorio erro={erros.parametros} htmlFor="coleta-parametros">
              <Select value={tec.ensaio} onChange={(e) => { setTec({ ...tec, ensaio: e.target.value, grandezaIdx: 0, valor: "", valor_referencia: "" }); setErros({}); }}>
                {ensaiosDoFluido(subtipoTecnico).map((e) => <option key={e.valor} value={e.valor}>{e.label}</option>)}
              </Select>
            </Field>}
            <Field label="Equipamento" obrigatorio erro={erros.equipamento} htmlFor="coleta-equipamento">
              <Select value={tec.equipamento} onChange={(e) => setTec({ ...tec, equipamento: e.target.value ? Number(e.target.value) : "" })}>
                <option value="">Selecione…</option>
                {equipamentos.map((eq) => <option key={eq.id} value={eq.id}>{eq.tag} — {eq.nome}</option>)}
              </Select>
            </Field>
            <Field label="Grandeza">
              <Select value={tec.grandezaIdx} onChange={(e) => setTec({ ...tec, grandezaIdx: Number(e.target.value), valor: "", valor_referencia: "" })}>
                {grandezas.map((g, i) => (
                  <option key={g.label} value={i}>{g.label}{g.unidade ? ` (${g.unidade})` : ""}</option>
                ))}
              </Select>
            </Field>
            {grandezaSel?.livre && <>
              <Field label="Grandeza informada pelo laboratório" obrigatorio erro={erros.grandeza_livre} htmlFor="coleta-grandeza_livre">
                <Input maxLength={80} value={tec.grandeza_livre} onChange={(e) => setTec({ ...tec, grandeza_livre: e.target.value })} />
              </Field>
              <Field label="Unidade informada pelo laboratório" erro={erros.unidade} htmlFor="coleta-unidade">
                <Input maxLength={20} value={tec.unidade_livre} onChange={(e) => setTec({ ...tec, unidade_livre: e.target.value })} />
              </Field>
            </>}
            <Field label="Ponto de medição" htmlFor="coleta-ponto_medicao" erro={erros.ponto_medicao} obrigatorio>
              <Input value={tec.ponto_medicao} onChange={(e) => setTec({ ...tec, ponto_medicao: e.target.value })} placeholder="Ex.: Enrolamento do estator" />
            </Field>

            {isSensitiva ? (
              <>
                <Field label="Condição">
                  <Select value={tec.criticidade} onChange={(e) => setTec({ ...tec, criticidade: e.target.value })}>
                    <option value="">Aguardando avaliação técnica</option>
                    <option value="NORMAL">Normal</option>
                    <option value="ALERTA">Alerta</option>
                    <option value="CRITICO">Crítico</option>
                  </Select>
                </Field>
                <Field label="Observação" className="lg:col-span-3">
                  <Input value={tec.observacao} onChange={(e) => setTec({ ...tec, observacao: e.target.value })} placeholder="Ex.: ruído anormal no acoplamento" />
                </Field>
              </>
            ) : (
              <>
                <Field label={`Valor${grandezaSel?.livre ? (tec.unidade_livre ? ` (${tec.unidade_livre})` : "") : grandezaSel?.unidade ? ` (${grandezaSel.unidade})` : " (adimensional)"}`} obrigatorio erro={erros.valor} htmlFor="coleta-valor">
                  <Input inputMode="decimal" value={tec.valor} onChange={(e) => setTec({ ...tec, valor: e.target.value })} />
                </Field>
                  <Field label="Valor de referência" erro={erros.valor_referencia} htmlFor="coleta-valor_referencia" hint="Na mesma unidade da leitura. Não aplica classificação automática.">
                    <Input inputMode="decimal" value={tec.valor_referencia} onChange={(e) => setTec({ ...tec, valor_referencia: e.target.value })} />
                  </Field>
              </>
            )}
            {!isSensitiva && <Field label="Observação da leitura" className="lg:col-span-2">
              <Input value={tec.observacao} onChange={(e) => setTec({ ...tec, observacao: e.target.value })} />
            </Field>}
            <div className="flex items-end">
              <Button onClick={salvarTecnica} loading={saving} disabled={saving} icon={Plus} className="w-full">Adicionar</Button>
            </div>
          </div>
          <p className="mt-3 text-xs text-fg-subtle">
            {isSensitiva
              ? "Inspeção qualitativa — a condição é informada pelo técnico."
              : "As leituras ficam pendentes de avaliação até a confirmação do critério aplicável. Uma referência informada não é um limite oficial."}
          </p>
          {tipo === "FLUIDOS" && tec.ensaio === "CR" && <Alert tone="warning" className="mt-3">A definição de CR e sua correspondência com os ensaios de laboratório precisam de confirmação do cliente. Registre a grandeza e a unidade do laudo original.</Alert>}
          {tipo === "FLUIDOS" && tec.ensaio === "CP" && <p className="mt-2 text-xs text-fg-subtle">Registre cada faixa como uma leitura. O código ISO 4406 possui três classes e não deve ser digitado como um número decimal. A ficha de ensaios de fluidos reúne as faixas e o código.</p>}
        </Card>
      )}

      {/* ---------- Tabelas ---------- */}
      {isVib &&
        (insp.medicoes_vibracao.length === 0 ? (
          <Card><EmptyState icon={Gauge} title="Nenhuma medição registrada" description="Adicione a primeira leitura de vibração no formulário acima." /></Card>
        ) : (
          <Table>
            <THead><TH>Equipamento</TH><TH>Ponto / subtipo</TH><TH>Dir.</TH><TH>Vrms (mm/s)</TH><TH>Zona</TH><TH>Criticidade</TH><TH>Diagnóstico</TH></THead>
            <TBody>
              {insp.medicoes_vibracao.map((m) => (
                <TR key={m.id} className="align-top">
                  <TD className="font-medium text-fg">{m.equipamento_tag}</TD>
                  <TD>{m.ponto_medicao}<p className="text-xs text-fg-subtle">{SUBTIPOS_VIBRACAO.find((s) => s.valor === m.subtipo)?.label ?? "Subtipo histórico não informado"}</p></TD><TD>{m.direcao}</TD>
                  <TD className="font-semibold text-fg">{m.velocidade_rms ?? "—"}</TD><TD>{m.zona_iso || "—"}</TD>
                  <TD><Classificacao medicao={m} /></TD>
                  <TD className="text-xs text-fg-subtle">{m.diagnostico_sugerido}<DadosColeta medicao={m} /></TD>
                </TR>
              ))}
            </TBody>
          </Table>
        ))}

      {isTermo &&
        (insp.medicoes_termografia.length === 0 ? (
          <Card><EmptyState icon={Thermometer} title="Nenhuma medição registrada" description="Adicione a primeira leitura de termografia no formulário acima." /></Card>
        ) : (
          <Table>
            <THead><TH>Equipamento</TH><TH>Ponto</TH><TH>Sistema</TH><TH>T.ponto</TH><TH>T.ref</TH><TH>ΔT (°C)</TH><TH>Criticidade</TH><TH>Diagnóstico</TH></THead>
            <TBody>
              {insp.medicoes_termografia.map((m) => (
                <TR key={m.id} className="align-top">
                  <TD className="font-medium text-fg">{m.equipamento_tag}</TD>
                  <TD>{m.ponto_medicao}</TD><TD className="text-xs">{m.sistema_display}</TD>
                  <TD>{m.temperatura_ponto}</TD><TD>{m.temperatura_referencia}</TD>
                  <TD className="font-semibold text-fg">{m.delta_t}</TD>
                  <TD><Classificacao medicao={m} /></TD>
                  <TD className="text-xs text-fg-subtle">{m.diagnostico_sugerido}<DadosColeta medicao={m} /></TD>
                </TR>
              ))}
            </TBody>
          </Table>
        ))}

      {isTec &&
        (insp.medicoes_tecnicas.length === 0 ? (
          <Card><EmptyState icon={FlaskConical} title="Nenhuma medição registrada" description="Adicione a primeira leitura no formulário acima." /></Card>
        ) : (
          <Table>
            <THead><TH>Equipamento</TH><TH>Ponto</TH><TH>Grandeza</TH><TH>Valor</TH><TH>Criticidade</TH><TH>Diagnóstico</TH></THead>
            <TBody>
              {insp.medicoes_tecnicas.map((m) => (
                <TR key={m.id} className="align-top">
                  <TD className="font-medium text-fg">{m.equipamento_tag}</TD>
                  <TD>{m.ponto_medicao}<p className="text-xs text-fg-subtle">{SUBTIPOS_TECNICOS[m.tipo]?.find((s) => s.valor === m.subtipo)?.label ?? "Subtipo histórico não informado"}{typeof m.parametros.ensaio === "string" ? ` · ${m.parametros.ensaio}` : ""}</p></TD><TD>{m.grandeza}</TD>
                  <TD className="font-semibold text-fg">{m.valor == null ? "Avaliação qualitativa" : `${m.valor} ${m.unidade}`}</TD>
                  <TD><Classificacao medicao={m} /></TD>
                  <TD className="text-xs text-fg-subtle">{m.diagnostico_sugerido}<DadosColeta medicao={m} /></TD>
                </TR>
              ))}
            </TBody>
          </Table>
        ))}
    </PageBody>
  );
}
