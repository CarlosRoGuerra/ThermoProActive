"use client";

import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { api, login as apiLogin, logout as apiLogout } from "./api";
import type { User } from "./types";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  signIn: (area: "portal" | "admin", email: string, password: string, lembrar?: boolean, codigoMfa?: string) => Promise<User>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api<User>("/auth/me/")
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  async function signIn(area: "portal" | "admin", email: string, password: string, lembrar = false, codigoMfa = "") {
    const u = await apiLogin(area, email, password, lembrar, codigoMfa);
    setUser(u);
    return u;
  }

  async function signOut() {
    try {
      await apiLogout();
    } finally {
      setUser(null);
    }
  }

  return (
    <AuthContext.Provider value={{ user, loading, signIn, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth deve ser usado dentro de AuthProvider");
  return ctx;
}
