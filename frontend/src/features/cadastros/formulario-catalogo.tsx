"use client";

import { useEffect, useMemo, useState } from "react";
import { Pencil, Plus } from "lucide-react";
import {
  Alert,
  Button,
  Field,
  FormGrid,
  Input,
  Modal,
  Select,
  Switch,
  Textarea,
  useToast,
} from "@/components/ds";
import { MultiSelect } from "@/components/multiselect";
import { api } from "@/lib/api";
import { useMutacao } from "@/lib/recurso";
import { useClienteAtivo } from "@/lib/cliente-ativo";
import type { CatalogDef, FieldDef } from "./catalogos";

/* ==========================================================================
   Formulário dinâmico de catálogo.
   --------------------------------------------------------------------------
   Monta os campos a partir da definição do catálogo (ver catalogos.ts) e cuida
   das particularidades do backend num lugar só:
     • edição envia campo vazio (permite limpar), criação omite;
     • `escolha` com `valorNumerico` vira número; sem ele, fica string;
     • imagem nova vai como multipart; sem arquivo novo, mantém a existente;
     • data vazia na edição é enviada como null, para conseguir apagar.

   Fica em modal porque a lista é o assunto principal da tela. Antes o
   formulário ficava acima da tabela e empurrava a lista para fora da vista a
   cada edição.
   ========================================================================== */

export type Registro = Record<string, unknown> & { id: number };
type Valor = string | number[] | File;
export type Opcao = { id: number; nome: string; sigla?: string; identificacao?: string };

function valorInicial(campo: FieldDef): Valor {
  if (campo.type === "color") return "#64748b";
  if (campo.type === "multiref") return [];
  if (campo.type === "boolean") return "false";
  return "";
}

