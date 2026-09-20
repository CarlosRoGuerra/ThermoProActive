"use client";

import { use } from "react";
import { AuthShell } from "@/features/auth/components/auth-shell";
import { InviteForm } from "@/features/auth/components/invite-form";

export default function PortalInvitePage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = use(params);
  return <AuthShell contexto="portal"><InviteForm contexto="portal" token={token} /></AuthShell>;
}
