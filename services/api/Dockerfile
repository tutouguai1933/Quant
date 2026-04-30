# 控制平面 API 容器镜像。
# 这个镜像给阿里云部署使用，负责对外提供 API 服务。
FROM python:3.11-slim

# 使用阿里云apt镜像加速
RUN sed -i 's@//deb.debian.org@//mirrors.aliyun.com@g' /etc/apt/sources.list.d/debian.sources

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 配置pip使用阿里云镜像
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/ && \
    pip config set install.trusted-host mirrors.aliyun.com

RUN apt-get update && apt-get install -y --no-install-recommends curl docker-cli && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY services/api/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY services /app/services
COPY packages /app/packages
COPY docs /app/docs
COPY README.md /app/README.md
COPY CONTEXT.md /app/CONTEXT.md
COPY plan.md /app/plan.md

CMD ["uvicorn", "services.api.app.main:app", "--host", "0.0.0.0", "--port", "9011"]
