/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Saída standalone: imagem Docker enxuta (server.js + deps mínimas).
  output: "standalone",
  // Raiz de tracing = esta pasta (evita aviso por lockfiles em diretórios pais).
  outputFileTracingRoot: import.meta.dirname,
  // O lint roda via `npm run lint` (ferramenta separada); o build usa apenas o
  // type-check do TypeScript para ser determinístico em CI/VPS.
  eslint: { ignoreDuringBuilds: true },
};

export default nextConfig;
