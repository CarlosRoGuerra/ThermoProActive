"use client";

import { useState } from "react";
import { ClipboardList, Save } from "lucide-react";
import { api } from "@/lib/api";
import {
  Alert,
  Badge,
  Button,
  Card,
  CardHeader,
  Field,
  FormGrid,
  Input,
  SegmentedControl,
  Select,
  Textarea,
  useToast,
} from "@/components/ds";
import { paraCampo } from "./numeros";
import { EnsaiosSolicitados, converter, type Numericos } from "./registro";
import {
  APLICACOES,
  CONDICOES_OPERACIONAIS,
  type AplicacaoFluido,
  type ColetaFluidoApi,
  type CondicaoOperacional,
  type EnsaioCatalogo,
  type Opcao,
  type ProdutoFluido,
} from "./tipos";

/* ==========================================================================
   Coleta da amostra de fluido lubrificante/hidráulico — a ficha 1 do relatório.
   Ordem pensada para o técnico em campo:

     Fluido → Coleta (data, ponto, condição) → Histórico do fluido
     → Ensaios solicitados → Observações → Salvar

   A aplicação marca os ensaios padrão acordados (lubrificante: FQ + EF;
   hidráulico: FQ + EF + CP) — o técnico ainda pode marcar ou desmarcar. Nenhum
   resultado de laboratório entra aqui: os laudos chegam depois, no escritório.
   ========================================================================== */

type NumericosColeta =
  | "temperatura_fluido_c" | "temperatura_ambiente_c" | "horas_equipamento" | "horas_fluido" | "volume_complemento_l"
  | "volume_reservatorio_l";
type SimNao = "" | "sim" | "nao";

const paraSimNao = (v: boolean | null | undefined): SimNao => (v == null ? "" : v ? "sim" : "nao");
const deSimNao = (v: SimNao) => (v === "" ? null : v === "sim");

function padraoDa(aplicacao: AplicacaoFluido | "", ensaios: EnsaioCatalogo[]) {
  return new Set(aplicacao ? ensaios.filter((e) => e.padrao_em?.includes(aplicacao)).map((e) => e.id) : []);
}

function SimNaoCampo({ label, valor, onMudar, disabled }: {
  label: string; valor: SimNao; onMudar: (v: SimNao) => void; disabled: boolean;
}) {
  return (
    <Field label={label}>
      <Select value={valor} disabled={disabled} onChange={(e) => onMudar(e.target.value as SimNao)}>
        <option value="">Não informado</option>
        <option value="sim">Sim</option>
        <option value="nao">Não</option>
      </Select>
    </Field>
  );
}

