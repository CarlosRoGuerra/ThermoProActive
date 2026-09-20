import type { Metadata, Viewport } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/lib/auth";
import { ClienteAtivoProvider } from "@/lib/cliente-ativo";

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
  title: {
    default: "Pred Ativos — Manutenção Preditiva",
    template: "%s · Pred Ativos",
  },
  description:
    "Plataforma de manutenção preditiva: inspeções em campo, análise por norma, laudos técnicos e portal do cliente.",
  applicationName: "Pred Ativos",
  // Painel autenticado: não deve ser indexado.
  robots: { index: false, follow: false },

  /* Ícones da marca. O App Router já publica sozinho `app/icon.png`,
     `app/apple-icon.png` e `app/favicon.ico`; a declaração explícita abaixo
     acrescenta os tamanhos que navegadores antigos procuram e o manifesto
     usado quando o sistema é instalado como aplicativo. */
  manifest: "/site.webmanifest",
  /*
   * Ícones declarados por inteiro, com os arquivos em `public/`.
   *
   * Por que não a convenção `app/icon.png` do App Router: declarar
   * `metadata.icons` SUPRIME a convenção, e o resultado foi o ícone do iOS
   * deixar de ser publicado silenciosamente. Com tudo explícito, o que está
   * escrito aqui é exatamente o que sai no HTML — e todos os arquivos ficam
   * num diretório só, fácil de substituir quando a marca mudar.
   *
   * Sem `mask-icon` (pinned tab do Safari): ele exige SVG vetorial de uma cor
   * só, e a marca recebida é raster. Precisaria do arquivo vetorial original.
   */
  icons: {
    icon: [
      { url: "/favicon.ico", sizes: "16x16 32x32 48x48", type: "image/x-icon" },
      { url: "/favicon-16x16.png", sizes: "16x16", type: "image/png" },
      { url: "/favicon-32x32.png", sizes: "32x32", type: "image/png" },
      { url: "/icon-256.png", sizes: "256x256", type: "image/png" },
      { url: "/brand/icon-192.png", sizes: "192x192", type: "image/png" },
      { url: "/brand/icon-512.png", sizes: "512x512", type: "image/png" },
    ],
    apple: [{ url: "/apple-touch-icon.png", sizes: "180x180", type: "image/png" }],
    shortcut: [{ url: "/favicon.ico" }],
  },
  other: {
    // Bloco do Windows: cor do azulejo ao fixar o site na barra de tarefas.
    "msapplication-TileColor": "#ffffff",
    "msapplication-TileImage": "/brand/mstile-150.png",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  // A interface é operada em campo, no celular: o zoom precisa continuar
  // disponível (WCAG 1.4.4 — Redimensionar texto).
  maximumScale: 5,
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f4f6fa" },
    { media: "(prefers-color-scheme: dark)", color: "#070b12" },
  ],
};

/**
 * Aplica o tema salvo antes da primeira pintura (evita o flash claro→escuro).
 * Roda antes do React hidratar, por isso é um script inline mínimo.
 */
const INICIAR_TEMA = `try{var t=localStorage.getItem('tpa-theme');if(t==='dark'||t==='light'){document.documentElement.dataset.theme=t;}}catch(e){}`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR" className={`${inter.variable} ${mono.variable}`} suppressHydrationWarning>
      <body className="font-sans">
        <script dangerouslySetInnerHTML={{ __html: INICIAR_TEMA }} />
        <AuthProvider>
          <ClienteAtivoProvider>{children}</ClienteAtivoProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
