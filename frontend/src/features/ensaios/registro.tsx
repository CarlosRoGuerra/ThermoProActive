"use client";

import { useMemo, useState } from "react";
import { ClipboardList, Save } from "lucide-react";
import { api } from "@/lib/api";
import {
  Alert,
  Badge,
  Button,
  Card,
  CardHeader,
  Checkbox,
  Field,
  FormGrid,
  Input,
  SegmentedControl,
  Select,
  useToast,
} from "@/components/ds";
import { tituloEnsaio } from "./cartao-ensaio";
import { MSG_NUMERO_INVALIDO, paraApi, paraCampo } from "./numeros";
import type {
  ColetaOleoApi,
  EnsaioCatalogo,
  EstadoChecklist,
  ItemChecklist,
  Opcao,
  RegistroEletricoApi,
} from "./tipos";

/* ==========================================================================
   Registro de campo do transformador — a ficha 1 do relatório.
   Óleo: coleta da amostra, ensaios solicitados e inspeção visual OK/NC/NA.
   Elétricos: condições do ensaio (TAP, temperaturas) e ensaios solicitados.
   Os ensaios marcados aqui são os que saem como "solicitados" no relatório.
   ========================================================================== */

type Numericos<K extends string> = Record<K, string>;

/** Converte os campos numéricos; devolve os erros por campo (texto inválido). */
function converter<K extends string>(campos: Numericos<K>) {
  const saida = {} as Record<K, string | null>;
  const erros: Partial<Record<K, string>> = {};
  for (const chave of Object.keys(campos) as K[]) {
    const v = paraApi(campos[chave]);
    if (v === undefined) erros[chave] = MSG_NUMERO_INVALIDO;
    else saida[chave] = v;
  }
  return { saida, erros };
}

function EnsaiosSolicitados({
  ensaios, marcados, onMudar, disabled,
}: {
  ensaios: EnsaioCatalogo[];
  marcados: Set<number>;
  onMudar: (proximo: Set<number>) => void;
  disabled: boolean;
}) {
  return (
    <fieldset>
      <legend className="label">Ensaios solicitados</legend>
      <div className="mt-1 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
        {ensaios.map((e) => (
          <Checkbox
            key={e.id}
            checked={marcados.has(e.id)}
            disabled={disabled}
            label={tituloEnsaio(e)}
            onChange={(v) => {
              const n = new Set(marcados);
              if (v) n.add(e.id);
              else n.delete(e.id);
              onMudar(n);
            }}
          />
        ))}
      </div>
    </fieldset>
  );
}

/* ------------------------------ Óleo isolante ------------------------------ */
type NumericosColeta = "temperatura_amostra_c" | "temperatura_ambiente_c" | "umidade_relativa_pct";
type Marcacao = { estado: EstadoChecklist | ""; observacao: string };

