"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import {
  CircleCheck,
  CircleSlash,
  ClipboardList,
  KeyRound,
  Pencil,
  ShieldCheck,
  UserPlus,
  Users,
} from "lucide-react";
import {
  Alert,
  Avatar,
  Badge,
  Button,
  ConfirmDialog,
  DataTable,
  EmptyState,
  MetricCard,
  MetricGrid,
  PageBody,
  PageHeader,
  PermissionDenied,
  SearchInput,
  SegmentedControl,
  SemDado,
  Toolbar,
  useConfirmacao,
  useToast,
  type Coluna,
  type ItemMenu,
} from "@/components/ds";
import { api } from "@/lib/api";
import { useLista, useMutacao } from "@/lib/recurso";
import { usePermissoes, NIVEL_LABEL, NIVEL_RESUMO, PERFIL_LABEL } from "@/lib/permissions";
import { plural, texto } from "@/lib/format";
import type { User } from "@/lib/types";
import { FormularioUsuario } from "@/features/usuarios/formulario-usuario";

/* ==========================================================================
   Usuários e acessos — tela nova.
   --------------------------------------------------------------------------
   O backend já tinha o CRUD completo (`/api/usuarios/`, restrito ao nível
   Master) e NENHUMA tela o usava: conceder acesso só era possível pelo admin do
   Django. Esta página fecha essa lacuna.

   Decisões:
     • A pergunta que a tela responde é "quem tem acesso a quê", então perfil e
       nível são colunas, não detalhe escondido.
     • Desativar > excluir: o vínculo do usuário com laudos e medições é
       histórico técnico. A ação principal é ligar/desligar o acesso.
     • Todo nível vem com a frase do que ele permite — é o que evita a dúvida
       recorrente "por que essa pessoa não consegue excluir?".
   ========================================================================== */

type Filtro = "todos" | "internos" | "clientes" | "inativos";

