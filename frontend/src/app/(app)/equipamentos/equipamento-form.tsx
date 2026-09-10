"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Activity, ArrowLeft, MapPin, Save, Settings } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useClienteAtivo } from "@/lib/cliente-ativo";
import { useAreasSetores } from "@/lib/hierarquia";
import type { CategoriaTecnica, DadosTecnicosMotor, DadosTecnicosTransformador, Equipamento, Paginated } from "@/lib/types";
import { Button, Card, Field, Input, Select, Spinner } from "@/components/ui";
import { Combobox } from "@/components/combobox";
import { DadosMotor, DadosTransformador } from "@/components/dados-tecnicos-equipamento";

const CLASSES_ISO = [
  { valor: "I", texto: "Classe I — pequenas máquinas (< 15 kW)" },
  { valor: "II", texto: "Classe II — máquinas médias (15 a 75 kW)" },
  { valor: "III", texto: "Classe III — grandes, base rígida (> 75 kW)" },
  { valor: "IV", texto: "Classe IV — grandes, base flexível (> 75 kW)" },
];

type Form = {
  tag: string;
  nome: string;
  tipo_equipamento: string; // id do catálogo "Tipos de equipamento"
  fabricante: string;
  modelo: string;
  numero_serie: string;
  potencia_kw: string;
  rotacao_nominal_rpm: string;
  tensao_nominal: string;
  fator_potencia_nominal: string;
  classe_iso: string;
  criticidade: string;
};

const FORM_VAZIO: Form = {
  tag: "", nome: "", tipo_equipamento: "", fabricante: "", modelo: "", numero_serie: "",
  potencia_kw: "", rotacao_nominal_rpm: "", tensao_nominal: "", fator_potencia_nominal: "",
  classe_iso: "II", criticidade: "",
};

type OpcaoTipo = { id: number; nome: string; categoria_tecnica: CategoriaTecnica };

