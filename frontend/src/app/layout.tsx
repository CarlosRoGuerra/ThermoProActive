import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/lib/auth";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

// Mono para dados técnicos (métricas, TAGs, timestamps) — leitura de instrumento.
const mono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "ThermoProActive — Manutenção Preditiva",
  description: "Plataforma de gestão de manutenção preditiva, inspeções e laudos técnicos.",
};

// Aplica o tema salvo antes da 1ª pintura (evita flash claro→escuro no carregamento).
const themeInit = `try{var t=localStorage.getItem('tpa-theme');if(t==='dark'||t==='light'){document.documentElement.dataset.theme=t;}}catch(e){}`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR" className={`${inter.variable} ${mono.variable}`} suppressHydrationWarning>
      <body className="font-sans">
        <script dangerouslySetInnerHTML={{ __html: themeInit }} />
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
