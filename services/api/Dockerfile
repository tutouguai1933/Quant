# 控制平面 API 容器镜像。
# 这个镜像给阿里云部署使用，负责对外提供 API 服务。
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

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
