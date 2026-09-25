import type { ComponentType } from "react";
import type { DossieTransformador, KpisTransformador, StatusEnsaio } from "../../tipos";
import { ddmmaaaa } from "../../shell/formato";
import { CINZA_KPI, GraficoDistribuicao, STATUS_KPI, StatTile } from "../../shell/kpis";

/* KPIs dos relatórios de transformador: quantos ensaios, quantos parâmetros
   fora da referência, status de cada ensaio e a próxima coleta/análise. A folha
   e a contracapa são do shell; as primitivas (StatTile, distribuição) também. */

const COR_STATUS: Record<StatusEnsaio, string> = {
  CONFORME: STATUS_KPI.good,
  NAO_CONFORME: STATUS_KPI.critical,
  NAO_COLETADO: STATUS_KPI.warning,
  NAO_REALIZADO: STATUS_KPI.warning,
  SEM_CRITERIO: CINZA_KPI,
  SEM_RESULTADO: "#c3c2b7",
};
const COR_VISUAL: Record<string, string> = {
  "Condição Normal": STATUS_KPI.good, "Não Conformidade": STATUS_KPI.critical, "Não Aplicável": CINZA_KPI,
};
const ORDEM_STATUS: StatusEnsaio[] = ["NAO_CONFORME", "NAO_COLETADO", "NAO_REALIZADO", "SEM_RESULTADO", "SEM_CRITERIO", "CONFORME"];

/** Resultado por ensaio: contagens agregadas (cabe o relatório de 1 ou de 50 transformadores). */
function TabelaPorEnsaio({ k }: { k: KpisTransformador }) {
  const porEnsaio = new Map<string, Record<StatusEnsaio, number>>();
  for (const e of k.status_por_ensaio) {
    const linha = porEnsaio.get(e.rotulo) ?? {
      CONFORME: 0, NAO_CONFORME: 0, SEM_CRITERIO: 0, NAO_COLETADO: 0, NAO_REALIZADO: 0, SEM_RESULTADO: 0,
    };
    linha[e.status] += 1;
    porEnsaio.set(e.rotulo, linha);
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
            <th className={th}>Conforme</th>
            <th className={th}>Não conforme</th>
            <th className={th}>Sem critério</th>
            <th className={th}>Sem resultado</th>
          </tr>
        </thead>
        <tbody>
          {Array.from(porEnsaio.entries()).map(([rotulo, n]) => (
            <tr key={rotulo} className="border-b border-slate-100">
              <td className="px-2 py-1.5 font-medium text-slate-800">{rotulo}</td>
              <td className={td}>{n.CONFORME}</td>
              <td className={td} style={n.NAO_CONFORME ? { color: STATUS_KPI.critical, fontWeight: 700 } : undefined}>{n.NAO_CONFORME}</td>
              <td className={td}>{n.SEM_CRITERIO}</td>
              <td className={td}>{n.NAO_COLETADO + n.NAO_REALIZADO + n.SEM_RESULTADO}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function KpisTransformadores({ d, Extras }: { d: DossieTransformador; Extras?: ComponentType<{ k: KpisTransformador }> }) {
  const k = d.kpis;
  const statusDoRotulo = new Map(k.status_por_ensaio.map((e) => [e.status_rotulo, e.status]));
  const rank = (rotulo: string) => ORDEM_STATUS.indexOf(statusDoRotulo.get(rotulo) ?? "SEM_RESULTADO");
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap gap-3">
        <StatTile valor={k.transformadores} rotulo="Transformadores" />
        <StatTile valor={k.ensaios_realizados} rotulo="Ensaios realizados" />
        <StatTile valor={k.parametros_avaliados} rotulo="Parâmetros avaliados" />
        <StatTile valor={k.parametros_fora} rotulo="Parâmetros fora da referência" cor={k.parametros_fora ? STATUS_KPI.critical : undefined} />
        {/* Data em corpo menor: no tamanho dos números ela não cabe no cartão. */}
        <StatTile valor={<span className="text-lg">{k.proxima_data ? ddmmaaaa(k.proxima_data) : "—"}</span>} rotulo="Próxima coleta / análise" />
      </div>
      {Extras && <Extras k={k} />}
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
        <GraficoDistribuicao
          titulo="Status dos Ensaios"
          segmentos={[...k.status_ensaios]
            .sort((a, z) => rank(a.rotulo) - rank(z.rotulo))
            .map((s) => ({ ...s, cor: COR_STATUS[statusDoRotulo.get(s.rotulo) ?? "SEM_RESULTADO"] }))}
        />
        {k.inspecao_visual && k.inspecao_visual.length > 0 && (
          <GraficoDistribuicao
            titulo="Inspeção Visual na Coleta"
            segmentos={k.inspecao_visual.map((s) => ({ ...s, cor: COR_VISUAL[s.rotulo] ?? CINZA_KPI }))}
          />
        )}
      </div>
      <TabelaPorEnsaio k={k} />
    </div>
  );
}
