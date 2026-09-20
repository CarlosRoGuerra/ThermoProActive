"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowRight,
  Check,
  ClipboardCheck,
  LifeBuoy,
  ScrollText,
  Activity,
  X,
  type LucideIcon,
} from "lucide-react";
import { Button, Card, IconButton, LegendaEstados, ProgressBar, cn } from "@/components/ds";
import { primeiroNome } from "@/lib/format";
import type { PortalVisaoGeral, User } from "@/lib/types";

/* ==========================================================================
   Primeiro acesso ao Portal do Cliente
   --------------------------------------------------------------------------
   O problema relatado era "dificuldade de novos clientes". A resposta aqui NÃO
   é um tour de 8 passos que todo mundo pula — é um cartão de orientação que:

     • diz onde a pessoa está e o que este portal responde;
     • lista as 4 coisas que ela precisa saber achar, com link direto;
     • marca sozinho o que ela já viu (o progresso é real, não decorativo);
     • ensina a escala de estados — o vocabulário do produto — de uma vez;
     • desaparece quando o checklist termina, e pode ser fechado a qualquer
       momento sem perder nada (reabre em "Como usar o portal").

   O que já foi visitado fica no navegador desta pessoa. Não é dado de negócio:
   se o storage for limpo, o cartão volta e nada se perde.
   ========================================================================== */

type PassoId = "equipamentos" | "alertas" | "laudos" | "ajuda";

type Passo = {
  id: PassoId;
  titulo: string;
  descricao: string;
  href: string;
  icon: LucideIcon;
};

const PASSOS: Passo[] = [
  {
    id: "equipamentos",
    titulo: "Veja seus equipamentos",
    descricao: "A lista do seu parque, com o estado de cada máquina na última medição.",
    href: "/portal/equipamentos",
    icon: Activity,
  },
  {
    id: "alertas",
    titulo: "Saiba onde ficam os alertas",
    descricao: "Tudo que exige decisão sua chega aqui — e também por e-mail.",
    href: "/portal/alertas",
    icon: ClipboardCheck,
  },
  {
    id: "laudos",
    titulo: "Baixe um laudo técnico",
    descricao: "Os laudos assinados ficam disponíveis para consulta e download em PDF.",
    href: "/portal/laudos",
    icon: ScrollText,
  },
  {
    id: "ajuda",
    titulo: "Conheça o portal em 2 minutos",
    descricao: "O que cada área mostra e com quem falar quando precisar.",
    href: "/portal/ajuda",
    icon: LifeBuoy,
  },
];

const CHAVE_VISITADOS = "tpa-portal-visitados";
const CHAVE_FECHADO = "tpa-portal-boas-vindas-fechado";

function ler<T>(chave: string, padrao: T): T {
  try {
    const bruto = localStorage.getItem(chave);
    return bruto ? (JSON.parse(bruto) as T) : padrao;
  } catch {
    return padrao;
  }
}

function gravar(chave: string, valor: unknown) {
  try {
    localStorage.setItem(chave, JSON.stringify(valor));
  } catch {
    /* sem persistência: o cartão simplesmente reaparece na próxima visita */
  }
}

/** Marca um passo como visto. Chamado pelas próprias páginas do portal. */
export function marcarVisitado(id: PassoId) {
  const atuais = ler<PassoId[]>(CHAVE_VISITADOS, []);
  if (atuais.includes(id)) return;
  gravar(CHAVE_VISITADOS, [...atuais, id]);
}

/** Registra a visita a uma página do portal (usar no topo da página). */
export function useRegistrarVisita(id: PassoId) {
  useEffect(() => {
    marcarVisitado(id);
  }, [id]);
}

