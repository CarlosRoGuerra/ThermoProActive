"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Building2, Loader2, MapPin, Phone, Save } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { Cliente } from "@/lib/types";
import { Button, Card, Field, Input, Spinner } from "@/components/ui";

const UFS = [
  "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG",
  "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
];

type Form = {
  nome: string;
  nome_fantasia: string;
  cnpj: string;
  unidade_negocio: string;
  cep: string;
  logradouro: string;
  numero: string;
  complemento: string;
  bairro: string;
  cidade: string;
  uf: string;
  contato_gestor: string;
  departamento: string;
  email: string;
  telefone: string;
};

const FORM_VAZIO: Form = {
  nome: "", nome_fantasia: "", cnpj: "", unidade_negocio: "",
  cep: "", logradouro: "", numero: "", complemento: "", bairro: "", cidade: "", uf: "",
  contato_gestor: "", departamento: "", email: "", telefone: "",
};

/** 00000000 → 00000-000 */
function formatarCep(valor: string) {
  const d = valor.replace(/\D/g, "").slice(0, 8);
  return d.length > 5 ? `${d.slice(0, 5)}-${d.slice(5)}` : d;
}

/** 00000000000000 → 00.000.000/0000-00 */
function formatarCnpj(valor: string) {
  const d = valor.replace(/\D/g, "").slice(0, 14);
  return d
    .replace(/^(\d{2})(\d)/, "$1.$2")
    .replace(/^(\d{2})\.(\d{3})(\d)/, "$1.$2.$3")
    .replace(/\.(\d{3})(\d)/, ".$1/$2")
    .replace(/(\d{4})(\d)/, "$1-$2");
}

/** (00) 00000-0000 */
function formatarTelefone(valor: string) {
  const d = valor.replace(/\D/g, "").slice(0, 11);
  if (d.length <= 2) return d;
  if (d.length <= 6) return `(${d.slice(0, 2)}) ${d.slice(2)}`;
  if (d.length <= 10) return `(${d.slice(0, 2)}) ${d.slice(2, 6)}-${d.slice(6)}`;
  return `(${d.slice(0, 2)}) ${d.slice(2, 7)}-${d.slice(7)}`;
}

