/**
 * Curva e duração de movimento do produto.
 *
 * Um valor só, para que toda transição tenha a mesma "física": entradas rápidas
 * que desaceleram no fim. Sistema de operação transmite estabilidade — nada de
 * mola, salto ou movimento contínuo.
 *
 * Os componentes de animação (FadeIn/Stagger) que existiam aqui foram
 * absorvidos pelo Design System: o `LoadingState` reserva o espaço do conteúdo,
 * e Modal/Drawer/Toast/DropdownMenu animam a si mesmos. Escalonar a entrada de
 * cartões num painel denso só atrasava a leitura do número.
 */
export const EASE_OUT = [0.22, 1, 0.36, 1] as const;

/** Durações em segundos, espelhando os tokens `duration-*` do Tailwind. */
export const DURACAO = {
  rapida: 0.15,
  normal: 0.2,
  lenta: 0.3,
} as const;
