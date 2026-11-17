import { ddmmaaaa } from "../../shell/formato";
import { CINZA_KPI, GraficoDistribuicao, STATUS_KPI, StatTile } from "../../shell/kpis";
import { numero } from "../transformador/formato";
import type { DossieSubestacao } from "./tipos";

/* KPIs dos ensaios elétricos de subestação: totais, os maiores erros do ciclo (relação, pickup,
   tempo) e a distribuição dos status. Os destaques vêm prontos do backend (mesmas regras). */

const COR_STATUS: Record<string, string> = {
  CONFORME: STATUS_KPI.good,
  NAO_CONFORME: STATUS_KPI.critical,
  SEM_CRITERIO: CINZA_KPI,
  NAO_COLETADO: STATUS_KPI.warning,
  NAO_REALIZADO: STATUS_KPI.serious,
  SEM_RESULTADO: "#cbd5e1",
};

export function KpisSubestacao({ d }: { d: DossieSubestacao }) {
  const k = d.kpis;
  const statusDoRotulo = new Map(k.status_por_ensaio.map((e) => [e.status_rotulo, e.status]));
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap gap-3">
        <StatTile valor={k.equipamentos} rotulo="Equipamentos" />
        <StatTile valor={k.ensaios_realizados} rotulo="Ensaios realizados" />
        <StatTile valor={k.parametros_avaliados} rotulo="Medições avaliadas" />
        <StatTile valor={k.parametros_fora} rotulo="Medições fora da referência"
          cor={k.parametros_fora ? STATUS_KPI.critical : undefined} />
        {/* Data em corpo menor: no tamanho dos números ela não cabe no cartão. */}
        <StatTile valor={<span className="text-lg">{k.proxima_data ? ddmmaaaa(k.proxima_data) : "—"}</span>}
          rotulo="Próxima análise" />
      </div>
      {k.destaques.length > 0 && (
        <div className="flex flex-wrap gap-3">
          {k.destaques.map((x) => (
            <StatTile key={x.rotulo}
              valor={x.valor != null ? `${numero(x.valor, x.casas)} ${x.unidade}` : "—"}
              rotulo={`${x.rotulo} · ${x.detalhe}`} />
          ))}
        </div>
      )}
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
        <GraficoDistribuicao
          titulo="Status dos Ensaios"
          segmentos={k.status_ensaios.map((s) => ({
            ...s, cor: COR_STATUS[statusDoRotulo.get(s.rotulo) ?? "SEM_RESULTADO"] ?? CINZA_KPI,
          }))}
        />
      </div>
    </div>
  );
}
