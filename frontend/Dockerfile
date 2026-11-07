# Frontend ThermoProActive — Next.js 15 (saída standalone)
# Multi-stage: deps -> build -> runner (imagem final mínima).

FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# NEXT_PUBLIC_* é embutido no bundle em build-time. O navegador (no host) acessa a API
# publicada em localhost:8000. Sobrescreva via build-arg para outro host.
ARG NEXT_PUBLIC_API_URL=http://localhost:8000/api
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0
# Roda como o usuário não-privilegiado 'node' (já existe na imagem): uma falha no
# servidor Next não dá root dentro do container. Cache do Next gravável pelo usuário.
COPY --from=builder --chown=node:node /app/public ./public
COPY --from=builder --chown=node:node /app/.next/standalone ./
COPY --from=builder --chown=node:node /app/.next/static ./.next/static
RUN mkdir -p /app/.next/cache && chown node:node /app/.next/cache
USER node
EXPOSE 3000
CMD ["node", "server.js"]
