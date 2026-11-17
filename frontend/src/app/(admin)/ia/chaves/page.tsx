"use client";

import { useState } from "react";
import Link from "next/link";
import { KeyRound, Pencil, Plus, Trash2 } from "lucide-react";
import {
  Alert,
  Badge,
  Button,
  ConfirmDialog,
  DataTable,
  EmptyState,
  Field,
  FormGrid,
  Input,
  Modal,
  PageBody,
  PageHeader,
  Select,
  SemDado,
  useConfirmacao,
  useToast,
  type Coluna,
  type ItemMenu,
} from "@/components/ds";
import { api } from "@/lib/api";
import { useMutacao, useRecurso } from "@/lib/recurso";
import { PROVEDORES, type ChaveIA, type ProvedorIA } from "@/features/ia/tipos";

/**
 * Chaves de API de IA — onde o Master cola a chave de cada provedor.
 *
 * A chave é gravada cifrada e não volta para a tela: depois de salvar, só os quatro
 * últimos caracteres aparecem. Trocar é colar a nova por cima. O uso de cada chave é
 * ligado em outro lugar (Administração → Inteligência artificial → Ativação).
 */

type Form = { provedor: ProvedorIA; rotulo: string; chave: string; modelo_padrao: string; url_base: string };
const FORM_VAZIO: Form = { provedor: "ANTHROPIC", rotulo: "", chave: "", modelo_padrao: "", url_base: "" };

