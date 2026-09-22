"use client";

/**
 * Metade inferior da folha da OSP quando a intervenção é um BALANCEAMENTO corretivo.
 *
 * O cabeçalho da folha (OSP nº, empresa, TAG, diagnóstico, Grau de Risco) é o mesmo da
 * preditiva e continua em `dossie.tsx` — aqui trocam-se os blocos que não descrevem
 * uma corretiva já executada:
 *
 *   Tendência/Espectro  → Mostrador de fase (Trim) e Evolução da Vibração
 *   Planejamento/Corretiva Prog./Finalização → Resultado do Balanceamento
 *   Retorno de Informação (ROI preditivo)    → Economia Energética Gerada
 *
 * Nada é calculado aqui: todos os números vêm prontos do backend
 * (`apps.servicos.relatorio_corretivo`), que é a mesma fonte da tela do serviço.
 * Valor ausente sai como estado de ausência — num laudo, um zero inventado é pior
 * que um campo em branco.
 *
 * Formatação, tokens de impressão e o bloco de Economia (comum a qualquer tipo de
 * corretiva, não só balanceamento) vêm de `corretiva-base.tsx`.
 */
import type { ReactNode } from "react";
import { AntesDepois, MostradorPolar, type PontoGrafico } from "@/components/balanceamento-graficos";
import {
  AUSENTE, ESTILOS_CORRETIVA, TOKENS_IMPRESSAO, EconomiaGerada,
  grau, nm, pct, type EconomiaCorretiva,
} from "./corretiva-base";

/* ------------------------------- Tipos ------------------------------------ */
type Corrida = { mms: number; fase: number | null } | null;

export type PontoCorretiva = {
  id: number;
  codigo_ponto: string;
  numero_mancal: number;
  direcao: string;
  identificacao: string;
  plano: number | null;
  reference: Corrida;
  trial: Corrida;
  trim: Corrida;
  completo: boolean;
  residual_pct: number | null;
  reducao_pct: number | null;
  zona_iso: string;
  criticidade: string;
  criticidade_display: string;
  eficaz: boolean;
  diagnostico: string;
};

export type PlanoCorretiva = {
  id: number;
  numero: number;
  descricao: string;
  massa_teste_g: number | null;
  angulo_teste: number | null;
  massa_final_g: number | null;
  angulo_final: number | null;
};

export type { EconomiaCorretiva };

export type Corretiva = {
  servico_id: number;
  tipo: string;
  rotacao_hz: number | null;
  rotacao_rpm: number | null;
  classe_iso: string;
  ponto_foco: number | null;
  // Velocidade inicial oficial do balanceamento (Reference Run do ponto de foco) —
  // vem pronta do backend; nunca é o valor genérico de `Achado.velocidade_global`
  // nem as amplitudes do Trial/Trim (ver apps.servicos.relatorio_corretivo).
  velocidade_referencia: number | null;
  planos: PlanoCorretiva[];
  pontos: PontoCorretiva[];
  resultado: {
    pontos_completos: number;
    reducao_media_pct: number | null;
    criticidade_final: string | null;
  };
  economia: EconomiaCorretiva | null;
};

/* ------------------- Amplitudes (só velocidade no balanceamento) ----------- */

/**
 * No balanceamento a grandeza de interesse é a velocidade vibracional: a norma de
 * severidade (ISO 10816/20816) e o antes/depois do serviço estão todos em mm/s. A
 * aceleração continua existindo no banco e nos relatórios preditivos — só não
 * descreve este serviço.
 *
 * A fonte é o Reference Run do ponto de foco (`Corretiva.velocidade_referencia`),
 * não o `Achado.velocidade_global` da análise genérica — este balanceamento não
 * coleta esse campo, e usá-lo duplicaria a mesma medição em dois lugares.
 */
