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
/**
 * Sugestão de plano por posição do mancal (confirmado com o cliente, 2026-09-16):
 * num trem acoplado motor→equipamento acionado, o peso de prova vai no plano OPOSTO
 * ao mancal de maior amplitude — mancal 1 (motor, lado oposto ao acoplamento) ou
 * mancal 3 (equipamento acionado, lado do acoplamento) apontam pro Plano 2; mancal 2
 * (motor, lado do acoplamento) ou mancal 4 (equipamento acionado, lado oposto ao
 * acoplamento) apontam pro Plano 1. Fora dessa numeração (trem com mais de 4 mancais,
 * ou configuração atípica) não há sugestão — o técnico decide livremente.
 *
 * É só um valor inicial pro `<Select>` de plano: nunca decide sozinha, nunca
 * impede a troca manual.
 */
export function sugerirPlano(numeroMancal: number): 1 | 2 | null {
  if (numeroMancal === 1 || numeroMancal === 3) return 2;
  if (numeroMancal === 2 || numeroMancal === 4) return 1;
  return null;
}

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
