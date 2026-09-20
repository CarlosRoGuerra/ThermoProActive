"use client";

import { Suspense } from "react";
import { AuthShell } from "@/features/auth/components/auth-shell";
import { ResetPasswordForm } from "@/features/auth/components/recovery-forms";

export default function PortalResetPage() {
  return <AuthShell contexto="portal"><Suspense><ResetPasswordForm contexto="portal" /></Suspense></AuthShell>;
}
