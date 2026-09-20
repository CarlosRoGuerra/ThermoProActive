import {
  Activity,
  Bell,
  Boxes,
  Building2,
  ClipboardCheck,
  ClipboardList,
  Database,
  Factory,
  FileChartColumn,
  FileText,
  Gauge,
  House,
  LifeBuoy,
  type LucideIcon,
  Map,
  ScrollText,
  Users,
  Wrench,
} from "lucide-react";
import type { Habilidade } from "./permissions";

/**
 * Arquitetura de navegação — declarativa, em um lugar só.
 *
 * Antes o menu era um array solto dentro do layout, com 8 itens no mesmo nível e
 * 12 sub-itens de "Dados de sistema" sem agrupamento. Aqui ele é dado:
 *   • itens agrupados por INTENÇÃO (o que a pessoa vem fazer), não por tabela;
 *   • cada item declara a habilidade que exige — quem não tem, não vê (e o
 *     guarda de rota impede o acesso direto por URL);
 *   • os dois portais usam a mesma estrutura, com conteúdos diferentes.
 */

export type ItemNav = {
  href: string;
  label: string;
  icon: LucideIcon;
  /** Habilidade necessária; sem ela o item não é montado. */
  exige?: Habilidade;
  /** Sub-itens abertos sob o item (submenu). */
  filhos?: { href: string; label: string; exige?: Habilidade }[];
  /** Casa também com estas rotas para marcar o item como ativo. */
  tambemAtivoEm?: string[];
  /** Chave do contador exibido à direita (ex.: alertas não lidos). */
  contador?: "alertas";
};

export type GrupoNav = {
  /** Rótulo da seção. `null` = itens sem cabeçalho (topo do menu). */
  titulo: string | null;
  itens: ItemNav[];
};

/* ==========================================================================
   PORTAL OPERACIONAL (equipe interna)
   ========================================================================== */

/** Tabelas de referência do sistema — curadas pelo nível Master. */
const DADOS_SISTEMA = [
  { href: "/cadastros?item=normas", label: "Normas (NBRs)" },
  { href: "/cadastros?item=tecnologias", label: "Tecnologias de análise" },
  { href: "/cadastros?item=instrumentos", label: "Instrumentação" },
  { href: "/cadastros?item=tipos-equipamento", label: "Tipos de equipamento" },
  { href: "/cadastros?item=tipos-componente", label: "Tipos de componente" },
  { href: "/cadastros?item=tipos-anomalia", label: "Tipos de anomalia" },
  { href: "/cadastros?item=tipos-recomendacao", label: "Tipos de recomendação" },
  { href: "/cadastros?item=criticidades", label: "Tipos de criticidade" },
  { href: "/cadastros?item=condicoes", label: "Condição do equipamento" },
  { href: "/cadastros?item=tipos-inspecao", label: "Tipos de inspeção" },
  { href: "/cadastros?item=falhas-recorrentes", label: "Falhas recorrentes" },
  { href: "/cadastros?item=grupos-acesso", label: "Grupos de acesso" },
];

/** Estrutura do cliente ativo — só aparece quando há um cliente em atendimento. */
const ESTRUTURA_CLIENTE = [
  { href: "/cadastros?item=areas", label: "Áreas" },
  { href: "/cadastros?item=setores", label: "Setores" },
  { href: "/equipamentos", label: "Equipamentos" },
  { href: "/rotas", label: "Rotas de inspeção" },
];

/** Fluxo campo → escritório (spec do Fabrício). */
const FLUXO_INSPECAO = [
  { href: "/inspecoes/campo", label: "Análise de campo" },
  { href: "/servicos", label: "Manutenção corretiva" },
  { href: "/inspecoes/final", label: "Análise final" },
  { href: "/relatorios-inspecao", label: "Relatório técnico" },
];

/**
 * @param temClienteAtivo Injeta a estrutura do cliente sob "Clientes".
 */
export function navAdmin(temClienteAtivo: boolean): GrupoNav[] {
  return [
    {
      titulo: null,
      itens: [
        { href: "/dashboard", label: "Visão geral", icon: Gauge, exige: "area:admin" },
        {
          href: "/clientes",
          label: "Clientes",
          icon: Building2,
          exige: "clientes:gerenciar",
          filhos: temClienteAtivo ? ESTRUTURA_CLIENTE : undefined,
        },
      ],
    },
    {
      titulo: "Operação",
      itens: [
        {
          href: "/inspecoes/campo",
          label: "Inspeções",
          icon: ClipboardList,
          exige: "operacional:ver",
          filhos: FLUXO_INSPECAO,
          tambemAtivoEm: ["/inspecoes", "/relatorios-inspecao", "/servicos"],
        },
        { href: "/osps", label: "Ordens de serviço", icon: Wrench, exige: "osp:ver" },
        { href: "/laudos", label: "Laudos técnicos", icon: FileText, exige: "laudos:ver" },
        { href: "/notificacoes", label: "Alertas", icon: Bell, exige: "operacional:ver", contador: "alertas" },
      ],
    },
    {
      titulo: "Análise",
      itens: [
        { href: "/relatorios", label: "Relatórios", icon: FileChartColumn, exige: "relatorios:ver" },
      ],
    },
    {
      titulo: "Administração",
      itens: [
        {
          href: "/usuarios",
          label: "Usuários e acessos",
          icon: Users,
          exige: "usuarios:ver",
          filhos: [
            { href: "/usuarios/solicitacoes", label: "Solicitações de acesso" },
          ],
        },
        { href: "/prestadores", label: "Prestadores", icon: Factory, exige: "prestadores:gerenciar" },
        {
          href: "/cadastros",
          label: "Dados de sistema",
          icon: Database,
          exige: "dados-sistema:ver",
          filhos: DADOS_SISTEMA,
        },
      ],
    },
  ];
}

