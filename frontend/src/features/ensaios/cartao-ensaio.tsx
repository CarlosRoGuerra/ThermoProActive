"use client";

import { useMemo, useState } from "react";
import { FlaskConical, Plus, Save } from "lucide-react";
import { api } from "@/lib/api";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  Field,
  FormGrid,
  Input,
  Select,
  Textarea,
  useToast,
  type Tom,
} from "@/components/ds";
import type { SituacaoEnsaio, StatusEnsaio } from "@/features/relatorio-inspecao/tipos";
import { CRITICIDADES, SITUACOES, type Criticidade, type EnsaioCatalogo, type InstrumentoOpcao, type ResultadoApi } from "./tipos";
import { EditorValores, camposIniciais, valoresParaApi, type CamposValores } from "./valores";

/* ==========================================================================
   Um ensaio do transformador (FQ, CR, PCB, 2-FAL, R×T, R×I, R×O): situação,
   valores e laudo. Gravar devolve a avaliação calculada pelo servidor — erro
   do R×T, IP/IA, TG/TGC, conformidade — com as regras do relatório.
   ========================================================================== */

const TOM_STATUS: Record<StatusEnsaio, Tom> = {
  CONFORME: "success",
  NAO_CONFORME: "danger",
  SEM_CRITERIO: "neutral",
  NAO_COLETADO: "warning",
  NAO_REALIZADO: "warning",
  SEM_RESULTADO: "neutral",
};

const ROTULO_SIGLA: Record<string, string> = { "2FAL": "2-FAL", RXT: "R×T", RXI: "R×I", RXO: "R×O" };
export const rotuloEnsaio = (sigla: string) => ROTULO_SIGLA[sigla] ?? sigla;
/** "FQ — Físico-Químico"; quando o nome é a própria sigla (2-FAL), só ela. */
export const tituloEnsaio = (e: { sigla: string; nome: string }) =>
  rotuloEnsaio(e.sigla) === e.nome ? e.nome : `${rotuloEnsaio(e.sigla)} — ${e.nome}`;

type Laudo = {
  situacao: SituacaoEnsaio;
  numero_laudo: string;
  criticidade: Criticidade;
  data_analise: string;
  data_proxima: string;
  instrumento: string;
  conclusao: string;
  recomendacao: string;
  informacoes_adicionais: string;
};

function laudoDe(r: ResultadoApi | null): Laudo {
  return {
    situacao: r?.situacao ?? "REALIZADO",
    numero_laudo: r?.numero_laudo ?? "",
    criticidade: r?.criticidade ?? "",
    data_analise: r?.data_analise ?? "",
    data_proxima: r?.data_proxima ?? "",
    instrumento: r?.instrumento ? String(r.instrumento) : "",
    conclusao: r?.conclusao ?? "",
    recomendacao: r?.recomendacao ?? "",
    informacoes_adicionais: r?.informacoes_adicionais ?? "",
  };
}

const rotuloInstrumento = (i: InstrumentoOpcao) =>
  [i.tipo, [i.marca, i.modelo].filter(Boolean).join(" "), i.numero_serie && `(${i.numero_serie})`].filter(Boolean).join(" — ");

