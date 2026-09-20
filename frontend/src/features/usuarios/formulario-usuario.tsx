"use client";

import { useEffect, useState } from "react";
import { Info, MailPlus } from "lucide-react";
import {
  Alert,
  Button,
  Field,
  FormGrid,
  FormSection,
  Input,
  Modal,
  RadioGroup,
  Select,
  Switch,
  useToast,
} from "@/components/ds";
import { Combobox } from "@/components/combobox";
import { api } from "@/lib/api";
import { useMutacao } from "@/lib/recurso";
import { useClientes } from "@/lib/hierarquia";
import {
  NIVEL_LABEL,
  NIVEL_RESUMO,
  PERFIL_LABEL,
  PERFIS_CLIENTE,
  PERFIS_INTERNOS,
} from "@/lib/permissions";
import type { Nivel, Perfil, User } from "@/lib/types";

/**
 * Cadastro e edição de usuário (nível Master).
 *
 * Em modal, não em página: conceder acesso é uma tarefa curta e o Master
 * costuma fazer várias seguidas — tirar ele da lista a cada vez atrapalha.
 *
 * A escolha de perfil vem antes de tudo porque ela muda o resto do formulário:
 * usuário de cliente precisa de empresa vinculada e não tem conselho de classe;
 * usuário interno é o contrário. Mostrar os dois conjuntos ao mesmo tempo é o
 * que produzia formulário gigante com metade dos campos irrelevantes.
 */

type Formulario = {
  nome: string;
  email: string;
  perfil: Perfil;
  nivel: Nivel;
  cargo: string;
  celular: string;
  cpf: string;
  conselho_classe: string;
  cliente: number | "";
  is_active: boolean;
  password: string;
};

const VAZIO: Formulario = {
  nome: "",
  email: "",
  perfil: "TECNICO",
  nivel: "PLENO",
  cargo: "",
  celular: "",
  cpf: "",
  conselho_classe: "",
  cliente: "",
  is_active: true,
  password: "",
};

const NIVEIS: Nivel[] = ["MASTER", "SENIOR", "PLENO", "JUNIOR"];

