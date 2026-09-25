import type { Dist, DossieInspecao } from "../../tipos";
import { moeda } from "../../shell/formato";
import {
  CINZA_KPI, GraficoDistribuicao, Medidor, STATUS_KPI, StatTile, comCoresCategoricas,
} from "../../shell/kpis";

/* KPIs da inspeção por rota: condições (Grau de Risco), alarmes, componentes,
   anomalias e os indicadores das OSPs. A folha e a contracapa são do shell. */

const VERDE_OK_KPI = "#008300"; // categórica slot 6 — distinto do status "good" (ΔE 9.7, validado)

function corStatusGR(rotuloBruto: string): string {
  const r = rotuloBruto.replace(/[^A-Za-z0-9]/g, "").toUpperCase();
  if (r === "GR1") return STATUS_KPI.critical;
  if (r === "GR2") return STATUS_KPI.serious;
  if (r === "GR3") return STATUS_KPI.warning;
  if (r === "GR4") return STATUS_KPI.good;
  if (r === "OK" || r === "GR0") return VERDE_OK_KPI;
  return CINZA_KPI;
}
function corAlarmeKPI(rotulo: string): string {
  if (rotulo.includes("Crítico")) return STATUS_KPI.critical;
  if (rotulo.includes("Alerta")) return STATUS_KPI.serious;
  if (rotulo.includes("Aviso")) return STATUS_KPI.warning;
  return CINZA_KPI;
}
const ORDEM_SEVERIDADE_GR = ["GR1", "GR2", "GR3", "GR4", "OK", "GR0"];
function ordenarPorSeveridade(itens: Dist[]): Dist[] {
  const rank = (r: string) => {
    const idx = ORDEM_SEVERIDADE_GR.indexOf(r.replace(/[^A-Za-z0-9]/g, "").toUpperCase());
    return idx === -1 ? ORDEM_SEVERIDADE_GR.length : idx;
  };
  return [...itens].sort((a, z) => rank(a.rotulo) - rank(z.rotulo));
}
const ORDEM_ALARME = ["Nível 3", "Nível 2", "Nível 1"];
function ordenarAlarmes(itens: Dist[]): Dist[] {
  return [...itens].sort(
    (a, z) => ORDEM_ALARME.findIndex((p) => a.rotulo.startsWith(p)) - ORDEM_ALARME.findIndex((p) => z.rotulo.startsWith(p)),
  );
}

export function KpisInspecao({ d }: { d: DossieInspecao }) {
  const b = d.secao_b;
  return (
    <div className="space-y-6">
      {/* Indicadores-chave (stat tiles) */}
      <div className="flex flex-wrap gap-3">
        <StatTile valor={b.equip_monitorados} rotulo="Equipamentos monitorados" />
        <StatTile valor={b.anomalias_diagnosticadas} rotulo="Anomalias diagnosticadas" cor={STATUS_KPI.critical} />
        <StatTile valor={b.media_anomalias_por_equipamento} rotulo="Média de anomalias / equipamento" />
        <StatTile valor={moeda(b.custo_evitado)} rotulo="Custo evitado" cor={STATUS_KPI.good} />
        {b.mtbf_dias != null && <StatTile valor={`${b.mtbf_dias} d`} rotulo="MTBF estimado" />}
      </div>

      {/* Medidores (valor vs. limite) */}
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
        <div>
          <div className="mb-1.5 flex items-baseline justify-between">
            <h3 className="text-sm font-bold text-slate-800">Taxa de acerto do diagnóstico</h3>
            <span className="text-lg font-semibold text-slate-800">
              {b.taxa_acerto_diagnostico != null ? `${b.taxa_acerto_diagnostico}%` : "—"}
            </span>
          </div>
          {b.taxa_acerto_diagnostico != null ? (
            <>
              <Medidor valor={b.taxa_acerto_diagnostico} meta={90} />
              <p className="mt-1 text-[10px] text-slate-400">{b.diagnosticos_avaliados} OSP(s) avaliada(s) · meta ≥ 90%</p>
            </>
          ) : <p className="text-xs text-slate-400">Nenhum diagnóstico confirmado ainda.</p>}
        </div>
        <div>
          <div className="mb-1.5 flex items-baseline justify-between">
            <h3 className="text-sm font-bold text-slate-800">Cobertura de ativos críticos</h3>
            <span className="text-lg font-semibold text-slate-800">
              {b.cobertura_ativos_criticos != null ? `${b.cobertura_ativos_criticos}%` : "—"}
            </span>
          </div>
          {b.cobertura_ativos_criticos != null ? (
            <Medidor valor={b.cobertura_ativos_criticos} />
          ) : <p className="text-xs text-slate-400">Nenhum equipamento criticidade A cadastrado.</p>}
        </div>
      </div>

      {/* Distribuições (parte-do-todo) */}
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
        <GraficoDistribuicao
          titulo="Status das Condições"
          segmentos={ordenarPorSeveridade(b.condicoes).map((s) => ({ ...s, cor: corStatusGR(s.rotulo) }))}
        />
        {b.alarmes.length > 0 && (
          <GraficoDistribuicao
            titulo="Status dos Tipos de Alarmes"
            segmentos={ordenarAlarmes(b.alarmes).map((s) => ({ ...s, cor: corAlarmeKPI(s.rotulo) }))}
          />
        )}
        <GraficoDistribuicao titulo="Status dos Componentes" segmentos={comCoresCategoricas(b.componentes)} />
        <GraficoDistribuicao titulo="Status das Anomalias" segmentos={comCoresCategoricas(b.anomalias)} />
      </div>

      {/* Médias de diagnóstico — o backend só preenche as grandezas que a
          tecnologia mede (ver MediaDiagnostico em relatorio_tecnico/inspecao.py). */}
      {(b.diagnostico_medio.velocidade != null || b.diagnostico_medio.aceleracao != null || b.diagnostico_medio.temperatura != null) && (
        <div>
          <h3 className="mb-2 text-sm font-bold text-slate-800">Média dos Valores de Diagnóstico</h3>
          <div className="flex flex-wrap gap-3">
            {b.diagnostico_medio.velocidade != null && (
              <StatTile valor={b.diagnostico_medio.velocidade} rotulo="Velocidade RMS (mm/s)" />
            )}
            {b.diagnostico_medio.aceleracao != null && (
              <StatTile valor={b.diagnostico_medio.aceleracao} rotulo="Aceleração RMS (g)" />
            )}
            {b.diagnostico_medio.temperatura != null && (
              <StatTile valor={`${b.diagnostico_medio.temperatura}°C`} rotulo="Temperatura medida" />
            )}
          </div>
        </div>
      )}
    </div>
  );
}
