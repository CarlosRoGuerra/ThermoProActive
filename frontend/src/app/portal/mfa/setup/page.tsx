"use client";

import { Card } from "@/components/ds";
import { MfaSetup } from "@/features/auth/components/mfa-setup";

export default function PortalMfaSetupPage() {
  return <div className="mx-auto max-w-lg"><Card><MfaSetup contexto="portal" /></Card></div>;
}
