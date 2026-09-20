"use client";

import { AuthShell } from "@/features/auth/components/auth-shell";
import { ForgotPasswordForm } from "@/features/auth/components/recovery-forms";

export default function AdminForgotPage() {
  return <AuthShell contexto="admin"><ForgotPasswordForm contexto="admin" /></AuthShell>;
}
