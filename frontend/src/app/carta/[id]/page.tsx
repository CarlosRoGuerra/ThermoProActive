import CartaClient from "./carta-client";

export default async function CartaPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <CartaClient relatorioId={Number(id)} />;
}
