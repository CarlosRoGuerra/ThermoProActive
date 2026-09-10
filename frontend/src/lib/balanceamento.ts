// Lógica pura do balanceamento (sem React) — testável isoladamente.
import type { BalanceamentoPonto, ServicoCampo } from "./types";

/**
 * Pontos efetivamente usados no balanceamento (para gráfico/resultado — não confundir
 * com "todos os pontos armazenados no serviço", que continuam guardados para o
 * relatório técnico mesmo sem gerar gráfico).
 *
 * Definição (confirmada com o cliente, 2026-09-10): o ponto de foco do serviço, mais
 * qualquer ponto explicitamente vinculado a um Plano. Isso dá 1 ponto num serviço de 1
 * plano (o próprio foco, normalmente sem vínculo de plano) e até 2 num serviço de 2
 * planos (um por plano, cobrindo o caso em que o técnico vinculou pontos diferentes a
 * cada plano). Nunca depende de quantos mancais existem no equipamento.
 */
export function pontosUsados(servico: ServicoCampo): BalanceamentoPonto[] {
  const porId = new Map(servico.pontos.map((p) => [p.id, p]));
  const usados: BalanceamentoPonto[] = [];
  const vistos = new Set<number>();

  for (const plano of servico.planos) {
    const ponto = servico.pontos.find((p) => p.plano === plano.id);
    if (ponto && !vistos.has(ponto.id)) {
      usados.push(ponto);
      vistos.add(ponto.id);
    }
  }

  const foco = servico.ponto_foco != null ? porId.get(servico.ponto_foco) : undefined;
  if (foco && !vistos.has(foco.id)) {
    usados.unshift(foco);
    vistos.add(foco.id);
  }

  return usados;
}
