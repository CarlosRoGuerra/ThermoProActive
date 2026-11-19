import { FONTE_RELATORIO } from "./folhas";

/* Impressão com paged.js (rotas /imprimir e /carta): o que precisa estar pronto
   antes de o paged.js medir as folhas e o que entra depois que ele pagina. */

/** Esconde a fonte do paged.js sem tirá-la do layout: as folhas em fluxo da carta
 *  medem a altura do texto ali dentro (com `display: none` não haveria medida). */
export const CSS_FONTE_PAGINACAO = `
  .paged-source { position: absolute; left: 0; top: 0; width: 210mm; height: 0; overflow: hidden; visibility: hidden; }
  @media print { .paged-source { display: none; } }
`;

const LIMITE_ESPERA_MS = 15000;

/** Espera tudo o que muda a altura das folhas: as folhas em fluxo terminarem de
 *  medir (`data-paginando`), as imagens carregarem e as fontes ficarem prontas. */
export async function esperarLayout(fonte: HTMLElement, cancelado: () => boolean) {
  const limite = Date.now() + LIMITE_ESPERA_MS;
  while (fonte.querySelector("[data-paginando]")) {
    if (cancelado()) return;
    // Sem a medida, o PDF sairia sem os itens 5 e 6 da carta: melhor falhar.
    if (Date.now() > limite) throw new Error("As folhas da carta não terminaram de paginar.");
    await new Promise((r) => setTimeout(r, 30));
  }
  const imgs = Array.from(fonte.querySelectorAll("img"));
  await Promise.all(
    imgs.map((im) =>
      im.complete ? Promise.resolve() : new Promise((res) => { im.onload = im.onerror = () => res(null); })
    )
  );
  await document.fonts.ready;
}

/** "Página X de Y" no pé direito de cada folha, alinhado à margem direita do texto
 *  (carta 15 mm, demais folhas 5 mm). Capa e contracapas contam, mas não mostram:
 *  o telefone ocupa esse canto. */
export function numerarPaginas(alvo: HTMLElement) {
  const paginas = Array.from(alvo.querySelectorAll<HTMLElement>(".pagedjs_page"));
  paginas.forEach((pagina, i) => {
    const folha = pagina.querySelector<HTMLElement>(".pagedjs_sheet");
    if (!folha || pagina.querySelector(".pagina-capa")) return;
    const numero = document.createElement("div");
    numero.className = "numero-pagina";
    numero.textContent = `Página ${i + 1} de ${paginas.length}`;
    Object.assign(numero.style, {
      position: "absolute", bottom: "4mm", right: pagina.querySelector(".pagina-carta") ? "15mm" : "5mm",
      fontFamily: FONTE_RELATORIO, fontSize: "8pt", lineHeight: "1", color: "#64748b", zIndex: "2",
    });
    folha.appendChild(numero);
  });
}
