FROM node:24.20.0-alpine@sha256:e67514e5d0f6c46656005e1b693b2ec9d52e80b641307de684d4a015ba7a4eaf AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY index.html tsconfig.json vite.config.ts ./
COPY build-revision.txt build-environment.json ./
COPY public/ public/
COPY src/ src/
RUN npm run build
RUN node -e 'const fs=require("fs"); const receipt=JSON.parse(fs.readFileSync("build-environment.json")); fs.writeFileSync("dist/__capstone-build", JSON.stringify({version:JSON.parse(fs.readFileSync("package.json")).version, revision:receipt.source_revision, environment:receipt.environment, dirty:false}))'

FROM caddy:2.10.2-alpine@sha256:4c6e91c6ed0e2fa03efd5b44747b625fec79bc9cd06ac5235a779726618e530d
COPY Caddyfile /etc/caddy/Caddyfile
COPY --from=build /app/dist/ /srv/
EXPOSE 3000
