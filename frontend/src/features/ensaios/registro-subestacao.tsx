"use client";

import { useState } from "react";
import { ClipboardList, Save } from "lucide-react";
import { api } from "@/lib/api";
import { Badge, Button, Card, CardHeader, Field, FormGrid, Input, Select, Textarea, useToast } from "@/components/ds";
import { EnsaiosSolicitados, converter, type Numericos } from "./registro";
import { paraCampo } from "./numeros";
import type { DadosPlacaApi, EnsaioCatalogo, ModuloSubestacao, RegistroSubestacaoApi } from "./tipos";

/* ==========================================================================
   Registro de campo dos ensaios de subestação (TC, TP, DJ, CS, RP) e os dados de
   placa do equipamento. O registro é a ficha 1 do relatório (condições do ensaio e
   ensaios solicitados); a placa é o dado que os cálculos usam: relação nominal e
   classe (TC/TP), tensão e polos (DJ/CS), funções do relé (RP).
   ========================================================================== */

type NumericosRegistro = "temperatura_equipamento_c" | "temperatura_ambiente_c" | "umidade_relativa_pct";

export function RegistroSubestacao({
  itemId, dataPadrao, analistaPadrao, ensaios, registro, podeEditar, onSalvo,
}: {
  itemId: number;
  dataPadrao: string;
  analistaPadrao: string;
  ensaios: EnsaioCatalogo[];
  registro: RegistroSubestacaoApi | null;
  podeEditar: boolean;
  onSalvo: (r: RegistroSubestacaoApi) => void;
}) {
  const toast = useToast();
  const [dataEnsaio, setDataEnsaio] = useState(registro?.data_ensaio ?? dataPadrao);
  const [analista, setAnalista] = useState(registro?.analista ?? analistaPadrao);
  const [numeros, setNumeros] = useState<Numericos<NumericosRegistro>>({
    temperatura_equipamento_c: paraCampo(registro?.temperatura_equipamento_c),
    temperatura_ambiente_c: paraCampo(registro?.temperatura_ambiente_c),
    umidade_relativa_pct: paraCampo(registro?.umidade_relativa_pct),
  });
  const [solicitados, setSolicitados] = useState(new Set(registro?.ensaios ?? []));
  const [erros, setErros] = useState<Partial<Record<NumericosRegistro | "data", string>>>({});
  const [salvando, setSalvando] = useState(false);

  async function salvar() {
    const { saida, erros: errosNum } = converter(numeros);
    const errosTodos: typeof erros = { ...errosNum, ...(dataEnsaio ? {} : { data: "Informe a data do ensaio." }) };
    setErros(errosTodos);
    if (Object.keys(errosTodos).length) return;
    setSalvando(true);
    try {
      const salvo = await api<RegistroSubestacaoApi>(
        registro ? `/registros-ensaio-subestacao/${registro.id}/` : "/registros-ensaio-subestacao/",
        {
          method: registro ? "PATCH" : "POST",
          body: { item: itemId, data_ensaio: dataEnsaio, analista, ...saida, ensaios: Array.from(solicitados) },
        }
      );
      toast.sucesso("Registro dos ensaios salvo");
      onSalvo(salvo);
    } catch (e) {
      toast.falha(e, "Não foi possível salvar o registro dos ensaios.");
    } finally {
      setSalvando(false);
    }
  }

  const bloqueado = !podeEditar || salvando;
  const num = (chave: NumericosRegistro, label: string, sufixo: string) => (
    <Field label={label} erro={erros[chave]}>
      <Input inputMode="decimal" tecnico sufixo={sufixo} value={numeros[chave]} disabled={bloqueado}
        onChange={(e) => setNumeros((n) => ({ ...n, [chave]: e.target.value }))} />
    </Field>
  );

  return (
    <Card>
      <CardHeader
        icon={ClipboardList}
        title="Registro dos ensaios"
        description="Dados da ficha 1 do relatório. Os ensaios marcados aqui são os que saem como solicitados."
        actions={registro ? <Badge tone="success">Registrado</Badge> : <Badge tone="warning">Não registrado</Badge>}
      />
      <div className="space-y-5">
        <FormGrid colunas={3}>
          <Field label="Data do ensaio" obrigatorio erro={erros.data}>
            <Input type="date" value={dataEnsaio} disabled={bloqueado} onChange={(e) => setDataEnsaio(e.target.value)} />
          </Field>
          <Field label="Analista">
            <Input value={analista} maxLength={120} disabled={bloqueado} onChange={(e) => setAnalista(e.target.value)} />
          </Field>
          {num("temperatura_equipamento_c", "Temperatura do equipamento", "°C")}
          {num("temperatura_ambiente_c", "Temperatura ambiente", "°C")}
          {num("umidade_relativa_pct", "Umidade relativa", "%")}
        </FormGrid>

        <EnsaiosSolicitados ensaios={ensaios} marcados={solicitados} onMudar={setSolicitados} disabled={bloqueado} />

        {podeEditar && (
          <div className="flex justify-end">
            <Button icon={Save} loading={salvando} onClick={salvar}>
              {registro ? "Salvar registro" : "Registrar ensaios"}
            </Button>
          </div>
        )}
      </div>
    </Card>
  );
}

