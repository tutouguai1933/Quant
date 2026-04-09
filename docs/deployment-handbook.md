# Quant 部署手册

这份文档专门回答：

- 本地怎么跑
- 阿里云怎么部署
- 代理和白名单怎么理解
- 出问题先查什么

## 1. 当前部署分工

默认分工已经固定：

- `WSL`：日常开发、本地测试、本地页面联调
- GitHub：唯一代码基线
- 阿里云服务器：真实 `dry-run / live` 验证和最终部署

## 2. 端口规则

标准主端口：

- API：`9011`
- Web：`9012`
- Freqtrade REST：`9013`
- Qlib：`9014`
- OpenClaw：`9015`

临时联调：

- `Quant-Debug-N`
- 每个调试条目占一个新的 10 端口区间

临时联调时：

- 按 `/home/djy/.port-registry.yaml` 申请 `Quant-Debug-N`
- 例如 `Quant-Debug-1` 可使用 `9021-9030`

## 3. 本地部署

### 环境

```bash
source /home/djy/miniforge3/etc/profile.d/conda.sh
conda activate quant
cd /home/djy/Quant
```

### API

```bash
set -a
source .env.quant.local
set +a
/home/djy/Quant/.venv/bin/python -m uvicorn services.api.app.main:app --host 127.0.0.1 --port 9011
```

### Web

```bash
cd apps/web
pnpm build
HOSTNAME=127.0.0.1 PORT=9012 pnpm start
```

## 4. Freqtrade 部署

当前骨架在：

- `infra/freqtrade/docker-compose.yml`
- `infra/freqtrade/.env.example`
- `infra/freqtrade/user_data/config.base.json`
- `infra/freqtrade/user_data/config.live.base.json`

最小启动：

```bash
cd /home/djy/Quant/infra/freqtrade
cp .env.example .env
cp user_data/config.private.json.example user_data/config.private.json
docker compose up -d
```

当前约定：

- Spot
- `dry-run` 优先
- REST 只监听 `127.0.0.1:9013`

## 5. 云上部署

当前统一部署目录：

- `infra/deploy`

最小步骤：

1. 从 GitHub 拉代码
2. 进入 `infra/deploy`
3. 准备 `.env`
4. 准备 `api.env`
5. 准备 Freqtrade 私有配置
6. `docker compose up -d --build`

当前云上组件：

- API
- WebUI
- Freqtrade
- Mihomo

## 6. Binance 访问说明

当前链路分成两类：

### 公开行情

优先走：

- `data-api.binance.vision`

### 签名账户和真实下单

继续走：

- `api.binance.com`

原因：

- 当前大陆服务器需要代理
- 公开行情和签名链路的稳定性要求不同

## 7. 代理和白名单

当前最重要的原则：

- Binance 白名单认的是**最终出口 IP**
- 如果服务器通过 Mihomo 节点出网，白名单里加的应该是**代理节点出口 IP**
- 不是阿里云服务器自己的公网 IP

当前做法：

- 固定单一节点
- 不自动切换
- 尽量保持出口稳定

## 8. 验证顺序

部署或联调时，固定按这个顺序查：

1. 端口有没有起来
2. 服务日志有没有报错
3. API 是否返回正常
4. 页面是否真的变化

## 9. 当前最常用验证命令

端口：

```bash
ss -ltnp | grep ':9011 '
ss -ltnp | grep ':9012 '
ss -ltnp | grep ':9013 '
```

接口：

```bash
curl -s http://127.0.0.1:9011/healthz
curl -s http://127.0.0.1:9012
curl -s http://127.0.0.1:9013/api/v1/ping
```

## 10. 当前最关键的运维入口

- 执行相关：  
  [docs/ops-freqtrade.md](/home/djy/Quant/docs/ops-freqtrade.md)
- 研究相关：  
  [docs/ops-qlib.md](/home/djy/Quant/docs/ops-qlib.md)
- 本地演示与验收：  
  [docs/ops.md](/home/djy/Quant/docs/ops.md)

## 11. 一句最重要的话

先确认服务和接口，再看页面；  
不要把页面异常直接当成部署异常，也不要把接口成功直接当成页面已经可用。
