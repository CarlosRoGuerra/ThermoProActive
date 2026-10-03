import { EnsaiosFluidoPagina } from "./ensaios-fluido";

export default async function EnsaiosFluidoPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <EnsaiosFluidoPagina itemId={Number(id)} />;
}