export function RegistroColeta({
  itemId, dataPadrao, ensaios, coleta, pontos, fluidos, checklist, possuiTanque, podeEditar, onSalvo,
}: {
  itemId: number;
  dataPadrao: string;
  ensaios: EnsaioCatalogo[];
  coleta: ColetaOleoApi | null;
  pontos: Opcao[];
  fluidos: Opcao[];
  checklist: ItemChecklist[];
  possuiTanque: boolean | null;
  podeEditar: boolean;
  onSalvo: (c: ColetaOleoApi) => void;
}) {
  const toast = useToast();
  const [dataColeta, setDataColeta] = useState(coleta?.data_coleta ?? dataPadrao);
  const [amostrador, setAmostrador] = useState(coleta?.amostrador ?? "");
  const [numeros, setNumeros] = useState<Numericos<NumericosColeta>>({
    temperatura_amostra_c: paraCampo(coleta?.temperatura_amostra_c),
    temperatura_ambiente_c: paraCampo(coleta?.temperatura_ambiente_c),
    umidade_relativa_pct: paraCampo(coleta?.umidade_relativa_pct),
  });
  const [ponto, setPonto] = useState(coleta?.ponto_coleta ? String(coleta.ponto_coleta) : "");
  const [fluido, setFluido] = useState(coleta?.tipo_fluido ? String(coleta.tipo_fluido) : "");
  const [solicitados, setSolicitados] = useState(new Set(coleta?.ensaios ?? []));
  // Sem tanque de expansão no cadastro: os itens exclusivos já começam "NA".
  const tanquePreenchido = !coleta && possuiTanque === false;
  const [marcacoes, setMarcacoes] = useState<Record<number, Marcacao>>(() => {
    const m: Record<number, Marcacao> = {};
    for (const item of checklist) {
      const salvo = coleta?.inspecao_visual.find((l) => l.item_checklist === item.id);
      m[item.id] = salvo
        ? { estado: salvo.estado, observacao: salvo.observacao }
        : { estado: tanquePreenchido && item.grupo === "TANQUE_EXPANSAO" ? "NA" : "", observacao: "" };
    }
    return m;
  });
  const [erros, setErros] = useState<Partial<Record<NumericosColeta | "data", string>>>({});
  const [salvando, setSalvando] = useState(false);

  const grupos = useMemo(() => ({
    geral: checklist.filter((i) => i.grupo === "GERAL"),
    tanque: checklist.filter((i) => i.grupo === "TANQUE_EXPANSAO"),
  }), [checklist]);
  const marcados = Object.values(marcacoes).filter((m) => m.estado).length;

  function marcar(ids: ItemChecklist[], estado: EstadoChecklist) {
    setMarcacoes((m) => {
      const n = { ...m };
      for (const i of ids) if (!n[i.id].estado) n[i.id] = { ...n[i.id], estado };
      return n;
    });
  }

  async function salvar() {
    const { saida, erros: errosNum } = converter(numeros);
    const errosTodos: typeof erros = { ...errosNum, ...(dataColeta ? {} : { data: "Informe a data da coleta." }) };
    setErros(errosTodos);
    if (Object.keys(errosTodos).length) return;
    setSalvando(true);
    try {
      const body = {
        item: itemId, data_coleta: dataColeta, amostrador, ...saida,
        ponto_coleta: ponto ? Number(ponto) : null, tipo_fluido: fluido ? Number(fluido) : null,
        ensaios: Array.from(solicitados),
        inspecao_visual: Object.entries(marcacoes)
          .filter(([, m]) => m.estado)
          .map(([id, m]) => ({ item_checklist: Number(id), estado: m.estado, observacao: m.observacao })),
      };
      const salvo = await api<ColetaOleoApi>(coleta ? `/coletas-oleo/${coleta.id}/` : "/coletas-oleo/", {
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
      <Input
        inputMode="decimal"
        tecnico
        sufixo={sufixo}
        value={numeros[chave]}
        disabled={bloqueado}
        onChange={(e) => setNumeros((n) => ({ ...n, [chave]: e.target.value }))}
      />
    </Field>
  );

  return (
    <Card>
      <CardHeader
        icon={ClipboardList}
        title="Registro da coleta de amostra"
        description="Dados da ficha 1 do relatório de óleo. Os ensaios marcados saem como solicitados."
        actions={coleta ? <Badge tone="success">Registrada</Badge> : <Badge tone="warning">Não registrada</Badge>}
      />
      <div className="space-y-5">
        <FormGrid colunas={3}>
          <Field label="Data da coleta" obrigatorio erro={erros.data}>
            <Input type="date" value={dataColeta} disabled={bloqueado} onChange={(e) => setDataColeta(e.target.value)} />
          </Field>
          <Field label="Amostrador">
            <Input value={amostrador} maxLength={120} disabled={bloqueado} onChange={(e) => setAmostrador(e.target.value)} />
          </Field>
          {num("temperatura_amostra_c", "Temperatura da amostra", "°C")}
          {num("temperatura_ambiente_c", "Temperatura ambiente", "°C")}
          {num("umidade_relativa_pct", "Umidade relativa do ar", "%")}
          <Field label="Ponto de coleta">
            <Select value={ponto} disabled={bloqueado} onChange={(e) => setPonto(e.target.value)}>
              <option value="">Selecione…</option>
              {pontos.map((p) => <option key={p.id} value={p.id}>{p.nome}</option>)}
            </Select>
          </Field>
          <Field label="Tipo de fluido">
            <Select value={fluido} disabled={bloqueado} onChange={(e) => setFluido(e.target.value)}>
              <option value="">Selecione…</option>
              {fluidos.map((f) => <option key={f.id} value={f.id}>{f.nome}</option>)}
            </Select>
          </Field>
        </FormGrid>

        <EnsaiosSolicitados ensaios={ensaios} marcados={solicitados} onMudar={setSolicitados} disabled={bloqueado} />

        <div className="space-y-3 border-t border-border pt-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h3 className="text-sm font-semibold text-fg">Inspeção visual</h3>
              <p className="text-xs text-fg-muted">
                OK — condição normal · NC — não conformidade · NA — não aplicável ({marcados}/{checklist.length} marcados)
              </p>
            </div>
            {podeEditar && (
              <div className="flex flex-wrap gap-2">
                <Button size="xs" variant="secondary" onClick={() => marcar(grupos.geral, "OK")}>
                  Gerais sem marcação → OK
                </Button>
                <Button size="xs" variant="secondary" onClick={() => marcar(grupos.tanque, "NA")}>
                  Tanque de expansão → NA
                </Button>
              </div>
            )}
          </div>
          {tanquePreenchido && (
            <Alert tone="info">O cadastro diz que este transformador não tem tanque de expansão: os itens exclusivos começam como NA.</Alert>
          )}
          <GrupoChecklist titulo="Geral" itens={grupos.geral} marcacoes={marcacoes} onMudar={setMarcacoes} disabled={bloqueado} />
          <GrupoChecklist
            titulo="Exclusivo para equipamentos com tanque de expansão"
            itens={grupos.tanque}
            marcacoes={marcacoes}
            onMudar={setMarcacoes}
            disabled={bloqueado}
          />
        </div>

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

function GrupoChecklist({
  titulo, itens, marcacoes, onMudar, disabled,
}: {
  titulo: string;
  itens: ItemChecklist[];
  marcacoes: Record<number, Marcacao>;
  onMudar: (f: (m: Record<number, Marcacao>) => Record<number, Marcacao>) => void;
  disabled: boolean;
}) {
  if (!itens.length) return null;
  return (
    <div>
      <p className="mb-1.5 text-xs font-medium text-fg-muted">{titulo}</p>
      <ul className="divide-y divide-border rounded-lg border border-border">
        {itens.map((item) => {
          const m = marcacoes[item.id];
          return (
            <li key={item.id} className="px-3 py-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-sm text-fg">{item.nome}</span>
                <SegmentedControl<EstadoChecklist | "">
                  label={`Estado de ${item.nome}`}
                  tamanho="sm"
                  valor={m.estado}
                  onMudar={(estado) => {
                    if (!disabled) onMudar((atual) => ({ ...atual, [item.id]: { ...atual[item.id], estado } }));
                  }}
                  opcoes={[
                    { valor: "OK", label: "OK" },
                    { valor: "NC", label: "NC" },
                    { valor: "NA", label: "NA" },
                  ]}
                />
              </div>
              {m.estado === "NC" && (
                <Input
                  className="mt-2"
                  placeholder="O que foi observado (sai no relatório)"
                  value={m.observacao}
                  disabled={disabled}
                  onChange={(e) =>
                    onMudar((atual) => ({ ...atual, [item.id]: { ...atual[item.id], observacao: e.target.value } }))
                  }
                />
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/* ---------------------------- Ensaios elétricos ---------------------------- */
type NumericosRegistro = "tensao_tap_v" | "temperatura_oleo_c" | "temperatura_ambiente_c" | "umidade_relativa_pct";

export function RegistroEletrico({
  itemId, dataPadrao, analistaPadrao, ensaios, registro, podeEditar, onSalvo,
}: {
  itemId: number;
  dataPadrao: string;
  analistaPadrao: string;
  ensaios: EnsaioCatalogo[];
  registro: RegistroEletricoApi | null;
  podeEditar: boolean;
  onSalvo: (r: RegistroEletricoApi) => void;
}) {
  const toast = useToast();
  const [dataEnsaio, setDataEnsaio] = useState(registro?.data_ensaio ?? dataPadrao);
  const [analista, setAnalista] = useState(registro?.analista ?? analistaPadrao);
  const [tap, setTap] = useState(registro?.tap ?? "");
  const [numeros, setNumeros] = useState<Numericos<NumericosRegistro>>({
    tensao_tap_v: paraCampo(registro?.tensao_tap_v),
    temperatura_oleo_c: paraCampo(registro?.temperatura_oleo_c),
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
      const salvo = await api<RegistroEletricoApi>(
        registro ? `/registros-ensaio-eletrico/${registro.id}/` : "/registros-ensaio-eletrico/",
        {
          method: registro ? "PATCH" : "POST",
          body: { item: itemId, data_ensaio: dataEnsaio, analista, tap, ...saida, ensaios: Array.from(solicitados) },
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
  const num = (chave: NumericosRegistro, label: string, sufixo: string, hint?: string) => (
    <Field label={label} erro={erros[chave]} hint={hint}>
      <Input
        inputMode="decimal"
        tecnico
        sufixo={sufixo}
        value={numeros[chave]}
        disabled={bloqueado}
        onChange={(e) => setNumeros((n) => ({ ...n, [chave]: e.target.value }))}
      />
    </Field>
  );

  return (
    <Card>
      <CardHeader
        icon={ClipboardList}
        title="Registro dos ensaios elétricos"
        description="Dados da ficha 1 do relatório. A tensão do TAP entra na relação nominal do R×T."
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
          <Field label="TAP" hint="Posição do comutador no ensaio">
            <Input value={tap} maxLength={10} tecnico disabled={bloqueado} onChange={(e) => setTap(e.target.value)} />
          </Field>
          {num("tensao_tap_v", "Tensão do TAP", "V", "Ex.: 11400 (a ficha mostra em kV)")}
          {num("temperatura_oleo_c", "Temperatura do óleo", "°C", "Corrige a resistência ôhmica para 75 °C")}
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
