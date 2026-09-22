"use client";

import { Fragment, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Calculator, ClipboardPen, Save, Stethoscope } from "lucide-react";
import { api } from "@/lib/api";
import {
  Alert,
  Badge,
  Button,
  Card,
  CardHeader,
  DescriptionList,
  ErrorCard,
  Field,
  FormActions,
  Input,
  LoadingState,
  PageBody,
  PageHeader,
  Select,
  SemDado,
  Textarea,
  useToast,
} from "@/components/ds";
import { useLista, useMutacao, useRecurso } from "@/lib/recurso";
import { data as fmtData, texto } from "@/lib/format";
import type { OrdemServico, User } from "@/lib/types";

/* ==========================================================================
   Portal do Cliente — Retorno de informação da OSP
   --------------------------------------------------------------------------
   A ÚNICA tela de escrita do Portal. O cliente não abre nem edita a ordem: ele
   devolve o que só ele sabe depois de executar a corretiva — quando planejou,
   quando executou, quem executou, o que foi feito, se a abertura da máquina
   confirmou o diagnóstico e quanto custou de fato.

   Por que esses campos e não outros: o backend recusa o resto. A lista aqui
   espelha `OrdemServicoSerializer.CAMPOS_RETORNO_CLIENTE`; qualquer campo a
   mais que este formulário mandasse seria descartado silenciosamente pelo DRF.

   O diagnóstico da ThermoProActive aparece em cima, somente leitura, porque é
   ele que dá sentido ao preenchimento: você responde sobre o que foi
   recomendado.
   ========================================================================== */

/** Linhas da tabela "Avaliação de Resultados". `temQtd` = a linha tem coluna Qtde. */
const LINHAS_ROI = [
  { chave: "mao_obra", rotulo: "Mão de obra (h)", temQtd: true },
  { chave: "terceirizado", rotulo: "Serviço terceirizado (h)", temQtd: true },
  { chave: "material", rotulo: "Material de reparo (R$)", temQtd: false },
  { chave: "producao", rotulo: "Produção (h/ton)", temQtd: true },
  { chave: "outros", rotulo: "Outros (R$)", temQtd: false },
] as const;

type Campos = Record<string, string>;

