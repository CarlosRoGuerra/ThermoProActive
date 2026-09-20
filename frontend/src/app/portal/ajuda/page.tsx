"use client";

import Link from "next/link";
import {
  Activity,
  Bell,
  ClipboardCheck,
  FileChartColumn,
  LifeBuoy,
  Mail,
  Phone,
  ScrollText,
  Wrench,
  type LucideIcon,
} from "lucide-react";
import {
  Alert,
  Card,
  CardHeader,
  EstadoBadge,
  GRAUS,
  PageBody,
  PageHeader,
  SplitLayout,
} from "@/components/ds";
import { useAuth } from "@/lib/auth";
import { useRecurso } from "@/lib/recurso";
import { BoasVindasPortal, BotaoReabrirOrientacao, useRegistrarVisita } from "@/features/portal/onboarding";
import type { PortalVisaoGeral } from "@/lib/types";

/* ==========================================================================
   Portal do Cliente — Como usar o portal
   --------------------------------------------------------------------------
   Ajuda escrita, curta e no lugar onde a pessoa vai procurar. Substitui o tour
   guiado que ninguém completa: cada área do menu tem um parágrafo dizendo o que
   responde, e a escala de estados — o vocabulário do produto — é explicada uma
   vez, por extenso.
   ========================================================================== */

const AREAS: { icon: LucideIcon; titulo: string; href: string; texto: string }[] = [
  {
    icon: Activity,
    titulo: "Meus equipamentos",
    href: "/portal/equipamentos",
    texto:
      "A lista do seu parque monitorado. Cada linha mostra o estado apurado na última coleta e quando ela foi feita. Os equipamentos que exigem decisão aparecem no topo, sem precisar filtrar.",
  },
  {
    icon: Bell,
    titulo: "Alertas",
    href: "/portal/alertas",
    texto:
      "Tudo que exige a sua atenção: equipamento em condição crítica, ordem de serviço aberta, laudo publicado e prazo prestes a vencer. Os mesmos avisos chegam por e-mail.",
  },
  {
    icon: ClipboardCheck,
    titulo: "Inspeções",
    href: "/portal/inspecoes",
    texto:
      "O histórico das coletas feitas na sua planta. Abrindo uma inspeção você vê ponto por ponto: o que foi medido, com que valor e qual o resultado contra o limite da norma.",
  },
  {
    icon: Wrench,
    titulo: "Ordens de serviço",
    href: "/portal/ordens-servico",
    texto:
      "As intervenções recomendadas, com urgência e prazo. Elas nascem automaticamente de uma medição crítica — não é preciso solicitar.",
  },
  {
    icon: ScrollText,
    titulo: "Laudos técnicos",
    href: "/portal/laudos",
    texto:
      "Os documentos assinados pelo responsável técnico, com diagnóstico, recomendações e conclusão. Cada laudo tem também o relatório completo, pronto para imprimir ou salvar em PDF.",
  },
  {
    icon: FileChartColumn,
    titulo: "Relatórios",
    href: "/portal/relatorios",
    texto:
      "Consolidados por período para levar à reunião. Você confere o resultado na tela antes de exportar em PDF, Excel ou CSV.",
  },
];

const PERGUNTAS: { pergunta: string; resposta: string }[] = [
  {
    pergunta: "Posso editar alguma informação aqui?",
    resposta:
      "Não. O portal é de consulta: quem alimenta os dados técnicos é a equipe da ThermoProActive, com os instrumentos calibrados e as normas aplicáveis. Isso garante que o laudo tenha valor técnico.",
  },
  {
    pergunta: "O que significa “disponibilidade do parque”?",
    resposta:
      "É o percentual dos seus equipamentos monitorados que não teve nenhuma medição crítica na última coleta. É uma medida de condição mecânica, não de disponibilidade de produção.",
  },
  {
    pergunta: "Um equipamento aparece como “sem medição”. Isso é problema?",
    resposta:
      "Não. Significa que ele já está cadastrado, mas ainda não passou por uma coleta. Ele entra na próxima rota de inspeção.",
  },
  {
    pergunta: "Quem mais da minha empresa pode acessar?",
    resposta:
      "Os acessos são concedidos por perfil (gestor corporativo, gestor local, PCM e manutentor). Para incluir ou remover alguém, fale com o seu gestor de contrato — nós cadastramos.",
  },
  {
    pergunta: "Não estou recebendo os e-mails de alerta.",
    resposta:
      "Verifique a caixa de spam e confirme o e-mail no seu perfil. Se estiver correto, nos avise: os canais de envio são configurados do nosso lado.",
  },
];

