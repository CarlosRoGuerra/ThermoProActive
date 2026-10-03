import type { DossieFluido, KpisFluido, StatusFluido } from "../../tipos";
import { ddmmaaaa } from "../../shell/formato";
import { CINZA_KPI, GraficoDistribuicao, STATUS_KPI, StatTile } from "../../shell/kpis";

/* KPIs da análise de fluidos: quantas amostras e equipamentos, o que ficou
   pendente, quantos parâmetros em alerta/crítico pelas referências cadastradas,
   a limpeza (CP) frente à meta e a criticidade dos laudos. Nada de vibração. */

const COR_STATUS: Record<StatusFluido, string> = {
  ROTINA: STATUS_KPI.good,
  ALERTA: STATUS_KPI.warning,
  CRITICA: STATUS_KPI.critical,
  SEM_CRITERIO: CINZA_KPI,
  NAO_COLETADO: STATUS_KPI.serious,
  NAO_REALIZADO: STATUS_KPI.serious,
  SEM_RESULTADO: "#c3c2b7",
};
const COR_CRITICIDADE: Record<string, string> = {
  Rotina: STATUS_KPI.good, Alerta: STATUS_KPI.warning, "Crítica": STATUS_KPI.critical, "Não classificado": CINZA_KPI,
};
const ORDEM: StatusFluido[] = ["CRITICA", "ALERTA", "NAO_COLETADO", "NAO_REALIZADO", "SEM_RESULTADO", "SEM_CRITERIO", "ROTINA"];

function TabelaPorEnsaio({ k }: { k: KpisFluido }) {
  type Linha = Record<"dentro" | "alerta" | "critica" | "sem" | "pendente", number>;
  const porEnsaio = new Map<string, Linha>();
  for (const e of k.status_por_ensaio) {
    const l = porEnsaio.get(e.rotulo) ?? { dentro: 0, alerta: 0, critica: 0, sem: 0, pendente: 0 };
    if (e.status === "ROTINA") l.dentro += 1;
    else if (e.status === "ALERTA") l.alerta += 1;
    else if (e.status === "CRITICA") l.critica += 1;
    else if (e.status === "SEM_CRITERIO") l.sem += 1;
    else l.pendente += 1;
    porEnsaio.set(e.rotulo, l);
  }
  if (!porEnsaio.size) return null;
  const th = "px-2 py-1.5 text-[10px] font-semibold text-slate-500";
  const td = "px-2 py-1.5 text-right tabular-nums text-slate-800";
  return (
    <div>
      <h3 className="mb-2 text-sm font-bold text-slate-800">Resultado por Ensaio</h3>
      <table className="w-full border-collapse text-xs">
        <thead>
          <tr className="border-b border-slate-300 [&>th:not(:first-child)]:text-right">
            <th className={`${th} text-left`}>Ensaio</th>
            <th className={th}>Dentro das referências</th>
            <th className={th}>Alerta</th>
            <th className={th}>Crítica</th>
            <th className={th}>Sem referência</th>
            <th className={th}>Pendente</th>
          </tr>
        </thead>
        <tbody>
          {Array.from(porEnsaio.entries()).map(([rotulo, n]) => (
            <tr key={rotulo} className="border-b border-slate-100">
              <td className="px-2 py-1.5 font-medium text-slate-800">{rotulo}</td>
              <td className={td}>{n.dentro}</td>
              <td className={td} style={n.alerta ? { fontWeight: 700 } : undefined}>{n.alerta}</td>
              <td className={td} style={n.critica ? { color: STATUS_KPI.critical, fontWeight: 700 } : undefined}>{n.critica}</td>
              <td className={td}>{n.sem}</td>
              <td className={td}>{n.pendente}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function KpisFluidos({ d }: { d: DossieFluido }) {
  const k = d.kpis;
  const statusDoRotulo = new Map(k.status_por_ensaio.map((e) => [e.status_rotulo, e.status]));
  const rank = (rotulo: string) => ORDEM.indexOf(statusDoRotulo.get(rotulo) ?? "SEM_RESULTADO");
  const cps = k.limpeza.dentro + k.limpeza.fora + k.limpeza.sem_meta;
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap gap-3">
        <StatTile valor={k.amostras} rotulo="Amostras analisadas" />
        <StatTile valor={k.equipamentos} rotulo="Equipamentos monitorados" />
        <StatTile valor={k.ensaios_realizados} rotulo="Ensaios realizados" />
        <StatTile valor={k.ensaios_pendentes} rotulo="Ensaios pendentes" cor={k.ensaios_pendentes ? STATUS_KPI.serious : undefined} />
      </div>
      <div className="flex flex-wrap gap-3">
        <StatTile valor={k.parametros_alerta} rotulo="Parâmetros em alerta" />
        <StatTile valor={k.parametros_criticos} rotulo="Parâmetros críticos" cor={k.parametros_criticos ? STATUS_KPI.critical : undefined} />
        <StatTile valor={k.parametros_sem_referencia} rotulo="Parâmetros sem referência" />
        {cps > 0 && (
          <StatTile valor={`${k.limpeza.fora} de ${cps}`} rotulo="Limpeza (CP) acima da meta" cor={k.limpeza.fora ? STATUS_KPI.critical : undefined} />
        )}
        {/* Data em corpo menor: no tamanho dos números ela não cabe no cartão. */}
        <StatTile valor={<span className="text-lg">{k.proxima_data ? ddmmaaaa(k.proxima_data) : "—"}</span>} rotulo="Próxima coleta" />
      </div>
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
        <GraficoDistribuicao
          titulo="Avaliação dos Ensaios pelas Referências"
          segmentos={[...k.avaliacao_ensaios]
            .sort((a, z) => rank(a.rotulo) - rank(z.rotulo))
            .map((s) => ({ ...s, cor: COR_STATUS[statusDoRotulo.get(s.rotulo) ?? "SEM_RESULTADO"] }))}
        />
        {k.laudos_por_criticidade.length > 0 && (
          <GraficoDistribuicao
            titulo="Criticidade dos Laudos"
            segmentos={k.laudos_por_criticidade.map((s) => ({ ...s, cor: COR_CRITICIDADE[s.rotulo] ?? CINZA_KPI }))}
          />
        )}
      </div>
      {cps > 0 && (
        <p className="text-xs text-slate-600">
          Limpeza do fluido (ISO 4406): {k.limpeza.dentro} dentro da meta, {k.limpeza.fora} acima da meta
          {k.limpeza.sem_meta ? ` e ${k.limpeza.sem_meta} sem meta cadastrada` : ""}.
        </p>
      )}
      <TabelaPorEnsaio k={k} />
    </div>
  );
}
