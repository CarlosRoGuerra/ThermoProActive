"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Activity, Gauge, MapPin, Save, Settings, ShieldCheck } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useClienteAtivo } from "@/lib/cliente-ativo";
import { useAreasSetores } from "@/lib/hierarquia";
import type {
  CategoriaTecnica,
  CriterioVibracao,
  DadosTecnicosMotor,
  DadosTecnicosTransformador,
  Equipamento,
  Paginated,
  TipoEquipamentoOpcao,
} from "@/lib/types";
import {
  Alert,
  Badge,
  Button,
  Card,
  Field,
  FormActions,
  Input,
  LoadingState,
  PageBody,
  PageHeader,
  Select,
} from "@/components/ds";
import { Combobox } from "@/components/combobox";
import {
  CamposDatasheet,
  FotoPlaca,
  datasheetInicial,
  salvarDatasheet,
  type ValoresDatasheet,
} from "@/components/dados-tecnicos-equipamento";

/* ==========================================================================
   Cadastro de equipamento — o TIPO decide o que aparece, sempre pelo vínculo
   explícito do catálogo (nunca pelo nome digitado):

     Localização → Identificação → Classificação operacional
     → Dados técnicos (datasheet da categoria técnica do tipo)
     → Severidade de vibração (só nos tipos avaliados por vibração)

   Transformador mostra só dados de transformador; motor, só os do motor. Tipo
   sem categoria não ganha campos "genéricos" de motor: mostra que não tem ficha
   técnica e onde configurar.
   ========================================================================== */

/* Grupos em uso desde 07/10/2026 (ISO 20816-3 — definição do responsável técnico).
   As classes II–IV da ISO 10816-1 só aparecem em equipamento antigo, para revisão. */
const CLASSES_ISO = [
  { valor: "I", texto: "Classe I — até 15 kW" },
  { valor: "G2", texto: "Grupo 2 — 15 a 300 kW (ISO 20816-3)" },
  { valor: "G1", texto: "Grupo 1 — acima de 300 kW (ISO 20816-3)" },
];
const CLASSES_HISTORICAS: Record<string, string> = {
  II: "Classe II (ISO 10816-1) — revisar: escolha o grupo atual",
  III: "Classe III (ISO 10816-1) — revisar: escolha o grupo atual",
  IV: "Classe IV (ISO 10816-1) — revisar: escolha o grupo atual",
};

const ROTULO_CATEGORIA: Record<Exclude<CategoriaTecnica, "">, string> = {
  MOTOR_ELETRICO: "Motor elétrico",
  TRANSFORMADOR: "Transformador",
};

type Form = {
  tag: string;
  nome: string;
  tipo_equipamento: string; // id do catálogo "Tipos de equipamento"
  fabricante: string;
  modelo: string;
  numero_serie: string;
  numero_patrimonio: string;
  ano_fabricacao: string;
  classe_iso: string;
  criticidade: string;
};

const FORM_VAZIO: Form = {
  tag: "", nome: "", tipo_equipamento: "", fabricante: "", modelo: "", numero_serie: "",
  numero_patrimonio: "", ano_fabricacao: "", classe_iso: "", criticidade: "",
};

/** Valores de placa que ficaram em colunas genéricas do equipamento (cadastro anterior). */
type Legado = Pick<Equipamento, "potencia_kw" | "rotacao_nominal_rpm" | "tensao_nominal" | "fator_potencia_nominal">;

function Secao({ icon: Icon, titulo, descricao }: { icon: typeof Activity; titulo: string; descricao: string }) {
  return (
    <div className="mb-4 flex items-start gap-3 border-b border-border pb-3">
      <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary-subtle text-primary">
        <Icon className="h-4 w-4" />
      </div>
      <div>
        <h2 className="text-sm font-semibold text-fg">{titulo}</h2>
        <p className="text-xs text-fg-subtle">{descricao}</p>
      </div>
    </div>
  );
}

const mmS = (v: string) => `${Number(v).toLocaleString("pt-BR", { minimumFractionDigits: 2 })} mm/s`;