function moeda(v: number) {
  return v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

/** ISO do servidor → valor aceito por <input type="datetime-local">. */
function paraCampoDataHora(iso?: string | null) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(
    d.getMinutes()
  )}`;
}

export function RetornoOsp({ ospId }: { ospId: number }) {
  const router = useRouter();
  const toast = useToast();
  const { dados: osp, falha, carregando, recarregar } = useRecurso<
    OrdemServico & Record<string, unknown>
  >(`/osps/${ospId}/`, "ordem de serviço");
  // Quem planejou/executou/finalizou sai da própria equipe — o backend recusa
  // apontar alguém de outra empresa, então a lista já vem recortada de lá.
  const { itens: equipe } = useLista<User>("/minha-equipe/?page_size=200", "equipe da empresa");
  const mutacao = useMutacao("retorno da ordem de serviço");
  const [msg, setMsg] = useState<string | null>(null);

  const [campos, setCampos] = useState<Campos>({
    planejado_em: "", planejado_por: "",
    executado_em: "", executado_por: "",
    finalizado_por: "", descricao_corretiva: "", resultado_confirmacao: "PENDENTE",
  });
  const [roi, setRoi] = useState<Campos>({});
  const set = (c: string, v: string) => setCampos((f) => ({ ...f, [c]: v }));
  const setR = (c: string, v: string) => setRoi((f) => ({ ...f, [c]: v }));

  useEffect(() => {
    if (!osp) return;
    setCampos({
      planejado_em: paraCampoDataHora(osp.planejado_em as string | null),
      planejado_por: osp.planejado_por ? String(osp.planejado_por) : "",
      executado_em: paraCampoDataHora(osp.executado_em as string | null),
      executado_por: osp.executado_por ? String(osp.executado_por) : "",
      finalizado_por: osp.finalizado_por ? String(osp.finalizado_por) : "",
      descricao_corretiva: (osp.descricao_corretiva as string) ?? "",
      resultado_confirmacao: (osp.resultado_confirmacao as string) ?? "PENDENTE",
    });
    const r: Campos = {};
    for (const p of ["pred", "emerg"]) {
      for (const l of LINHAS_ROI) {
        if (l.temQtd) {
          const kq = `${p}_${l.chave}_h`;
          r[kq] = osp[kq] ? String(osp[kq]) : "";
        }
        const kv = `${p}_${l.chave}_valor`;
        r[kv] = osp[kv] ? String(osp[kv]) : "";
      }
    }
    setRoi(r);
  }, [osp]);

  // Totais ao vivo, como na tabela verde do relatório.
  const totais = useMemo(() => {
    const soma = (p: string) =>
      LINHAS_ROI.reduce((acc, l) => acc + (Number(roi[`${p}_${l.chave}_valor`]) || 0), 0);
    const pred = soma("pred");
    const emerg = soma("emerg");
    return { pred, emerg, retorno: emerg - pred };
  }, [roi]);

  async function salvar() {
    setMsg(null);
    const body: Record<string, unknown> = {
      planejado_em: campos.planejado_em || null,
      planejado_por: campos.planejado_por || null,
      executado_em: campos.executado_em || null,
      executado_por: campos.executado_por || null,
      finalizado_por: campos.finalizado_por || null,
      descricao_corretiva: campos.descricao_corretiva,
      resultado_confirmacao: campos.resultado_confirmacao,
    };
    for (const [k, v] of Object.entries(roi)) body[k] = v === "" ? null : Number(v);
    const r = await mutacao.executar(() => api(`/osps/${ospId}/`, { method: "PATCH", body }));
    if (r.ok) {
      toast.sucesso("Retorno enviado", { descricao: "A equipe técnica já consegue ver." });
      router.push("/portal/ordens-servico");
    } else {
      setMsg(r.falha.descricao || r.falha.titulo);
    }
  }

  if (carregando) {
    return <LoadingState variante="formulario" linhas={4} label="Carregando a ordem de serviço…" />;
  }
  if (falha) return <ErrorCard falha={falha} onRetry={recarregar} />;
  if (!osp) return null;

  const pessoas = (
    <>
      <option value="">— não informado —</option>
      {equipe.map((u) => (
        <option key={u.id} value={u.id}>
          {u.nome}
        </option>
      ))}
    </>
  );

  return (
    <PageBody>
      <PageHeader
        icon={ClipboardPen}
        title={`Informar execução — OSP ${osp.numero}`}
        description="Depois que a corretiva for feita, registre aqui o que aconteceu. É esse retorno que fecha o ciclo da manutenção preditiva e alimenta o retorno do investimento no relatório técnico."
        trilha={[
          { label: "Ordens de serviço", href: "/portal/ordens-servico" },
          { label: osp.numero },
        ]}
        selo={<Badge tone="neutral">{osp.status_display}</Badge>}
      />

      {/* --- O que foi recomendado (leitura) --- */}
      <Card>
        <CardHeader
          icon={Stethoscope}
          title="O que a ThermoProActive recomendou"
          description="Diagnóstico técnico da última coleta. Esta parte é da equipe e não muda por aqui."
        />
        <DescriptionList
          items={[
            { label: "Equipamento", value: texto(osp.equipamento_tag) },
            { label: "Grau de risco", value: texto(osp.grau_risco_display) },
            { label: "Componente", value: <SemDado>{texto(osp.componente)}</SemDado> },
            { label: "Prazo (SLA)", value: osp.sla_data ? fmtData(osp.sla_data) : <SemDado /> },
            { label: "Anomalia detectada", value: texto(osp.anomalia), largo: true },
            { label: "Recomendação", value: texto(osp.recomendacao), largo: true },
          ]}
        />
      </Card>

      {/* --- Execução (retorno) --- */}
      <Card>
        <CardHeader
          icon={ClipboardPen}
          title="Execução da corretiva"
          description="Quando foi planejada, quando foi executada e por quem."
        />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Planejamento em" hint="Data em que a intervenção entrou na programação.">
            <Input
              type="datetime-local"
              value={campos.planejado_em}
              onChange={(e) => set("planejado_em", e.target.value)}
            />
          </Field>
          <Field label="Planejamento por">
            <Select
              value={campos.planejado_por}
              onChange={(e) => set("planejado_por", e.target.value)}
            >
              {pessoas}
            </Select>
          </Field>
          <Field label="Corretiva em" hint="Data em que a máquina foi efetivamente intervinda.">
            <Input
              type="datetime-local"
              value={campos.executado_em}
              onChange={(e) => set("executado_em", e.target.value)}
            />
          </Field>
          <Field label="Corretiva por">
            <Select
              value={campos.executado_por}
              onChange={(e) => set("executado_por", e.target.value)}
            >
              {pessoas}
            </Select>
          </Field>
          <Field label="Finalização por" className="sm:col-span-2">
            <Select
              value={campos.finalizado_por}
              onChange={(e) => set("finalizado_por", e.target.value)}
            >
              {pessoas}
            </Select>
          </Field>
          <Field
            label="O que foi feito"
            className="sm:col-span-2"
            hint="Descreva a intervenção: peça trocada, ajuste realizado, serviço contratado."
          >
            <Textarea
              rows={3}
              value={campos.descricao_corretiva}
              placeholder="Ex.: Rolamento 6308 do mancal LA substituído; acoplamento realinhado."
              onChange={(e) => set("descricao_corretiva", e.target.value)}
            />
          </Field>
          <Field label="Confirmação do diagnóstico" className="sm:col-span-2">
            <Select
              value={campos.resultado_confirmacao}
              onChange={(e) => set("resultado_confirmacao", e.target.value)}
            >
              <option value="PENDENTE">Aguardando confirmação</option>
              <option value="CONFIRMADO">Confirmado — a máquina apresentava o problema</option>
              <option value="NAO_CONFIRMADO">Não confirmado — o problema era outro</option>
            </Select>
            <p className="mt-1 text-xs text-fg-subtle">
              A abertura da máquina confirmou o que a preditiva apontou? Esta resposta alimenta o
              KPI &quot;Taxa de Acerto do Diagnóstico&quot; do seu relatório.
            </p>
          </Field>
        </div>
      </Card>

      {/* --- Avaliação de Resultados (retorno) --- */}
      <Card>
        <CardHeader
          icon={Calculator}
          title="Quanto custou"
          description="Compare o custo desta correção planejada com o que teria custado a mesma falha em emergência. A diferença é o retorno que a preditiva gerou."
          dica="Preencha só o que se aplica. Campos em branco contam como zero."
        />
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-sm">
            <thead>
              <tr className="text-xs uppercase tracking-wide text-fg-subtle">
                <th className="px-2 py-2 text-left font-medium"></th>
                <th className="px-2 py-2 text-center font-medium" colSpan={2}>
                  O que custou (planejada)
                </th>
                <th className="px-2 py-2 text-center font-medium" colSpan={2}>
                  O que custaria (emergência)
                </th>
              </tr>
              <tr className="border-b border-border text-[11px] text-fg-subtle">
                <th />
                <th className="px-2 pb-2 font-normal">Qtde</th>
                <th className="px-2 pb-2 font-normal">Valor (R$)</th>
                <th className="px-2 pb-2 font-normal">Qtde</th>
                <th className="px-2 pb-2 font-normal">Valor (R$)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {LINHAS_ROI.map((l) => (
                <tr key={l.chave}>
                  <td className="px-2 py-2 font-medium text-fg">{l.rotulo}</td>
                  {(["pred", "emerg"] as const).map((p) => (
                    <Fragment key={p}>
                      <td className="px-2 py-2">
                        {l.temQtd ? (
                          <Input
                            type="number"
                            step="0.01"
                            value={roi[`${p}_${l.chave}_h`] ?? ""}
                            onChange={(e) => setR(`${p}_${l.chave}_h`, e.target.value)}
                          />
                        ) : (
                          <span className="block text-center text-fg-subtle">—</span>
                        )}
                      </td>
                      <td className="px-2 py-2">
                        <Input
                          type="number"
                          step="0.01"
                          value={roi[`${p}_${l.chave}_valor`] ?? ""}
                          onChange={(e) => setR(`${p}_${l.chave}_valor`, e.target.value)}
                        />
                      </td>
                    </Fragment>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="mt-4 grid grid-cols-1 gap-3 border-t border-border pt-4 sm:grid-cols-3">
          <div>
            <p className="text-xs text-fg-subtle">Total da correção planejada</p>
            <p className="font-mono text-lg font-semibold tabular-nums text-fg">
              {moeda(totais.pred)}
            </p>
          </div>
          <div>
            <p className="text-xs text-fg-subtle">Total se fosse emergência</p>
            <p className="font-mono text-lg font-semibold tabular-nums text-fg">
              {moeda(totais.emerg)}
            </p>
          </div>
          <div>
            <p className="text-xs text-fg-subtle">Retorno do investimento</p>
            <p
              className={`font-mono text-lg font-semibold tabular-nums ${
                totais.retorno >= 0 ? "text-success-fg" : "text-danger-fg"
              }`}
            >
              {moeda(totais.retorno)}
            </p>
          </div>
        </div>
      </Card>

      {msg && (
        <Alert tone="danger" title="Não foi possível enviar" onClose={() => setMsg(null)}>
          {msg}
        </Alert>
      )}
      <FormActions alinhamento="entre">
        <span className="hidden text-xs text-fg-subtle sm:inline">
          Você pode voltar e completar depois — nada aqui é definitivo.
        </span>
        <span className="flex flex-1 items-center justify-end gap-2 sm:flex-none">
          <Button variant="secondary" onClick={() => router.push("/portal/ordens-servico")}>
            Cancelar
          </Button>
          <Button onClick={salvar} loading={mutacao.enviando} icon={Save}>
            Enviar retorno
          </Button>
        </span>
      </FormActions>
    </PageBody>
  );
}
