# syntax=docker/dockerfile:1.7
# Frontend Next.js Trema Job Search — build en workspace pnpm, image runtime "standalone" minimale
FROM node:22-alpine AS base
RUN corepack enable && corepack prepare pnpm@11.23.0 --activate
WORKDIR /repo

# ---- Dépendances (workspace) ----
FROM base AS deps
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml turbo.json ./
COPY packages/api-client/package.json packages/api-client/
COPY apps/web/package.json apps/web/
RUN --mount=type=cache,id=pnpm,target=/root/.local/share/pnpm/store \
    pnpm install --frozen-lockfile

# ---- Build ----
FROM deps AS build
# URL de l'API vue depuis le navigateur ; figée dans le bundle au build
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL \
    NEXT_TELEMETRY_DISABLED=1
COPY packages/api-client/ packages/api-client/
COPY apps/web/ apps/web/
RUN pnpm --filter web build

# ---- Runtime ----
FROM node:22-alpine AS runner
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0
WORKDIR /app
RUN addgroup -S nextjs && adduser -S nextjs -G nextjs
# La sortie "standalone" contient un serveur Node autonome et ses seules dépendances nécessaires
COPY --from=build --chown=nextjs:nextjs /repo/apps/web/.next/standalone ./
COPY --from=build --chown=nextjs:nextjs /repo/apps/web/.next/static ./apps/web/.next/static
USER nextjs
EXPOSE 3000
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
    CMD wget -qO- http://localhost:${PORT}/ >/dev/null 2>&1 || exit 1
CMD ["node", "apps/web/server.js"]