/** O critério aplicado à classe: norma, limites das zonas e a origem de cada valor. */
function CriterioAplicado({ criterio }: { criterio: CriterioVibracao }) {
  const acordo = criterio.origem !== "NORMA";
  return (
    <div className="rounded-lg border border-border p-3 text-sm" data-testid="criterio-vibracao">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium text-fg">
          {criterio.norma}
          {criterio.edicao ? `:${criterio.edicao}` : ""} · Classe {criterio.classe}
        </span>
        <Badge tone={acordo ? "warning" : "neutral"}>{criterio.origem_display}</Badge>
      </div>
      <dl className="mt-2 grid grid-cols-3 gap-2 text-xs">
        {([["A/B", criterio.limites.ab], ["B/C", criterio.limites.bc], ["C/D", criterio.limites.cd]] as const).map(
          ([zona, v]) => (
            <div key={zona}>
              <dt className="text-fg-subtle">Limite {zona}</dt>
              <dd className="data font-medium text-fg">{mmS(v)}</dd>
            </div>
          )
        )}
      </dl>
      {criterio.fonte && <p className="mt-2 text-xs text-fg-subtle">Fonte: {criterio.fonte}</p>}
    </div>
  );
}

export function EquipamentoForm({ equipamentoId }: { equipamentoId?: number }) {
  const router = useRouter();
  const editando = equipamentoId !== undefined;

  const { clienteAtivo } = useClienteAtivo();
  const [form, setForm] = useState<Form>(FORM_VAZIO);
  // O cliente vem do "ambiente" ativo — não se escolhe de novo aqui.
  const [cliente, setCliente] = useState<number | "">(clienteAtivo?.id ?? "");
  const [area, setArea] = useState<number | "">("");
  const [setor, setSetor] = useState<number | "">("");
  const [pai, setPai] = useState<number | "">("");
  const [candidatosPai, setCandidatosPai] = useState<Equipamento[]>([]);
  const [tiposEquip, setTiposEquip] = useState<TipoEquipamentoOpcao[]>([]);
  const [dadosMotor, setDadosMotor] = useState<DadosTecnicosMotor | null>(null);
  const [dadosTransformador, setDadosTransformador] = useState<DadosTecnicosTransformador | null>(null);
  // Campos do datasheet específico (motor/transformador), editados no quadro
  // "Dados técnicos" e gravados junto com o equipamento.
  const [valoresMotor, setValoresMotor] = useState<ValoresDatasheet>({});
  const [valoresTrafo, setValoresTrafo] = useState<ValoresDatasheet>({});
  // O que o servidor devolveu na última leitura (critério aplicado e valores legados).
  const [salvo, setSalvo] = useState<Equipamento | null>(null);
  const [carregando, setCarregando] = useState(editando);
  const [salvando, setSalvando] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const { opcoesAreas, opcoesSetores } = useAreasSetores(cliente, area);

  // Novo equipamento: segue o cliente ativo (troca de cliente no topo reflete aqui).
  useEffect(() => {
    if (!editando && clienteAtivo) setCliente(clienteAtivo.id);
  }, [clienteAtivo, editando]);

  // Tipos de equipamento vêm do catálogo (Dados de sistema).
  useEffect(() => {
    api<Paginated<TipoEquipamentoOpcao>>("/tipos-equipamento/?page_size=500")
      .then((d) => setTiposEquip(d.results))
      .catch(() => setTiposEquip([]));
  }, []);

  // Possíveis "equipamentos principais": os do mesmo setor, menos o próprio.
  useEffect(() => {
    if (!setor) {
      setCandidatosPai([]);
      return;
    }
    api<Paginated<Equipamento>>(`/equipamentos/?setor=${setor}&page_size=300`)
      .then((d) => setCandidatosPai(d.results.filter((e) => e.id !== equipamentoId)))
      .catch(() => setCandidatosPai([]));
  }, [setor, equipamentoId]);

  const opcoesPai = candidatosPai.map((e) => ({ id: e.id, label: e.tag, hint: e.nome }));

  const set = (campo: keyof Form, valor: string) => setForm((f) => ({ ...f, [campo]: valor }));

  function aplicarDatasheets(e: Equipamento) {
    setDadosMotor(e.dados_motor);
    setDadosTransformador(e.dados_transformador);
    setValoresMotor(datasheetInicial(e.dados_motor));
    setValoresTrafo(datasheetInicial(e.dados_transformador));
    setSalvo(e);
  }

  // Recarrega só o equipamento (foto da placa enviada; o motor recalcula a classe).
  async function recarregarEquipamento() {
    if (!editando) return;
    const e = await api<Equipamento>(`/equipamentos/${equipamentoId}/`);
    setForm((f) => ({ ...f, classe_iso: e.classe_iso || "" }));
    aplicarDatasheets(e);
  }

  // Carrega o equipamento e reconstitui a cascata a partir do setor salvo.
  useEffect(() => {
    if (!editando) return;
    api<Equipamento & { setor: number; cliente_id: number }>(`/equipamentos/${equipamentoId}/`)
      .then(async (e) => {
        setForm({
          tag: e.tag ?? "",
          nome: e.nome ?? "",
          tipo_equipamento: e.tipo_equipamento ? String(e.tipo_equipamento) : "",
          fabricante: e.fabricante ?? "",
          modelo: e.modelo ?? "",
          numero_serie: e.numero_serie ?? "",
          numero_patrimonio: e.numero_patrimonio ?? "",
          ano_fabricacao: e.ano_fabricacao ? String(e.ano_fabricacao) : "",
          classe_iso: e.classe_iso || "",
          criticidade: e.criticidade ?? "",
        });
        aplicarDatasheets(e);
        setCliente(e.cliente_id ?? "");
        // Descobre a área a partir do setor para preencher o passo intermediário.
        try {
          const s = await api<{ area: number }>(`/setores/${e.setor}/`);
          setArea(s.area);
        } catch {
          /* sem área: o usuário reescolhe */
        }
        setSetor(e.setor ?? "");
        setPai(e.equipamento_pai ?? "");
      })
      .catch(() => setMsg("Não foi possível carregar este equipamento."))
      .finally(() => setCarregando(false));
  }, [equipamentoId, editando]);

  // Vínculos explícitos do catálogo — decidem o que aparece; nunca o nome do tipo.
  const tipoSelecionado = tiposEquip.find((t) => String(t.id) === form.tipo_equipamento);
  const categoria: CategoriaTecnica = tipoSelecionado?.categoria_tecnica ?? "";
  const avaliaVibracao = !!tipoSelecionado?.analise_vibracao && categoria !== "TRANSFORMADOR";

  async function salvar() {
    setSalvando(true);
    setMsg(null);
    try {
      // Potência/rotação/tensão/FP genéricos não são mais editados aqui: os
      // dados de placa moram no datasheet da categoria (o do motor sincroniza
      // para o equipamento, que a Economia energética lê).
      const body: Record<string, unknown> = {
        setor,
        equipamento_pai: pai === "" ? null : pai,
        tag: form.tag,
        nome: form.nome,
        tipo_equipamento: form.tipo_equipamento === "" ? null : Number(form.tipo_equipamento),
        fabricante: form.fabricante,
        modelo: form.modelo,
        numero_serie: form.numero_serie,
        numero_patrimonio: form.numero_patrimonio,
        ano_fabricacao: form.ano_fabricacao === "" ? null : Number(form.ano_fabricacao),
        criticidade: form.criticidade,
      };
      if (avaliaVibracao && categoria !== "MOTOR_ELETRICO") body.classe_iso = form.classe_iso;

      const gravado = editando
        ? await api<Equipamento>(`/equipamentos/${equipamentoId}/`, { method: "PATCH", body })
        : await api<Equipamento>("/equipamentos/", { method: "POST", body });

      // Datasheet do tipo (motor/transformador) no mesmo gesto. Se só ele falhar,
      // o equipamento já existe: abre a edição para corrigir sem perder nada.
      if (categoria) {
        try {
          await salvarDatasheet(
            categoria,
            gravado.id,
            categoria === "MOTOR_ELETRICO" ? dadosMotor : dadosTransformador,
            categoria === "MOTOR_ELETRICO" ? valoresMotor : valoresTrafo
          );
        } catch (e) {
          setMsg(
            `O equipamento foi salvo, mas os dados técnicos não: ${
              e instanceof ApiError ? JSON.stringify(e.data) : "erro inesperado"
            }. Corrija e salve de novo.`
          );
          setSalvando(false);
          if (!editando) router.push(`/equipamentos/${gravado.id}`);
          return;
        }
      }
      router.push("/equipamentos");
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "Erro ao salvar o equipamento.");
      setSalvando(false);
    }
  }

  const podeSalvar = form.tag.trim() !== "" && form.nome.trim() !== "" && setor !== "";

  if (carregando) {
    return <LoadingState variante="formulario" linhas={4} label="Carregando o equipamento…" />;
  }

  // Placa gravada nas colunas genéricas antes do datasheet por tipo existir.
  const legado: [string, string][] = salvo
    ? ([
        ["Potência", salvo.potencia_kw ? `${salvo.potencia_kw} kW` : ""],
        ["Rotação", salvo.rotacao_nominal_rpm ? `${salvo.rotacao_nominal_rpm} RPM` : ""],
        ["Tensão", salvo.tensao_nominal ? `${salvo.tensao_nominal} V` : ""],
        ["Fator de potência", salvo.fator_potencia_nominal ?? ""],
      ] satisfies [string, string][]).filter(([, v]) => v !== "")
    : [];
  const criterioSalvo =
    salvo?.criterio_vibracao && salvo.classe_iso === form.classe_iso ? salvo.criterio_vibracao : null;

  return (
    <PageBody>
      <PageHeader
        icon={Activity}
        title={editando ? "Editar equipamento" : "Novo equipamento"}
        description="A localização segue a hierarquia Cliente → Área → Setor. O tipo de equipamento define os dados técnicos que aparecem."
        trilha={[{ label: "Equipamentos", href: "/equipamentos" }, { label: editando ? "Editar" : "Novo" }]}
      />

      {/* --- 1. Localização (dentro do cliente ativo) --- */}
      <Card>
        <Secao
          icon={MapPin}
          titulo="Localização"
          descricao={
            clienteAtivo
              ? `Cliente: ${clienteAtivo.nome_fantasia || clienteAtivo.nome}. Escolha a área e o setor.`
              : "Ative um cliente no topo para cadastrar equipamentos."
          }
        />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Área" obrigatorio>
            <Combobox
              value={area}
              onChange={(v) => {
                setArea(v);
                setSetor("");
                setPai("");
              }}
              options={opcoesAreas}
              placeholder={cliente ? "Buscar área…" : "Ative um cliente antes"}
              emptyText="Nenhuma área cadastrada para este cliente."
              disabled={!cliente}
              permiteLimpar={false}
            />
          </Field>
          <Field label="Setor" obrigatorio>
            <Combobox
              value={setor}
              onChange={(v) => {
                setSetor(v);
                setPai("");
              }}
              options={opcoesSetores}
              placeholder={area ? "Buscar setor…" : "Escolha a área antes"}
              emptyText="Nenhum setor cadastrado para esta área."
              disabled={!area}
              permiteLimpar={false}
            />
          </Field>
        </div>

        {/* Sub-item: um equipamento dentro de outro (ex.: exaustor da caldeira). */}
        <div className="mt-4 border-t border-border pt-4">
          <Field label="Faz parte de outro equipamento? (opcional)">
            <Combobox
              value={pai}
              onChange={setPai}
              options={opcoesPai}
              placeholder={setor ? "Nenhum — é um equipamento principal" : "Escolha o setor antes"}
              limparLabel="Nenhum — é um equipamento principal"
              emptyText="Nenhum outro equipamento neste setor."
              disabled={!setor}
            />
          </Field>
          <p className="mt-1.5 text-xs text-fg-subtle">
            Use quando esta máquina for um <strong>sub-item</strong> de outra — por exemplo, o
            Exaustor que pertence à Caldeira. Os componentes (motor, mancais) ficam abaixo dele.
          </p>
        </div>
      </Card>

      {/* --- 2. Identificação --- */}
      <Card>
        <Secao icon={Activity} titulo="Identificação" descricao="TAG e número de série são usados na busca em campo." />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Field label="TAG" obrigatorio>
            <Input value={form.tag} maxLength={60} placeholder="Ex.: BBA-101" onChange={(e) => set("tag", e.target.value)} />
          </Field>
          <Field label="Nome / Descrição" obrigatorio className="lg:col-span-3">
            <Input
              value={form.nome}
              maxLength={160}
              placeholder="Ex.: Bomba de Vácuo Nº.01 - Motor Elétrico"
              onChange={(e) => set("nome", e.target.value)}
            />
          </Field>
          <Field
            label="Tipo de equipamento"
            hint={
              !tipoSelecionado
                ? "Define os dados técnicos do cadastro."
                : categoria
                  ? `Ficha técnica: ${ROTULO_CATEGORIA[categoria]}`
                  : "Sem ficha técnica específica"
            }
          >
            <Select value={form.tipo_equipamento} onChange={(e) => set("tipo_equipamento", e.target.value)}>
              <option value="">Selecione…</option>
              {tiposEquip.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.nome}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Fabricante">
            <Input value={form.fabricante} maxLength={80} onChange={(e) => set("fabricante", e.target.value)} />
          </Field>
          <Field label="Modelo">
            <Input value={form.modelo} maxLength={80} onChange={(e) => set("modelo", e.target.value)} />
          </Field>
          <Field label="Número de série">
            <Input value={form.numero_serie} maxLength={80} onChange={(e) => set("numero_serie", e.target.value)} />
          </Field>
          <Field label="Número de patrimônio">
            <Input value={form.numero_patrimonio} maxLength={60} onChange={(e) => set("numero_patrimonio", e.target.value)} />
          </Field>
          <Field label="Ano de fabricação">
            <Input
              type="number"
              inputMode="numeric"
              min={1900}
              max={2100}
              value={form.ano_fabricacao}
              onChange={(e) => set("ano_fabricacao", e.target.value)}
            />
          </Field>
        </div>
      </Card>

      {/* --- 3. Classificação operacional (comum a qualquer equipamento) --- */}
      <Card>
        <Secao
          icon={ShieldCheck}
          titulo="Classificação operacional"
          descricao="A criticidade indica a importância do equipamento no processo e norteia a periodicidade de monitoramento contratada."
        />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Field label="Criticidade (importância)">
            <Select value={form.criticidade} onChange={(e) => set("criticidade", e.target.value)}>
              <option value="">— não classificado —</option>
              <option value="A">A — Alta (crítico ao processo)</option>
              <option value="B">B — Média (importante)</option>
              <option value="C">C — Baixa (auxiliar)</option>
            </Select>
          </Field>
        </div>
      </Card>

      {/* --- 4. Dados técnicos — só os da categoria técnica do tipo --- */}
      <Card as="section">
        <Secao
          icon={Settings}
          titulo={categoria ? `Dados técnicos — ${ROTULO_CATEGORIA[categoria]}` : "Dados técnicos"}
          descricao={
            categoria === "TRANSFORMADOR"
              ? "Dados de placa do transformador — usados nas fichas de óleo isolante e de ensaios elétricos."
              : categoria === "MOTOR_ELETRICO"
                ? "Dados de placa do motor — a potência e o tipo de base definem a classe de vibração."
                : "Os campos aparecem conforme a ficha técnica do tipo de equipamento."
          }
        />
        {categoria ? (
          <>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <CamposDatasheet
                categoria={categoria}
                valores={categoria === "MOTOR_ELETRICO" ? valoresMotor : valoresTrafo}
                onMudar={categoria === "MOTOR_ELETRICO" ? setValoresMotor : setValoresTrafo}
              />
            </div>
            {categoria === "TRANSFORMADOR" && (
              <p className="mt-3 text-xs text-fg-subtle">
                A tensão secundária de fase e o grupo de ligação calculam a relação nominal do R×T; o tanque de
                expansão define os itens da inspeção visual na coleta de óleo.
              </p>
            )}
          </>
        ) : !tipoSelecionado ? (
          <p className="text-sm text-fg-muted">Escolha o tipo de equipamento para ver os dados técnicos.</p>
        ) : (
          <div className="space-y-3">
            <Alert tone="info" title={`O tipo «${tipoSelecionado.nome}» não tem ficha técnica específica`}>
              Se for motor elétrico ou transformador, associe a categoria técnica em{" "}
              <Link href="/cadastros?item=tipos-equipamento" className="font-medium underline underline-offset-2">
                Dados de sistema → Tipos de equipamento
              </Link>{" "}
              (nível Master). O sistema não deduz a categoria pelo nome do tipo.
            </Alert>
            {legado.length > 0 && (
              <div className="rounded-lg border border-border p-3 text-sm" data-testid="placa-legada">
                <p className="text-xs font-medium text-fg-muted">Dados de placa do cadastro anterior (somente leitura)</p>
                <p className="mt-1 text-fg">{legado.map(([k, v]) => `${k}: ${v}`).join(" · ")}</p>
                <p className="mt-1 text-xs text-fg-subtle">
                  Continuam disponíveis para a Economia energética do balanceamento.
                </p>
              </div>
            )}
          </div>
        )}
      </Card>

      {/* Foto da placa: arquivo do datasheet, existe depois de salvo. */}
      {categoria === "MOTOR_ELETRICO" && dadosMotor && (
        <FotoPlaca categoria="MOTOR_ELETRICO" dados={dadosMotor} onMudou={recarregarEquipamento} />
      )}
      {categoria === "TRANSFORMADOR" && dadosTransformador && (
        <FotoPlaca categoria="TRANSFORMADOR" dados={dadosTransformador} onMudou={recarregarEquipamento} />
      )}

      {/* --- 5. Severidade de vibração — só nos tipos avaliados por vibração --- */}
      {avaliaVibracao && (
        <Card as="section">
          <Secao
            icon={Gauge}
            titulo="Severidade de vibração"
            descricao="Grupo da máquina no critério de severidade. Os limites vêm do perfil normativo cadastrado, com a origem de cada valor."
          />
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Field
              label={categoria === "MOTOR_ELETRICO" ? "Classe (calculada pelos dados do motor)" : "Classe da máquina"}
              hint={
                categoria === "MOTOR_ELETRICO"
                  ? "A potência do motor decide: até 15 kW Classe I; até 300 kW Grupo 2; acima, Grupo 1."
                  : "Obrigatório: toda máquina avaliada por vibração tem grupo."
              }
            >
              <Select
                value={form.classe_iso}
                disabled={categoria === "MOTOR_ELETRICO"}
                onChange={(e) => set("classe_iso", e.target.value)}
              >
                <option value="">Selecione…</option>
                {CLASSES_ISO.map((c) => (
                  <option key={c.valor} value={c.valor}>
                    {c.texto}
                  </option>
                ))}
                {CLASSES_HISTORICAS[form.classe_iso] && (
                  <option value={form.classe_iso}>{CLASSES_HISTORICAS[form.classe_iso]}</option>
                )}
              </Select>
            </Field>
            {criterioSalvo ? (
              <CriterioAplicado criterio={criterioSalvo} />
            ) : (
              <p className="self-center text-xs text-fg-subtle">
                O critério aplicado a esta classe aparece depois de salvar.
              </p>
            )}
          </div>
        </Card>
      )}

      {msg && (
        <Alert tone="danger" title="Não foi possível salvar" onClose={() => setMsg(null)}>
          {msg}
        </Alert>
      )}
      <FormActions alinhamento="entre">
        <span className="hidden text-xs text-fg-subtle sm:inline">Campos marcados com * são obrigatórios.</span>
        <span className="flex flex-1 items-center justify-end gap-2 sm:flex-none">
          <Button variant="secondary" onClick={() => router.push("/equipamentos")}>
            Cancelar
          </Button>
          <Button onClick={salvar} loading={salvando} disabled={!podeSalvar} icon={Save}>
            {editando ? "Salvar alterações" : "Cadastrar equipamento"}
          </Button>
        </span>
      </FormActions>
    </PageBody>
  );
}