/* ------------------------------ Dados de placa ------------------------------ */
type CampoPlaca = "tensao_nominal_kv" | "corrente_nominal_a" | "relacao_texto" | "relacao_transformacao"
  | "classe_exatidao" | "carga_nominal_va" | "numero_nucleos" | "polaridade" | "numero_polos"
  | "capacidade_interrupcao_ka" | "mecanismo" | "funcoes_protecao";

/** Campos de placa que cada tipo usa (os demais não aparecem no cadastro do equipamento). */
const CAMPOS_POR_MODULO: Record<ModuloSubestacao, CampoPlaca[]> = {
  ENSAIO_ELETRICO_TC: ["tensao_nominal_kv", "corrente_nominal_a", "relacao_texto", "relacao_transformacao",
    "classe_exatidao", "carga_nominal_va", "numero_nucleos", "polaridade"],
  ENSAIO_ELETRICO_TP: ["tensao_nominal_kv", "relacao_texto", "relacao_transformacao", "classe_exatidao",
    "carga_nominal_va", "polaridade"],
  ENSAIO_ELETRICO_DJ: ["tensao_nominal_kv", "corrente_nominal_a", "capacidade_interrupcao_ka", "numero_polos", "mecanismo"],
  ENSAIO_ELETRICO_CS: ["tensao_nominal_kv", "corrente_nominal_a", "numero_polos", "mecanismo"],
  ENSAIO_ELETRICO_RP: ["funcoes_protecao"],
};
const NUMERICOS_PLACA: CampoPlaca[] = ["tensao_nominal_kv", "corrente_nominal_a", "relacao_transformacao",
  "carga_nominal_va", "numero_nucleos", "numero_polos", "capacidade_interrupcao_ka"];

const ROTULOS_PLACA: Record<CampoPlaca, { label: string; sufixo?: string; hint?: string }> = {
  tensao_nominal_kv: { label: "Tensão nominal", sufixo: "kV" },
  corrente_nominal_a: { label: "Corrente nominal", sufixo: "A" },
  relacao_texto: { label: "Relação de placa", hint: "Como está na placa, ex.: 600/5 A" },
  relacao_transformacao: { label: "Relação nominal (primário ÷ secundário)", hint: "600/5 → 120. Base do erro de relação." },
  classe_exatidao: { label: "Classe de exatidão", hint: "Ex.: 0,5 · 1 · 3 · 5P · 10P (TC); 0,5 · 3P (TP)" },
  carga_nominal_va: { label: "Carga nominal", sufixo: "VA" },
  numero_nucleos: { label: "Número de núcleos" },
  polaridade: { label: "Polaridade declarada", hint: "Subtrativa ou aditiva, como na placa" },
  numero_polos: { label: "Número de polos" },
  capacidade_interrupcao_ka: { label: "Capacidade de interrupção", sufixo: "kA" },
  mecanismo: { label: "Mecanismo de operação" },
  funcoes_protecao: { label: "Funções de proteção do relé", hint: "Uma por linha, com o código ANSI: 50/51 — fase A" },
};

