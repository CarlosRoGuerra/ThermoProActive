import { FolhaCampo } from "./folha-campo";

export default async function FolhaCampoPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <FolhaCampo carregamentoId={Number(id)} />;
}
