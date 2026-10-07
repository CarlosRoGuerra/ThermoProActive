import ImprimirClient from "./imprimir-client";

export default async function ImprimirPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { id } = await params;
  const busca = await searchParams;
  // Envio do mês (fluidos): só a coleta e só as amostras com desvio.
  const carregamento = typeof busca.carregamento === "string" && /^\d+$/.test(busca.carregamento) ? busca.carregamento : "";
  const recorte = carregamento
    ? `?carregamento=${carregamento}${busca.somente_desvios === "1" ? "&somente_desvios=1" : ""}`
    : "";
  return <ImprimirClient relatorioId={Number(id)} recorte={recorte} />;
}
