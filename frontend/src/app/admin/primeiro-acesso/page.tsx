import Link from "next/link";
import { AuthShell } from "@/features/auth/components/auth-shell";

export default function AdminFirstAccessPage() {
  return <AuthShell contexto="admin"><h1 className="text-2xl font-semibold text-fg">Primeiro acesso administrativo</h1><p className="mt-3 text-sm leading-relaxed text-fg-muted">Colaboradores entram somente por convite. Use o link pessoal recebido no e-mail corporativo para criar sua senha e configurar o segundo fator quando exigido.</p><Link href="/admin/login" className="mt-6 inline-block font-medium text-primary hover:underline">Voltar para a Área Administrativa</Link></AuthShell>;
}
