# MCP Guardian frontend — Next.js (SSR, NOT a static export: dynamic routes +
# client fetch). Multi-stage build, serves with `next start -p 3000`.
#
# NEXT_PUBLIC_* vars are inlined into the client bundle at BUILD time — pass
# them as build args (docker compose does this from the root .env):
#   docker build --build-arg NEXT_PUBLIC_API_URL=https://<api-gateway-url> -t mcp-guardian-web .
#
# The RUNTIME ENV below satisfies `next start` but does not re-inline client
# code; rebuilding is the way to change the API URL (see docs/deploy.md).

# ---- 1. dependencies --------------------------------------------------------
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# ---- 2. build ---------------------------------------------------------------
FROM node:20-alpine AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Public env at build time (see note above about build-time inlining).
# next.config.js validates CHIMERA/Cognito vars in production builds; the
# placeholders below keep container builds working before real values exist.
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ARG NEXT_PUBLIC_CHIMERA_API_URL=http://localhost:8000
ARG NEXT_PUBLIC_COGNITO_DOMAIN=placeholder.auth.us-east-1.amazoncognito.com
ARG NEXT_PUBLIC_COGNITO_APP_CLIENT_ID=placeholder-client-id
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL \
    NEXT_PUBLIC_CHIMERA_API_URL=$NEXT_PUBLIC_CHIMERA_API_URL \
    NEXT_PUBLIC_COGNITO_DOMAIN=$NEXT_PUBLIC_COGNITO_DOMAIN \
    NEXT_PUBLIC_COGNITO_APP_CLIENT_ID=$NEXT_PUBLIC_COGNITO_APP_CLIENT_ID

RUN npm run build

# ---- 3. runner --------------------------------------------------------------
FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    PORT=3000 \
    NEXT_PUBLIC_API_URL=http://localhost:8000

COPY --from=deps /app/node_modules ./node_modules
COPY --from=build /app/.next ./.next
COPY --from=build /app/public ./public
COPY package.json next.config.js ./

EXPOSE 3000
CMD ["./node_modules/.bin/next", "start", "-p", "3000"]
