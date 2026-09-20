"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Building2, Factory, Loader2, MapPin, Phone, Save } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { Empresa } from "@/lib/types";
import {
  Alert,
  Button,
  Card,
  Field,
  FormActions,
  Input,
  LoadingState,
  PageBody,
  PageHeader,
} from "@/components/ds";
import { LogoUpload } from "@/components/logo-upload";

const UFS = [
  "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG",
  "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
];

type Form = {
  nome: string;
  cnpj: string;
  inscricao_estadual: string;
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
  site: string;
};

const FORM_VAZIO: Form = {
  nome: "", cnpj: "", inscricao_estadual: "",
  cep: "", logradouro: "", numero: "", complemento: "", bairro: "", cidade: "", uf: "",
  contato_gestor: "", departamento: "", email: "", telefone: "", site: "",
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

export function PrestadorForm({ prestadorId }: { prestadorId?: number }) {
  const router = useRouter();
  const editando = prestadorId !== undefined;

  const [form, setForm] = useState<Form>(FORM_VAZIO);
  const [logoAtual, setLogoAtual] = useState<string | null>(null);
  const [logoFile, setLogoFile] = useState<File | null>(null);
  const [logoAlterada, setLogoAlterada] = useState(false);
  const [carregando, setCarregando] = useState(editando);
  const [salvando, setSalvando] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [buscandoCep, setBuscandoCep] = useState(false);
  const [cepMsg, setCepMsg] = useState<string | null>(null);

  const set = useCallback(
    (campo: keyof Form, valor: string) => setForm((f) => ({ ...f, [campo]: valor })),
    []
  );

  function aoEscolherLogo(arquivo: File | null) {
    setLogoFile(arquivo);
    setLogoAlterada(true);
  }

  useEffect(() => {
    if (!editando) return;
    api<Empresa>(`/empresas/${prestadorId}/`)
      .then((c) => {
        setForm({
          nome: c.nome ?? "",
          cnpj: c.cnpj ?? "",
          inscricao_estadual: c.inscricao_estadual ?? "",
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
          site: c.site ?? "",
        });
        setLogoAtual(c.logomarca ?? null);
      })
      .catch(() => setMsg("Não foi possível carregar este prestador."))
      .finally(() => setCarregando(false));
  }, [prestadorId, editando]);

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
      let body: FormData | Form = form;
      if (logoAlterada) {
        const fd = new FormData();
        Object.entries(form).forEach(([k, v]) => fd.append(k, v));
        fd.append("logomarca", logoFile ?? "");
        body = fd;
      }
      if (editando) {
        await api(`/empresas/${prestadorId}/`, { method: "PATCH", body });
      } else {
        await api("/empresas/", { method: "POST", body });
      }
      router.push("/prestadores");
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "Erro ao salvar o prestador.");
      setSalvando(false);
    }
  }

  const podeSalvar = form.nome.trim() !== "" && form.cnpj.trim() !== "";

  if (carregando) {
    return (
      <LoadingState variante="formulario" linhas={4} label="Carregando o prestador…" />
    );
  }

  return (
    <PageBody>
      <PageHeader
        icon={Factory}
        title={editando ? "Editar prestador" : "Novo prestador"}
        description={"Empresa contratada que executa o serviço. Estes dados saem no cabeçalho e no rodapé dos relatórios técnicos."}
        trilha={[{ label: "Prestadores", href: "/prestadores" }, { label: editando ? "Editar" : "Novo" }]}
      />

      {/* --- Identificação --- */}
      <Card>
        <Secao
          icon={Building2}
          titulo="Identificação"
          descricao="Dados cadastrais da empresa prestadora."
        />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Field label="Razão social" obrigatorio className="lg:col-span-2">
            <Input
              value={form.nome}
              maxLength={160}
              placeholder="Ex.: Thermoproactive Serviços Ltda"
              onChange={(e) => set("nome", e.target.value)}
            />
          </Field>
          <Field label="CNPJ" obrigatorio>
            <Input
              value={form.cnpj}
              inputMode="numeric"
              placeholder="00.000.000/0000-00"
              onChange={(e) => set("cnpj", formatarCnpj(e.target.value))}
            />
          </Field>
          <Field label="Inscrição estadual">
            <Input
              value={form.inscricao_estadual}
              maxLength={30}
              placeholder="Ex.: Isenta"
              onChange={(e) => set("inscricao_estadual", e.target.value)}
            />
          </Field>
        </div>
        <div className="mt-4 border-t border-border pt-4">
          <LogoUpload
            urlAtual={logoAtual}
            onArquivo={aoEscolherLogo}
            ajuda="Logomarca HORIZONTAL, PNG com fundo transparente, recortada rente (ex.: ~2000px de largura). Aparece no cabeçalho e nas capas dos relatórios."
          />
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
                <Loader2 className="absolute right-2.5 top-1/2 h-4 w-4 -translate-y-1/2 animate-spin text-primary" />
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
          descricao="Contato para o cabeçalho dos relatórios."
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
          <Field label="Telefone">
            <Input value={form.telefone} maxLength={40} onChange={(e) => set("telefone", e.target.value)} />
          </Field>
          <Field label="E-mail">
            <Input type="email" value={form.email} onChange={(e) => set("email", e.target.value)} />
          </Field>
          <Field label="Site (rodapé do relatório)">
            <Input
              value={form.site}
              maxLength={120}
              placeholder="Ex.: thermoproactive.com.br"
              onChange={(e) => set("site", e.target.value)}
            />
          </Field>
        </div>
      </Card>

      {/* --- Ações --- */}
      {msg && (
        <Alert tone="danger" title="Não foi possível salvar" onClose={() => setMsg(null)}>
          {msg}
        </Alert>
      )}
      <FormActions alinhamento="entre">
        <span className="hidden text-xs text-fg-subtle sm:inline">
          Campos marcados com * são obrigatórios.
        </span>
        <span className="flex flex-1 items-center justify-end gap-2 sm:flex-none">
        <Button variant="secondary" onClick={() => router.push("/prestadores")}>
          Cancelar
        </Button>
        <Button onClick={salvar} loading={salvando} disabled={!podeSalvar} icon={Save}>
          {editando ? "Salvar alterações" : "Cadastrar prestador"}
        </Button>
      </span>
      </FormActions>
    </PageBody>
  );
}