export function AmplitudeBalanceamento({ velocidade }: { velocidade: number | null }) {
  const linha = { minHeight: "5mm", lineHeight: "5mm" } as const;
  return (
    <>
      <div style={{ ...linha, fontWeight: 700 }}>Amplitudes [valor global]</div>
      <div style={linha}>
        <span style={{ fontWeight: 700 }}>Velocidade [mm/s]:</span> {nm(velocidade)}
      </div>
    </>
  );
}

/* ------------------------ Mostrador de fase (Trim) ------------------------- */

function paraGrafico(p: PontoCorretiva): PontoGrafico {
  return {
    codigo_ponto: p.codigo_ponto,
    reference: p.reference,
    trial: p.trial,
    trim: p.trim,
    reducao_pct: p.reducao_pct,
    zona_iso: p.zona_iso,
    completo: p.completo,
  };
}

/** Ponto representado no mostrador: o foco do balanceamento; sem foco, o 1º ponto. */
function pontoDoMostrador(c: Corretiva): PontoCorretiva | null {
  return c.pontos.find((p) => p.id === c.ponto_foco) ?? c.pontos[0] ?? null;
}

function MostradorTrim({ c }: { c: Corretiva }) {
  const ponto = pontoDoMostrador(c);
  return (
    <div className="bal-bloco">
      <div className="bal-titulo">Mostrador de Fase — Trim Run</div>
      {ponto ? (
        <>
          <MostradorPolar
            ponto={paraGrafico(ponto)}
            tamanho="46mm"
            series={["trim"]}
            mensagemVazia="Trim Run ainda não informado — o mostrador final sai com a fase do Trim Run, nunca com a do Trial."
          />
          <div className="bal-linha" style={{ marginTop: "1mm" }}>
            <b>Ponto:</b> {ponto.codigo_ponto}
            {ponto.identificacao ? ` — ${ponto.identificacao}` : ""}
          </div>
        </>
      ) : (
        <p className="bal-vazio">Nenhum ponto de medição registrado neste serviço.</p>
      )}
    </div>
  );
}

/* --------------------- Resultado do balanceamento -------------------------- */

