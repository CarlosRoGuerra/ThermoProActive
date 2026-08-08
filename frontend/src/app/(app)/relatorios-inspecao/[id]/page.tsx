import { RelatorioDossie } from "./dossie";

export default async function RelatorioDossiePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <RelatorioDossie relatorioId={Number(id)} />;
}