export function CartaoEnsaio({
  itemId, ensaio, resultado, solicitado, instrumentos, podeEditar, onSalvo,
}: {
  itemId: number;
  ensaio: EnsaioCatalogo;
  resultado: ResultadoApi | null;
  solicitado: boolean;
  instrumentos: InstrumentoOpcao[];
  podeEditar: boolean;
  onSalvo: (r: ResultadoApi) => void;
}) {
  const toast = useToast();
  // Aberto quando há resultado ou o registro de campo pediu o ensaio (inclusive se
  // o pedido chega depois, ao salvar a coleta); os demais, só por escolha.
  const [abertoManual, setAberto] = useState(false);
  const aberto = abertoManual || !!resultado || solicitado;
  const [laudo, setLaudo] = useState<Laudo>(() => laudoDe(resultado));
  const [campos, setCampos] = useState<CamposValores>(() => camposIniciais(ensaio, resultado?.valores ?? []));
  const [erros, setErros] = useState<Record<string, string>>({});
  const [alterado, setAlterado] = useState(false);
  const [salvando, setSalvando] = useState(false);

  // Sem amostra ou sem ensaio não há valores: a ficha sai com a situação e o laudo.
  const semValores = laudo.situacao === "NAO_COLETADO" || laudo.situacao === "NAO_REALIZADO";
  const avaliacao = resultado && !alterado ? resultado.avaliacao : null;
  const status = resultado?.avaliacao.status;
  const opcoesInstrumento = useMemo(() => instrumentos.map((i) => ({ id: i.id, rotulo: rotuloInstrumento(i) })), [instrumentos]);

  function mudarLaudo(parcial: Partial<Laudo>) {
    setLaudo((l) => ({ ...l, ...parcial }));
    setAlterado(true);
  }

  async function salvar() {
    const { valores, erros: errosValores } = semValores ? { valores: [], erros: {} } : valoresParaApi(ensaio, campos);
    setErros(errosValores);
    if (Object.keys(errosValores).length) {
      toast.erro("Há valores inválidos", { descricao: "Corrija os campos marcados antes de salvar." });
      return;
    }
    setSalvando(true);
    try {
      const body = {
        item: itemId, ensaio: ensaio.id, ...laudo,
        data_analise: laudo.data_analise || null, data_proxima: laudo.data_proxima || null,
        instrumento: laudo.instrumento ? Number(laudo.instrumento) : null,
        valores,
      };
      const salvo = await api<ResultadoApi>(resultado ? `/resultados-ensaio/${resultado.id}/` : "/resultados-ensaio/", {
        method: resultado ? "PATCH" : "POST", body,
      });
      setAlterado(false);
      toast.sucesso(`${rotuloEnsaio(ensaio.sigla)} salvo — ${salvo.avaliacao.status_rotulo.toLowerCase()}`);
      onSalvo(salvo);
    } catch (e) {
      toast.falha(e, `Não foi possível salvar o ${rotuloEnsaio(ensaio.sigla)}.`);
    } finally {
      setSalvando(false);
    }
  }

  const bloqueado = !podeEditar || salvando;
  const titulo = tituloEnsaio(ensaio);

  return (
    <Card>
      <CardHeader
        icon={FlaskConical}
        title={titulo}
        description={solicitado ? "Solicitado no registro de campo" : "Não solicitado no registro de campo"}
        actions={
          status ? (
            <Badge tone={TOM_STATUS[status]}>{resultado?.avaliacao.status_rotulo}</Badge>
          ) : (
            <Badge tone="neutral">Sem resultado</Badge>
          )
        }
      />

      {!aberto ? (
        podeEditar ? (
          <Button size="sm" variant="secondary" icon={Plus} onClick={() => setAberto(true)}>
            Lançar resultado
          </Button>
        ) : (
          <p className="text-sm text-fg-muted">Sem resultado registrado.</p>
        )
      ) : (
        <div className="space-y-5">
          <FormGrid colunas={3}>
            <Field label="Situação">
              <Select value={laudo.situacao} disabled={bloqueado}
                onChange={(e) => mudarLaudo({ situacao: e.target.value as SituacaoEnsaio })}>
                {SITUACOES.map((s) => <option key={s.valor} value={s.valor}>{s.label}</option>)}
              </Select>
            </Field>
            <Field label="Número do laudo">
              <Input value={laudo.numero_laudo} maxLength={40} tecnico disabled={bloqueado}
                onChange={(e) => mudarLaudo({ numero_laudo: e.target.value })} />
            </Field>
            <Field label="Criticidade" hint="Do laudo — não é o Grau de Risco">
              <Select value={laudo.criticidade} disabled={bloqueado}
                onChange={(e) => mudarLaudo({ criticidade: e.target.value as Criticidade })}>
                {CRITICIDADES.map((c) => <option key={c.valor} value={c.valor}>{c.label}</option>)}
              </Select>
            </Field>
          </FormGrid>

          {!semValores && (
            <section>
              <h3 className="mb-2 text-sm font-semibold text-fg">Valores obtidos</h3>
              <EditorValores
                ensaio={ensaio}
                campos={campos}
                onMudar={(c) => {
                  setCampos(c);
                  setAlterado(true);
                }}
                erros={erros}
                avaliacao={avaliacao}
                disabled={bloqueado}
              />
              {alterado && resultado && (
                <p className="mt-2 text-xs text-fg-subtle">Alterações ainda não salvas — os cálculos voltam depois de salvar.</p>
              )}
            </section>
          )}

          <FormGrid colunas={3}>
            <Field label="Data da análise">
              <Input type="date" value={laudo.data_analise} disabled={bloqueado}
                onChange={(e) => mudarLaudo({ data_analise: e.target.value })} />
            </Field>
            <Field label={ensaio.rotulo_proxima}>
              <Input type="date" value={laudo.data_proxima} disabled={bloqueado}
                onChange={(e) => mudarLaudo({ data_proxima: e.target.value })} />
            </Field>
            <Field label="Instrumento" hint={instrumentos.length ? undefined : "Nenhum instrumento vinculado a esta tecnologia"}>
              <Select value={laudo.instrumento} disabled={bloqueado || !instrumentos.length}
                onChange={(e) => mudarLaudo({ instrumento: e.target.value })}>
                <option value="">—</option>
                {opcoesInstrumento.map((i) => <option key={i.id} value={i.id}>{i.rotulo}</option>)}
              </Select>
            </Field>
          </FormGrid>

          <FormGrid colunas={1}>
            <Field label={ensaio.rotulo_conclusao}>
              <Textarea rows={2} value={laudo.conclusao} disabled={bloqueado}
                onChange={(e) => mudarLaudo({ conclusao: e.target.value })} />
            </Field>
            <Field label="Recomendação">
              <Textarea rows={2} value={laudo.recomendacao} disabled={bloqueado}
                onChange={(e) => mudarLaudo({ recomendacao: e.target.value })} />
            </Field>
            <Field label="Informações adicionais">
              <Textarea rows={2} value={laudo.informacoes_adicionais} disabled={bloqueado}
                onChange={(e) => mudarLaudo({ informacoes_adicionais: e.target.value })} />
            </Field>
          </FormGrid>

          {podeEditar && (
            <div className="flex justify-end">
              <Button icon={Save} loading={salvando} onClick={salvar}>
                Salvar {rotuloEnsaio(ensaio.sigla)}
              </Button>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}