export function FormularioUsuario({
  aberto,
  usuario,
  onFechar,
  onSalvo,
}: {
  aberto: boolean;
  /** `null` = novo usuário. */
  usuario: User | null;
  onFechar: () => void;
  onSalvo: () => void;
}) {
  const toast = useToast();
  const mutacao = useMutacao("cadastro de usuário");
  const { opcoes: opcoesClientes } = useClientes(aberto);
  const [form, setForm] = useState<Formulario>(VAZIO);
  const [erros, setErros] = useState<Partial<Record<keyof Formulario, string>>>({});

  // Reabrir o modal sempre começa do estado certo (novo em branco, edição cheia).
  useEffect(() => {
    if (!aberto) return;
    setErros({});
    setForm(
      usuario
        ? {
            nome: usuario.nome,
            email: usuario.email,
            perfil: usuario.perfil,
            nivel: usuario.nivel,
            cargo: usuario.cargo ?? "",
            celular: "",
            cpf: "",
            conselho_classe: usuario.conselho_classe ?? "",
            cliente: usuario.cliente ?? "",
            is_active: usuario.is_active !== false,
            password: "",
          }
        : VAZIO
    );
  }, [aberto, usuario]);

  const ehCliente = PERFIS_CLIENTE.includes(form.perfil);
  const editando = !!usuario;

  function definir<K extends keyof Formulario>(campo: K, valor: Formulario[K]) {
    setForm((f) => ({ ...f, [campo]: valor }));
    // Corrigir o campo limpa o erro dele — o usuário vê o progresso.
    setErros((e) => (e[campo] ? { ...e, [campo]: undefined } : e));
  }

  function validar(): boolean {
    const novos: Partial<Record<keyof Formulario, string>> = {};
    if (!form.nome.trim()) novos.nome = "Informe o nome completo.";
    if (!form.email.trim()) novos.email = "Informe o e-mail de acesso.";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim()))
      novos.email = "Este e-mail não parece válido.";
    if (ehCliente && !form.cliente)
      novos.cliente = "Usuário de cliente precisa estar vinculado a uma empresa.";
    if (editando && form.password && form.password.length < 15)
      novos.password = "A nova senha precisa ter ao menos 15 caracteres.";
    setErros(novos);
    return Object.keys(novos).length === 0;
  }

  async function salvar() {
    if (!validar()) return;

    const corpo: Record<string, unknown> = {
      nome: form.nome.trim(),
      email: form.email.trim().toLowerCase(),
      perfil: form.perfil,
      nivel: form.nivel,
      cargo: form.cargo.trim(),
      celular: form.celular.trim(),
      cpf: form.cpf.trim(),
      conselho_classe: ehCliente ? "" : form.conselho_classe.trim(),
      cliente: ehCliente ? form.cliente : null,
      is_active: form.is_active,
    };
    const r = await mutacao.executar(() =>
      editando
        ? api(`/usuarios/${usuario!.id}/`, { method: "PATCH", body: corpo })
        : api("/auth/convites/", {
            method: "POST",
            body: {
              nome: form.nome.trim(),
              email: form.email.trim().toLowerCase(),
              tipo: ehCliente ? "portal" : "admin",
              perfil: form.perfil,
              nivel: form.nivel,
              cliente: ehCliente ? form.cliente : null,
              empresa: null,
            },
          })
    );

    if (r.ok) {
      toast.sucesso(editando ? "Acesso atualizado" : "Convite enviado", {
        descricao: editando
          ? `As alterações de ${form.nome} já valem no próximo acesso dele.`
          : `${form.nome} receberá um link pessoal, de uso único, para criar a própria senha.`,
      });
      onSalvo();
      return;
    }

    // Erro de validação do backend: mostra no campo, não num toast genérico.
    const dados = (r.falha.tipo === "validacao" ? r.falha.descricao : "") || "";
    if (/email/i.test(dados)) setErros({ email: "Já existe um usuário com este e-mail." });
    toast.erro(r.falha.titulo, { descricao: r.falha.descricao });
  }

  return (
    <Modal
      aberto={aberto}
      onFechar={onFechar}
      travarFundo
      tamanho="lg"
      title={editando ? "Editar acesso" : "Convidar usuário"}
      description={
        editando
          ? "Alterações de perfil e nível passam a valer no próximo acesso desta pessoa."
          : "Defina quem é a pessoa e qual o alcance do acesso. A senha será criada por ela."
      }
      footer={
        <>
          <Button variant="secondary" size="sm" onClick={onFechar} disabled={mutacao.enviando}>
            Cancelar
          </Button>
          <Button size="sm" onClick={salvar} loading={mutacao.enviando}>
            {editando ? "Salvar alterações" : "Enviar convite"}
          </Button>
        </>
      }
    >
      <div className="space-y-6">
        <FormSection
          title="Onde esta pessoa trabalha"
          description="O perfil decide qual das duas experiências ela vê ao entrar."
        >
          <RadioGroup
            label="Área de acesso"
            orientacao="horizontal"
            value={ehCliente ? "cliente" : "interno"}
            onChange={(v) => definir("perfil", v === "cliente" ? "CLIENTE_PCM" : "TECNICO")}
            options={[
              { valor: "interno", label: "Equipe ThermoProActive", hint: "Painel operacional" },
              { valor: "cliente", label: "Cliente", hint: "Portal de consulta" },
            ]}
          />

          <FormGrid colunas={2} className="mt-4">
            <Field label="Perfil" obrigatorio>
              <Select value={form.perfil} onChange={(e) => definir("perfil", e.target.value as Perfil)}>
                {(ehCliente ? PERFIS_CLIENTE : PERFIS_INTERNOS).map((p) => (
                  <option key={p} value={p}>
                    {PERFIL_LABEL[p]}
                  </option>
                ))}
              </Select>
            </Field>

            <Field label="Nível de acesso" obrigatorio hint={NIVEL_RESUMO[form.nivel]}>
              <Select value={form.nivel} onChange={(e) => definir("nivel", e.target.value as Nivel)}>
                {NIVEIS.map((n) => (
                  <option key={n} value={n}>
                    {NIVEL_LABEL[n]}
                  </option>
                ))}
              </Select>
            </Field>

            {ehCliente && (
              <Field
                label="Empresa vinculada"
                obrigatorio
                erro={erros.cliente}
                hint="Define tudo o que esta pessoa consegue ver no portal."
                className="sm:col-span-2"
              >
                <Combobox
                  value={form.cliente}
                  onChange={(v) => definir("cliente", v)}
                  options={opcoesClientes}
                  placeholder="Buscar cliente…"
                  permiteLimpar={false}
                />
              </Field>
            )}
          </FormGrid>

          {form.nivel === "MASTER" && (
            <div className="mt-4">
              <Alert tone="warning" icon={Info}>
                O nível Master concede e revoga acessos e mantém as tabelas de referência do
                sistema. Reserve-o a quem responde por isso.
              </Alert>
            </div>
          )}
        </FormSection>

        <FormSection title="Identificação">
          <FormGrid colunas={2}>
            <Field label="Nome completo" obrigatorio erro={erros.nome} className="sm:col-span-2">
              <Input
                value={form.nome}
                onChange={(e) => definir("nome", e.target.value)}
                autoComplete="off"
                data-autofocus
              />
            </Field>
            <Field
              label="E-mail de acesso"
              obrigatorio
              erro={erros.email}
              hint="É com este e-mail que a pessoa entra."
            >
              <Input
                type="email"
                value={form.email}
                onChange={(e) => definir("email", e.target.value)}
                autoComplete="off"
              />
            </Field>
            <Field label="Cargo / função">
              <Input value={form.cargo} onChange={(e) => definir("cargo", e.target.value)} />
            </Field>
            <Field label="Celular" hint="Usado nos avisos por WhatsApp.">
              <Input
                value={form.celular}
                onChange={(e) => definir("celular", e.target.value)}
                inputMode="tel"
                placeholder="(00) 00000-0000"
              />
            </Field>
            {!ehCliente && (
              <>
                <Field label="CPF">
                  <Input
                    value={form.cpf}
                    onChange={(e) => definir("cpf", e.target.value)}
                    inputMode="numeric"
                    placeholder="000.000.000-00"
                  />
                </Field>
                <Field
                  label="Conselho de classe"
                  hint="Sem este registro a pessoa não consegue assinar laudos."
                  className="sm:col-span-2"
                >
                  <Input
                    value={form.conselho_classe}
                    onChange={(e) => definir("conselho_classe", e.target.value)}
                    placeholder="Ex.: CREA-SP 1234567890"
                  />
                </Field>
              </>
            )}
          </FormGrid>
        </FormSection>

        {editando ? <FormSection title="Senha e situação" description="Deixe a senha em branco para manter a atual.">
          <FormGrid colunas={2}>
            <Field
              label={editando ? "Nova senha" : "Senha inicial"}
              erro={erros.password}
              hint="No mínimo 15 caracteres."
            >
              <Input
                type="password"
                value={form.password}
                onChange={(e) => definir("password", e.target.value)}
                autoComplete="new-password"
                placeholder={editando ? "Manter a senha atual" : ""}
              />
            </Field>
            <div className="flex items-end">
              <Switch
                checked={form.is_active}
                onChange={(v) => definir("is_active", v)}
                label="Acesso ativo"
                hint="Desligado, a pessoa não consegue entrar — o histórico dela é preservado."
                className="w-full"
              />
            </div>
          </FormGrid>

        </FormSection> : <Alert tone="info" icon={MailPlus}>O convite expira em 72 horas e só pode ser usado uma vez. A pessoa não consegue alterar o perfil ou o nível definidos aqui.</Alert>}
      </div>
    </Modal>
  );
}
