import { EnsaiosSubestacaoPagina } from "./ensaios-subestacao";

export default async function EnsaiosSubestacaoPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <EnsaiosSubestacaoPagina itemId={Number(id)} />;
}
