"use client";

import { useMemo } from "react";
import { useAuth } from "./auth";
import type { Nivel, Perfil, User } from "./types";

/**
 * RBAC do front-end — espelho fiel das permissões do backend.
 *
 * IMPORTANTE (segurança): isto é UX, não é controle de acesso. A autorização
 * real vive no DRF (`apps/accounts/permissions.py`: IsInterno, IsMaster,
 * InternoEditaClienteVisualiza, MasterEditaDemaisVisualizam). O front usa este
 * módulo para NÃO OFERECER o que o usuário não pode fazer — evitando o 403 na
 * cara do usuário — e para desviar rotas que ele não deveria alcançar.
 *
 * Se uma regra mudar no backend, mude aqui também: os dois lados são a mesma
 * matriz, decidida com o cliente (Anexo I 2.1 + reunião de 22/07/2026).
 *
 *   Ambiente × Nível
 *   BackEnd (equipe interna)      FrontEnd (cliente)
 *     Master  cura dados de sistema, gerencia usuários, exclui
 *     Sênior  opera e exclui
 *     Pleno   opera, não exclui
 *     Júnior  opera, não exclui
 *
 * O FrontEnd (Portal) é de CONSULTA. A única escrita que ele tem é o retorno
 * de informação da Ordem de Serviço (`osp:responder`) — decisão de
 * 2026-09-21, que reverte a de 2026-09-18. Convidar a própria equipe
 * (`equipe:gerenciar`) continua com o Master do cliente: é gestão da conta,
 * não dado operacional.
 */

/** Cada verbo que a interface precisa decidir mostrar ou não. */
export type Habilidade =
  /* Áreas (qual portal o usuário enxerga) */
  | "area:admin"
  | "area:portal"
  /* Operação sobre dados do cliente */
  | "operacional:ver"
  | "operacional:criar"
  | "operacional:editar"
  | "operacional:excluir"
  /* Cadastro de clientes e sua estrutura (áreas, setores, equipamentos, rotas) —
     exclusivo da equipe interna, em /clientes, /equipamentos, /rotas (admin). */
  | "clientes:gerenciar"
  /*
   * Escrita no parque técnico (equipamentos, rotas, inspeções, medições).
   * Exclusivo da equipe interna desde 2026-09-21, quando a decisão de
   * autoatendimento de 2026-09-18 foi revertida: o Portal consulta e devolve
   * informação, mas quem cadastra e diagnostica é a CONTRATADA.
   */
  | "parque:gerenciar"
  /* Tabelas de referência do sistema (normas, tipos, criticidades…) */
  | "dados-sistema:ver"
  | "dados-sistema:curar"
  /* Pessoas */
  | "usuarios:ver"
  | "usuarios:gerenciar"
  /* Equipe do PRÓPRIO cliente, vista de dentro do Portal (não confundir com
     "usuarios:*", que é a concessão de acesso pela ThermoProActive). */
  | "equipe:ver"
  | "equipe:gerenciar"
  /* Documentos técnicos */
  | "laudos:ver"
  | "laudos:emitir"
  | "laudos:assinar"
  /* Ordens de serviço */
  | "osp:ver"
  | "osp:criar"
  | "osp:mudar-status"
  /* Retorno de informação: o cliente devolve quando a corretiva foi planejada
     e executada, por quem, o que foi feito, se o diagnóstico se confirmou e
     quanto custou. É a ÚNICA escrita do Portal — ver, no backend,
     `OrdemServicoSerializer.CAMPOS_RETORNO_CLIENTE`. */
  | "osp:responder"
  /* Relatórios e exportações */
  | "relatorios:ver"
  | "relatorios:exportar"
  /* Prestadores de serviço terceirizados */
  | "prestadores:gerenciar";

const NIVEIS_QUE_EXCLUEM: Nivel[] = ["MASTER", "SENIOR"];

