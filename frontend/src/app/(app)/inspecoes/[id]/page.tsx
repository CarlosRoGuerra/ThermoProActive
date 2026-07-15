"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, FileText, FlaskConical, Gauge, Plus, Thermometer } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Equipamento, Inspecao, Laudo, Paginated } from "@/lib/types";
import {
  Button,
  Card,
  CriticidadeBadge,
  EmptyState,
  Field,
  Input,
  Select,
  Spinner,
  Table,
  TBody,
  TD,
  TH,
  THead,
  TR,
} from "@/components/ui";

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

// Grandezas e unidades por tipo de análise técnica (Anexo I 2.3.2.3–2.3.2.10).
type Grandeza = { label: string; unidade: string; usaRef: boolean };
const SCHEMA_TECNICO: Record<string, Grandeza[]> = {
  ENSAIO_ELETRICO: [
    { label: "Resistência de isolação", unidade: "MΩ", usaRef: false },
    { label: "Relação de transformação (TTR)", unidade: "%", usaRef: true },
    { label: "Resistência ôhmica", unidade: "Ω", usaRef: true },
  ],
  FLUIDOS: [
    { label: "Água", unidade: "ppm", usaRef: true },
    { label: "Viscosidade", unidade: "cSt", usaRef: true },
    { label: "Contagem de partículas (ISO 4406)", unidade: "código", usaRef: true },
    { label: "TAN", unidade: "mgKOH/g", usaRef: true },
  ],
  ULTRASSOM: [{ label: "Nível", unidade: "dB", usaRef: false }],
  ESPESSURA: [{ label: "Espessura", unidade: "mm", usaRef: true }],
  QUALIDADE_ENERGIA: [
    { label: "THD de tensão", unidade: "%", usaRef: false },
    { label: "THD de corrente", unidade: "%", usaRef: false },
    { label: "Desequilíbrio de tensão", unidade: "%", usaRef: false },
  ],
  CORRETIVA: [
    { label: "Desalinhamento", unidade: "mm/100mm", usaRef: false },
    { label: "Balanceamento residual", unidade: "g·mm", usaRef: false },
  ],
  SENSITIVA: [{ label: "Inspeção sensorial", unidade: "", usaRef: false }],
};

