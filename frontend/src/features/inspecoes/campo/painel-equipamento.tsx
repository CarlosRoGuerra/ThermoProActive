"use client";

import { useState } from "react";
import {
  ChevronDown,
  ClipboardCheck,
  CopyPlus,
  Pencil,
  Plus,
  Trash2,
  TriangleAlert,
} from "lucide-react";
import {
  Alert,
  Badge,
  Button,
  Card,
  CardHeader,
  DescriptionList,
  EmptyState,
  Field,
  SemDado,
  Select,
  Skeleton,
  cn,
} from "@/components/ds";
import { useRecurso } from "@/lib/recurso";
import { numeroUnidade } from "@/lib/format";
import type { Achado, Condicao, Equipamento, ItemInspecao } from "@/lib/types";
import { EXPLICACAO_ESTADO, ROTULO_ESTADO, estadoDoItem } from "./progresso";

/* ==========================================================================
   Painel do equipamento — a coluna direita da folha de campo.
   --------------------------------------------------------------------------
   Tudo o que o técnico faz num equipamento acontece aqui, sem trocar de página:
   ver a identificação, definir a condição e registrar as análises.

   A ficha técnica é buscada sob demanda (só do equipamento aberto) e fica
   recolhida: no campo o que importa é a TAG e o estado; a placa é consulta
   ocasional.
   ========================================================================== */

