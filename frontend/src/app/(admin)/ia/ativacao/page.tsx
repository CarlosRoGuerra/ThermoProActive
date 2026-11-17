"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { KeyRound, Sparkles } from "lucide-react";
import {
  Alert,
  Badge,
  Button,
  Card,
  ErrorCard,
  Field,
  FormGrid,
  Input,
  LoadingState,
  PageBody,
  PageHeader,
  Select,
  Switch,
  useToast,
} from "@/components/ds";
import { api } from "@/lib/api";
import { useMutacao, useRecurso } from "@/lib/recurso";
import type { AtivacaoIA, ChaveIA } from "@/features/ia/tipos";

/**
 * Ativação da IA — onde o Master liga ou desliga o uso de IA em cada recurso do
 * sistema e escolhe qual chave (e qual modelo) o recurso usa.
 *
 * Um recurso só liga com uma chave cadastrada em Chaves de API. Enquanto o recurso
 * aparece como "em desenvolvimento", a escolha fica gravada e nada é enviado ao provedor.
 */

type Rascunho = { habilitado: boolean; credencial: string; modelo: string };

const rascunhoDe = (a: AtivacaoIA): Rascunho => ({
  habilitado: a.habilitado,
  credencial: a.credencial == null ? "" : String(a.credencial),
  modelo: a.modelo,
});

function CartaoRecurso({ ativacao, chaves, onSalvo }: { ativacao: AtivacaoIA; chaves: ChaveIA[]; onSalvo: (a: AtivacaoIA) => void }) {
  const toast = useToast();
  const gravacao = useMutacao("ativação de IA");
  const [r, setR] = useState<Rascunho>(rascunhoDe(ativacao));
  useEffect(() => setR(rascunhoDe(ativacao)), [ativacao]);

  const original = rascunhoDe(ativacao);
  const mudou = r.habilitado !== original.habilitado || r.credencial !== original.credencial || r.modelo !== original.modelo;
  const chave = chaves.find((c) => String(c.id) === r.credencial);
  const semChave = r.credencial === "";

  async function salvar() {
    const res = await gravacao.executar(() =>
      api<AtivacaoIA>(`/ia/ativacoes/${ativacao.recurso}/`, {
        method: "PATCH",
        body: { habilitado: r.habilitado, credencial: semChave ? null : Number(r.credencial), modelo: r.modelo.trim() },
      })
    );
    if (res.ok) {
      toast.sucesso(res.dados.habilitado ? "Uso de IA habilitado" : "Uso de IA desligado", { descricao: res.dados.recurso_display });
      onSalvo(res.dados);
    }
  }

  return (
    <Card as="section">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-base font-semibold text-fg">{ativacao.recurso_display}</h2>
          <p className="mt-1 max-w-2xl text-sm text-fg-muted">{ativacao.descricao}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {!ativacao.implementado && (
            <Badge tone="warning" title="A função ainda não foi entregue. A escolha fica gravada e passa a valer quando ela entrar no sistema.">
              Em desenvolvimento
            </Badge>
          )}
          <Badge tone={ativacao.habilitado ? "success" : "neutral"} dot>{ativacao.habilitado ? "Habilitado" : "Desligado"}</Badge>
        </div>
      </div>

      <div className="mt-4 space-y-4">
        {gravacao.falha && <Alert tone="danger" title={gravacao.falha.titulo}>{gravacao.falha.descricao}</Alert>}
        <FormGrid colunas={2}>
          <Field label="Chave de API usada" hint={chaves.length === 0 ? "Nenhuma chave cadastrada." : undefined}>
            <Select
              value={r.credencial}
              onChange={(e) => setR((x) => ({ ...x, credencial: e.target.value, habilitado: e.target.value === "" ? false : x.habilitado }))}
            >
              <option value="">— nenhuma —</option>
              {chaves.map((c) => (
                <option key={c.id} value={c.id} disabled={!c.legivel}>
                  {c.provedor_display} — {c.rotulo} ({c.chave_mascarada}){c.legivel ? "" : " — cadastrar de novo"}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Modelo" hint="Em branco usa o modelo padrão da chave.">
            <Input
              value={r.modelo}
              maxLength={120}
              spellCheck={false}
              placeholder={chave?.modelo_padrao || "Modelo padrão da chave"}
              onChange={(e) => setR((x) => ({ ...x, modelo: e.target.value }))}
            />
          </Field>
        </FormGrid>
        <Switch
          checked={r.habilitado}
          disabled={semChave}
          onChange={(v) => setR((x) => ({ ...x, habilitado: v }))}
          label="Usar IA neste recurso"
          hint={
            semChave
              ? "Escolha a chave de API para poder habilitar."
              : ativacao.implementado
                ? "Ligado, os dados do recurso são enviados ao provedor da chave escolhida."
                : "Este recurso ainda não foi entregue: a escolha fica gravada e nada é enviado por enquanto."
          }
        />
        <div className="flex justify-end">
          <Button onClick={salvar} loading={gravacao.enviando} disabled={!mudou}>Salvar</Button>
        </div>
      </div>
    </Card>
  );
}

export default function AtivacaoIaPage() {
  const ativacoes = useRecurso<AtivacaoIA[]>("/ia/ativacoes/", "ativação de IA");
  const chaves = useRecurso<ChaveIA[]>("/ia/chaves/", "chaves de IA");
  const carregando = ativacoes.carregando || chaves.carregando;
  const falha = ativacoes.falha ?? chaves.falha;
  const listaChaves = chaves.dados ?? [];

  return (
    <PageBody>
      <PageHeader
        icon={Sparkles}
        title="Ativação da IA"
        description="Liga ou desliga o uso de inteligência artificial em cada recurso do sistema e define qual chave de API ele usa."
        trilha={[{ label: "Inteligência artificial", href: "/ia" }, { label: "Ativação" }]}
        actions={
          <Link href="/ia/chaves">
            <Button variant="secondary" icon={KeyRound}>Chaves de API</Button>
          </Link>
        }
      />

      {carregando ? (
        <LoadingState variante="cartoes" linhas={2} label="Carregando os recursos de IA…" />
      ) : falha ? (
        <ErrorCard falha={falha} onRetry={() => { ativacoes.recarregar(); chaves.recarregar(); }} />
      ) : (
        <>
          {listaChaves.length === 0 && (
            <Alert
              tone="warning"
              title="Cadastre uma chave de API primeiro"
              actions={<Link href="/ia/chaves"><Button size="sm" variant="secondary" icon={KeyRound}>Cadastrar chave</Button></Link>}
            >
              Um recurso só pode ser habilitado depois que a chave do provedor estiver cadastrada.
            </Alert>
          )}
          <Alert tone="info" title="O que acontece ao habilitar">
            Com um recurso habilitado, os dados que ele analisa (gráficos de vibração, laudos de laboratório) são enviados
            ao provedor da chave escolhida. Desligado, nada sai do sistema e as telas funcionam como hoje.
          </Alert>
          {(ativacoes.dados ?? []).map((a) => (
            <CartaoRecurso
              key={a.recurso}
              ativacao={a}
              chaves={listaChaves}
              onSalvo={(novo) => {
                ativacoes.definirDados((atual) => (atual ? atual.map((x) => (x.recurso === novo.recurso ? novo : x)) : atual));
                chaves.recarregar(); // atualiza o "em uso por" das chaves
              }}
            />
          ))}
        </>
      )}
    </PageBody>
  );
}