function ResultadoBalanceamento({ c }: { c: Corretiva }) {
  const completos = c.pontos.filter((p) => p.completo);
  const numeroDoPlano = (id: number | null) => c.planos.find((pl) => pl.id === id)?.numero ?? null;

  return (
    <div className="bal-bloco">
      <div className="bal-barra">Resultado do Balanceamento</div>
      {completos.length ? (
        <table className="bal-tabela" style={{ marginTop: "1.5mm" }}>
          <colgroup>
            <col style={{ width: "13mm" }} />
            <col style={{ width: "11mm" }} />
            <col style={{ width: "17mm" }} />
            <col style={{ width: "17mm" }} />
            <col style={{ width: "17mm" }} />
            <col style={{ width: "15mm" }} />
          </colgroup>
          <thead>
            <tr>
              <th>Ponto</th>
              <th>Plano</th>
              <th>Antes [mm/s]</th>
              <th>Depois [mm/s]</th>
              <th>Redução</th>
              <th>ISO</th>
            </tr>
          </thead>
          <tbody>
            {completos.map((p) => (
              <tr key={p.id}>
                <td className="centro">{p.codigo_ponto}</td>
                <td className="centro">{numeroDoPlano(p.plano) ?? AUSENTE}</td>
                <td className="num">{nm(p.reference?.mms ?? null)}</td>
                <td className="num">{nm(p.trim?.mms ?? null)}</td>
                <td className="num bal-reducao">{pct(p.reducao_pct)}</td>
                <td className="centro">{p.zona_iso || AUSENTE}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="bal-vazio">
          Trim Run ainda não informado — sem ele o serviço não tem resultado medido.
        </p>
      )}

      <div className="bal-linha" style={{ marginTop: "1.5mm" }}>
        <b>Classe ISO do equipamento:</b> {c.classe_iso || AUSENTE} &nbsp;·&nbsp;{" "}
        <b>Situação final:</b>{" "}
        {completos.length
          ? completos.find((p) => p.criticidade === c.resultado.criticidade_final)
              ?.criticidade_display || c.resultado.criticidade_final || AUSENTE
          : AUSENTE}
        {c.resultado.reducao_media_pct != null && (
          <>
            {" "}&nbsp;·&nbsp; <b>Redução média:</b>{" "}
            <span className="bal-reducao" style={{ fontSize: "10pt" }}>
              {pct(c.resultado.reducao_media_pct)}
            </span>
          </>
        )}
      </div>

      {/* A correção que FICOU na máquina: massa e ângulo da massa de correção.
          Massa/ângulo de teste pertencem ao Trial Run e não representam o
          resultado — o rótulo deixa explícito que é a MASSA DE CORREÇÃO, não a
          fase vibracional medida no mostrador acima (grandezas independentes:
          uma é onde o peso foi fixado, a outra é o que o instrumento mediu). */}
      {c.planos.length ? (
        c.planos.map((pl) => (
          <div key={pl.id} className="bal-linha">
            <b>Plano {pl.numero}</b>
            {pl.descricao ? ` (${pl.descricao})` : ""} — Massa de correção:{" "}
            <b>{pl.massa_final_g == null ? AUSENTE : `${nm(pl.massa_final_g)} g`}</b> · Ângulo da
            massa de correção: <b>{grau(pl.angulo_final)}</b>
          </div>
        ))
      ) : (
        <div className="bal-linha">Nenhum plano de correção registrado.</div>
      )}
    </div>
  );
}

/* ------------------------ Evolução da vibração ----------------------------- */

function EvolucaoVibracao({ c }: { c: Corretiva }) {
  const pontos = c.pontos.filter((p) => p.reference && p.trim).map(paraGrafico);
  return (
    <div className="bal-bloco">
      <div className="bal-titulo">Evolução da Vibração</div>
      {pontos.length ? (
        <AntesDepois pontos={pontos} />
      ) : (
        <p className="bal-vazio">
          A evolução aparece quando algum ponto tiver o Trim Run medido.
        </p>
      )}
    </div>
  );
}

/* ------------------------------ Folha -------------------------------------- */

/**
 * Metade inferior da folha. Mantém a geometria física do gabarito
 * (90 + 10 + 80 + 10 = 190mm), para a foto continuar exatamente onde estava.
 */
export function CorpoBalanceamento({
  corretiva,
  foto,
}: {
  corretiva: Corretiva;
  /** O slot da foto vem pronto da folha — o upload de evidências não muda. */
  foto: ReactNode;
}) {
  return (
    <div style={TOKENS_IMPRESSAO}>
      <style>{ESTILOS_CORRETIVA}</style>

      {/* Linha 1 — Foto do equipamento | Mostrador de fase (Trim Run) */}
      <div
        style={{
          width: "190mm",
          display: "grid",
          gridTemplateColumns: "90mm 10mm 80mm 10mm",
          alignItems: "start",
          marginTop: "6mm",
        }}
      >
        <div style={{ width: "90mm" }}>
          <div style={{ marginLeft: "10mm", width: "80mm" }}>{foto}</div>
          <div style={{ height: "4mm" }} />
          <AmplitudeBalanceamento velocidade={corretiva.velocidade_referencia} />
        </div>
        <div />
        <div style={{ width: "80mm" }}>
          <MostradorTrim c={corretiva} />
        </div>
        <div />
      </div>

      {/* Linha 2 — Resultado do balanceamento | Evolução da vibração */}
      <div
        style={{
          width: "190mm",
          display: "grid",
          gridTemplateColumns: "90mm 10mm 80mm 10mm",
          alignItems: "start",
          marginTop: "4mm",
        }}
      >
        <div style={{ width: "90mm" }}>
          <ResultadoBalanceamento c={corretiva} />
        </div>
        <div />
        <div style={{ width: "80mm" }}>
          <EvolucaoVibracao c={corretiva} />
        </div>
        <div />
      </div>

      <EconomiaGerada economia={corretiva.economia} />
    </div>
  );
}