export function DadosPlacaSubestacao({
  equipamentoId, modulo, placa, podeEditar, onSalvo,
}: {
  equipamentoId: number;
  modulo: ModuloSubestacao;
  placa: DadosPlacaApi | null;
  podeEditar: boolean;
  onSalvo: (p: DadosPlacaApi) => void;
}) {
  const toast = useToast();
  const campos = CAMPOS_POR_MODULO[modulo];
  const [texto, setTexto] = useState<Record<string, string>>(() =>
    Object.fromEntries(campos.map((c) => [c, NUMERICOS_PLACA.includes(c) ? paraCampo(placa?.[c] as string | number | null) : String(placa?.[c] ?? "")]))
  );
  const [erros, setErros] = useState<Record<string, string>>({});
  const [salvando, setSalvando] = useState(false);
  const bloqueado = !podeEditar || salvando;

  async function salvar() {
    const numericos = Object.fromEntries(campos.filter((c) => NUMERICOS_PLACA.includes(c)).map((c) => [c, texto[c] ?? ""]));
    const { saida, erros: errosNum } = converter(numericos as Numericos<string>);
    setErros(errosNum as Record<string, string>);
    if (Object.keys(errosNum).length) return;
    const corpo: Record<string, unknown> = { equipamento: equipamentoId };
    for (const c of campos) {
      if (NUMERICOS_PLACA.includes(c)) corpo[c] = saida[c] ?? null;
      else corpo[c] = (texto[c] ?? "").trim();
    }
    setSalvando(true);
    try {
      const salvo = await api<DadosPlacaApi>(
        placa ? `/dados-placa-subestacao/${placa.id}/` : "/dados-placa-subestacao/",
        { method: placa ? "PATCH" : "POST", body: corpo }
      );
      toast.sucesso("Dados de placa salvos");
      onSalvo(salvo);
    } catch (e) {
      toast.falha(e, "Não foi possível salvar os dados de placa.");
    } finally {
      setSalvando(false);
    }
  }

  return (
    <Card>
      <CardHeader
        icon={ClipboardList}
        title="Dados de placa"
        description="Do equipamento. Os cálculos usam a relação, a classe e os polos desta placa; o laudo guarda a placa do momento do lançamento."
        actions={placa ? <Badge tone="success">Cadastrada</Badge> : <Badge tone="warning">Não cadastrada</Badge>}
      />
      <FormGrid colunas={3}>
        {campos.map((c) => {
          const r = ROTULOS_PLACA[c];
          if (c === "funcoes_protecao") {
            return (
              <div key={c} className="sm:col-span-3">
                <Field label={r.label} hint={r.hint}>
                  <Textarea rows={3} value={texto[c] ?? ""} disabled={bloqueado}
                    onChange={(e) => setTexto((t) => ({ ...t, [c]: e.target.value }))} />
                </Field>
              </div>
            );
          }
          if (c === "polaridade") {
            return (
              <Field key={c} label={r.label} hint={r.hint}>
                <Select value={texto[c] ?? ""} disabled={bloqueado} onChange={(e) => setTexto((t) => ({ ...t, [c]: e.target.value }))}>
                  <option value="">—</option>
                  <option value="Subtrativa">Subtrativa</option>
                  <option value="Aditiva">Aditiva</option>
                </Select>
              </Field>
            );
          }
          const numerico = NUMERICOS_PLACA.includes(c);
          return (
            <Field key={c} label={r.label} hint={r.hint} erro={erros[c]}>
              <Input
                inputMode={numerico ? "decimal" : "text"}
                tecnico={numerico}
                sufixo={r.sufixo}
                value={texto[c] ?? ""}
                disabled={bloqueado}
                onChange={(e) => setTexto((t) => ({ ...t, [c]: e.target.value }))}
              />
            </Field>
          );
        })}
      </FormGrid>
      {podeEditar && (
        <div className="mt-4 flex justify-end">
          <Button icon={Save} loading={salvando} onClick={salvar}>
            {placa ? "Salvar dados de placa" : "Cadastrar dados de placa"}
          </Button>
        </div>
      )}
    </Card>
  );
}
