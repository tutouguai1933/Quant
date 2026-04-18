# WebUI 容器镜像。
# 这个镜像在服务器上构建并启动 Next.js 控制台。
FROM node:20-bookworm-slim

ENV PNPM_HOME=/pnpm
ENV PATH=/pnpm:$PATH

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

RUN corepack enable

WORKDIR /app/apps/web

COPY apps/web/package.json /app/apps/web/package.json
COPY apps/web/pnpm-lock.yaml /app/apps/web/pnpm-lock.yaml
RUN pnpm install --frozen-lockfile --prod=false

COPY apps/web /app/apps/web

RUN pnpm build

ENV NODE_ENV=production

CMD ["pnpm", "start", "--hostname", "0.0.0.0", "--port", "9012"]
