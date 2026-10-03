import type { DossieShell } from "../tipos";
import { moduloDoRelatorio, temModulo } from "../modulos";
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
/** Payload de um módulo que esta versão da tela não conhece: aviso, nunca outro layout. */
function SemModulo({ d }: { d: DossieShell }) {
  return (
    <section className="pagina bg-white p-6" role="alert">
      <p className="py-12 text-center text-sm text-slate-600">
        O relatório do módulo técnico «{d.modulo || "não configurado"}» não está disponível nesta versão da tela.
      </p>
    </section>
  );
}

export function RelatorioCorpo({ d }: { d: DossieShell }) {
  if (!temModulo(d)) return <SemModulo d={d} />;
  const cab = d.cabecalho;
  const modulo = moduloDoRelatorio(d);
  const { Kpis, KpisComplementares, Fichas, Conclusoes } = modulo;

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
      {KpisComplementares && <KpisComplementares d={d} />}

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
  if (!temModulo(d)) return <SemModulo d={d} />;
  return <CartaCorpo d={d} carta={moduloDoRelatorio(d).carta(d)} />;
}