/* ==========================================================================
   PORTAL DO CLIENTE
   --------------------------------------------------------------------------
   Sete itens, sem submenu, sem jargão interno. O cliente não precisa saber que
   existe "análise de campo" e "análise final": para ele é UMA inspeção. Nada de
   "OSP", "cadastros" ou "dados de sistema" aparece aqui.
   ========================================================================== */

export function navPortal(): GrupoNav[] {
  return [
    {
      titulo: null,
      itens: [
        { href: "/portal", label: "Início", icon: House },
        { href: "/portal/equipamentos", label: "Meus equipamentos", icon: Activity },
        { href: "/portal/alertas", label: "Alertas", icon: Bell, contador: "alertas" },
      ],
    },
    {
      titulo: "Serviços",
      itens: [
        { href: "/portal/inspecoes", label: "Inspeções", icon: ClipboardCheck },
        { href: "/portal/ordens-servico", label: "Ordens de serviço", icon: Wrench },
      ],
    },
    {
      titulo: "Documentos",
      itens: [
        { href: "/portal/laudos", label: "Laudos técnicos", icon: ScrollText },
        { href: "/portal/relatorios", label: "Relatórios", icon: FileChartColumn },
      ],
    },
    {
      titulo: "Minha empresa",
      itens: [{ href: "/portal/equipe", label: "Equipe", icon: Users }],
    },
    {
      titulo: "Ajuda",
      itens: [{ href: "/portal/ajuda", label: "Como usar o portal", icon: LifeBuoy }],
    },
  ];
}

/* ==========================================================================
   Trilha de navegação — rótulo por segmento de rota.
   Um lugar só, para que "relatorios-inspecao" nunca apareça cru na tela.
   ========================================================================== */

export const ROTULO_ROTA: Record<string, string> = {
  dashboard: "Visão geral",
  clientes: "Clientes",
  equipamentos: "Equipamentos",
  rotas: "Rotas de inspeção",
  inspecoes: "Inspeções",
  campo: "Análise de campo",
  final: "Análise final",
  "relatorios-inspecao": "Relatório técnico",
  servicos: "Manutenção corretiva",
  atividades: "Atividades",
  osps: "Ordens de serviço",
  laudos: "Laudos técnicos",
  relatorio: "Relatório completo",
  relatorios: "Relatórios",
  notificacoes: "Alertas",
  alertas: "Alertas",
  cadastros: "Dados de sistema",
  prestadores: "Prestadores",
  usuarios: "Usuários e acessos",
  solicitacoes: "Solicitações de acesso",
  equipe: "Equipe",
  portal: "Portal",
  "ordens-servico": "Ordens de serviço",
  ajuda: "Ajuda",
  perfil: "Meu perfil",
  novo: "Novo",
  nova: "Nova",
};

/** Rótulo de um segmento; ids numéricos viram "#123". */
export function rotuloSegmento(segmento: string): string {
  if (/^\d+$/.test(segmento)) return `#${segmento}`;
  return ROTULO_ROTA[segmento] ?? segmento.replace(/-/g, " ");
}

/**
 * Trilha derivada do pathname. A última entrada é a página atual (sem link).
 * Não inclui a raiz — o componente Breadcrumb já a adiciona.
 */
export function trilhaDe(pathname: string): { label: string; href?: string }[] {
  const segmentos = pathname.split("/").filter(Boolean);
  return segmentos.map((seg, i) => ({
    label: rotuloSegmento(seg),
    href: i < segmentos.length - 1 ? `/${segmentos.slice(0, i + 1).join("/")}` : undefined,
  }));
}

/** Título da página a partir da rota — usado na topbar quando não há outro. */
export function tituloDaRota(pathname: string): string {
  const segmentos = pathname.split("/").filter(Boolean);
  if (segmentos.length === 0) return "Início";
  // Ignora o id final para não intitular a página como "#123".
  const relevante = [...segmentos].reverse().find((s) => !/^\d+$/.test(s)) ?? segmentos[0];
  return rotuloSegmento(relevante);
}

/** Ícones reaproveitados por atalhos e estados vazios das telas do portal. */
export const ICONES_DOMINIO = {
  equipamento: Activity,
  inspecao: ClipboardCheck,
  osp: Wrench,
  laudo: ScrollText,
  relatorio: FileChartColumn,
  alerta: Bell,
  cliente: Building2,
  rota: Map,
  ajuda: LifeBuoy,
  parque: Boxes,
} satisfies Record<string, LucideIcon>;
