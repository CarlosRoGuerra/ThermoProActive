import { AnaliseFinal } from "./analise-final";

export default async function AnaliseFinalEditPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <AnaliseFinal achadoId={Number(id)} />;
}
