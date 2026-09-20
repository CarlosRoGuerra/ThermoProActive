import { redirect } from "next/navigation";

/** Compatibilidade para links antigos; a autenticação agora tem entradas separadas. */
export default function LegacyLogin() {
  redirect("/portal/login");
}
