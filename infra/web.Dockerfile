# Frontend: build the React app, then serve it with Caddy, which also forwards /api to the
# backend (same job as the Vite dev proxy). Build context: repository root.
FROM node:24-alpine AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npx vite build

FROM caddy:2.10-alpine
COPY infra/web.Caddyfile /etc/caddy/Caddyfile
COPY --from=build /app/dist /srv
