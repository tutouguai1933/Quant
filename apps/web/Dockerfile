# WebUI 容器镜像。
# 这个镜像在服务器上构建并启动 Next.js 控制台。
FROM node:22-bookworm-slim

# 接受 API URL 作为构建参数
ARG QUANT_API_BASE_URL=http://127.0.0.1:9011/api/v1
ENV QUANT_API_BASE_URL=${QUANT_API_BASE_URL}

ENV PNPM_HOME=/pnpm
ENV PATH=/pnpm:$PATH

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

RUN corepack enable

WORKDIR /app/apps/web

COPY apps/web/package.json /app/apps/web/package.json
COPY apps/web/pnpm-lock.yaml /app/apps/web/pnpm-lock.yaml
COPY apps/web/.npmrc /app/apps/web/.npmrc
# 限制 Node 堆内存：服务器只有 1.6G 内存，install/build 不限内存会让系统 swap 打满卡死
ENV NODE_OPTIONS=--max-old-space-size=1024
# 使用 npm 安装避免 pnpm 的 sharp 构建问题
RUN npm install --legacy-peer-deps

COPY apps/web /app/apps/web

RUN npm run build

ENV NODE_ENV=production

CMD ["npm", "start", "--", "--hostname", "0.0.0.0", "--port", "9012"]
