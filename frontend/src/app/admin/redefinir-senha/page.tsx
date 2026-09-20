"use client";

import { Suspense } from "react";
import { AuthShell } from "@/features/auth/components/auth-shell";
import { ResetPasswordForm } from "@/features/auth/components/recovery-forms";

export default function AdminResetPage() {
  return <AuthShell contexto="admin"><Suspense><ResetPasswordForm contexto="admin" /></Suspense></AuthShell>;
}
