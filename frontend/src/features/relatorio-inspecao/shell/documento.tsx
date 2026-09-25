import type { DossieShell } from "../tipos";
import { moduloDoRelatorio } from "../modulos";
import { CartaCorpo } from "./carta";
import { SecaoEquipamentos } from "./equipamentos";
import { CapaRelatorio, Contracapa, PaginaInterna } from "./folhas";

/**
 * Relatório técnico completo — usado pela tela do relatório e pela rota de
 * impressão (/imprimir/[id]). Sequência comum a qualquer tecnologia:
 *
 *   CAPA → CARTA AO CLIENTE → KPIs → EQUIPAMENTOS MONITORADOS → FICHAS TÉCNICAS → CONCLUSÕES
 *
 * O que muda por tecnologia vem do módulo (`modulos/`): conteúdo da carta, dos
 * KPIs, as fichas e, se houver, as conclusões. Toda página é filha direta de
 * `.print-area` (os módulos devolvem fragmentos) — a quebra de página da
 * "Impressão simples" depende disso.
 */
export function RelatorioCorpo({ d }: { d: DossieShell }) {
  const cab = d.cabecalho;
  const modulo = moduloDoRelatorio(d);
  const { Kpis, Fichas, Conclusoes } = modulo;

  return (
    <div className="print-area space-y-4 text-slate-800">
      {/* ===================== CAPA (folha única, gabarito AVSMD_Capa) ===================== */}
      <CapaRelatorio cab={cab} />

      {/* ========================= SEÇÃO A — CARTA ========================= */}
      <CartaCorpo d={d} carta={modulo.carta(d)} />

      {/* ========================= SEÇÃO B — KPIs ========================= */}
      <Contracapa cab={cab} titulo={"KPI’s\nDashboard’s"} />
      <PaginaInterna cab={cab}>
        <Kpis d={d} />
      </PaginaInterna>

      {/* ============== SEÇÃO C — EQUIPAMENTOS MONITORADOS ============== */}
      <Contracapa cab={cab} titulo={"Equipamentos\nContemplados"} />
      <SecaoEquipamentos cab={cab} c={d.secao_c} />

      {/* ============ FICHAS TÉCNICAS DA TECNOLOGIA (ex.: Seção D — OSPs) ============ */}
      <Fichas d={d} />

      {/* ========================= CONCLUSÕES ========================= */}
      {Conclusoes && <Conclusoes d={d} />}
    </div>
  );
}

/** Carta ao Cliente avulsa (rota /carta/[id]) — a mesma do relatório. */
export function CartaDoRelatorio({ d }: { d: DossieShell }) {
  return <CartaCorpo d={d} carta={moduloDoRelatorio(d).carta(d)} />;
}
