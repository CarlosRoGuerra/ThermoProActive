import Link from "next/link";
import { AuthShell } from "@/features/auth/components/auth-shell";

export default function PortalFirstAccessPage() {
  return <AuthShell contexto="portal"><h1 className="text-2xl font-semibold text-fg">Primeiro acesso</h1><p className="mt-3 text-sm leading-relaxed text-fg-muted">Seu primeiro acesso começa pelo convite enviado ao seu e-mail. Abra o link pessoal para confirmar seus dados e criar uma senha.</p><Link href="/portal/login" className="mt-6 inline-block font-medium text-primary hover:underline">Voltar ao login</Link></AuthShell>;
}
