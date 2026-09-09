"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Gauge } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useClienteAtivo } from "@/lib/cliente-ativo";
import { useClientes } from "@/lib/hierarquia";
import type { Equipamento, Paginated, ServicoCampo, TipoServico } from "@/lib/types";
import { Button, Card, Field, Input, PageHeader, Select, Textarea } from "@/components/ui";
import { Combobox } from "@/components/combobox";

const hoje = () => new Date().toISOString().slice(0, 10);

export default function NovoServicoPage() {
  const router = useRouter();
  const params = useSearchParams();
  const { user } = useAuth();
  const { opcoes: opcoesClientes } = useClientes();
  const { clienteAtivo } = useClienteAtivo();

  const [cliente, setCliente] = useState<number | "">(clienteAtivo?.id ?? "");
  const [equipamentos, setEquipamentos] = useState<Equipamento[]>([]);
  const [instrumentos, setInstrumentos] = useState<{ id: number; identificacao?: string; tipo: string }[]>([]);
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  const [form, setForm] = useState({
    equipamento: "" as number | "",
    tipo: "BALANCEAMENTO" as TipoServico,
    data_execucao: hoje(),
    rotacao_hz: "",
    instrumento: "" as number | "",
    custo_servico: "",
    observacoes: "",
  });

  // Vindo do botão "Executar serviço" da OSP: o contexto (qual OSP, qual análise)
  // chega pela URL. Nenhuma medição vem preenchida — só a identificação.
  const ospOrigem = params.get("osp");
  const achadoOrigem = params.get("achado");

  useEffect(() => {
    if (clienteAtivo) setCliente(clienteAtivo.id);
  }, [clienteAtivo]);

  useEffect(() => {
    if (!cliente) return setEquipamentos([]);
    api<Paginated<Equipamento>>(`/equipamentos/?setor__area__cliente=${cliente}&page_size=1000`)
      .then((d) => setEquipamentos(d.results))
      .catch(() => setEquipamentos([]));
  }, [cliente]);

  useEffect(() => {
    api<Paginated<{ id: number; tipo: string; identificacao?: string }>>("/instrumentos/?page_size=200")
      .then((d) => setInstrumentos(d.results))
      .catch(() => setInstrumentos([]));
  }, []);

  async function salvar() {
    if (!cliente || !form.equipamento) {
      return setErro("Escolha o cliente e o equipamento.");
    }
    setSalvando(true);
    setErro(null);
    try {
      const criado = await api<ServicoCampo>("/servicos/", {
        method: "POST",
        body: {
          cliente,
          equipamento: form.equipamento,
          tipo: form.tipo,
          data_execucao: form.data_execucao,
          rotacao_hz: form.rotacao_hz || null,
          instrumento: form.instrumento || null,
          custo_servico: form.custo_servico || null,
          observacoes: form.observacoes,
          analista: user?.id,
          osp: ospOrigem ? Number(ospOrigem) : null,
          achado: achadoOrigem ? Number(achadoOrigem) : null,
        },
      });
      router.push(`/servicos/${criado.id}`);
    } catch (e) {
      setErro(e instanceof ApiError ? JSON.stringify(e.data) : "Falha ao salvar.");
      setSalvando(false);
    }
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title="Novo serviço de campo"
        description="Identificação da intervenção. As medições são lançadas na folha, no equipamento."
        icon={Gauge}
      />

      <Card className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Cliente">
            <Combobox value={cliente} onChange={setCliente} options={opcoesClientes} />
          </Field>
          <Field label="Equipamento">
            <Combobox
              value={form.equipamento}
              onChange={(v) => setForm({ ...form, equipamento: v })}
              options={equipamentos.map((e) => ({ id: e.id, label: e.tag, hint: e.nome }))}
              disabled={!cliente}
              placeholder={cliente ? "Selecione…" : "Escolha o cliente primeiro"}
            />
          </Field>
          <Field label="Tipo de serviço">
            <Select
              value={form.tipo}
              onChange={(e) => setForm({ ...form, tipo: e.target.value as TipoServico })}
            >
              <option value="BALANCEAMENTO">Balanceamento dinâmico em campo</option>
              <option value="ALINHAMENTO">Alinhamento a laser</option>
            </Select>
          </Field>
          <Field label="Data de execução">
            <Input
              type="date"
              value={form.data_execucao}
              onChange={(e) => setForm({ ...form, data_execucao: e.target.value })}
            />
          </Field>
          <Field label="Rotação (Hz)">
            <Input
              type="number"
              step="0.01"
              inputMode="decimal"
              placeholder="29,74"
              value={form.rotacao_hz}
              onChange={(e) => setForm({ ...form, rotacao_hz: e.target.value })}
            />
            <p className="mt-1 text-xs text-fg-subtle">
              {form.rotacao_hz
                ? `= ${Math.round(Number(form.rotacao_hz) * 60)} RPM`
                : "A RPM é calculada a partir da frequência."}
            </p>
          </Field>
          <Field label="Instrumento">
            <Combobox
              value={form.instrumento}
              onChange={(v) => setForm({ ...form, instrumento: v })}
              options={instrumentos.map((i) => ({ id: i.id, label: i.identificacao || i.tipo }))}
              placeholder="Opcional"
            />
          </Field>
          <Field label="Custo do serviço (R$)">
            <Input
              type="number"
              step="0.01"
              inputMode="decimal"
              placeholder="1606,00"
              value={form.custo_servico}
              onChange={(e) => setForm({ ...form, custo_servico: e.target.value })}
            />
            <p className="mt-1 text-xs text-fg-subtle">Usado no payback. Informado a cada serviço.</p>
          </Field>
        </div>

        <Field label="Observações">
          <Textarea
            rows={3}
            value={form.observacoes}
            onChange={(e) => setForm({ ...form, observacoes: e.target.value })}
          />
        </Field>

        {erro && <p className="text-sm text-[var(--danger)]">{erro}</p>}

        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={() => router.back()}>
            Cancelar
          </Button>
          <Button onClick={salvar} disabled={salvando}>
            {salvando ? "Salvando…" : "Criar e abrir a folha"}
          </Button>
        </div>
      </Card>
    </div>
  );
}
