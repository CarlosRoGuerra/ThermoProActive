"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { LoaderCircle } from "lucide-react";
import { Logo } from "@/components/ds";
import { useAuth } from "@/lib/auth";
import { rotaInicial } from "@/lib/permissions";

/**
 * Porta de entrada: manda cada um para a sua casa.
 * Cliente → /portal/dashboard · equipe interna → /admin/dashboard.
 */
export default function Home() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    router.replace(rotaInicial(user));
  }, [user, loading, router]);

  return (
    <div className="flex min-h-[100dvh] flex-col items-center justify-center gap-5 bg-bg px-6">
      <Logo tamanho="lg" />
      <p role="status" className="flex items-center gap-2.5 text-sm text-fg-muted">
        <LoaderCircle className="h-4 w-4 animate-spin text-primary" aria-hidden="true" />
        Abrindo a plataforma…
      </p>
    </div>
  );
}
