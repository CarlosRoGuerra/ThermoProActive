"use client";

import Link from "next/link";
import { Activity, BadgeCheck, LockKeyhole, Radar, ShieldCheck } from "lucide-react";
import { Logo, ThemeToggle } from "@/components/ds";
import { RodapeMarca } from "@/components/shell/rodape";
import type { ContextoAuth } from "../api";

export function AuthShell({
  contexto,
  children,
}: {
  contexto: ContextoAuth;
  children: React.ReactNode;
}) {
  return contexto === "portal" ? (
    <PortalShell>{children}</PortalShell>
  ) : (
    <AdminShell>{children}</AdminShell>
  );
}

function PortalShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-[100dvh] bg-bg lg:grid lg:grid-cols-[minmax(22rem,0.9fr)_minmax(30rem,1.1fr)]">
      <aside className="relative hidden overflow-hidden bg-chrome p-10 lg:flex lg:min-h-[100dvh] lg:flex-col xl:p-14">
        <div
          className="pointer-events-none absolute inset-0 opacity-[0.08]"
          aria-hidden="true"
          style={{ backgroundImage: "linear-gradient(var(--chrome-fg) 1px,transparent 1px),linear-gradient(90deg,var(--chrome-fg) 1px,transparent 1px)", backgroundSize: "48px 48px" }}
        />
        <div className="relative"><Logo tamanho="lg" onChrome /></div>
        <div className="relative my-auto max-w-lg py-14">
          <div className="mb-7 flex h-14 w-14 items-center justify-center rounded-2xl border border-chrome-border bg-chrome-active text-[#a8c9fc]">
            <Radar className="h-7 w-7" aria-hidden="true" />
          </div>
          <h2 className="text-3xl font-semibold leading-tight text-chrome-fg xl:text-4xl">
            A condição dos seus ativos, sempre ao alcance.
          </h2>
          <p className="mt-5 max-w-md text-base leading-relaxed text-chrome-fg-muted">
            Acompanhe equipamentos, inspeções, alertas e relatórios em um ambiente feito para a sua operação.
          </p>
          <div className="mt-10 grid gap-4 border-t border-chrome-border pt-7 sm:grid-cols-2">
            <PortalValue icon={Activity} title="Monitoramento claro" text="Do alerta ao laudo técnico." />
            <PortalValue icon={BadgeCheck} title="Dados protegidos" text="Acesso restrito à sua empresa." />
          </div>
        </div>
        <p className="relative text-xs text-chrome-fg-subtle">
          Portal do Cliente · Pred Ativos
        </p>
      </aside>
      <main className="flex min-h-[100dvh] flex-col">
        <header className="flex items-center justify-between px-5 py-5 sm:px-8 lg:justify-end">
          <Link href="/portal/login" className="lg:hidden"><Logo tamanho="md" /></Link>
          <ThemeToggle />
        </header>
        <div className="flex flex-1 items-center justify-center px-5 pb-12 sm:px-8">
          <div className="w-full max-w-md animate-slide-up">{children}</div>
        </div>
        <RodapeMarca />
      </main>
    </div>
  );
}

function PortalValue({ icon: Icon, title, text }: { icon: typeof Activity; title: string; text: string }) {
  return (
    <div className="flex gap-3">
      <Icon className="mt-0.5 h-5 w-5 shrink-0 text-[#a8c9fc]" aria-hidden="true" />
      <div><p className="text-sm font-semibold text-chrome-fg">{title}</p><p className="mt-0.5 text-xs text-chrome-fg-muted">{text}</p></div>
    </div>
  );
}

function AdminShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-[100dvh] bg-chrome text-chrome-fg">
      <div className="mx-auto flex min-h-[100dvh] max-w-[1440px] flex-col px-5 sm:px-8 lg:px-12">
        <header className="flex items-center justify-between border-b border-chrome-border py-5">
          <Link href="/admin/login"><Logo tamanho="md" onChrome /></Link>
          <div className="flex items-center gap-3">
            <span className="hidden items-center gap-2 rounded-full border border-chrome-border px-3 py-1.5 text-xs font-medium text-chrome-fg-muted sm:flex">
              <ShieldCheck className="h-3.5 w-3.5 text-success" aria-hidden="true" /> Ambiente restrito
            </span>
            <ThemeToggle />
          </div>
        </header>
        <main className="grid flex-1 items-center gap-12 py-12 lg:grid-cols-[1fr_28rem] lg:py-16">
          <section className="hidden max-w-xl lg:block">
            <LockKeyhole className="h-10 w-10 text-primary" aria-hidden="true" />
            <p className="mt-8 text-sm font-medium text-[#a8c9fc]">Pred Ativos Control</p>
            <h2 className="mt-3 text-4xl font-semibold leading-tight text-chrome-fg">
              Operação técnica com acesso controlado.
            </h2>
            <p className="mt-5 max-w-lg text-base leading-relaxed text-chrome-fg-muted">
              Ambiente exclusivo para colaboradores autorizados. As ações relevantes ficam registradas na trilha de segurança.
            </p>
          </section>
          <section className="rounded-2xl border border-chrome-border bg-surface p-6 text-fg shadow-xl sm:p-8">
            {children}
          </section>
        </main>
        <footer className="border-t border-chrome-border py-5 text-xs text-chrome-fg-subtle">
          Acesso monitorado · Pred Ativos
        </footer>
        <RodapeMarca onChrome />
      </div>
    </div>
  );
}