export default function ChavesIaPage() {
  const toast = useToast();
  const lista = useRecurso<ChaveIA[]>("/ia/chaves/", "chaves de IA");
  const gravacao = useMutacao("gravação da chave de IA");
  const exclusao = useMutacao("remoção da chave de IA");
  const remocao = useConfirmacao<ChaveIA>();

  /** `null` = modal fechado; `"nova"` = cadastro; objeto = edição. */
  const [editando, setEditando] = useState<ChaveIA | "nova" | null>(null);
  const [form, setForm] = useState<Form>(FORM_VAZIO);
  const set = <K extends keyof Form>(campo: K, valor: Form[K]) => setForm((f) => ({ ...f, [campo]: valor }));

  function abrir(alvo: ChaveIA | "nova") {
    gravacao.limparFalha();
    setForm(
      alvo === "nova"
        ? FORM_VAZIO
        : { provedor: alvo.provedor, rotulo: alvo.rotulo, chave: "", modelo_padrao: alvo.modelo_padrao, url_base: alvo.url_base }
    );
    setEditando(alvo);
  }

  const nova = editando === "nova";
  const exigeEndereco = form.provedor === "OUTRO";
  const podeSalvar =
    form.rotulo.trim() !== "" && (!nova || form.chave.trim().length >= 8) && (!exigeEndereco || form.url_base.trim() !== "");

  async function salvar() {
    if (!editando) return;
    const corpo: Record<string, string> = {
      provedor: form.provedor,
      rotulo: form.rotulo.trim(),
      modelo_padrao: form.modelo_padrao.trim(),
      url_base: form.url_base.trim(),
    };
    // Na edição, a chave só vai se foi colada uma nova: em branco, a gravada fica.
    if (form.chave.trim()) corpo.chave = form.chave.trim();
    const r = await gravacao.executar(() =>
      nova
        ? api<ChaveIA>("/ia/chaves/", { method: "POST", body: corpo })
        : api<ChaveIA>(`/ia/chaves/${(editando as ChaveIA).id}/`, { method: "PATCH", body: corpo })
    );
    if (r.ok) {
      toast.sucesso(nova ? "Chave cadastrada" : "Chave atualizada", { descricao: `${r.dados.provedor_display} — ${r.dados.rotulo}` });
      setEditando(null);
      setForm(FORM_VAZIO); // a chave digitada não fica na memória da tela
      lista.recarregar();
    }
  }

  async function remover(c: ChaveIA) {
    const r = await exclusao.executar(() => api(`/ia/chaves/${c.id}/`, { method: "DELETE" }));
    if (r.ok) {
      toast.sucesso("Chave removida", { descricao: `“${c.rotulo}” foi apagada do sistema.` });
      lista.recarregar();
    } else {
      toast.erro(r.falha.titulo, { descricao: r.falha.descricao });
    }
  }

  const colunas: Coluna<ChaveIA>[] = [
    {
      chave: "provedor",
      header: "Provedor",
      mobile: "subtitulo",
      valor: (c) => c.provedor_display,
      celula: (c) => c.provedor_display,
    },
    {
      chave: "rotulo",
      header: "Identificação",
      mobile: "titulo",
      valor: (c) => c.rotulo,
      celula: (c) => <span className="font-medium text-fg">{c.rotulo}</span>,
    },
    {
      chave: "chave",
      header: "Chave",
      mobile: "meta",
      tecnico: true,
      celula: (c) =>
        c.legivel ? c.chave_mascarada : <Badge tone="danger" title="A chave de cifra do servidor mudou. Edite e cole a chave de novo.">Cadastrar de novo</Badge>,
    },
    {
      chave: "modelo",
      header: "Modelo padrão",
      mobile: "meta",
      tecnico: true,
      valor: (c) => c.modelo_padrao,
      celula: (c) => c.modelo_padrao || <SemDado />,
    },
    {
      chave: "uso",
      header: "Em uso por",
      mobile: "meta",
      celula: (c) => (c.em_uso.length ? c.em_uso.join(", ") : <span className="text-fg-subtle">Nenhum recurso</span>),
    },
  ];

  const acoes = (c: ChaveIA): ItemMenu[] => [
    { label: "Editar ou trocar a chave", icon: Pencil, onClick: () => abrir(c) },
    { label: "Remover chave", icon: Trash2, destrutivo: true, onClick: () => remocao.pedir(c) },
  ];

  return (
    <PageBody>
      <PageHeader
        icon={KeyRound}
        title="Chaves de API de IA"
        description="As chaves dos provedores de inteligência artificial que o sistema pode usar. Cadastrar a chave não liga nada: o uso é habilitado por recurso, em Ativação."
        trilha={[{ label: "Inteligência artificial", href: "/ia" }, { label: "Chaves de API" }]}
        actions={<Button icon={Plus} onClick={() => abrir("nova")}>Nova chave</Button>}
      />

      <Alert tone="info" title="A chave não é exibida depois de salva">
        Ela fica cifrada no banco e aparece só pelos quatro últimos caracteres. Para trocar, edite e cole a nova.
        Depois de cadastrar, habilite o uso em{" "}
        <Link href="/ia/ativacao" className="font-medium underline">Ativação</Link>.
      </Alert>

      <DataTable<ChaveIA>
        itens={lista.dados ?? []}
        colunas={colunas}
        getId={(c) => c.id}
        carregando={lista.carregando}
        falha={lista.falha}
        onRetry={lista.recarregar}
        onLinhaClick={(c) => abrir(c)}
        acoes={acoes}
        legenda="Chaves de API de IA cadastradas, por provedor"
        vazio={
          <EmptyState
            icon={KeyRound}
            title="Nenhuma chave cadastrada"
            description="Cole aqui a chave de API do provedor de IA que a empresa contratou. Sem chave, nenhum recurso de IA pode ser habilitado."
            action={<Button icon={Plus} onClick={() => abrir("nova")}>Nova chave</Button>}
          />
        }
      />

      <Modal
        aberto={editando !== null}
        onFechar={() => setEditando(null)}
        title={nova ? "Nova chave de API" : "Editar chave de API"}
        description={nova ? "A chave é gerada no painel do provedor. Cole-a aqui." : "Deixe a chave em branco para manter a que está gravada."}
        travarFundo
        footer={
          <>
            <Button variant="secondary" onClick={() => setEditando(null)}>Cancelar</Button>
            <Button onClick={salvar} loading={gravacao.enviando} disabled={!podeSalvar}>Salvar</Button>
          </>
        }
      >
        <div className="space-y-4">
          {gravacao.falha && <Alert tone="danger" title={gravacao.falha.titulo}>{gravacao.falha.descricao}</Alert>}
          <FormGrid colunas={2}>
            <Field label="Provedor" obrigatorio>
              <Select value={form.provedor} onChange={(e) => set("provedor", e.target.value as ProvedorIA)}>
                {PROVEDORES.map((p) => <option key={p.valor} value={p.valor}>{p.rotulo}</option>)}
              </Select>
            </Field>
            <Field label="Identificação" obrigatorio hint="Como reconhecer esta chave. Ex.: Conta principal.">
              <Input value={form.rotulo} maxLength={80} onChange={(e) => set("rotulo", e.target.value)} />
            </Field>
          </FormGrid>
          <Field
            label="Chave de API"
            obrigatorio={nova}
            hint={nova ? "Mínimo de 8 caracteres. Não será exibida de novo." : `Gravada: ${(editando as ChaveIA | null)?.chave_mascarada ?? ""}. Cole outra só para trocar.`}
          >
            <Input
              type="password"
              autoComplete="off"
              spellCheck={false}
              value={form.chave}
              maxLength={500}
              placeholder={nova ? "Cole a chave" : "Manter a chave gravada"}
              onChange={(e) => set("chave", e.target.value)}
            />
          </Field>
          <Field label="Modelo padrão" hint="Identificador do modelo no provedor. Cada recurso pode usar outro. Pode ficar em branco por enquanto.">
            <Input value={form.modelo_padrao} maxLength={120} spellCheck={false} onChange={(e) => set("modelo_padrao", e.target.value)} />
          </Field>
          <Field
            label="Endereço da API"
            obrigatorio={exigeEndereco}
            hint={exigeEndereco ? "Endereço base da API deste provedor." : "Em branco usa o endereço oficial do provedor. Preencha só para um servidor próprio."}
          >
            <Input type="url" value={form.url_base} placeholder="https://" spellCheck={false} onChange={(e) => set("url_base", e.target.value)} />
          </Field>
        </div>
      </Modal>

      <ConfirmDialog
        aberto={!!remocao.alvo}
        onFechar={remocao.cancelar}
        onConfirmar={() => remocao.executar(remover)}
        enviando={exclusao.enviando}
        title="Remover esta chave?"
        confirmarLabel="Remover chave"
        mensagem={
          <>
            A chave <strong>{remocao.alvo?.rotulo}</strong> ({remocao.alvo?.provedor_display}) será apagada do sistema.
          </>
        }
        detalhe={
          remocao.alvo?.em_uso.length
            ? `Estes recursos usam a chave e serão desligados: ${remocao.alvo.em_uso.join(", ")}.`
            : "Nenhum recurso habilitado usa esta chave."
        }
        irreversivel
      />
    </PageBody>
  );
}
