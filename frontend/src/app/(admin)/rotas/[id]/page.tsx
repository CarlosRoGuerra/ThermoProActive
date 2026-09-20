import { RotaForm } from "../rota-form";

export default async function EditarRotaPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <RotaForm rotaId={Number(id)} />;
}
