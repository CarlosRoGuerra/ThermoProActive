"use client";

import { AuthShell } from "@/features/auth/components/auth-shell";
import { ForgotPasswordForm } from "@/features/auth/components/recovery-forms";

export default function PortalForgotPage() {
  return <AuthShell contexto="portal"><ForgotPasswordForm contexto="portal" /></AuthShell>;
}
