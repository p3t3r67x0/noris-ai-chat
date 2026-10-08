FROM node:25-bookworm-slim AS base
RUN npm install --global pnpm@11.1.3
WORKDIR /app
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY frontend/package.json ./frontend/package.json

FROM base AS development
COPY frontend ./frontend
RUN pnpm install --frozen-lockfile
RUN chown -R node:node /app/frontend
WORKDIR /app/frontend
USER node
EXPOSE 3000
CMD ["pnpm", "dev", "--host", "0.0.0.0", "--port", "3000"]

FROM base AS build
COPY frontend ./frontend
RUN pnpm install --frozen-lockfile
RUN pnpm --dir frontend build

FROM node:25-bookworm-slim AS production
WORKDIR /app
COPY --from=build --chown=node:node /app/frontend/.output ./
USER node
ENV NODE_ENV=production HOST=0.0.0.0 PORT=3000
EXPOSE 3000
CMD ["node", "server/index.mjs"]
