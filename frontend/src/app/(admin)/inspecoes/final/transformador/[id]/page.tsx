import { EnsaiosTransformadorPagina } from "./ensaios-transformador";

export default async function EnsaiosTransformadorPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <EnsaiosTransformadorPagina itemId={Number(id)} />;
}