export default function UsuariosPage() {
  const toast = useToast();
  const { pode, user: eu } = usePermissoes();
  const [busca, setBusca] = useState("");
  const [filtro, setFiltro] = useState<Filtro>("todos");
  const [emEdicao, setEmEdicao] = useState<User | null | "novo">(null);

  const lista = useLista<User>(
    pode("usuarios:ver") ? "/usuarios/?page_size=300" : null,
    "usuários"
  );
  const mutacao = useMutacao("alteração de acesso");
  const alternancia = useConfirmacao<User>();

  // O ViewSet inteiro exige nível Master: sem ele, nem a leitura existe.
  if (!pode("usuarios:ver")) {
    return (
      <PageBody>
        <PermissionDenied
          destino="/dashboard"
          destinoLabel="Ir para a visão geral"
          motivo="A concessão de acessos é exclusiva do nível Master, para que ninguém perca o controle de quem entra no sistema e do que cada um pode fazer."
        />
      </PageBody>
    );
  }

  const usuarios = lista.itens;
  const internos = usuarios.filter((u) => u.is_interno);
  const clientes = usuarios.filter((u) => u.is_cliente);
  const inativos = usuarios.filter((u) => u.is_active === false);
  const masters = internos.filter((u) => u.is_master);

  const visiveis = useMemo(() => {
    const base =
      filtro === "internos"
        ? internos
        : filtro === "clientes"
        ? clientes
        : filtro === "inativos"
        ? inativos
        : usuarios;
    return base;
  }, [filtro, usuarios, internos, clientes, inativos]);

  async function alternarAtivo(u: User) {
    const r = await mutacao.executar(() =>
      api(`/usuarios/${u.id}/`, { method: "PATCH", body: { is_active: !u.is_active } })
    );
    if (r.ok) {
      toast.sucesso(
        u.is_active ? "Acesso desativado" : "Acesso reativado",
        {
          descricao: u.is_active
            ? `${u.nome} não consegue mais entrar. O histórico de trabalho dele fica preservado.`
            : `${u.nome} já pode entrar novamente.`,
        }
      );
      lista.recarregar();
    } else {
      toast.erro(r.falha.titulo, { descricao: r.falha.descricao });
    }
  }

  const colunas: Coluna<User>[] = [
    {
      chave: "nome",
      header: "Pessoa",
      mobile: "titulo",
      valor: (u) => u.nome,
      celula: (u) => (
        <span className="flex items-center gap-2.5">
          <Avatar nome={u.nome} tamanho="xs" />
          <span className="min-w-0">
            <span className="block truncate font-medium text-fg">{u.nome}</span>
            <span className="block truncate text-xs text-fg-subtle">{u.email}</span>
          </span>
        </span>
      ),
    },
    {
      chave: "perfil",
      header: "Perfil",
      mobile: "meta",
      valor: (u) => PERFIL_LABEL[u.perfil] ?? u.perfil_display,
      celula: (u) => (
        <Badge tone={u.is_interno ? "primary" : "info"}>
          {PERFIL_LABEL[u.perfil] ?? u.perfil_display}
        </Badge>
      ),
    },
    {
      chave: "nivel",
      header: "Nível",
      mobile: "meta",
      valor: (u) => ({ MASTER: 4, SENIOR: 3, PLENO: 2, JUNIOR: 1 })[u.nivel] ?? 0,
      celula: (u) => (
        <Badge
          tone={u.is_master ? "warning" : "neutral"}
          icon={u.is_master ? ShieldCheck : undefined}
          title={NIVEL_RESUMO[u.nivel]}
        >
          {NIVEL_LABEL[u.nivel] ?? u.nivel_display}
        </Badge>
      ),
    },
    {
      chave: "cargo",
      header: "Cargo",
      mobile: "meta",
      valor: (u) => u.cargo,
      celula: (u) => (u.cargo ? texto(u.cargo) : <SemDado />),
    },
    {
      chave: "conselho",
      header: "Conselho",
      mobile: "oculta",
      valor: (u) => u.conselho_classe,
      celula: (u) =>
        u.conselho_classe ? (
          <span className="data text-xs">{u.conselho_classe}</span>
        ) : u.is_interno ? (
          <SemDado>Não assina laudos</SemDado>
        ) : (
          <SemDado />
        ),
    },
    {
      chave: "situacao",
      header: "Situação",
      mobile: "meta",
      valor: (u) => (u.is_active === false ? 0 : 1),
      celula: (u) =>
        u.is_active === false ? (
          <Badge tone="danger" icon={CircleSlash}>
            Acesso desativado
          </Badge>
        ) : (
          <Badge tone="success" icon={CircleCheck}>
            Ativo
          </Badge>
        ),
    },
  ];

  const acoes = (u: User): ItemMenu[] => {
    const ehEuMesmo = u.id === eu?.id;
    return [
      { label: "Editar dados e acesso", onClick: () => setEmEdicao(u), icon: Pencil },
      {
        label: u.is_active === false ? "Reativar acesso" : "Desativar acesso",
        onClick: () => alternancia.pedir(u),
        icon: u.is_active === false ? CircleCheck : CircleSlash,
        destrutivo: u.is_active !== false,
        disabled: ehEuMesmo,
        motivoDesabilitado: "Você não pode desativar o seu próprio acesso.",
      },
    ];
  };

  return (
    <PageBody>
      <PageHeader
        icon={Users}
        title="Usuários e acessos"
        description="Quem entra no sistema e o que cada um pode fazer. O perfil define a área (equipe interna ou portal do cliente); o nível define o alcance das ações."
        trilha={[{ label: "Usuários e acessos" }]}
        actions={
          <>
            <Link href="/usuarios/solicitacoes">
              <Button variant="secondary" icon={ClipboardList}>
                Solicitações de acesso
              </Button>
            </Link>
            <Button icon={UserPlus} onClick={() => setEmEdicao("novo")}>
              Convidar usuário
            </Button>
          </>
        }
      />

      {masters.length === 1 && (
        <Alert tone="warning" title="Há apenas um usuário de nível Master" icon={KeyRound}>
          Se esse acesso for perdido, ninguém poderá conceder novos acessos nem manter os dados de
          sistema. Considere promover um segundo responsável a Master.
        </Alert>
      )}

      <MetricGrid colunas={4}>
        <MetricCard
          label="Equipe interna"
          value={internos.filter((u) => u.is_active !== false).length}
          icon={Users}
          contexto="com acesso ativo ao painel operacional"
        />
        <MetricCard
          label="Usuários de cliente"
          value={clientes.filter((u) => u.is_active !== false).length}
          icon={Users}
          contexto="com acesso ao portal"
        />
        <MetricCard
          label="Nível Master"
          value={masters.length}
          tone={masters.length === 1 ? "warning" : "neutral"}
          icon={ShieldCheck}
          contexto="podem conceder acessos"
          dica="Só o nível Master cria usuários e mantém as tabelas de referência do sistema."
        />
        <MetricCard
          label="Acessos desativados"
          value={inativos.length}
          contexto="histórico preservado"
        />
      </MetricGrid>

      <Toolbar
        busca={
          <SearchInput
            value={busca}
            onChange={setBusca}
            label="Buscar usuário"
            placeholder="Nome, e-mail, cargo…"
          />
        }
        filtros={
          <SegmentedControl
            label="Filtrar usuários"
            tamanho="sm"
            valor={filtro}
            onMudar={setFiltro}
            opcoes={[
              { valor: "todos", label: `Todos (${usuarios.length})` },
              { valor: "internos", label: `Equipe (${internos.length})` },
              { valor: "clientes", label: `Clientes (${clientes.length})` },
              { valor: "inativos", label: `Desativados (${inativos.length})` },
            ]}
          />
        }
        resumo={usuarios.length > 0 ? plural(visiveis.length, "usuário") : undefined}
      />

      <DataTable<User>
        itens={visiveis}
        colunas={colunas}
        getId={(u) => u.id}
        busca={busca}
        camposBusca={(u) => [u.email, u.cargo, u.grupo_acesso, u.conselho_classe]}
        carregando={lista.carregando}
        falha={lista.falha}
        onRetry={lista.recarregar}
        onLinhaClick={(u) => setEmEdicao(u)}
        acoes={acoes}
        ordenacaoInicial={{ chave: "nome", direcao: "asc" }}
        tomDaLinha={(u) => (u.is_active === false ? "muted" : undefined)}
        legenda="Usuários com perfil, nível de acesso, cargo e situação"
        vazio={
          <EmptyState
            icon={Users}
            title="Nenhum usuário cadastrado além do seu"
            description="Cadastre a equipe técnica e os contatos do cliente para que cada um entre com o seu próprio acesso."
            action={
              <Button icon={UserPlus} onClick={() => setEmEdicao("novo")}>
                Convidar usuário
              </Button>
            }
          />
        }
      />

      <FormularioUsuario
        aberto={emEdicao !== null}
        usuario={emEdicao === "novo" ? null : emEdicao}
        onFechar={() => setEmEdicao(null)}
        onSalvo={() => {
          setEmEdicao(null);
          lista.recarregar();
        }}
      />

      <ConfirmDialog
        aberto={!!alternancia.alvo}
        onFechar={alternancia.cancelar}
        onConfirmar={() => alternancia.executar(alternarAtivo)}
        enviando={mutacao.enviando}
        tom={alternancia.alvo?.is_active === false ? "primary" : "danger"}
        icon={alternancia.alvo?.is_active === false ? CircleCheck : CircleSlash}
        title={
          alternancia.alvo?.is_active === false ? "Reativar este acesso?" : "Desativar este acesso?"
        }
        confirmarLabel={alternancia.alvo?.is_active === false ? "Reativar" : "Desativar acesso"}
        mensagem={
          alternancia.alvo?.is_active === false ? (
            <>
              <strong>{alternancia.alvo?.nome}</strong> voltará a entrar no sistema com o mesmo
              perfil e nível de antes.
            </>
          ) : (
            <>
              <strong>{alternancia.alvo?.nome}</strong> deixará de conseguir entrar no sistema
              imediatamente.
            </>
          )
        }
        detalhe={
          alternancia.alvo?.is_active !== false
            ? "Nada do que essa pessoa registrou é apagado: laudos, medições e inspeções continuam vinculados ao nome dela. É por isso que desativamos em vez de excluir."
            : undefined
        }
      />
    </PageBody>
  );
}
