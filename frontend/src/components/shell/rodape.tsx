/**
 * Crédito fixo do rodapé — em toda página, dentro e fora do login.
 *
 * "Pred Ativos" é o produto; "by Thermoproactive" é quem o constrói e opera —
 * mesmo relacionamento de uma marca com o estúdio por trás dela. Fica no fim
 * do conteúdo rolável (não fixo sobre a tela), pra não competir com a barra
 * inferior de ação da folha de campo no celular.
 */
export function RodapeMarca({
  onChrome = false,
  className = "",
}: {
  /** Sobre o fundo escuro de navegação/login — mesmo par usado por `Logo`. */
  onChrome?: boolean;
  className?: string;
}) {
  return (
    <footer
      className={`py-6 text-center text-2xs ${onChrome ? "text-chrome-fg-subtle" : "text-fg-subtle"} ${className}`}
    >
      by Thermoproactive
    </footer>
  );
}