export function PainelEquipamento({
  item,
  condicoes,
  podeEditar,
  ehCorretiva,
  salvandoCondicao,
  onDefinirCondicao,
  onNovaAnalise,
  onEditarAnalise,
  onRemoverAnalise,
  onAnalisarCorretiva,
  onAdicionarLinha,
  onRemoverItem,
}: {
  item: ItemInspecao;
  condicoes: Condicao[];
  podeEditar: boolean;
  ehCorretiva: boolean;
  salvandoCondicao: boolean;
  onDefinirCondicao: (valor: string) => void;
  onNovaAnalise: () => void;
  onEditarAnalise: (a: Achado) => void;
  onRemoverAnalise: (a: Achado) => void;
  onAnalisarCorretiva: () => void;
  onAdicionarLinha: () => void;
  onRemoverItem: () => void;
}) {
  const estado = estadoDoItem(item);
  const condicaoAtual = condicoes.find((c) => c.id === item.condicao) ?? null;
  const exigeAcao = !!condicaoAtual?.gera_acao;
  const achados = item.achados ?? [];

  return (
    <div className="space-y-4">
      {/* ---------- Identificação ---------- */}
      <Card>
        <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
          <div className="min-w-0">
            <p className="data text-lg font-semibold text-fg">{item.equipamento_tag}</p>
            <p className="text-sm text-fg-muted">{item.equipamento_nome}</p>
            {/* Caminho hierárquico: o contexto não se perde. */}
            <p className="mt-1 text-xs text-fg-subtle">
              {item.area_nome} <span aria-hidden="true">/</span> {item.setor_nome}
              {item.tipo_equipamento_nome && (
                <>
                  {" "}
                  <span aria-hidden="true">·</span> {item.tipo_equipamento_nome}
                </>
              )}
            </p>
          </div>
          <Badge
            tone={
              estado === "PENDENTE"
                ? "neutral"
                : estado === "INCOMPLETO"
                ? "warning"
                : estado === "COM_ACHADO"
                ? "danger"
                : "success"
            }
            title={EXPLICACAO_ESTADO[estado]}
          >
            {ROTULO_ESTADO[estado]}
          </Badge>
        </div>

        <FichaTecnica equipamentoId={item.equipamento} />
      </Card>

      {/* ---------- Condição ---------- */}
      <Card>
        <CardHeader
          title="Condição do equipamento"
          description="É ela que libera a transferência e define se há ação a registrar."
        />
        <Field
          label="Condição"
          obrigatorio
          hint={
            condicaoAtual?.descricao ||
            (item.condicao == null
              ? "Defina a condição deste equipamento antes de concluir a análise."
              : undefined)
          }
        >
          <Select
            value={item.condicao != null ? String(item.condicao) : ""}
            onChange={(e) => onDefinirCondicao(e.target.value)}
            disabled={!podeEditar || salvandoCondicao}
          >
            <option value="">Selecione a condição…</option>
            {condicoes.map((c) => (
              <option key={c.id} value={c.id}>
                {c.sigla ? `${c.sigla} — ${c.nome}` : c.nome}
              </option>
            ))}
          </Select>
        </Field>

        {condicaoAtual && (
          <div className="mt-3">
            {exigeAcao ? (
              achados.length === 0 ? (
                <Alert tone="warning" icon={TriangleAlert} title="Esta condição exige ação">
                  Registre ao menos uma análise para este equipamento — é ela que vira achado,
                  ordem de serviço e folha no relatório técnico.
                </Alert>
              ) : (
                <Alert tone="info">
                  {achados.length === 1
                    ? "1 análise registrada."
                    : `${achados.length} análises registradas.`}{" "}
                  Elas seguem para revisão na Análise final.
                </Alert>
              )
            ) : (
              <Alert tone="success">
                Equipamento inspecionado sem necessidade de ação. Pode seguir para o próximo.
              </Alert>
            )}
          </div>
        )}
      </Card>

      {/* ---------- Análises ---------- */}
      <Card>
        <CardHeader
          title="Análises registradas"
          description={
            ehCorretiva
              ? "Nesta tecnologia corretiva, a análise técnica é feita no painel do serviço."
              : "Um equipamento pode ter mais de uma análise — um achado por componente/anomalia."
          }
          actions={
            podeEditar ? (
              ehCorretiva ? (
                <Button size="sm" icon={ClipboardCheck} onClick={onAnalisarCorretiva}>
                  {item.analise ? "Abrir análise" : "Iniciar análise"}
                </Button>
              ) : (
                <Button size="sm" icon={Plus} onClick={onNovaAnalise}>
                  Nova análise
                </Button>
              )
            ) : undefined
          }
        />

        {ehCorretiva ? (
          <p className="text-sm text-fg-muted">
            {item.analise
              ? "Análise iniciada para este equipamento."
              : "Nenhuma análise iniciada ainda."}
          </p>
        ) : achados.length === 0 ? (
          <EmptyState
            compacto
            icon={ClipboardCheck}
            title="Nenhuma análise neste equipamento"
            description={
              exigeAcao
                ? "A condição escolhida exige ação: registre o componente, a anomalia e a recomendação."
                : "Não é obrigatório: a condição atual não exige ação."
            }
            action={
              podeEditar ? (
                <Button size="sm" icon={Plus} onClick={onNovaAnalise}>
                  Registrar análise
                </Button>
              ) : undefined
            }
          />
        ) : (
          <ul className="space-y-2">
            {achados.map((a) => (
              <li
                key={a.id}
                className="flex items-start justify-between gap-3 rounded-lg bg-surface-muted/60 px-3 py-2.5"
              >
                <div className="min-w-0 text-sm">
                  <div className="flex flex-wrap items-center gap-1.5">
                    {(a.condicao_sigla || a.condicao_nome) && (
                      <Badge tone="warning">{a.condicao_sigla || a.condicao_nome}</Badge>
                    )}
                    <span className="font-medium text-fg">
                      {a.tipo_componente_nome || a.componente_texto || "Análise"}
                    </span>
                  </div>
                  {(a.tipo_anomalia_nome || a.anomalia_texto) && (
                    <p className="mt-0.5 text-xs text-fg-muted">
                      {a.tipo_anomalia_nome || a.anomalia_texto}
                    </p>
                  )}
                  {a.numero_osp && (
                    <p className="data mt-1 text-2xs text-fg-subtle">OSP {a.numero_osp}</p>
                  )}
                </div>
                {podeEditar && (
                  <div className="flex shrink-0 items-center gap-1">
                    <Button size="xs" variant="ghost" icon={Pencil} onClick={() => onEditarAnalise(a)}>
                      Editar
                    </Button>
                    <Button
                      size="xs"
                      variant="ghost"
                      icon={Trash2}
                      onClick={() => onRemoverAnalise(a)}
                      className="text-danger-fg hover:bg-danger-subtle"
                    >
                      <span className="sr-only">Remover análise</span>
                    </Button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </Card>

      {/* ---------- Ações da linha ----------
          Só no fluxo preditivo: na manutenção corretiva o item carrega o
          ServicoCampo/plano de balanceamento (1:1 com o equipamento) — duplicar
          ou remover a linha por aqui quebraria essa relação, e a folha original
          nunca ofereceu isso para itens corretivos. */}
      {podeEditar && !ehCorretiva && (
        <div className="flex flex-wrap items-center gap-2">
          <Button
            size="sm"
            variant="secondary"
            icon={CopyPlus}
            onClick={onAdicionarLinha}
            title="Alguns equipamentos são medidos mais de uma vez na mesma rota"
          >
            Nova linha deste equipamento
          </Button>
          <Button
            size="sm"
            variant="ghost"
            icon={Trash2}
            onClick={onRemoverItem}
            className="text-danger-fg hover:bg-danger-subtle"
          >
            Remover da folha
          </Button>
        </div>
      )}
    </div>
  );
}

/**
 * Ficha de placa do equipamento — recolhida por padrão.
 * Só busca quando o técnico abre, e só do equipamento em tela.
 */
function FichaTecnica({ equipamentoId }: { equipamentoId: number }) {
  const [aberta, setAberta] = useState(false);
  const { dados, carregando } = useRecurso<Equipamento>(
    aberta ? `/equipamentos/${equipamentoId}/` : null,
    "dados técnicos do equipamento"
  );

  return (
    <div className="mt-4 border-t border-border pt-3">
      <button
        type="button"
        onClick={() => setAberta((v) => !v)}
        aria-expanded={aberta}
        className="inline-flex items-center gap-1.5 text-xs font-medium text-fg-muted transition-colors hover:text-fg"
      >
        <ChevronDown
          className={cn("h-3.5 w-3.5 transition-transform duration-fast", aberta && "rotate-180")}
          aria-hidden="true"
        />
        Ficha técnica do equipamento
      </button>

      {aberta && (
        <div className="mt-3">
          {carregando ? (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {Array.from({ length: 8 }).map((_, i) => (
                <div key={i}>
                  <Skeleton className="h-2.5 w-16" />
                  <Skeleton className="mt-1.5 h-3.5 w-24" />
                </div>
              ))}
            </div>
          ) : !dados ? (
            <p className="text-xs text-fg-subtle">Não foi possível carregar a ficha agora.</p>
          ) : (
            <DescriptionList
              colunas={4}
              items={[
                { label: "Fabricante", value: dados.fabricante || <SemDado /> },
                { label: "Modelo", value: dados.modelo || <SemDado /> },
                { label: "Nº de série", value: dados.numero_serie || <SemDado />, tecnico: true },
                {
                  label: "Potência",
                  value: dados.potencia_kw ? numeroUnidade(dados.potencia_kw, "kW") : <SemDado />,
                  tecnico: true,
                },
                {
                  label: "Rotação",
                  value: dados.rotacao_nominal_rpm ? `${dados.rotacao_nominal_rpm} RPM` : <SemDado />,
                  tecnico: true,
                },
                {
                  label: "Classe ISO",
                  value: dados.classe_iso ? (
                    <Badge tone="primary" title={dados.classe_iso_display}>
                      {dados.classe_iso}
                    </Badge>
                  ) : (
                    <SemDado />
                  ),
                },
                {
                  label: "Classe do ativo",
                  value: dados.criticidade ? dados.criticidade_display : <SemDado />,
                },
                {
                  label: "Equipamento pai",
                  value: dados.equipamento_pai_tag || <SemDado>Principal</SemDado>,
                  tecnico: !!dados.equipamento_pai_tag,
                },
              ]}
            />
          )}
        </div>
      )}
    </div>
  );
}
