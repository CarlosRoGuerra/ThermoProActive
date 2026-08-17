// paged.js (0.4.x) não publica tipos — declaração mínima do que usamos.
declare module "pagedjs" {
  export class Previewer {
    preview(
      content: string | HTMLElement,
      stylesheets: Array<Record<string, string> | string>,
      renderTo: HTMLElement
    ): Promise<{ pages: unknown[]; total: number }>;
  }
}
