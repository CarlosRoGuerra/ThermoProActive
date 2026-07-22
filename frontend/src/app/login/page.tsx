"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { ShieldCheck } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { Button, Field, Input, ThemeToggle } from "@/components/ui";
import { EASE_OUT } from "@/components/motion";

const DEMO = [
  ["admin@thermoproactive.com", "Administrador"],
  ["tecnico@thermoproactive.com", "Técnico/Analista"],
  ["cliente@exemplo.com", "Cliente (PCM)"],
];

export default function LoginPage() {
  const { signIn } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("tecnico@thermoproactive.com");
  const [password, setPassword] = useState("thermo123");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const u = await signIn(email, password);
      router.replace(u.is_cliente ? "/portal" : "/dashboard");
    } catch {
      setError("E-mail ou senha inválidos.");
      setBusy(false);
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center bg-bg p-4">
      <ThemeToggle className="absolute right-4 top-4" />
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, ease: EASE_OUT }}
        className="w-full max-w-sm"
      >
        <div className="mb-8 flex flex-col items-center text-center">
          <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-accent to-accent-2 text-white shadow-sm">
            <ShieldCheck className="h-6 w-6" />
          </div>
          <h1 className="text-xl font-semibold tracking-tight text-fg">ThermoProActive</h1>
          <p className="mt-1 text-sm text-fg-muted">Gestão de Manutenção Preditiva</p>
        </div>

        <div className="rounded-2xl border border-border bg-surface p-6 shadow-sm sm:p-7">
          <form onSubmit={handleSubmit} className="space-y-4">
            <Field label="E-mail" htmlFor="email">
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
              />
            </Field>
            <Field label="Senha" htmlFor="senha">
              <Input
                id="senha"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="current-password"
              />
            </Field>

            {error && (
              <motion.p
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                className="rounded-lg bg-danger-subtle px-3 py-2 text-sm text-danger-fg"
              >
                {error}
              </motion.p>
            )}

            <Button type="submit" loading={busy} className="w-full">
              Entrar
            </Button>
          </form>
        </div>

        <div className="mt-5 rounded-xl border border-border bg-surface-muted/50 p-3.5 text-xs text-fg-muted">
          <p className="font-medium text-fg-muted">Acessos de demonstração · senha: thermo123</p>
          <ul className="mt-2 space-y-1">
            {DEMO.map(([mail, role]) => (
              <li key={mail} className="flex items-center justify-between gap-2">
                <button
                  type="button"
                  onClick={() => setEmail(mail)}
                  className="font-mono text-fg-muted transition-colors hover:text-accent"
                >
                  {mail}
                </button>
                <span className="text-fg-subtle">{role}</span>
              </li>
            ))}
          </ul>
        </div>
      </motion.div>
    </div>
  );
}