function Secao({
  icon: Icon,
  titulo,
  descricao,
}: {
  icon: typeof Activity;
  titulo: string;
  descricao: string;
}) {
  return (
    <div className="mb-4 flex items-start gap-3 border-b border-border pb-3">
      <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-accent-subtle text-accent">
        <Icon className="h-4 w-4" />
      </div>
      <div>
        <h2 className="text-sm font-semibold text-fg">{titulo}</h2>
        <p className="text-xs text-fg-subtle">{descricao}</p>
      </div>
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
  const [tiposEquip, setTiposEquip] = useState<OpcaoTipo[]>([]);
  const [dadosMotor, setDadosMotor] = useState<DadosTecnicosMotor | null>(null);
  const [dadosTransformador, setDadosTransformador] = useState<DadosTecnicosTransformador | null>(null);
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
    api<Paginated<OpcaoTipo>>("/tipos-equipamento/?page_size=1000")
      .then((d) => setTiposEquip(d.results))
      .catch(() => setTiposEquip([]));
  }, []);

  // Possíveis "equipamentos principais": os do mesmo setor, menos o próprio.
  useEffect(() => {
    if (!setor) {
      setCandidatosPai([]);
      return;
    }
    api<Paginated<Equipamento>>(`/equipamentos/?setor=${setor}&page_size=1000`)
      .then((d) => setCandidatosPai(d.results.filter((e) => e.id !== equipamentoId)))
      .catch(() => setCandidatosPai([]));
  }, [setor, equipamentoId]);

  const opcoesPai = candidatosPai.map((e) => ({
    id: e.id,
    label: e.tag,
    hint: e.nome,
  }));

  const set = (campo: keyof Form, valor: string) => setForm((f) => ({ ...f, [campo]: valor }));

  // Recarrega só o equipamento (usado pelos cards de dados técnicos ao salvar —
  // motor/transformador podem ter sincronizado potência/tensão/FP/classe ISO).
  async function recarregarEquipamento() {
    if (!editando) return;
    const e = await api<Equipamento>(`/equipamentos/${equipamentoId}/`);
    setForm((f) => ({
      ...f,
      potencia_kw: e.potencia_kw ? String(e.potencia_kw) : "",
      rotacao_nominal_rpm: e.rotacao_nominal_rpm ? String(e.rotacao_nominal_rpm) : "",
      tensao_nominal: e.tensao_nominal ? String(e.tensao_nominal) : "",
      fator_potencia_nominal: e.fator_potencia_nominal ? String(e.fator_potencia_nominal) : "",
      classe_iso: e.classe_iso ?? "II",
    }));
    setDadosMotor(e.dados_motor);
    setDadosTransformador(e.dados_transformador);
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
          potencia_kw: e.potencia_kw ? String(e.potencia_kw) : "",
          rotacao_nominal_rpm: e.rotacao_nominal_rpm ? String(e.rotacao_nominal_rpm) : "",
          tensao_nominal: e.tensao_nominal ? String(e.tensao_nominal) : "",
          fator_potencia_nominal: e.fator_potencia_nominal ? String(e.fator_potencia_nominal) : "",
          classe_iso: e.classe_iso ?? "II",
          criticidade: e.criticidade ?? "",
        });
        setDadosMotor(e.dados_motor);
        setDadosTransformador(e.dados_transformador);
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

  async function salvar() {
    setSalvando(true);
    setMsg(null);
    try {
      const body: Record<string, unknown> = {
        setor,
        equipamento_pai: pai === "" ? null : pai,
        tag: form.tag,
        nome: form.nome,
        tipo_equipamento: form.tipo_equipamento === "" ? null : Number(form.tipo_equipamento),
        fabricante: form.fabricante,
        modelo: form.modelo,
        numero_serie: form.numero_serie,
        classe_iso: form.classe_iso,
        criticidade: form.criticidade,
      };
      body.potencia_kw = form.potencia_kw === "" ? null : Number(form.potencia_kw);
      body.rotacao_nominal_rpm =
        form.rotacao_nominal_rpm === "" ? null : Number(form.rotacao_nominal_rpm);
      body.tensao_nominal = form.tensao_nominal === "" ? null : Number(form.tensao_nominal);
      body.fator_potencia_nominal =
        form.fator_potencia_nominal === "" ? null : Number(form.fator_potencia_nominal);

      if (editando) {
        await api(`/equipamentos/${equipamentoId}/`, { method: "PATCH", body });
      } else {
        await api("/equipamentos/", { method: "POST", body });
      }
      router.push("/equipamentos");
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "Erro ao salvar o equipamento.");
      setSalvando(false);
    }
  }

  const podeSalvar = form.tag.trim() !== "" && form.nome.trim() !== "" && setor !== "";
  // Vínculo explícito do catálogo (TipoEquipamento.categoria_tecnica) — decide qual
  // card de dados técnicos específicos mostrar, nunca inferido pelo nome do tipo.
  const tipoSelecionado = tiposEquip.find((t) => String(t.id) === form.tipo_equipamento);
  const categoria: CategoriaTecnica = tipoSelecionado?.categoria_tecnica ?? "";

  if (carregando) {
    return (
      <Card>
        <Spinner label="Carregando equipamento…" />
      </Card>
    );
  }

  return (
    <div className="space-y-5">
      <div>
        <Link
          href="/equipamentos"
          className="inline-flex items-center gap-1.5 text-xs font-medium text-fg-muted transition-colors hover:text-fg"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Voltar para equipamentos
        </Link>
        <h1 className="mt-2 text-xl font-semibold tracking-tight text-fg">
          {editando ? "Editar equipamento" : "Novo equipamento"}
        </h1>
        <p className="mt-0.5 text-sm text-fg-muted">
          A localização segue a hierarquia Cliente → Área → Setor.
        </p>
      </div>

      {/* --- Localização (dentro do cliente ativo) --- */}
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
          <Field label="Área *">
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
          <Field label="Setor *">
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

      {/* --- Identificação --- */}
      <Card>
        <Secao
          icon={Activity}
          titulo="Identificação"
          descricao="TAG e número de série são usados na busca em campo."
        />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Field label="TAG *">
            <Input
              value={form.tag}
              maxLength={60}
              placeholder="Ex.: BBA-101"
              onChange={(e) => set("tag", e.target.value)}
            />
          </Field>
          <Field label="Nome / Descrição *" className="lg:col-span-3">
            <Input
              value={form.nome}
              maxLength={160}
              placeholder="Ex.: Bomba de Vácuo Nº.01 - Motor Elétrico"
              onChange={(e) => set("nome", e.target.value)}
            />
          </Field>
          <Field label="Tipo de equipamento">
            <Select
              value={form.tipo_equipamento}
              onChange={(e) => set("tipo_equipamento", e.target.value)}
            >
              <option value="">Selecione…</option>
              {tiposEquip.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.nome}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Fabricante">
            <Input
              value={form.fabricante}
              maxLength={80}
              onChange={(e) => set("fabricante", e.target.value)}
            />
          </Field>
          <Field label="Modelo">
            <Input value={form.modelo} maxLength={80} onChange={(e) => set("modelo", e.target.value)} />
          </Field>
          <Field label="Número de série">
            <Input
              value={form.numero_serie}
              maxLength={80}
              onChange={(e) => set("numero_serie", e.target.value)}
            />
          </Field>
        </div>
      </Card>

      {/* --- Dados técnicos --- */}
      <Card>
        <Secao
          icon={Settings}
          titulo="Dados técnicos"
          descricao={
            categoria
              ? "Potência, rotação, tensão e FP vêm do datasheet específico abaixo — aqui só a classificação geral."
              : "A classe ISO define os limiares de severidade da análise de vibração."
          }
        />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {!categoria && (
            <>
              <Field label="Potência (kW)">
                <Input
                  type="number"
                  step="0.01"
                  value={form.potencia_kw}
                  onChange={(e) => set("potencia_kw", e.target.value)}
                />
              </Field>
              <Field label="Rotação nominal (RPM)">
                <Input
                  type="number"
                  value={form.rotacao_nominal_rpm}
                  onChange={(e) => set("rotacao_nominal_rpm", e.target.value)}
                />
              </Field>
              <Field label="Tensão nominal (V)">
                <Input
                  type="number"
                  step="0.01"
                  placeholder="Da placa do motor"
                  value={form.tensao_nominal}
                  onChange={(e) => set("tensao_nominal", e.target.value)}
                />
              </Field>
              <Field label="Fator de potência nominal">
                <Input
                  type="number"
                  step="0.001"
                  min="0"
                  max="1"
                  placeholder="Da placa do motor"
                  value={form.fator_potencia_nominal}
                  onChange={(e) => set("fator_potencia_nominal", e.target.value)}
                />
              </Field>
            </>
          )}
          <Field label={categoria ? "Classe ISO (calculada pelo datasheet abaixo)" : "Classe ISO (vibração)"}>
            <Select
              value={form.classe_iso}
              disabled={categoria === "MOTOR_ELETRICO"}
              onChange={(e) => set("classe_iso", e.target.value)}
            >
              {CLASSES_ISO.map((c) => (
                <option key={c.valor} value={c.valor}>
                  {c.texto}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Criticidade (importância)">
            <Select value={form.criticidade} onChange={(e) => set("criticidade", e.target.value)}>
              <option value="">— não classificado —</option>
              <option value="A">A — Alta (crítico ao processo)</option>
              <option value="B">B — Média (importante)</option>
              <option value="C">C — Baixa (auxiliar)</option>
            </Select>
          </Field>
        </div>
        <p className="mt-3 text-xs text-fg-subtle">
          {categoria === "MOTOR_ELETRICO"
            ? "A Classe ISO é calculada automaticamente pela potência e tipo de base informados no datasheet do motor (acima de 75 kW decide entre III e IV) — o campo fica travado aqui."
            : "A criticidade (padrão A/B/C) indica a importância do equipamento no processo e norteia a periodicidade de monitoramento contratada. Tensão e fator de potência nominais (da placa do motor) preenchem automaticamente a Economia energética do balanceamento — sem eles, o técnico precisa digitar na hora."}
        </p>
      </Card>

      {/* --- Datasheet específico por tipo (Motor Elétrico, Transformador…) --- */}
      {categoria === "MOTOR_ELETRICO" && !editando && (
        <Card>
          <p className="text-sm text-fg-muted">
            Salve o equipamento primeiro para preencher os dados técnicos do motor.
          </p>
        </Card>
      )}
      {categoria === "MOTOR_ELETRICO" && editando && (
        <DadosMotor
          equipamentoId={equipamentoId!}
          dados={dadosMotor}
          podeEditar
          onMudou={recarregarEquipamento}
        />
      )}
      {categoria === "TRANSFORMADOR" && !editando && (
        <Card>
          <p className="text-sm text-fg-muted">
            Salve o equipamento primeiro para preencher os dados técnicos do transformador.
          </p>
        </Card>
      )}
      {categoria === "TRANSFORMADOR" && editando && (
        <DadosTransformador
          equipamentoId={equipamentoId!}
          dados={dadosTransformador}
          podeEditar
          onMudou={recarregarEquipamento}
        />
      )}

      {msg && (
        <Card>
          <p className="text-sm text-danger-fg">{msg}</p>
        </Card>
      )}
      <div className="flex flex-wrap items-center justify-end gap-3 pb-2">
        <span className="mr-auto text-xs text-fg-subtle">* campos obrigatórios</span>
        <Button variant="secondary" onClick={() => router.push("/equipamentos")}>
          Cancelar
        </Button>
        <Button onClick={salvar} loading={salvando} disabled={!podeSalvar} icon={Save}>
          {editando ? "Salvar alterações" : "Cadastrar equipamento"}
        </Button>
      </div>
    </div>
  );
}