export default function InspecaoDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const router = useRouter();
  const [insp, setInsp] = useState<Inspecao | null>(null);
  const [equipamentos, setEquipamentos] = useState<Equipamento[]>([]);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const tipo = insp?.tipo_analise ?? "";
  const isVib = tipo === "VIBRACAO";
  const isTermo = tipo === "TERMOGRAFIA";
  const isTec = !!insp && !isVib && !isTermo;
  const isSensitiva = tipo === "SENSITIVA";
  const grandezas = useMemo(() => SCHEMA_TECNICO[tipo] ?? [], [tipo]);

  const [vib, setVib] = useState({
    equipamento: "" as number | "", componente: "" as number | "", ponto_medicao: "",
    direcao: "H", rotacao_rpm: "", velocidade_rms: "", fator_crista: "",
  });
  const [termo, setTermo] = useState({
    equipamento: "" as number | "", ponto_medicao: "", sistema: "ELETRICO",
    temperatura_ponto: "", temperatura_referencia: "", carga_percentual: "",
  });
  const [tec, setTec] = useState({
    equipamento: "" as number | "", ponto_medicao: "", grandezaIdx: 0,
    valor: "", valor_referencia: "", criticidade: "NORMAL", observacao: "",
  });

  async function load() {
    const data = await api<Inspecao>(`/inspecoes/${id}/`);
    setInsp(data);
    if (user?.is_interno) {
      const eqs = await api<Paginated<Equipamento>>(
        `/equipamentos/?setor__area__cliente=${data.cliente}`
      );
      setEquipamentos(eqs.results);
    }
  }

  useEffect(() => {
    load().finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, user]);

  const equipSel = equipamentos.find((e) => e.id === vib.equipamento);
  const grandezaSel = grandezas[tec.grandezaIdx];

  async function salvar(endpoint: string, body: Record<string, unknown>, limpar: () => void) {
    setSaving(true);
    setMsg(null);
    try {
      await api(endpoint, { method: "POST", body });
      limpar();
      await load();
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "Erro ao salvar.");
    } finally {
      setSaving(false);
    }
  }

  const salvarVibracao = () =>
    salvar(
      "/medicoes-vibracao/",
      {
        inspecao: Number(id), equipamento: vib.equipamento, componente: vib.componente || null,
        ponto_medicao: vib.ponto_medicao, direcao: vib.direcao,
        rotacao_rpm: vib.rotacao_rpm ? Number(vib.rotacao_rpm) : null,
        velocidade_rms: vib.velocidade_rms, fator_crista: vib.fator_crista || null,
      },
      () => setVib({ ...vib, ponto_medicao: "", velocidade_rms: "", fator_crista: "" })
    );

  const salvarTermografia = () =>
    salvar(
      "/medicoes-termografia/",
      {
        inspecao: Number(id), equipamento: termo.equipamento, ponto_medicao: termo.ponto_medicao,
        sistema: termo.sistema, temperatura_ponto: termo.temperatura_ponto,
        temperatura_referencia: termo.temperatura_referencia,
        carga_percentual: termo.carga_percentual || null,
      },
      () => setTermo({ ...termo, ponto_medicao: "", temperatura_ponto: "", temperatura_referencia: "" })
    );

  const salvarTecnica = () =>
    salvar(
      "/medicoes-tecnicas/",
      {
        inspecao: Number(id), equipamento: tec.equipamento, tipo,
        ponto_medicao: tec.ponto_medicao, grandeza: grandezaSel?.label ?? "",
        unidade: grandezaSel?.unidade ?? "",
        valor: isSensitiva ? 0 : tec.valor,
        valor_referencia: grandezaSel?.usaRef && tec.valor_referencia ? tec.valor_referencia : null,
        parametros: isSensitiva ? { criticidade: tec.criticidade, observacao: tec.observacao } : {},
      },
      () => setTec({ ...tec, ponto_medicao: "", valor: "", valor_referencia: "", observacao: "" })
    );

  async function gerarLaudo() {
    setMsg(null);
    try {
      const laudo = await api<Laudo>("/laudos/gerar/", { method: "POST", body: { inspecao: Number(id) } });
      router.push(`/laudos/${laudo.id}`);
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "Erro ao gerar laudo.");
    }
  }

  if (loading) return <Spinner />;
  if (!insp) return <p className="text-fg-muted">Inspeção não encontrada.</p>;

  const Icon = isVib ? Gauge : isTermo ? Thermometer : FlaskConical;
  const tecValido = isSensitiva
    ? !!tec.equipamento && !!tec.ponto_medicao
    : !!tec.equipamento && !!tec.ponto_medicao && !!tec.valor;

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <button
            onClick={() => router.back()}
            className="inline-flex items-center gap-1 text-sm text-fg-muted transition-colors hover:text-fg"
          >
            <ArrowLeft className="h-4 w-4" /> Voltar
          </button>
          <h1 className="mt-1.5 flex items-center gap-2 text-xl font-semibold tracking-tight text-fg">
            <Icon className="h-5 w-5 text-accent" />
            Inspeção #{insp.id} — {insp.cliente_nome}
          </h1>
          <p className="mt-0.5 text-sm text-fg-muted">
            {insp.tipo_analise_display} · {insp.data} · Técnico: {insp.tecnico_nome}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <CriticidadeBadge value={insp.criticidade_maxima} />
          {user?.is_interno && insp.qtd_medicoes > 0 && (
            <Button onClick={gerarLaudo} icon={FileText}>
              Gerar laudo
            </Button>
          )}
        </div>
      </header>

      {msg && <div className="rounded-lg bg-danger-subtle px-3 py-2 text-sm text-danger-fg">{msg}</div>}

      {/* ---------- Formulário de Vibração ---------- */}
      {user?.is_interno && isVib && (
        <Card>
          <h2 className="mb-4 text-sm font-semibold text-fg">Registrar medição de vibração</h2>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <Field label="Equipamento">
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
            <Field label="Ponto de medição">
              <Input value={vib.ponto_medicao} onChange={(e) => setVib({ ...vib, ponto_medicao: e.target.value })} placeholder="Ex.: Mancal LA" />
            </Field>
            <Field label="Direção">
              <Select value={vib.direcao} onChange={(e) => setVib({ ...vib, direcao: e.target.value })}>
                {DIRECOES.map((d) => <option key={d.v} value={d.v}>{d.label}</option>)}
              </Select>
            </Field>
            <Field label="Rotação (RPM)">
              <Input type="number" value={vib.rotacao_rpm} onChange={(e) => setVib({ ...vib, rotacao_rpm: e.target.value })} />
            </Field>
            <Field label="Velocidade RMS (mm/s) *">
              <Input type="number" step="0.01" value={vib.velocidade_rms} onChange={(e) => setVib({ ...vib, velocidade_rms: e.target.value })} />
            </Field>
            <Field label="Fator de crista">
              <Input type="number" step="0.01" value={vib.fator_crista} onChange={(e) => setVib({ ...vib, fator_crista: e.target.value })} />
            </Field>
            <div className="flex items-end">
              <Button onClick={salvarVibracao} loading={saving} disabled={!vib.equipamento || !vib.ponto_medicao || !vib.velocidade_rms} icon={Plus} className="w-full">Adicionar</Button>
            </div>
          </div>
          <p className="mt-3 text-xs text-fg-subtle">Zona ISO e criticidade calculadas automaticamente (ISO 10816/20816).</p>
        </Card>
      )}

      {/* ---------- Formulário de Termografia ---------- */}
      {user?.is_interno && isTermo && (
        <Card>
          <h2 className="mb-4 text-sm font-semibold text-fg">Registrar medição de termografia</h2>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <Field label="Equipamento">
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
            <Field label="Ponto de medição">
              <Input value={termo.ponto_medicao} onChange={(e) => setTermo({ ...termo, ponto_medicao: e.target.value })} placeholder="Ex.: Conexão fase R" />
            </Field>
            <Field label="Carga (%)">
              <Input type="number" step="0.1" value={termo.carga_percentual} onChange={(e) => setTermo({ ...termo, carga_percentual: e.target.value })} />
            </Field>
            <Field label="Temp. do ponto (°C) *">
              <Input type="number" step="0.1" value={termo.temperatura_ponto} onChange={(e) => setTermo({ ...termo, temperatura_ponto: e.target.value })} />
            </Field>
            <Field label="Temp. de referência (°C) *">
              <Input type="number" step="0.1" value={termo.temperatura_referencia} onChange={(e) => setTermo({ ...termo, temperatura_referencia: e.target.value })} />
            </Field>
            <div className="flex items-end lg:col-span-2">
              <Button onClick={salvarTermografia} loading={saving} disabled={!termo.equipamento || !termo.ponto_medicao || !termo.temperatura_ponto || !termo.temperatura_referencia} icon={Plus} className="w-full">Adicionar</Button>
            </div>
          </div>
          <p className="mt-3 text-xs text-fg-subtle">ΔT e criticidade calculados automaticamente (NBR 15572 / NETA).</p>
        </Card>
      )}

      {/* ---------- Formulário Técnico genérico ---------- */}
      {user?.is_interno && isTec && (
        <Card>
          <h2 className="mb-4 text-sm font-semibold text-fg">Registrar medição — {insp.tipo_analise_display}</h2>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <Field label="Equipamento">
              <Select value={tec.equipamento} onChange={(e) => setTec({ ...tec, equipamento: e.target.value ? Number(e.target.value) : "" })}>
                <option value="">Selecione…</option>
                {equipamentos.map((eq) => <option key={eq.id} value={eq.id}>{eq.tag} — {eq.nome}</option>)}
              </Select>
            </Field>
            <Field label="Grandeza">
              <Select value={tec.grandezaIdx} onChange={(e) => setTec({ ...tec, grandezaIdx: Number(e.target.value) })}>
                {grandezas.map((g, i) => (
                  <option key={g.label} value={i}>{g.label}{g.unidade ? ` (${g.unidade})` : ""}</option>
                ))}
              </Select>
            </Field>
            <Field label="Ponto de medição">
              <Input value={tec.ponto_medicao} onChange={(e) => setTec({ ...tec, ponto_medicao: e.target.value })} placeholder="Ex.: Enrolamento do estator" />
            </Field>

            {isSensitiva ? (
              <>
                <Field label="Condição">
                  <Select value={tec.criticidade} onChange={(e) => setTec({ ...tec, criticidade: e.target.value })}>
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
                <Field label={`Valor${grandezaSel?.unidade ? ` (${grandezaSel.unidade})` : ""} *`}>
                  <Input type="number" step="0.0001" value={tec.valor} onChange={(e) => setTec({ ...tec, valor: e.target.value })} />
                </Field>
                {grandezaSel?.usaRef && (
                  <Field label="Valor de referência">
                    <Input type="number" step="0.0001" value={tec.valor_referencia} onChange={(e) => setTec({ ...tec, valor_referencia: e.target.value })} />
                  </Field>
                )}
              </>
            )}
            <div className="flex items-end">
              <Button onClick={salvarTecnica} loading={saving} disabled={!tecValido} icon={Plus} className="w-full">Adicionar</Button>
            </div>
          </div>
          <p className="mt-3 text-xs text-fg-subtle">
            {isSensitiva
              ? "Inspeção qualitativa — a condição é informada pelo técnico."
              : "A criticidade é calculada automaticamente pelo motor de regras do tipo de análise."}
          </p>
        </Card>
      )}

      {/* ---------- Tabelas ---------- */}
      {isVib &&
        (insp.medicoes_vibracao.length === 0 ? (
          <Card><EmptyState icon={Gauge} title="Nenhuma medição registrada" description="Adicione a primeira leitura de vibração no formulário acima." /></Card>
        ) : (
          <Table>
            <THead><TH>Equipamento</TH><TH>Ponto</TH><TH>Dir.</TH><TH>Vrms (mm/s)</TH><TH>Zona</TH><TH>Criticidade</TH><TH>Diagnóstico</TH></THead>
            <TBody>
              {insp.medicoes_vibracao.map((m) => (
                <TR key={m.id} className="align-top">
                  <TD className="font-medium text-fg">{m.equipamento_tag}</TD>
                  <TD>{m.ponto_medicao}</TD><TD>{m.direcao}</TD>
                  <TD className="font-semibold text-fg">{m.velocidade_rms}</TD><TD>{m.zona_iso}</TD>
                  <TD><CriticidadeBadge value={m.criticidade} /></TD>
                  <TD className="text-xs text-fg-subtle">{m.diagnostico_sugerido}</TD>
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
                  <TD><CriticidadeBadge value={m.criticidade} /></TD>
                  <TD className="text-xs text-fg-subtle">{m.diagnostico_sugerido}</TD>
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
                  <TD>{m.ponto_medicao}</TD><TD>{m.grandeza}</TD>
                  <TD className="font-semibold text-fg">{m.valor} {m.unidade}</TD>
                  <TD><CriticidadeBadge value={m.criticidade} /></TD>
                  <TD className="text-xs text-fg-subtle">{m.diagnostico_sugerido}</TD>
                </TR>
              ))}
            </TBody>
          </Table>
        ))}
    </div>
  );
}
