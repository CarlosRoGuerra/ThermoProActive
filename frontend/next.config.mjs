/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async headers() {
    const securityHeaders = [
      { key: "X-Content-Type-Options", value: "nosniff" },
      { key: "X-Frame-Options", value: "DENY" },
      { key: "Referrer-Policy", value: "same-origin" },
    ];
    return [
      { source: "/:path*", headers: securityHeaders },
      {
        source: "/portal/:path*",
        headers: [{ key: "Cache-Control", value: "private, no-store, max-age=0" }],
      },
      {
        source: "/admin/:path*",
        headers: [{ key: "Cache-Control", value: "private, no-store, max-age=0" }],
      },
    ];
  },
  // Saída standalone: imagem Docker enxuta (server.js + deps mínimas).
  output: "standalone",
  // Raiz de tracing = esta pasta (evita aviso por lockfiles em diretórios pais).
  outputFileTracingRoot: import.meta.dirname,
  // O lint roda via `npm run lint` (ferramenta separada); o build usa apenas o
  // type-check do TypeScript para ser determinístico em CI/VPS.
  eslint: { ignoreDuringBuilds: true },
};

export default nextConfig;
