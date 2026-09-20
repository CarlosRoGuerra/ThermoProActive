"use client";

import { Suspense } from "react";
import { AuthShell } from "@/features/auth/components/auth-shell";
import { LoginForm } from "@/features/auth/components/login-form";

export default function PortalLoginPage() {
  return <AuthShell contexto="portal"><Suspense><LoginForm contexto="portal" /></Suspense></AuthShell>;
}