export default function PortalAjudaPage() {
  useRegistrarVisita("ajuda");
  const { user } = useAuth();
  const { dados } = useRecurso<PortalVisaoGeral>("/portal/visao-geral/", "visão geral do portal");

  return (
    <PageBody>
      <PageHeader
        icon={LifeBuoy}
        title="Como usar o portal"
        description="O que cada área mostra, como ler os estados dos equipamentos e com quem falar quando precisar."
        trilha={[{ label: "Ajuda" }]}
        actions={<BotaoReabrirOrientacao />}
      />

      {user && <BoasVindasPortal user={user} visao={dados} sempreVisivel />}

      <SplitLayout
        principal={
          <>
            <Card>
              <CardHeader
                title="As áreas do portal"
                description="Cada item do menu responde a uma pergunta diferente."
              />
              <ul className="divide-y divide-border">
                {AREAS.map((a) => {
                  const Icone = a.icon;
                  return (
                    <li key={a.href} className="py-3.5 first:pt-0 last:pb-0">
                      <Link href={a.href} className="group flex gap-3.5 rounded-lg">
                        <span
                          className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary-subtle text-primary"
                          aria-hidden="true"
                        >
                          <Icone className="h-[1.125rem] w-[1.125rem]" />
                        </span>
                        <span className="min-w-0">
                          <span className="block text-sm font-semibold text-fg group-hover:text-primary">
                            {a.titulo}
                          </span>
                          <span className="mt-0.5 block text-sm text-fg-muted">{a.texto}</span>
                        </span>
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </Card>

            <Card>
              <CardHeader title="Perguntas frequentes" />
              <div className="divide-y divide-border">
                {PERGUNTAS.map((p) => (
                  <details key={p.pergunta} className="group py-3 first:pt-0 last:pb-0">
                    <summary className="cursor-pointer list-none text-sm font-medium text-fg marker:content-none">
                      <span className="inline-flex items-start gap-2">
                        <span
                          className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary transition-transform group-open:scale-150"
                          aria-hidden="true"
                        />
                        {p.pergunta}
                      </span>
                    </summary>
                    <p className="mt-2 pl-3.5 text-sm text-fg-muted">{p.resposta}</p>
                  </details>
                ))}
              </div>
            </Card>
          </>
        }
        apoio={
          <>
            <Card>
              <CardHeader
                title="A escala de estados"
                description="O mesmo vocabulário em toda a plataforma."
              />
              <ul className="space-y-3">
                {(["NORMAL", "ATENCAO", "ALERTA", "CRITICO", "SEM_DADOS"] as const).map((grau) => (
                  <li key={grau} className="text-sm">
                    <EstadoBadge grau={grau} />
                    <p className="mt-1 text-xs text-fg-muted">{GRAUS[grau].significado}</p>
                  </li>
                ))}
              </ul>
            </Card>

            <Card>
              <CardHeader title="Precisa falar com a gente?" />
              <Alert tone="info">
                Para dúvidas técnicas sobre um laudo, cite o número do documento — isso acelera a
                resposta.
              </Alert>
              <ul className="mt-4 space-y-3 text-sm">
                <li className="flex items-center gap-2.5">
                  <Mail className="h-4 w-4 shrink-0 text-fg-subtle" aria-hidden="true" />
                  <a href="mailto:contato@thermoproactive.com.br" className="text-primary hover:underline">
                    contato@thermoproactive.com.br
                  </a>
                </li>
                <li className="flex items-center gap-2.5">
                  <Phone className="h-4 w-4 shrink-0 text-fg-subtle" aria-hidden="true" />
                  <span className="text-fg-muted">
                    Fale com o seu gestor de contrato para atendimento direto.
                  </span>
                </li>
              </ul>
            </Card>
          </>
        }
      />
    </PageBody>
  );
}
