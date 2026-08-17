import ImprimirClient from "./imprimir-client";

export default async function ImprimirPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <ImprimirClient relatorioId={Number(id)} />;
}
