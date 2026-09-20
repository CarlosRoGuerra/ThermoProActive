"use client";

import { AuthShell } from "@/features/auth/components/auth-shell";
import { MfaSetup } from "@/features/auth/components/mfa-setup";
import { RouteGuard } from "@/components/shell/guard";

export default function AdminMfaSetupPage() {
  return <RouteGuard area="admin">{() => <AuthShell contexto="admin"><MfaSetup contexto="admin" /></AuthShell>}</RouteGuard>;
}
