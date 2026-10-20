FROM node:24.21.0-bookworm-slim AS build

ENV COREPACK_HOME=/tmp/corepack
RUN corepack enable && corepack prepare pnpm@12.11.2 --activate
WORKDIR /app
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY tools/openapi/package.json tools/openapi/package.json
COPY . .
RUN pnpm install --frozen-lockfile
RUN pnpm build

FROM node:24.21.0-bookworm-slim AS production-deps

ENV COREPACK_HOME=/tmp/corepack
RUN corepack enable && corepack prepare pnpm@12.11.2 --activate
WORKDIR /app
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY tools/openapi/package.json tools/openapi/package.json
RUN pnpm install --prod --frozen-lockfile --ignore-scripts

FROM node:24.21.0-bookworm-slim AS runtime
ENV NODE_ENV=production \
    HOST=0.0.0.0 \
    PORT=3000
RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin app
WORKDIR /app
COPY --from=production-deps --chown=app:app /app/node_modules ./node_modules
COPY --chown=app:app package.json ./package.json
COPY --from=build --chown=app:app /app/build ./build
USER app
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD ["node", "-e", "fetch('http://127.0.0.1:3000/').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"]
CMD ["./node_modules/.bin/react-router-serve", "build/server/index.js"]
