"use client";

import { Building2, Mail, Moon, Palette, ShieldCheck, UserCog } from "lucide-react";
import {
  Alert,
  Avatar,
  Badge,
  Card,
  CardHeader,
  DescriptionList,
  PageBody,
  PageHeader,
  SemDado,
  ThemeToggle,
} from "@/components/ds";
import { useAuth } from "@/lib/auth";
import { NIVEL_LABEL, NIVEL_RESUMO, PERFIL_LABEL } from "@/lib/permissions";
import { texto } from "@/lib/format";

/**
 * Meu perfil — mesma tela nos dois portais.
 *
 * É de consulta por decisão de produto: quem concede e altera acesso é o nível
 * Master (backend: UserViewSet + IsMaster). A tela existe porque o usuário
 * precisa saber QUEM ele é no sistema e POR QUE não consegue certas ações — a
 * dúvida "por que não consigo excluir?" some quando o nível e o que ele permite
 * estão escritos na tela.
 */
export function MeuPerfil({ ehCliente }: { ehCliente: boolean }) {
  const { user } = useAuth();
  if (!user) return null;

  return (
    <PageBody>
      <PageHeader
        icon={UserCog}
        title="Meu perfil"
        description="Seus dados de acesso e as preferências de exibição desta plataforma."
        trilha={[{ label: "Meu perfil" }]}
      />

      <Card>
        <div className="flex flex-wrap items-center gap-4">
          <Avatar nome={user.nome} tamanho="lg" />
          <div className="min-w-0 flex-1">
            <p className="text-lg font-semibold text-fg">{user.nome}</p>
            <p className="flex items-center gap-1.5 text-sm text-fg-muted">
              <Mail className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
              {user.email}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-1.5">
            <Badge tone={ehCliente ? "info" : "primary"} icon={ShieldCheck}>
              {PERFIL_LABEL[user.perfil] ?? user.perfil_display}
            </Badge>
            <Badge tone="neutral">Nível {NIVEL_LABEL[user.nivel] ?? user.nivel_display}</Badge>
          </div>
        </div>
      </Card>

      <Card>
        <CardHeader
          title="Dados de acesso"
          description="Para corrigir qualquer informação desta seção, fale com quem administra os acessos."
          icon={Building2}
        />
        <DescriptionList
          colunas={3}
          items={[
            { label: "Nome completo", value: texto(user.nome) },
            { label: "E-mail de acesso", value: texto(user.email) },
            { label: "Cargo / função", value: texto(user.cargo) },
            {
              label: "Perfil de acesso",
              value: PERFIL_LABEL[user.perfil] ?? user.perfil_display,
            },
            {
              label: "Grupo de acesso",
              value: user.grupo_acesso,
              tecnico: true,
            },
            ...(ehCliente
              ? []
              : [
                  {
                    label: "Conselho de classe",
                    value: user.conselho_classe || <SemDado>Não informado</SemDado>,
                  },
                ]),
          ]}
        />

        {!ehCliente && (
          <div className="mt-5">
            <Alert tone={user.conselho_classe ? "info" : "warning"}>
              <strong>O que o seu nível permite:</strong> {NIVEL_RESUMO[user.nivel]}
              {!user.conselho_classe && (
                <>
                  {" "}
                  Sem o registro em conselho de classe (ex.: CREA) você não consegue assinar laudos —
                  peça ao nível Master para completar o seu cadastro.
                </>
              )}
            </Alert>
          </div>
        )}

        {ehCliente && (
          <div className="mt-5">
            <Alert tone="info">
              Este portal é de consulta. Os dados técnicos são registrados pela equipe da
              ThermoProActive, com instrumentos calibrados e as normas aplicáveis — é o que dá
              validade técnica aos laudos.
            </Alert>
          </div>
        )}
      </Card>

      <Card>
        <CardHeader
          title="Preferências de exibição"
          description="Valem só para este navegador."
          icon={Palette}
        />
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <p className="flex items-center gap-2 text-sm font-medium text-fg">
              <Moon className="h-4 w-4 shrink-0 text-fg-subtle" aria-hidden="true" />
              Tema claro ou escuro
            </p>
            <p className="mt-0.5 text-xs text-fg-muted">
              Por padrão a plataforma segue a configuração do seu sistema operacional. Use o botão
              para fixar uma das opções.
            </p>
          </div>
          <ThemeToggle className="shrink-0" />
        </div>
      </Card>

      <Card>
        <CardHeader title="Segurança da conta" icon={ShieldCheck} />
        <ul className="space-y-2.5 text-sm text-fg-muted">
          <li>
            Sua sessão expira automaticamente por inatividade. Se isso acontecer, é só entrar de
            novo — nada do que você estava vendo é perdido.
          </li>
          <li>
            Para trocar de senha ou encerrar o acesso de alguém da sua equipe, fale com quem
            administra os acessos.
          </li>
          <li>Nunca compartilhe seu login: cada pessoa deve ter o seu próprio.</li>
        </ul>
      </Card>
    </PageBody>
  );
}
