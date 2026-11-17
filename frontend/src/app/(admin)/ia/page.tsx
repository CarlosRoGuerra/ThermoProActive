import { redirect } from "next/navigation";

/** A área de IA tem dois lugares: as chaves e a ativação. A raiz abre o primeiro. */
export default function IaPage() {
  redirect("/ia/chaves");
}
