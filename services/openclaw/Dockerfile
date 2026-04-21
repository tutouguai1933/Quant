# OpenClaw 定时运维服务
# 负责按固定间隔调用 Quant API 的 patrol 接口
FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir requests schedule

COPY openclaw_scheduler.py /app/openclaw_scheduler.py

ENV QUANT_API_BASE_URL=http://api:9011/api/v1
ENV HEALTH_CHECK_INTERVAL=60
ENV STATE_SYNC_INTERVAL=300
ENV CYCLE_CHECK_INTERVAL=900

CMD ["python", "openclaw_scheduler.py"]