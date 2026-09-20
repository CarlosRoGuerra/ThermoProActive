"use client";

import { useState } from "react";
import { Clock, Mail, ShieldCheck, UserPlus, Users } from "lucide-react";
import {
  Alert,
  Avatar,
  Badge,
  Button,
  Card,
  EmptyState,
  Field,
  Input,
  LoadingState,
  Modal,
  PageBody,
  PageHeader,
  Select,
  useToast,
} from "@/components/ds";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useLista, useMutacao, useRecurso } from "@/lib/recurso";
import { usePermissoes } from "@/lib/permissions";
import { NIVEL_LABEL, PERFIL_LABEL, PERFIS_CLIENTE } from "@/lib/permissions";
import { dataHora } from "@/lib/format";
import type { Nivel, Perfil, User } from "@/lib/types";

/* ==========================================================================
   Equipe — Portal do Cliente.
   --------------------------------------------------------------------------
   O backend já sabia convidar um colega (POST /auth/convites/, restrito ao
   Master do lado do cliente — mesma regra de quem concede acesso do lado
   interno). Só não existia NENHUMA tela pra chegar lá: quem se cadastrava
   virava o único usuário da empresa, sem jeito de trazer o resto do time.

   "Ver quem já está" e "convidar" são coisas separadas de propósito: qualquer
   colega vê a equipe (transparência de quem tem acesso), só o Master convida
   — mesma régua do lado interno (Master concede, os demais operam).
   ========================================================================== */

type ConviteEnvio = {
  id: number;
  nome: string;
  email: string;
  perfil: Perfil;
  perfil_display: string;
  nivel: Nivel;
  nivel_display: string;
  criado_em: string;
  expira_em: string;
  expirado: boolean;
};

const NIVEIS_CONVITE: Nivel[] = ["SENIOR", "PLENO", "JUNIOR"];

