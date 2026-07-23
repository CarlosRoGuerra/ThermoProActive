"use client";

import { Fragment, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { AlertTriangle, ArrowLeft, Calculator, Save, Wrench } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useClientes } from "@/lib/hierarquia";
import type { Equipamento, OrdemServico, Paginated } from "@/lib/types";
import { Button, Card, Field, Input, Select, Spinner, Textarea } from "@/components/ui";
import { Combobox, type Opcao } from "@/components/combobox";

/** Graus de risco com o prazo do glossário técnico do relatório. */
const GRAUS = [
  { valor: "", texto: "— não classificado —" },
  { valor: "GR0", texto: "GR-0 — Sem anomalia" },
  { valor: "GR1", texto: "GR-1 — Risco eminente (3 dias)" },
  { valor: "GR2", texto: "GR-2 — Risco elevado (10 dias)" },
  { valor: "GR3", texto: "GR-3 — Risco moderado (20 dias)" },
  { valor: "GR4", texto: "GR-4 — Risco baixo (30 dias)" },
];

/** Linhas da tabela "Avaliação de Resultados". `temQtd` = a linha tem coluna Qtde. */
const LINHAS_ROI = [
  { chave: "mao_obra", rotulo: "Mão de obra (h)", temQtd: true },
  { chave: "terceirizado", rotulo: "Serviço terceirizado (h)", temQtd: true },
  { chave: "material", rotulo: "Material de reparo (R$)", temQtd: false },
  { chave: "producao", rotulo: "Produção (h/ton)", temQtd: true },
  { chave: "outros", rotulo: "Outros (R$)", temQtd: false },
] as const;

type Campos = Record<string, string>;

