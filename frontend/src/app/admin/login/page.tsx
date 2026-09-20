"use client";

import { Suspense } from "react";
import { AuthShell } from "@/features/auth/components/auth-shell";
import { LoginForm } from "@/features/auth/components/login-form";

export default function AdminLoginPage() {
  return <AuthShell contexto="admin"><Suspense><LoginForm contexto="admin" /></Suspense></AuthShell>;
}