export default function PortalEquipePage() {
  const { user } = useAuth();
  const { pode } = usePermissoes();
  const [convidando, setConvidando] = useState(false);

  const podeGerenciar = pode("equipe:gerenciar");

  const equipe = useLista<User>("/minha-equipe/?page_size=200", "equipe");
  // /minha-equipe/convites/ devolve uma lista simples (não paginada) — usa
  // useRecurso puro em vez de useLista, que espera o formato {results, count}.
  const convites = useRecurso<ConviteEnvio[]>(
    podeGerenciar ? "/minha-equipe/convites/" : null,
    "convites pendentes"
  );
  const convitesPendentes = convites.dados ?? [];

  return (
    <PageBody>
      <PageHeader
        icon={Users}
        title="Equipe"
        description="Quem da sua empresa tem acesso ao Portal Pred Ativos."
        trilha={[{ label: "Equipe" }]}
        actions={
          podeGerenciar ? (
            <Button icon={UserPlus} onClick={() => setConvidando(true)}>
              Convidar colaborador
            </Button>
          ) : undefined
        }
      />

      {!podeGerenciar && (
        <Alert tone="info" icon={ShieldCheck}>
          Só o Master da sua organização pode convidar novos colaboradores. Se precisar trazer
          alguém para a equipe, peça para {user?.nome ? "o responsável Master" : "quem administra o acesso"}.
        </Alert>
      )}

      <Card padding={false}>
        {equipe.carregando ? (
          <div className="p-4">
            <LoadingState variante="cartoes" linhas={3} label="Carregando a equipe…" />
          </div>
        ) : equipe.itens.length === 0 ? (
          <div className="p-4">
            <EmptyState icon={Users} title="Nenhum colaborador encontrado" compacto />
          </div>
        ) : (
          <ul className="divide-y divide-border">
            {equipe.itens.map((u) => (
              <li key={u.id} className="flex flex-wrap items-center gap-3 px-4 py-3.5">
                <Avatar nome={u.nome} />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-fg">
                    {u.nome}
                    {u.id === user?.id && <span className="ml-1.5 text-xs text-fg-subtle">(você)</span>}
                  </p>
                  <p className="truncate text-xs text-fg-muted">{u.email}</p>
                </div>
                <div className="flex shrink-0 flex-wrap items-center gap-1.5">
                  <Badge tone="neutral">{PERFIL_LABEL[u.perfil]}</Badge>
                  {u.is_master && <Badge tone="primary">Master</Badge>}
                  {!u.is_active && <Badge tone="danger">Inativo</Badge>}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      {podeGerenciar && (
        <>
          <h2 className="text-sm font-semibold text-fg">Convites pendentes</h2>
          {convites.carregando ? (
            <LoadingState variante="cartoes" linhas={2} label="Carregando convites…" />
          ) : convitesPendentes.length === 0 ? (
            <p className="text-sm text-fg-muted">Nenhum convite aguardando aceite no momento.</p>
          ) : (
            <ul className="space-y-2">
              {convitesPendentes.map((c) => (
                <li
                  key={c.id}
                  className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-surface px-4 py-3"
                >
                  <Mail className="h-4 w-4 shrink-0 text-fg-subtle" aria-hidden="true" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-fg">{c.nome}</p>
                    <p className="truncate text-xs text-fg-muted">{c.email}</p>
                  </div>
                  <Badge tone="neutral">{PERFIL_LABEL[c.perfil]}</Badge>
                  {c.expirado ? (
                    <Badge tone="danger" icon={Clock}>
                      Expirado
                    </Badge>
                  ) : (
                    <span className="text-xs text-fg-subtle">
                      enviado em {dataHora(c.criado_em)}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </>
      )}

      {podeGerenciar && (
        <ModalConvite aberto={convidando} onFechar={() => setConvidando(false)} onEnviado={() => {
          setConvidando(false);
          equipe.recarregar();
          convites.recarregar();
        }} />
      )}
    </PageBody>
  );
}

function ModalConvite({
  aberto,
  onFechar,
  onEnviado,
}: {
  aberto: boolean;
  onFechar: () => void;
  onEnviado: () => void;
}) {
  const { user } = useAuth();
  const toast = useToast();
  const mutacao = useMutacao("convite de colaborador");
  const [nome, setNome] = useState("");
  const [email, setEmail] = useState("");
  const [perfil, setPerfil] = useState<Perfil>("CLIENTE_PCM");
  const [nivel, setNivel] = useState<Nivel>("PLENO");
  const [erroEmail, setErroEmail] = useState<string | null>(null);

  function limpar() {
    setNome("");
    setEmail("");
    setPerfil("CLIENTE_PCM");
    setNivel("PLENO");
    setErroEmail(null);
  }

  async function enviar() {
    setErroEmail(null);
    if (!nome.trim() || !email.trim()) return;
    const r = await mutacao.executar(() =>
      api("/auth/convites/", {
        method: "POST",
        body: {
          nome: nome.trim(),
          email: email.trim().toLowerCase(),
          tipo: "portal",
          perfil,
          nivel,
          cliente: user?.cliente,
          empresa: null,
        },
      })
    );
    if (r.ok) {
      toast.sucesso("Convite enviado", {
        descricao: `${nome} recebe um link pessoal, de uso único, para criar a própria senha.`,
      });
      limpar();
      onEnviado();
      return;
    }
    if (r.falha.tipo === "validacao" && /email/i.test(r.falha.descricao)) {
      setErroEmail("Já existe uma conta ou convite pendente com este e-mail.");
    }
    toast.erro(r.falha.titulo, { descricao: r.falha.descricao });
  }

  return (
    <Modal
      aberto={aberto}
      onFechar={() => {
        limpar();
        onFechar();
      }}
      tamanho="sm"
      title="Convidar colaborador"
      description="Ele recebe um e-mail com um link pessoal para criar a própria senha — você não define a senha de ninguém."
      footer={
        <>
          <Button variant="secondary" size="sm" onClick={onFechar} disabled={mutacao.enviando}>
            Cancelar
          </Button>
          <Button
            size="sm"
            onClick={enviar}
            loading={mutacao.enviando}
            disabled={!nome.trim() || !email.trim()}
            icon={UserPlus}
          >
            Enviar convite
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Field label="Nome completo" obrigatorio>
          <Input value={nome} onChange={(e) => setNome(e.target.value)} placeholder="Ex.: Maria Souza" />
        </Field>
        <Field label="E-mail" obrigatorio erro={erroEmail}>
          <Input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="nome@suaempresa.com.br"
          />
        </Field>
        <Field label="Função no Portal" hint="Define o que a pessoa vê e faz por aqui.">
          <Select value={perfil} onChange={(e) => setPerfil(e.target.value as Perfil)}>
            {PERFIS_CLIENTE.map((p) => (
              <option key={p} value={p}>
                {PERFIL_LABEL[p]}
              </option>
            ))}
          </Select>
        </Field>
        <Field
          label="Nível de acesso"
          hint="Master é exclusivo do primeiro acesso da empresa — para promover alguém, peça à ThermoProActive."
        >
          <Select value={nivel} onChange={(e) => setNivel(e.target.value as Nivel)}>
            {NIVEIS_CONVITE.map((n) => (
              <option key={n} value={n}>
                {NIVEL_LABEL[n]}
              </option>
            ))}
          </Select>
        </Field>
      </div>
    </Modal>
  );
}