function moeda(v: number) {
  return v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function Secao({
  icon: Icon,
  titulo,
  descricao,
}: {
  icon: typeof Wrench;
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

export function OspForm({ ospId }: { ospId?: number }) {
  const router = useRouter();
  const editando = ospId !== undefined;

  const { opcoes: opcoesClientes } = useClientes();
  const [cliente, setCliente] = useState<number | "">("");
  const [equipamento, setEquipamento] = useState<number | "">("");
  const [equipamentos, setEquipamentos] = useState<Equipamento[]>([]);

  const [campos, setCampos] = useState<Campos>({
    titulo: "", grau_risco: "", componente: "", anomalia: "", recomendacao: "",
    observacao: "", amplitude_velocidade: "", amplitude_aceleracao: "",
    descricao_corretiva: "", status: "ABERTA", acompanhamento: "ABERTA",
  });
  const [roi, setRoi] = useState<Campos>({});
  const [carregando, setCarregando] = useState(editando);
  const [salvando, setSalvando] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const set = (c: string, v: string) => setCampos((f) => ({ ...f, [c]: v }));
  const setR = (c: string, v: string) => setRoi((f) => ({ ...f, [c]: v }));

  // Equipamentos do cliente escolhido (filtro no servidor).
  useEffect(() => {
    if (!cliente) {
      setEquipamentos([]);
      return;
    }
    api<Paginated<Equipamento>>(`/equipamentos/?setor__area__cliente=${cliente}&page_size=1000`)
      .then((d) => setEquipamentos(d.results))
      .catch(() => setEquipamentos([]));
  }, [cliente]);

  const opcoesEquip: Opcao[] = equipamentos.map((e) => ({
    id: e.id,
    label: e.tag,
    hint: e.nome,
  }));

  useEffect(() => {
    if (!editando) return;
    api<OrdemServico & Record<string, unknown>>(`/osps/${ospId}/`)
      .then((o) => {
        setCliente(o.cliente ?? "");
        setEquipamento(o.equipamento ?? "");
        setCampos({
          titulo: o.titulo ?? "",
          grau_risco: (o.grau_risco as string) ?? "",
          componente: (o.componente as string) ?? "",
          anomalia: (o.anomalia as string) ?? "",
          recomendacao: (o.recomendacao as string) ?? "",
          observacao: (o.observacao as string) ?? "",
          amplitude_velocidade: o.amplitude_velocidade ? String(o.amplitude_velocidade) : "",
          amplitude_aceleracao: o.amplitude_aceleracao ? String(o.amplitude_aceleracao) : "",
          descricao_corretiva: (o.descricao_corretiva as string) ?? "",
          status: o.status ?? "ABERTA",
          acompanhamento: (o.acompanhamento as string) ?? "ABERTA",
        });
        const r: Campos = {};
        for (const p of ["pred", "emerg"]) {
          for (const l of LINHAS_ROI) {
            if (l.temQtd) {
              const kq = `${p}_${l.chave}_${l.chave === "producao" ? "h" : "h"}`;
              r[kq] = o[kq] ? String(o[kq]) : "";
            }
            const kv = `${p}_${l.chave}_valor`;
            r[kv] = o[kv] ? String(o[kv]) : "";
          }
        }
        setRoi(r);
      })
      .catch(() => setMsg("Não foi possível carregar esta ordem de serviço."))
      .finally(() => setCarregando(false));
  }, [ospId, editando]);

  // Totais calculados ao vivo, como na tabela verde do relatório.
  const totais = useMemo(() => {
    const soma = (p: string) =>
      LINHAS_ROI.reduce((acc, l) => acc + (Number(roi[`${p}_${l.chave}_valor`]) || 0), 0);
    const pred = soma("pred");
    const emerg = soma("emerg");
    return { pred, emerg, retorno: emerg - pred };
  }, [roi]);

  async function salvar() {
    setSalvando(true);
    setMsg(null);
    try {
      const body: Record<string, unknown> = {
        cliente,
        equipamento,
        titulo: campos.titulo,
        grau_risco: campos.grau_risco,
        componente: campos.componente,
        anomalia: campos.anomalia,
        recomendacao: campos.recomendacao,
        observacao: campos.observacao,
        descricao_corretiva: campos.descricao_corretiva,
        status: campos.status,
        acompanhamento: campos.acompanhamento,
      };
      body.amplitude_velocidade =
        campos.amplitude_velocidade === "" ? null : Number(campos.amplitude_velocidade);
      body.amplitude_aceleracao =
        campos.amplitude_aceleracao === "" ? null : Number(campos.amplitude_aceleracao);
      for (const [k, v] of Object.entries(roi)) body[k] = v === "" ? null : Number(v);

      if (editando) {
        await api(`/osps/${ospId}/`, { method: "PATCH", body });
      } else {
        await api("/osps/", { method: "POST", body });
      }
      router.push("/osps");
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "Erro ao salvar a ordem de serviço.");
      setSalvando(false);
    }
  }

  const podeSalvar = campos.titulo.trim() !== "" && cliente !== "" && equipamento !== "";

  if (carregando) {
    return (
      <Card>
        <Spinner label="Carregando ordem de serviço…" />
      </Card>
    );
  }

  return (
    <div className="space-y-5">
      <div>
        <Link
          href="/osps"
          className="inline-flex items-center gap-1.5 text-xs font-medium text-fg-muted transition-colors hover:text-fg"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Voltar para ordens de serviço
        </Link>
        <h1 className="mt-2 text-xl font-semibold tracking-tight text-fg">
          {editando ? "Editar ordem de serviço" : "Nova ordem de serviço preditiva"}
        </h1>
        <p className="mt-0.5 text-sm text-fg-muted">
          O grau de risco define automaticamente o prazo de correção.
        </p>
      </div>

      {/* --- Identificação --- */}
      <Card>
        <Secao
          icon={Wrench}
          titulo="Identificação"
          descricao="Onde a anomalia foi detectada."
        />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Cliente *">
            <Combobox
              value={cliente}
              onChange={(v) => {
                setCliente(v);
                setEquipamento("");
              }}
              options={opcoesClientes}
              placeholder="Buscar cliente…"
              permiteLimpar={false}
            />
          </Field>
          <Field label="Equipamento *">
            <Combobox
              value={equipamento}
              onChange={setEquipamento}
              options={opcoesEquip}
              placeholder={cliente ? "Buscar por TAG…" : "Escolha o cliente antes"}
              emptyText="Nenhum equipamento para este cliente."
              disabled={!cliente}
              permiteLimpar={false}
            />
          </Field>
          <Field label="Título *" className="sm:col-span-2">
            <Input
              value={campos.titulo}
              maxLength={200}
              placeholder="Ex.: Bomba de Vácuo Nº.02 - Motor Elétrico"
              onChange={(e) => set("titulo", e.target.value)}
            />
          </Field>
          <Field label="Componente">
            <Input
              value={campos.componente}
              maxLength={120}
              placeholder="Ex.: Motor Elétrico"
              onChange={(e) => set("componente", e.target.value)}
            />
          </Field>
          <Field label="Grau de risco">
            <Select value={campos.grau_risco} onChange={(e) => set("grau_risco", e.target.value)}>
              {GRAUS.map((g) => (
                <option key={g.valor} value={g.valor}>
                  {g.texto}
                </option>
              ))}
            </Select>
          </Field>
        </div>
      </Card>

      {/* --- Diagnóstico --- */}
      <Card>
        <Secao
          icon={AlertTriangle}
          titulo="Diagnóstico"
          descricao="Conteúdo que sai na Seção D do relatório técnico."
        />
        <div className="grid grid-cols-1 gap-4">
          <Field label="Anomalia detectada">
            <Textarea
              rows={2}
              value={campos.anomalia}
              placeholder="Ex.: Desbalanceamento no rotor da bomba em baixa intensidade."
              onChange={(e) => set("anomalia", e.target.value)}
            />
          </Field>
          <Field label="Recomendação">
            <Textarea
              rows={2}
              value={campos.recomendacao}
              placeholder="Ex.: Substituir rolamento(s)."
              onChange={(e) => set("recomendacao", e.target.value)}
            />
          </Field>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label="Amplitude velocidade global (mm/s)">
              <Input
                type="number"
                step="0.01"
                value={campos.amplitude_velocidade}
                onChange={(e) => set("amplitude_velocidade", e.target.value)}
              />
            </Field>
            <Field label="Amplitude aceleração global (mm/s²)">
              <Input
                type="number"
                step="0.01"
                value={campos.amplitude_aceleracao}
                onChange={(e) => set("amplitude_aceleracao", e.target.value)}
              />
            </Field>
          </div>
          <Field label="Observação">
            <Textarea rows={2} value={campos.observacao} onChange={(e) => set("observacao", e.target.value)} />
          </Field>
        </div>
      </Card>

      {/* --- Avaliação de Resultados --- */}
      <Card>
        <Secao
          icon={Calculator}
          titulo="Avaliação de Resultados"
          descricao="Compara o custo da correção preditiva com o de uma emergência. A diferença é o retorno."
        />
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-sm">
            <thead>
              <tr className="text-xs uppercase tracking-wide text-fg-subtle">
                <th className="px-2 py-2 text-left font-medium"></th>
                <th className="px-2 py-2 text-center font-medium" colSpan={2}>
                  Manut. orientada preditiva
                </th>
                <th className="px-2 py-2 text-center font-medium" colSpan={2}>
                  Manut. emergencial
                </th>
              </tr>
              <tr className="border-b border-border text-[11px] text-fg-subtle">
                <th />
                <th className="px-2 pb-2 font-normal">Qtde</th>
                <th className="px-2 pb-2 font-normal">Valor (R$)</th>
                <th className="px-2 pb-2 font-normal">Qtde</th>
                <th className="px-2 pb-2 font-normal">Valor (R$)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {LINHAS_ROI.map((l) => (
                <tr key={l.chave}>
                  <td className="px-2 py-2 font-medium text-fg">{l.rotulo}</td>
                  {(["pred", "emerg"] as const).map((p) => (
                    <Fragment key={p}>
                      <td className="px-2 py-2">
                        {l.temQtd ? (
                          <Input
                            type="number"
                            step="0.01"
                            value={roi[`${p}_${l.chave}_h`] ?? ""}
                            onChange={(e) => setR(`${p}_${l.chave}_h`, e.target.value)}
                          />
                        ) : (
                          <span className="block text-center text-fg-subtle">—</span>
                        )}
                      </td>
                      <td className="px-2 py-2">
                        <Input
                          type="number"
                          step="0.01"
                          value={roi[`${p}_${l.chave}_valor`] ?? ""}
                          onChange={(e) => setR(`${p}_${l.chave}_valor`, e.target.value)}
                        />
                      </td>
                    </Fragment>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="mt-4 grid grid-cols-1 gap-3 border-t border-border pt-4 sm:grid-cols-3">
          <div>
            <p className="text-xs text-fg-subtle">Total preditiva</p>
            <p className="font-mono text-lg font-semibold tabular-nums text-fg">{moeda(totais.pred)}</p>
          </div>
          <div>
            <p className="text-xs text-fg-subtle">Total emergencial</p>
            <p className="font-mono text-lg font-semibold tabular-nums text-fg">{moeda(totais.emerg)}</p>
          </div>
          <div>
            <p className="text-xs text-fg-subtle">Retorno do investimento</p>
            <p
              className={`font-mono text-lg font-semibold tabular-nums ${
                totais.retorno >= 0 ? "text-success-fg" : "text-danger-fg"
              }`}
            >
              {moeda(totais.retorno)}
            </p>
          </div>
        </div>
      </Card>

      {/* --- Acompanhamento --- */}
      <Card>
        <Secao
          icon={Wrench}
          titulo="Situação"
          descricao="Status operacional e situação na reavaliação seguinte."
        />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Status">
            <Select value={campos.status} onChange={(e) => set("status", e.target.value)}>
              <option value="ABERTA">Aberta</option>
              <option value="PLANEJADA">Planejada</option>
              <option value="EXECUTADA">Executada</option>
              <option value="FINALIZADA">Finalizada</option>
              <option value="CANCELADA">Cancelada</option>
            </Select>
          </Field>
          <Field label="Acompanhamento">
            <Select
              value={campos.acompanhamento}
              onChange={(e) => set("acompanhamento", e.target.value)}
            >
              <option value="ABERTA">Aberta</option>
              <option value="CORRIGIDA">Corrigida</option>
              <option value="REINCIDENTE">Reincidente</option>
              <option value="NAO_REAVALIADA">Não reavaliada</option>
              <option value="RETORNO_INFO">Retorno de informação</option>
            </Select>
          </Field>
          <Field label="Descrição da corretiva executada" className="sm:col-span-2">
            <Textarea
              rows={2}
              value={campos.descricao_corretiva}
              onChange={(e) => set("descricao_corretiva", e.target.value)}
            />
          </Field>
        </div>
      </Card>

      {msg && (
        <Card>
          <p className="text-sm text-danger-fg">{msg}</p>
        </Card>
      )}
      <div className="flex flex-wrap items-center justify-end gap-3 pb-2">
        <span className="mr-auto text-xs text-fg-subtle">* campos obrigatórios</span>
        <Button variant="secondary" onClick={() => router.push("/osps")}>
          Cancelar
        </Button>
        <Button onClick={salvar} loading={salvando} disabled={!podeSalvar} icon={Save}>
          {editando ? "Salvar alterações" : "Criar ordem de serviço"}
        </Button>
      </div>
    </div>
  );
}
