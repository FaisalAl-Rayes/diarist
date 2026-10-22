# syntax=docker/dockerfile:1

FROM node:22-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:22-slim AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# This is a public browser identifier, never a Clerk secret key.
ARG NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY
ENV NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=$NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY
RUN npm run build

# Next.js "standalone" output bundles only the files node needs to run
# `server.js` — no full node_modules, no dev dependencies.
FROM node:22-slim AS run
WORKDIR /app
ENV NODE_ENV=production \
    PORT=3000

# The node:22-slim base image already ships a non-root "node" user (uid 1000).
USER node

COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static
COPY --from=build --chown=node:node /app/public ./public

EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD node -e "fetch('http://localhost:3000/sign-in',{redirect:'manual'}).then(r=>process.exit(r.status===200?0:1)).catch(()=>process.exit(1))"
CMD ["node", "server.js"]