/** Cabeçalho de seção do formulário. */
function Secao({
  icon: Icon,
  titulo,
  descricao,
}: {
  icon: typeof Building2;
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

export function ClienteForm({ clienteId }: { clienteId?: number }) {
  const router = useRouter();
  const editando = clienteId !== undefined;

  const [form, setForm] = useState<Form>(FORM_VAZIO);
  const [carregando, setCarregando] = useState(editando);
  const [salvando, setSalvando] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [buscandoCep, setBuscandoCep] = useState(false);
  const [cepMsg, setCepMsg] = useState<string | null>(null);

  const set = useCallback(
    (campo: keyof Form, valor: string) => setForm((f) => ({ ...f, [campo]: valor })),
    []
  );

  useEffect(() => {
    if (!editando) return;
    api<Cliente>(`/clientes/${clienteId}/`)
      .then((c) =>
        setForm({
          nome: c.nome ?? "",
          nome_fantasia: c.nome_fantasia ?? "",
          cnpj: c.cnpj ?? "",
          unidade_negocio: c.unidade_negocio ?? "",
          cep: c.cep ?? "",
          logradouro: c.logradouro ?? "",
          numero: c.numero ?? "",
          complemento: c.complemento ?? "",
          bairro: c.bairro ?? "",
          cidade: c.cidade ?? "",
          uf: c.uf ?? "",
          contato_gestor: c.contato_gestor ?? "",
          departamento: c.departamento ?? "",
          email: c.email ?? "",
          telefone: c.telefone ?? "",
        })
      )
      .catch(() => setMsg("Não foi possível carregar este cliente."))
      .finally(() => setCarregando(false));
  }, [clienteId, editando]);

  /** Consulta o ViaCEP e preenche o endereço automaticamente. */
  async function buscarCep(cepBruto: string) {
    const cep = cepBruto.replace(/\D/g, "");
    if (cep.length !== 8) return;
    setBuscandoCep(true);
    setCepMsg(null);
    try {
      const res = await fetch(`https://viacep.com.br/ws/${cep}/json/`);
      const data = await res.json();
      if (data.erro) {
        setCepMsg("CEP não encontrado — preencha o endereço manualmente.");
        return;
      }
      setForm((f) => ({
        ...f,
        logradouro: data.logradouro || f.logradouro,
        bairro: data.bairro || f.bairro,
        cidade: data.localidade || f.cidade,
        uf: data.uf || f.uf,
        complemento: data.complemento || f.complemento,
      }));
      setCepMsg("Endereço preenchido pelo CEP.");
    } catch {
      setCepMsg("Não foi possível consultar o CEP agora — preencha manualmente.");
    } finally {
      setBuscandoCep(false);
    }
  }

  async function salvar() {
    setSalvando(true);
    setMsg(null);
    try {
      if (editando) {
        await api(`/clientes/${clienteId}/`, { method: "PATCH", body: form });
      } else {
        await api("/clientes/", { method: "POST", body: form });
      }
      router.push("/clientes");
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "Erro ao salvar o cliente.");
      setSalvando(false);
    }
  }

  const podeSalvar = form.nome.trim() !== "" && form.cnpj.trim() !== "";

  if (carregando) {
    return (
      <Card>
        <Spinner label="Carregando cliente…" />
      </Card>
    );
  }

  return (
    <div className="space-y-5">
      {/* Cabeçalho da página */}
      <div>
        <Link
          href="/clientes"
          className="inline-flex items-center gap-1.5 text-xs font-medium text-fg-muted transition-colors hover:text-fg"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Voltar para clientes
        </Link>
        <h1 className="mt-2 text-xl font-semibold tracking-tight text-fg">
          {editando ? "Editar cliente" : "Novo cliente"}
        </h1>
        <p className="mt-0.5 text-sm text-fg-muted">
          Tomador de serviço — topo da hierarquia Cliente → Área → Setor → Equipamento.
        </p>
      </div>

      {/* --- Identificação --- */}
      <Card>
        <Secao
          icon={Building2}
          titulo="Identificação"
          descricao="Dados cadastrais da empresa contratante."
        />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Field label="Razão social *" className="lg:col-span-2">
            <Input
              value={form.nome}
              maxLength={160}
              placeholder="Ex.: Indústria Exemplo S.A."
              onChange={(e) => set("nome", e.target.value)}
            />
          </Field>
          <Field label="CNPJ *">
            <Input
              value={form.cnpj}
              inputMode="numeric"
              placeholder="00.000.000/0000-00"
              onChange={(e) => set("cnpj", formatarCnpj(e.target.value))}
            />
          </Field>
          <Field label="Nome fantasia">
            <Input
              value={form.nome_fantasia}
              maxLength={160}
              onChange={(e) => set("nome_fantasia", e.target.value)}
            />
          </Field>
          <Field label="Unidade de negócio" className="lg:col-span-2">
            <Input
              value={form.unidade_negocio}
              maxLength={120}
              placeholder="Ex.: Planta Campinas"
              onChange={(e) => set("unidade_negocio", e.target.value)}
            />
          </Field>
        </div>
      </Card>

      {/* --- Endereço --- */}
      <Card>
        <Secao
          icon={MapPin}
          titulo="Endereço"
          descricao="Digite o CEP que o restante é preenchido automaticamente."
        />
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4 lg:grid-cols-6">
          <Field label="CEP" className="col-span-2 sm:col-span-1">
            <div className="relative">
              <Input
                value={form.cep}
                inputMode="numeric"
                placeholder="00000-000"
                onChange={(e) => {
                  const v = formatarCep(e.target.value);
                  set("cep", v);
                  if (v.replace(/\D/g, "").length === 8) buscarCep(v);
                }}
                onBlur={(e) => buscarCep(e.target.value)}
              />
              {buscandoCep && (
                <Loader2 className="absolute right-2.5 top-1/2 h-4 w-4 -translate-y-1/2 animate-spin text-accent" />
              )}
            </div>
          </Field>
          <Field label="Logradouro" className="col-span-2 sm:col-span-3 lg:col-span-4">
            <Input
              value={form.logradouro}
              maxLength={200}
              onChange={(e) => set("logradouro", e.target.value)}
            />
          </Field>
          <Field label="Número" className="col-span-2 sm:col-span-1">
            <Input value={form.numero} maxLength={20} onChange={(e) => set("numero", e.target.value)} />
          </Field>
          <Field label="Complemento" className="col-span-2 sm:col-span-2">
            <Input
              value={form.complemento}
              maxLength={100}
              placeholder="Bloco, sala…"
              onChange={(e) => set("complemento", e.target.value)}
            />
          </Field>
          <Field label="Bairro" className="col-span-2 sm:col-span-2">
            <Input value={form.bairro} maxLength={100} onChange={(e) => set("bairro", e.target.value)} />
          </Field>
          <Field label="Cidade" className="col-span-2 sm:col-span-3 lg:col-span-1">
            <Input value={form.cidade} maxLength={100} onChange={(e) => set("cidade", e.target.value)} />
          </Field>
          <Field label="UF" className="col-span-2 sm:col-span-1">
            <select
              value={form.uf}
              onChange={(e) => set("uf", e.target.value)}
              className="input cursor-pointer"
            >
              <option value="">—</option>
              {UFS.map((uf) => (
                <option key={uf} value={uf}>
                  {uf}
                </option>
              ))}
            </select>
          </Field>
        </div>
        {cepMsg && <p className="mt-3 text-xs text-fg-muted">{cepMsg}</p>}
      </Card>

      {/* --- Contato --- */}
      <Card>
        <Secao
          icon={Phone}
          titulo="Contato"
          descricao="Responsável pelo acompanhamento dos serviços."
        />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Field label="Contato gestor">
            <Input
              value={form.contato_gestor}
              maxLength={120}
              onChange={(e) => set("contato_gestor", e.target.value)}
            />
          </Field>
          <Field label="Departamento">
            <Input
              value={form.departamento}
              maxLength={120}
              placeholder="Ex.: PCM"
              onChange={(e) => set("departamento", e.target.value)}
            />
          </Field>
          <Field label="E-mail">
            <Input type="email" value={form.email} onChange={(e) => set("email", e.target.value)} />
          </Field>
          <Field label="Telefone">
            <Input
              value={form.telefone}
              inputMode="numeric"
              placeholder="(00) 00000-0000"
              onChange={(e) => set("telefone", formatarTelefone(e.target.value))}
            />
          </Field>
        </div>
      </Card>

      {/* --- Ações --- */}
      {msg && (
        <Card>
          <p className="text-sm text-danger-fg">{msg}</p>
        </Card>
      )}
      <div className="flex flex-wrap items-center justify-end gap-3 pb-2">
        <span className="mr-auto text-xs text-fg-subtle">* campos obrigatórios</span>
        <Button variant="secondary" onClick={() => router.push("/clientes")}>
          Cancelar
        </Button>
        <Button onClick={salvar} loading={salvando} disabled={!podeSalvar} icon={Save}>
          {editando ? "Salvar alterações" : "Cadastrar cliente"}
        </Button>
      </div>
    </div>
  );
}