/** Resolve uma habilidade para um usuário. Única fonte da verdade no front. */
export function can(user: User | null | undefined, habilidade: Habilidade): boolean {
  if (!user) return false;

  const interno = user.is_interno;
  const cliente = user.is_cliente;
  // Confia no flag do backend quando ele vem; o nível é só fallback defensivo.
  const excluir = user.pode_excluir ?? NIVEIS_QUE_EXCLUEM.includes(user.nivel);
  const master = user.is_master;

  switch (habilidade) {
    case "area:admin":
      return interno;
    case "area:portal":
      return cliente;

    case "operacional:ver":
      return interno || cliente;
    case "operacional:criar":
    case "operacional:editar":
      return interno;
    case "operacional:excluir":
      return interno && excluir;

    case "clientes:gerenciar":
      return interno;

    case "parque:gerenciar":
      return interno;

    case "dados-sistema:ver":
      return interno;
    case "dados-sistema:curar":
      return user.pode_curar_dados_sistema ?? (interno && master);

    /* Só o Master concede acessos (backend: UserViewSet + IsMaster). Como o
       ViewSet inteiro exige Master, nem a leitura é liberada aos demais. */
    case "usuarios:ver":
    case "usuarios:gerenciar":
      return interno && master;

    /* Ver os colegas da própria empresa: qualquer usuário do Portal. Convidar
       (e um dia gerenciar) exige ser o Master do lado do cliente — é ele quem
       o backend deixa criar convites PORTAL para o próprio `cliente`
       (ConviteView + PodeConvidar). */
    case "equipe:ver":
      return cliente;
    case "equipe:gerenciar":
      return cliente && master;

    case "laudos:ver":
      return interno || cliente;
    case "laudos:emitir":
      return interno;
    /* Assinar exige registro em conselho de classe (CREA) — regra do Anexo I 3.1.2. */
    case "laudos:assinar":
      return interno && !!user.conselho_classe;

    case "osp:ver":
      return interno || cliente;
    case "osp:criar":
    case "osp:mudar-status":
      return interno;
    /* Qualquer nível do Portal responde: quem executou a corretiva costuma ser
       o manutentor, não o gestor. O backend também não exige Master aqui. */
    case "osp:responder":
      return interno || cliente;

    case "relatorios:ver":
    case "relatorios:exportar":
      return interno || cliente;

    case "prestadores:gerenciar":
      return interno;

    default:
      return false;
  }
}

/** Todas as habilidades precisam valer. */
export function canAll(user: User | null | undefined, habilidades: Habilidade[]): boolean {
  return habilidades.every((h) => can(user, h));
}

/** Basta uma habilidade valer. */
export function canAny(user: User | null | undefined, habilidades: Habilidade[]): boolean {
  return habilidades.some((h) => can(user, h));
}

/* ==========================================================================
   Rótulos de perfil — linguagem do usuário, não do banco.
   ========================================================================== */

export const PERFIL_LABEL: Record<Perfil, string> = {
  ADMIN: "Administrador",
  GESTOR: "Gestor / Supervisor",
  TECNICO: "Técnico / Analista",
  CLIENTE_CORP: "Cliente — Gestor Corporativo",
  CLIENTE_LOCAL: "Cliente — Gestor Local",
  CLIENTE_PCM: "Cliente — PCM",
  CLIENTE_MANUT: "Cliente — Manutentor",
};

export const NIVEL_LABEL: Record<Nivel, string> = {
  MASTER: "Master",
  SENIOR: "Sênior",
  PLENO: "Pleno",
  JUNIOR: "Júnior",
};

/** O que cada nível pode, em uma linha — usado na tela de usuários. */
export const NIVEL_RESUMO: Record<Nivel, string> = {
  MASTER: "Cura os dados de sistema, concede acessos e exclui registros.",
  SENIOR: "Opera inspeções, laudos e OSPs, e pode excluir registros.",
  PLENO: "Opera inspeções, laudos e OSPs. Não exclui registros.",
  JUNIOR: "Alimenta o sistema com acompanhamento. Não exclui registros.",
};

export const PERFIS_INTERNOS: Perfil[] = ["ADMIN", "GESTOR", "TECNICO"];
export const PERFIS_CLIENTE: Perfil[] = [
  "CLIENTE_CORP",
  "CLIENTE_LOCAL",
  "CLIENTE_PCM",
  "CLIENTE_MANUT",
];

/* ==========================================================================
   Guarda de rota — mapa declarativo prefixo → habilidade exigida.
   Ordem importa: o primeiro prefixo que casar decide.
   ========================================================================== */

type RegraRota = { prefixo: string; exige: Habilidade };

