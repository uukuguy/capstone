FROM node:24.20.0-alpine AS build

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY index.html tsconfig.json vite.config.ts ./
COPY build-revision.txt ./
COPY public/ public/
COPY src/ src/
ARG VITE_API_ORIGIN
RUN test -n "$VITE_API_ORIGIN" && npm run build

FROM caddy:2.10.2-alpine
COPY Caddyfile /etc/caddy/Caddyfile
COPY --from=build /app/dist/ /srv/
EXPOSE 3000