export function FormularioCatalogo({
  aberto,
  catalogo,
  registro,
  opcoes,
  onFechar,
  onSalvo,
}: {
  aberto: boolean;
  catalogo: CatalogDef;
  /** `null` = novo registro. */
  registro: Registro | null;
  /** Opções dos campos relacionais, por endpoint. */
  opcoes: Record<string, Opcao[]>;
  onFechar: () => void;
  onSalvo: () => void;
}) {
  const toast = useToast();
  const { clienteAtivo } = useClienteAtivo();
  const mutacao = useMutacao(`cadastro de ${catalogo.label.toLowerCase()}`);

  const vazio = useMemo(
    () => Object.fromEntries(catalogo.fields.map((f) => [f.key, valorInicial(f)])) as Record<string, Valor>,
    [catalogo]
  );
  const [form, setForm] = useState<Record<string, Valor>>(vazio);

  useEffect(() => {
    if (!aberto) return;
    if (!registro) {
      setForm(vazio);
      return;
    }
    const preenchido: Record<string, Valor> = {};
    for (const f of catalogo.fields) {
      const v = registro[f.key];
      if (f.type === "multiref") preenchido[f.key] = Array.isArray(v) ? (v as number[]) : [];
      else if (f.type === "color") preenchido[f.key] = String(v ?? "#64748b");
      else if (f.type === "boolean") preenchido[f.key] = v ? "true" : "false";
      else preenchido[f.key] = v == null ? "" : String(v);
    }
    setForm(preenchido);
  }, [aberto, registro, catalogo, vazio]);

  const editando = !!registro;

  const completo = catalogo.fields
    .filter((f) => f.required)
    .every((f) => {
      const v = form[f.key];
      return typeof v === "string" ? v.trim() !== "" : Array.isArray(v) ? v.length > 0 : v != null;
    });

  function definir(chave: string, valor: Valor) {
    setForm((f) => ({ ...f, [chave]: valor }));
  }

  async function salvar() {
    const corpo: Record<string, unknown> = {};
    const arquivos: [string, File][] = [];

    for (const f of catalogo.fields) {
      const v = form[f.key];
      if (f.type === "image") {
        // Só envia se houver arquivo novo; string = URL atual, que se mantém.
        if (v instanceof File) arquivos.push([f.key, v]);
      } else if (f.type === "multiref") {
        corpo[f.key] = Array.isArray(v) ? v : [];
      } else if (f.type === "boolean") {
        corpo[f.key] = v === "true";
      } else if (f.type === "ref" || (f.type === "escolha" && f.valorNumerico)) {
        if (v !== "" && v !== undefined) corpo[f.key] = Number(v);
      } else if (f.type === "escolha") {
        if (editando || (v !== "" && v !== undefined)) corpo[f.key] = v ?? "";
      } else if (f.type === "number") {
        if (v !== "" && v !== undefined) corpo[f.key] = Number(v);
      } else if (f.type === "date") {
        if (v !== "" && v !== undefined) corpo[f.key] = v;
        else if (editando) corpo[f.key] = null; // permite limpar a data
      } else if (editando || (v !== "" && v !== undefined)) {
        corpo[f.key] = v ?? "";
      }
    }

    // Área pertence ao cliente em atendimento: o vínculo entra na criação.
    if (catalogo.escopoCliente?.injeta && clienteAtivo && !editando) {
      corpo.cliente = clienteAtivo.id;
    }

    let carga: unknown = corpo;
    if (arquivos.length > 0) {
      const fd = new FormData();
      for (const [k, val] of Object.entries(corpo)) {
        if (Array.isArray(val)) val.forEach((x) => fd.append(k, String(x)));
        else fd.append(k, val == null ? "" : String(val));
      }
      for (const [k, arquivo] of arquivos) fd.append(k, arquivo);
      carga = fd;
    }

    const r = await mutacao.executar(() =>
      editando
        ? api(`/${catalogo.endpoint}/${registro!.id}/`, { method: "PATCH", body: carga })
        : api(`/${catalogo.endpoint}/`, { method: "POST", body: carga })
    );

    if (r.ok) {
      toast.sucesso(editando ? "Registro atualizado" : "Registro adicionado");
      onSalvo();
    } else {
      toast.erro(r.falha.titulo, { descricao: r.falha.descricao });
    }
  }

  return (
    <Modal
      aberto={aberto}
      onFechar={onFechar}
      travarFundo
      tamanho="lg"
      title={`${editando ? "Editar" : "Novo"} · ${catalogo.label}`}
      description={
        catalogo.escopoCliente
          ? "Este registro pertence ao cliente em atendimento."
          : "Tabela de referência: o que você cadastrar aqui aparece como opção nos formulários do sistema."
      }
      footer={
        <>
          <Button variant="secondary" size="sm" onClick={onFechar} disabled={mutacao.enviando}>
            Cancelar
          </Button>
          <Button
            size="sm"
            onClick={salvar}
            loading={mutacao.enviando}
            disabled={!completo}
            icon={editando ? Pencil : Plus}
          >
            {editando ? "Salvar alterações" : "Adicionar"}
          </Button>
        </>
      }
    >
      {mutacao.falha?.tipo === "validacao" && (
        <div className="mb-4">
          <Alert tone="danger" title="Confira os dados informados">
            {mutacao.falha.descricao}
          </Alert>
        </div>
      )}

      <FormGrid colunas={2}>
        {catalogo.fields.map((f, i) => {
          const largo = f.type === "textarea" || f.type === "image" || f.type === "multiref";
          return (
            <Field
              key={f.key}
              label={f.label}
              obrigatorio={f.required}
              className={largo ? "sm:col-span-2" : undefined}
              hint={
                f.maxLength && (f.type === undefined || f.type === "text")
                  ? `Até ${f.maxLength} caracteres.`
                  : undefined
              }
            >
              {f.type === "color" ? (
                <div className="flex items-center gap-2.5">
                  <input
                    type="color"
                    value={(form[f.key] as string) ?? "#64748b"}
                    onChange={(e) => definir(f.key, e.target.value)}
                    aria-label={f.label}
                    className="h-10 w-16 cursor-pointer rounded-lg border border-border bg-surface p-1"
                  />
                  <span className="data text-xs text-fg-muted">{String(form[f.key] ?? "")}</span>
                </div>
              ) : f.type === "multiref" ? (
                <MultiSelect
                  value={Array.isArray(form[f.key]) ? (form[f.key] as number[]) : []}
                  onChange={(ids) => definir(f.key, ids)}
                  options={(opcoes[f.optionsEndpoint ?? ""] ?? []).map((o) => ({
                    id: o.id,
                    label: o.nome,
                    hint: o.sigla || undefined,
                  }))}
                  placeholder="Selecione…"
                  emptyText="Nenhuma opção cadastrada ainda."
                />
              ) : f.type === "escolha" ? (
                <Select
                  value={(form[f.key] as string) ?? ""}
                  onChange={(e) => definir(f.key, e.target.value)}
                >
                  <option value="">Não se aplica</option>
                  {(f.escolhas ?? []).map((o) => (
                    <option key={o.valor} value={o.valor}>
                      {o.texto}
                    </option>
                  ))}
                </Select>
              ) : f.type === "boolean" ? (
                <Switch
                  checked={form[f.key] === "true"}
                  onChange={(v) => definir(f.key, v ? "true" : "false")}
                  label={form[f.key] === "true" ? "Sim" : "Não"}
                />
              ) : f.type === "image" ? (
                <div className="flex items-center gap-3">
                  {form[f.key] instanceof File ? (
                    <span className="max-w-32 truncate text-xs text-fg-muted">
                      {(form[f.key] as File).name}
                    </span>
                  ) : typeof form[f.key] === "string" && form[f.key] ? (
                    // eslint-disable-next-line @next/next/no-img-element -- imagem vinda da API
                    <img
                      src={form[f.key] as string}
                      alt=""
                      className="h-10 w-10 rounded object-contain ring-1 ring-border"
                    />
                  ) : null}
                  <input
                    type="file"
                    accept="image/*"
                    aria-label={f.label}
                    onChange={(e) => definir(f.key, e.target.files?.[0] ?? "")}
                    className="text-xs text-fg-muted file:mr-2 file:rounded-md file:border-0 file:bg-surface-muted file:px-2 file:py-1 file:text-xs file:text-fg"
                  />
                </div>
              ) : f.type === "ref" ? (
                <Select
                  value={(form[f.key] as string) ?? ""}
                  onChange={(e) => definir(f.key, e.target.value)}
                >
                  <option value="">Selecione…</option>
                  {(opcoes[f.optionsEndpoint ?? ""] ?? []).map((o) => (
                    <option key={o.id} value={o.id}>
                      {o.identificacao || o.nome}
                    </option>
                  ))}
                </Select>
              ) : f.type === "textarea" ? (
                <Textarea
                  rows={4}
                  value={(form[f.key] as string) ?? ""}
                  onChange={(e) => definir(f.key, e.target.value)}
                />
              ) : (
                <Input
                  type={f.type === "number" ? "number" : f.type === "date" ? "date" : "text"}
                  value={(form[f.key] as string) ?? ""}
                  maxLength={f.maxLength}
                  tecnico={f.type === "number"}
                  onChange={(e) => definir(f.key, e.target.value)}
                  {...(i === 0 ? { "data-autofocus": true } : {})}
                />
              )}
            </Field>
          );
        })}
      </FormGrid>
    </Modal>
  );
}