const REGRAS_ROTA: RegraRota[] = [
  { prefixo: "/portal/equipe", exige: "equipe:ver" },
  // A única tela de escrita do Portal: devolver as informações da execução de
  // uma OSP. Prefixo específico, checado ANTES do "/portal" genérico abaixo.
  // As rotas de cadastro que existiam aqui (/portal/equipamentos/novo,
  // /portal/ordens-servico/novo, /portal/inspecoes/editar) foram removidas
  // junto com as páginas em 2026-09-21.
  { prefixo: "/portal/ordens-servico/editar", exige: "osp:responder" },
  { prefixo: "/portal", exige: "area:portal" },
  { prefixo: "/usuarios", exige: "usuarios:ver" },
  { prefixo: "/cadastros", exige: "dados-sistema:ver" },
  { prefixo: "/clientes", exige: "clientes:gerenciar" },
  { prefixo: "/prestadores", exige: "prestadores:gerenciar" },
  { prefixo: "/equipamentos", exige: "clientes:gerenciar" },
  { prefixo: "/rotas", exige: "clientes:gerenciar" },
  { prefixo: "/inspecoes", exige: "operacional:ver" },
  { prefixo: "/relatorios-inspecao", exige: "operacional:ver" },
  { prefixo: "/servicos", exige: "operacional:ver" },
  { prefixo: "/osps", exige: "osp:ver" },
  { prefixo: "/laudos", exige: "laudos:ver" },
  { prefixo: "/relatorios", exige: "relatorios:ver" },
  { prefixo: "/alertas", exige: "operacional:ver" },
  { prefixo: "/notificacoes", exige: "operacional:ver" },
  { prefixo: "/dashboard", exige: "area:admin" },
];

/** A rota é permitida para este usuário? Rota sem regra é liberada a autenticados. */
export function podeAcessarRota(user: User | null | undefined, pathname: string): boolean {
  if (!user) return false;
  const regra = REGRAS_ROTA.find((r) => pathname === r.prefixo || pathname.startsWith(`${r.prefixo}/`));
  return regra ? can(user, regra.exige) : true;
}

/**
 * Onde este usuário deve cair ao entrar (ou quando bater numa rota proibida).
 * Cliente vai para o portal; equipe interna, para o painel operacional.
 */
export function rotaInicial(user: User | null | undefined): string {
  if (!user) return "/portal/login";
  return user.is_cliente ? "/portal/dashboard" : "/admin/dashboard";
}

/**
 * Rotas antigas de cliente → equivalente no portal. Links salvos pelo cliente
 * (favorito, e-mail antigo) continuam funcionando depois da separação dos portais.
 */
const EQUIVALENTE_NO_PORTAL: Record<string, string> = {
  "/laudos": "/portal/laudos",
  "/inspecoes": "/portal/inspecoes",
  "/osps": "/portal/ordens-servico",
  "/equipamentos": "/portal/equipamentos",
  "/relatorios": "/portal/relatorios",
  "/notificacoes": "/portal/alertas",
  "/dashboard": "/portal",
};

/** Destino de redirecionamento para um cliente que caiu numa rota interna. */
export function destinoNoPortal(pathname: string): string {
  const raiz = `/${pathname.split("/").filter(Boolean)[0] ?? ""}`;
  const base = EQUIVALENTE_NO_PORTAL[raiz];
  if (!base) return "/portal";
  // Preserva o /:id do detalhe (ex.: /laudos/12 → /portal/laudos/12).
  const resto = pathname.slice(raiz.length);
  return resto ? `${base}${resto}` : base;
}

/* ==========================================================================
   Hook de conveniência para componentes.
   ========================================================================== */

export function usePermissoes() {
  const { user } = useAuth();
  return useMemo(
    () => ({
      user,
      pode: (h: Habilidade) => can(user, h),
      podeTodas: (hs: Habilidade[]) => canAll(user, hs),
      podeAlguma: (hs: Habilidade[]) => canAny(user, hs),
      /* Atalhos usados o tempo todo nas telas. */
      interno: !!user?.is_interno,
      ehCliente: !!user?.is_cliente,
      master: !!user?.is_master,
      podeEditar: can(user, "operacional:editar"),
      podeExcluir: can(user, "operacional:excluir"),
    }),
    [user]
  );
}