export function RegistroColetaFluido({
  itemId, dataPadrao, analistaPadrao, ensaios, coleta, produtos, pontos, podeEditar, onSalvo,
}: {
  itemId: number;
  dataPadrao: string;
  analistaPadrao: string;
  ensaios: EnsaioCatalogo[];
  coleta: ColetaFluidoApi | null;
  produtos: ProdutoFluido[];
  pontos: Opcao[];
  podeEditar: boolean;
  onSalvo: (c: ColetaFluidoApi) => void;
}) {
  const toast = useToast();
  const [aplicacao, setAplicacao] = useState<AplicacaoFluido | "">(coleta?.aplicacao ?? "");
  const [produto, setProduto] = useState(coleta?.produto ? String(coleta.produto) : "");
  const [fluidoInformado, setFluidoInformado] = useState(coleta?.fluido_informado ?? "");
  const [grau, setGrau] = useState(coleta?.grau_viscosidade ?? "");
  const [dataColeta, setDataColeta] = useState(coleta?.data_coleta ?? dataPadrao);
  const [amostra, setAmostra] = useState(coleta?.identificacao_amostra ?? "");
  const [amostrador, setAmostrador] = useState(coleta?.amostrador ?? analistaPadrao);
  const [ponto, setPonto] = useState(coleta?.ponto_coleta ? String(coleta.ponto_coleta) : "");
  const [condicao, setCondicao] = useState<CondicaoOperacional>(coleta?.condicao_operacional ?? "");
  const [ultimaTroca, setUltimaTroca] = useState(coleta?.data_ultima_troca ?? "");
  const [complemento, setComplemento] = useState<SimNao>(paraSimNao(coleta?.complemento_recente));
  const [filtro, setFiltro] = useState<SimNao>(paraSimNao(coleta?.troca_filtro_recente));
  const [intervencao, setIntervencao] = useState(coleta?.intervencao_recente ?? "");
  const [observacoes, setObservacoes] = useState(coleta?.observacoes ?? "");
  const [numeros, setNumeros] = useState<Numericos<NumericosColeta>>({
    temperatura_fluido_c: paraCampo(coleta?.temperatura_fluido_c),
    temperatura_ambiente_c: paraCampo(coleta?.temperatura_ambiente_c),
    horas_equipamento: paraCampo(coleta?.horas_equipamento),
    horas_fluido: paraCampo(coleta?.horas_fluido),
    volume_complemento_l: paraCampo(coleta?.volume_complemento_l),
    volume_reservatorio_l: paraCampo(coleta?.volume_reservatorio_l),
  });
  const [solicitados, setSolicitados] = useState<Set<number>>(
    () => new Set(coleta?.ensaios ?? Array.from(padraoDa(coleta?.aplicacao ?? "", ensaios))),
  );
  const [erros, setErros] = useState<Partial<Record<NumericosColeta | "data" | "aplicacao", string>>>({});
  const [salvando, setSalvando] = useState(false);

  // Produto cadastrado da aplicação escolhida (sem aplicação definida = serve para as duas).
  const produtosDaAplicacao = produtos.filter((p) => !aplicacao || !p.aplicacao || p.aplicacao === aplicacao);

  function escolherAplicacao(a: AplicacaoFluido) {
    setAplicacao(a);
    // Troca de aplicação refaz a seleção padrão (é a regra acordada, não um palpite).
    setSolicitados(padraoDa(a, ensaios));
    const atual = produtos.find((p) => String(p.id) === produto);
    if (atual?.aplicacao && atual.aplicacao !== a) setProduto("");
  }

  function escolherProduto(id: string) {
    setProduto(id);
    const p = produtos.find((x) => String(x.id) === id);
    if (p?.grau_viscosidade && !grau) setGrau(p.grau_viscosidade);
  }

  async function salvar() {
    const { saida, erros: errosNum } = converter(numeros);
    const errosTodos: typeof erros = {
      ...errosNum,
      ...(dataColeta ? {} : { data: "Informe a data da coleta." }),
      ...(aplicacao ? {} : { aplicacao: "Escolha se o fluido é lubrificante ou hidráulico." }),
    };
    setErros(errosTodos);
    if (Object.keys(errosTodos).length) return;
    setSalvando(true);
    try {
      const body = {
        item: itemId, aplicacao, produto: produto ? Number(produto) : null,
        fluido_informado: produto ? "" : fluidoInformado, grau_viscosidade: grau,
        identificacao_amostra: amostra, data_coleta: dataColeta, amostrador,
        ponto_coleta: ponto ? Number(ponto) : null, condicao_operacional: condicao,
        data_ultima_troca: ultimaTroca || null,
        complemento_recente: deSimNao(complemento), troca_filtro_recente: deSimNao(filtro),
        intervencao_recente: intervencao, observacoes, ...saida,
        volume_complemento_l: complemento === "sim" ? saida.volume_complemento_l : null,
        ensaios: Array.from(solicitados),
      };
      const salvo = await api<ColetaFluidoApi>(coleta ? `/coletas-fluido/${coleta.id}/` : "/coletas-fluido/", {
        method: coleta ? "PATCH" : "POST", body,
      });
      toast.sucesso("Coleta salva");
      onSalvo(salvo);
    } catch (e) {
      toast.falha(e, "Não foi possível salvar a coleta.");
    } finally {
      setSalvando(false);
    }
  }

  const bloqueado = !podeEditar || salvando;
  const num = (chave: NumericosColeta, label: string, sufixo: string) => (
    <Field label={label} erro={erros[chave]}>
      <Input inputMode="decimal" tecnico sufixo={sufixo} value={numeros[chave]} disabled={bloqueado}
        onChange={(e) => setNumeros((n) => ({ ...n, [chave]: e.target.value }))} />
    </Field>
  );
  const semCp = aplicacao === "LUBRIFICANTE" && ensaios.some((e) => e.sigla === "CP" && solicitados.has(e.id));

  return (
    <Card>
      <CardHeader
        icon={ClipboardList}
        title="Coleta da amostra de fluido"
        description="Dados da ficha 1 do relatório. Os resultados do laboratório entram depois, ensaio por ensaio."
        actions={coleta ? <Badge tone="success">Registrada</Badge> : <Badge tone="warning">Não registrada</Badge>}
      />
      <div className="space-y-6">
        {/* 1. Fluido */}
        <section className="space-y-3">
          <h3 className="text-sm font-semibold text-fg">Fluido</h3>
          <Field label="Aplicação do fluido" obrigatorio erro={erros.aplicacao}
            hint="Define os ensaios padrão: lubrificante → FQ e EF; hidráulico → FQ, EF e CP.">
            <SegmentedControl
              label="Aplicação do fluido"
              valor={aplicacao}
              onMudar={(v) => !bloqueado && escolherAplicacao(v as AplicacaoFluido)}
              opcoes={APLICACOES.map((a) => ({ valor: a.valor, label: a.label }))}
            />
          </Field>
          <FormGrid colunas={3}>
            <Field label="Fluido em uso" hint={produtosDaAplicacao.length ? undefined : "Nenhum fluido cadastrado para a aplicação"}>
              <Select value={produto} disabled={bloqueado} onChange={(e) => escolherProduto(e.target.value)}>
                <option value="">Não cadastrado — informar abaixo</option>
                {produtosDaAplicacao.map((p) => (
                  <option key={p.id} value={p.id}>{[p.nome, p.fabricante].filter(Boolean).join(" — ")}</option>
                ))}
              </Select>
            </Field>
            {!produto && (
              <Field label="Fluido (nome comercial)">
                <Input value={fluidoInformado} maxLength={120} disabled={bloqueado}
                  onChange={(e) => setFluidoInformado(e.target.value)} />
              </Field>
            )}
            <Field label="Grau de viscosidade" hint="Ex.: ISO VG 46">
              <Input value={grau} maxLength={20} disabled={bloqueado} onChange={(e) => setGrau(e.target.value)} />
            </Field>
          </FormGrid>
        </section>

        {/* 2. Coleta */}
        <section className="space-y-3">
          <h3 className="text-sm font-semibold text-fg">Coleta</h3>
          <FormGrid colunas={3}>
            <Field label="Data da coleta" obrigatorio erro={erros.data}>
              <Input type="date" value={dataColeta} disabled={bloqueado} onChange={(e) => setDataColeta(e.target.value)} />
            </Field>
            <Field label="Amostrador">
              <Input value={amostrador} maxLength={120} disabled={bloqueado} onChange={(e) => setAmostrador(e.target.value)} />
            </Field>
            <Field label="Identificação da amostra" hint="Etiqueta/número do frasco no laboratório">
              <Input value={amostra} maxLength={40} tecnico disabled={bloqueado} onChange={(e) => setAmostra(e.target.value)} />
            </Field>
            <Field label="Ponto de coleta">
              <Select value={ponto} disabled={bloqueado} onChange={(e) => setPonto(e.target.value)}>
                <option value="">—</option>
                {pontos.map((p) => <option key={p.id} value={p.id}>{p.nome}</option>)}
              </Select>
            </Field>
            <Field label="Condição operacional na coleta">
              <Select value={condicao} disabled={bloqueado} onChange={(e) => setCondicao(e.target.value as CondicaoOperacional)}>
                <option value="">Não informada</option>
                {CONDICOES_OPERACIONAIS.map((c) => <option key={c.valor} value={c.valor}>{c.label}</option>)}
              </Select>
            </Field>
            {num("temperatura_fluido_c", "Temperatura do fluido", "°C")}
            {num("temperatura_ambiente_c", "Temperatura ambiente", "°C")}
          </FormGrid>
        </section>

        {/* 3. Histórico do fluido no equipamento */}
        <section className="space-y-3">
          <h3 className="text-sm font-semibold text-fg">Histórico do fluido</h3>
          <FormGrid colunas={3}>
            {num("volume_reservatorio_l", "Volume do reservatório", "L")}
            {num("horas_equipamento", "Horas do equipamento", "h")}
            {num("horas_fluido", "Horas do fluido (desde a troca)", "h")}
            <Field label="Última troca do fluido">
              <Input type="date" value={ultimaTroca} disabled={bloqueado} onChange={(e) => setUltimaTroca(e.target.value)} />
            </Field>
            <SimNaoCampo label="Complemento recente de fluido" valor={complemento} onMudar={setComplemento} disabled={bloqueado} />
            {complemento === "sim" && num("volume_complemento_l", "Volume complementado", "L")}
            <SimNaoCampo label="Troca recente de filtro" valor={filtro} onMudar={setFiltro} disabled={bloqueado} />
          </FormGrid>
          <Field label="Intervenção/manutenção recente">
            <Textarea rows={2} value={intervencao} disabled={bloqueado} onChange={(e) => setIntervencao(e.target.value)} />
          </Field>
        </section>

        {/* 4. Ensaios solicitados */}
        <section className="space-y-2">
          <EnsaiosSolicitados ensaios={ensaios} marcados={solicitados} onMudar={setSolicitados} disabled={bloqueado} />
          {semCp && (
            <p className="text-xs text-fg-subtle">CP marcada num lubrificante: só quando contratada (não é padrão para lubrificantes).</p>
          )}
          {!aplicacao && <Alert tone="info">Escolha a aplicação do fluido para marcar os ensaios padrão.</Alert>}
        </section>

        {/* 5. Observações */}
        <Field label="Observações">
          <Textarea rows={2} value={observacoes} disabled={bloqueado} onChange={(e) => setObservacoes(e.target.value)} />
        </Field>

        {podeEditar && (
          <div className="flex justify-end">
            <Button icon={Save} loading={salvando} onClick={salvar}>
              {coleta ? "Salvar coleta" : "Registrar coleta"}
            </Button>
          </div>
        )}
      </div>
    </Card>
  );
}
