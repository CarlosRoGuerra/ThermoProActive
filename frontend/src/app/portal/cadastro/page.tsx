"use client";

import { AuthShell } from "@/features/auth/components/auth-shell";
import { AccessRequestForm } from "@/features/auth/components/access-request-form";

export default function PortalRegistrationPage() {
  return <AuthShell contexto="portal"><AccessRequestForm /></AuthShell>;
}