export function BoasVindasPortal({
  user,
  visao,
  /** `true` na página de ajuda: mostra sempre, sem botão de fechar. */
  sempreVisivel = false,
}: {
  user: User;
  visao: PortalVisaoGeral | null;
  sempreVisivel?: boolean;
}) {
  const [visitados, setVisitados] = useState<PassoId[]>([]);
  const [fechado, setFechado] = useState(true);
  const [montado, setMontado] = useState(false);

  useEffect(() => {
    setVisitados(ler<PassoId[]>(CHAVE_VISITADOS, []));
    setFechado(ler<boolean>(CHAVE_FECHADO, false));
    setMontado(true);
  }, []);

  // Só decide o que mostrar depois de ler o navegador — evita o cartão piscar.
  if (!montado) return null;

  const concluidos = PASSOS.filter((p) => visitados.includes(p.id)).length;
  const completo = concluidos === PASSOS.length;
  if (!sempreVisivel && (fechado || completo)) return null;

  function fechar() {
    setFechado(true);
    gravar(CHAVE_FECHADO, true);
  }

  const nome = primeiroNome(user.nome);
  const parque = visao?.indicadores.equipamentos_monitorados ?? 0;

  return (
    <Card padding={false} className="overflow-hidden">
      <div className="border-b border-border bg-primary-subtle/60 px-4 py-4 sm:px-5">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-2xs font-semibold uppercase tracking-wide text-primary-subtle-fg">
              Primeiros passos
            </p>
            <h2 className="mt-1 text-base font-semibold text-fg">
              {nome ? `${nome}, ` : ""}este é o seu portal de manutenção preditiva
            </h2>
            <p className="mt-1 max-w-2xl text-sm text-fg-muted">
              {parque > 0
                ? `Acompanhamos ${parque} equipamento${parque > 1 ? "s" : ""} da sua operação. `
                : ""}
              Aqui você vê o estado do seu parque, recebe os alertas do que precisa de decisão e
              baixa os laudos técnicos. Nada aqui é editável — a equipe técnica alimenta os dados,
              você acompanha o resultado.
            </p>
          </div>
          {!sempreVisivel && (
            <IconButton icon={X} label="Fechar orientação" onClick={fechar} size="sm" />
          )}
        </div>

        <div className="mt-3.5 flex items-center gap-3">
          <ProgressBar
            valor={concluidos}
            max={PASSOS.length}
            label="Progresso dos primeiros passos"
            className="max-w-48 flex-1"
          />
          <span className="shrink-0 text-xs font-medium text-fg-muted">
            {concluidos} de {PASSOS.length}
          </span>
        </div>
      </div>

      <ol className="divide-y divide-border">
        {PASSOS.map((passo, i) => {
          const visto = visitados.includes(passo.id);
          const Icone = passo.icon;
          return (
            <li key={passo.id}>
              <Link
                href={passo.href}
                className="flex items-center gap-3.5 px-4 py-3 transition-colors hover:bg-surface-muted sm:px-5"
              >
                <span
                  className={cn(
                    "flex h-8 w-8 shrink-0 items-center justify-center rounded-lg",
                    visto ? "bg-success-subtle text-success-fg" : "bg-surface-muted text-fg-subtle"
                  )}
                  aria-hidden="true"
                >
                  {visto ? <Check className="h-4 w-4" strokeWidth={3} /> : <Icone className="h-4 w-4" />}
                </span>
                <span className="min-w-0 flex-1">
                  <span className={cn("block text-sm font-medium", visto ? "text-fg-muted" : "text-fg")}>
                    {i + 1}. {passo.titulo}
                    {visto && <span className="sr-only"> (concluído)</span>}
                  </span>
                  <span className="block text-xs text-fg-muted">{passo.descricao}</span>
                </span>
                <ArrowRight className="h-4 w-4 shrink-0 text-fg-subtle" aria-hidden="true" />
              </Link>
            </li>
          );
        })}
      </ol>

      <div className="border-t border-border bg-surface-muted/40 px-4 py-3.5 sm:px-5">
        <p className="mb-2 text-2xs font-semibold uppercase tracking-wide text-fg-subtle">
          Como ler o estado de um equipamento
        </p>
        <LegendaEstados graus={["NORMAL", "ATENCAO", "ALERTA", "CRITICO"]} />
      </div>
    </Card>
  );
}

/** Reabre a orientação — botão na página de ajuda. */
export function BotaoReabrirOrientacao() {
  const [reaberto, setReaberto] = useState(false);
  return (
    <Button
      variant="secondary"
      size="sm"
      success={reaberto}
      onClick={() => {
        gravar(CHAVE_FECHADO, false);
        gravar(CHAVE_VISITADOS, []);
        setReaberto(true);
      }}
    >
      Recomeçar os primeiros passos
    </Button>
  );
}
