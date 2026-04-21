# 项目启动与配置手册

本文档专门回答：
- 如何正确启动项目
- 必需的配置文件
- 常见启动问题与解决方案
- 最新修复和注意事项

## 1. 快速启动

### 1.1 Docker Compose 统一启动（推荐）

这是最简单的启动方式，所有服务在一个命令中启动：

```bash
cd /home/djy/Quant

# 首次启动或配置变更后（必须重建）
docker compose -f infra/deploy/docker-compose.yml up -d --build

# 日常启动（无需重建）
docker compose -f infra/deploy/docker-compose.yml up -d

# 查看服务状态
docker compose -f infra/deploy/docker-compose.yml ps
```

访问地址：
- Web 界面：http://localhost:9012
- API 服务：http://localhost:9011/api/v1
- Freqtrade：http://localhost:9013

### 1.2 本地开发启动

适用于开发调试，可以实时查看日志：

```bash
# 1. 激活环境
source /home/djy/miniforge3/etc/profile.d/conda.sh
conda activate quant
cd /home/djy/Quant

# 2. 启动 API
set -a
source .env.quant.local  # 或 infra/deploy/api.env
set +a
python -m uvicorn services.api.app.main:app --host 127.0.0.1 --port 9011

# 3. 启动 Web（另一个终端）
cd apps/web
pnpm build
HOSTNAME=127.0.0.1 PORT=9012 pnpm start

# 或开发模式（实时重载）
pnpm dev
```

## 2. 必需配置文件

### 2.1 API 服务配置

文件位置：`infra/deploy/api.env`

必需配置项：

```bash
# 数据库配置（可选，当前使用内存存储）
QUANT_DB_USERNAME=quant_admin
QUANT_DB_PASSWORD=quant_pass_2024

# Freqtrade 连接配置
QUANT_FREQTRADE_API_URL=http://freqtrade:9013
QUANT_FREQTRADE_API_USERNAME=Freqtrader
QUANT_FREQTRADE_API_PASSWORD=your_password_here
QUANT_FREQTRADE_API_TIMEOUT_SECONDS=10

# 运行模式
QUANT_RUNTIME_MODE=dry-run

# API 端口
QUANT_API_PORT=9011
```

### 2.2 Freqtrade 配置

需要两个配置文件：

1. **基础配置**：`infra/freqtrade/user_data/config.base.json`
   ```json
   {
     "api_server": {
       "enabled": true,
       "listen_ip_address": "0.0.0.0",
       "listen_port": 9013
     },
     "stake_currency": "USDT",
     "dry_run": true,
     "exchange": {
       "name": "binance"
     }
   }
   ```

2. **私有配置**：`infra/freqtrade/user_data/config.private.json`
   ```json
   {
     "exchange": {
       "key": "your_api_key",
       "secret": "your_api_secret"
     },
     "api_server": {
       "username": "Freqtrader",
       "password": "your_password_here"
     }
   }
   ```

### 2.3 代理配置（访问 Binance 需要）

中国大陆访问 Binance API 需要代理：

1. **Mihomo 配置**：`infra/mihomo/config.yaml`
   ```yaml
   mixed-port: 7890
   bind-address: "*"
   allow-lan: true

   proxies:
     - name: "host-vpn"
       type: http
       server: 10.255.255.254  # WSL 访问 Windows 主机
       port: 7897

   proxy-groups:
     - name: PROXY
       type: select
       proxies:
         - host-vpn

   rules:
     - MATCH,PROXY
   ```

2. **Freqtrade 代理配置**：`infra/freqtrade/user_data/config.proxy.mihomo.json`
   ```json
   {
     "exchange": {
       "ccxt_config": {
         "aiohttp_proxy": "http://mihomo:7890"
       },
       "ccxt_async_config": {
         "aiohttp_proxy": "http://mihomo:7890"
       }
     }
   }
   ```

### 2.4 Web 前端配置

前端默认无需额外配置，但需要注意：

- API 代理路径：`/api/control` → 后端 API
- 环境变量（可选）：`QUANT_API_BASE_URL=http://127.0.0.1:9011/api/v1`

## 3. 标准端口规则

固定端口：
- API：`9011`
- Web：`9012`
- Freqtrade REST：`9013`
- Qlib：`9014`
- OpenClaw：`9015`

临时联调端口：
- 通过端口注册表 `/home/djy/.port-registry.yaml` 申请
- 例如 `Quant-Debug-1` 使用 `9021-9030`

## 4. 服务组件说明

当前部署包含 4 个核心服务：

| 服务 | 容器名 | 端口 | 说明 |
|------|--------|------|------|
| mihomo | quant-mihomo | 7890 | 代理服务，转发 Binance API 请求 |
| freqtrade | quant-freqtrade | 9013 | 交易执行器，连接 Binance 执行交易 |
| api | quant-api | 9011 | 后端 API 服务，提供数据和业务逻辑 |
| web | quant-web | 9012 | 前端 Web 界面 |

服务依赖关系：
```
web → api → freqtrade → mihomo → Binance
```

## 5. 常见启动问题与解决方案

### 5.1 配置变更不生效

**症状**：修改配置文件后重启服务，配置未生效

**原因**：Docker 容器不会自动重新加载环境变量

**解决方案**：
```bash
# 方案 1：强制重建容器
docker compose -f infra/deploy/docker-compose.yml up -d --force-recreate

# 方案 2：完全重启（推荐）
docker compose -f infra/deploy/docker-compose.yml down
docker compose -f infra/deploy/docker-compose.yml up -d
```

### 5.2 页面显示降级模式

**症状**：页面显示"降级模式：部分数据加载失败"警告

**原因**：前端错误检测逻辑 bug（已于 2026-04-18 修复）

**验证**：
```bash
# 检查页面是否显示降级模式
curl -s http://localhost:9012/evaluation | grep -o "降级模式" | wc -l  # 应返回 0

# 检查 API 是否正常
curl -s http://localhost:9012/api/control/evaluation/workspace | \
  python3 -c "import sys, json; d=json.load(sys.stdin); print('Has error:', d.get('error') is not None)"
# 应输出: Has error: False
```

**解决方案**：
1. 确保 commit `91d27f1` 已部署
2. 重新构建并重启 web 服务：
   ```bash
   docker compose -f infra/deploy/docker-compose.yml build web
   docker compose -f infra/deploy/docker-compose.yml up -d web
   ```

详细修复文档：`docs/2026-04-18-degraded-mode-fix.md`

### 5.3 API 无法连接 Freqtrade

**症状**：API 返回 502 错误，无法获取 Freqtrade 数据

**排查步骤**：
```bash
# 1. 检查 Freqtrade 是否启动
docker logs quant-freqtrade

# 2. 检查 API 环境变量
docker exec quant-api env | grep QUANT_FREQTRADE

# 3. 测试容器间连接
docker exec quant-api curl http://freqtrade:9013/api/v1/ping

# 4. 如果配置变更，必须重建
docker compose -f infra/deploy/docker-compose.yml up -d --force-recreate api
```

### 5.4 Freqtrade 无法连接 Binance

**症状**：Freqtrade 日志显示 Binance API 连接失败

**排查步骤**：
```bash
# 1. 检查代理服务
docker logs quant-mihomo

# 2. 检查 Freqtrade 日志
docker logs quant-freqtrade | grep -i binance

# 3. 测试代理可达性
docker exec quant-freqtrade curl -x http://mihomo:7890 https://api.binance.com/api/v3/ping
```

### 5.5 Web 容器启动失败

**症状**：quant-web 容器状态为 unhealthy 或 exited

**排查步骤**：
```bash
# 1. 查看容器日志
docker logs quant-web

# 2. 检查健康状态
docker inspect quant-web | grep -A 10 "Health"

# 3. 检查端口占用
netstat -tlnp | grep 9012

# 4. 强制重建
docker compose -f infra/deploy/docker-compose.yml build web --no-cache
docker compose -f infra/deploy/docker-compose.yml up -d web
```

## 6. 常用运维命令

### 6.1 服务管理

```bash
# 启动所有服务
docker compose -f infra/deploy/docker-compose.yml up -d

# 重启单个服务
docker compose -f infra/deploy/docker-compose.yml restart api

# 停止所有服务
docker compose -f infra/deploy/docker-compose.yml down

# 查看服务状态
docker compose -f infra/deploy/docker-compose.yml ps

# 强制重建（配置变更后必须）
docker compose -f infra/deploy/docker-compose.yml up -d --force-recreate --build
```

### 6.2 日志查看

```bash
# 查看 API 日志
docker compose -f infra/deploy/docker-compose.yml logs -f api

# 查看 Freqtrade 日志
docker compose -f infra/deploy/docker-compose.yml logs -f freqtrade

# 查看 Web 日志
docker compose -f infra/deploy/docker-compose.yml logs -f web

# 查看所有服务日志
docker compose -f infra/deploy/docker-compose.yml logs -f
```

### 6.3 健康检查

```bash
# 检查所有容器健康状态
docker ps --filter "name=quant-" --format "table {{.Names}}\t{{.Status}}"

# 手动测试 API
curl http://localhost:9011/api/v1/health

# 手动测试 Web
curl http://localhost:9012

# 手动测试 Freqtrade
curl http://localhost:9013/api/v1/ping
```

## 7. 验证启动成功

### 7.1 基础验证

```bash
# 1. 检查所有容器健康
docker compose -f infra/deploy/docker-compose.yml ps
# 应看到 4 个容器状态为 Up (healthy)

# 2. 测试 API
curl -s http://localhost:9011/api/v1/health | python3 -m json.tool
# 应返回: {"status": "healthy", ...}

# 3. 测试 Web
curl -s http://localhost:9012 | grep -o "Quant Control Plane"
# 应找到页面标题

# 4. 测试前端 API 代理
curl -s http://localhost:9012/api/control/evaluation/workspace | \
  python3 -c "import sys, json; d=json.load(sys.stdin); print('error:', d.get('error'))"
# 应输出: error: None
```

### 7.2 页面验证

打开浏览器访问 http://localhost:9012：

1. 首页应显示主工作台
2. 点击侧栏导航，各页面应正常加载
3. 页面不应显示"降级模式"警告
4. 登录后应能访问所有页面

### 7.3 功能验证

```bash
# 测试登录
curl -s 'http://localhost:9012/login' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'username=admin&password=1933' \
  -c /tmp/cookies.txt

# 测试评估页面
curl -s -b /tmp/cookies.txt http://localhost:9012/evaluation | \
  grep -o "评估与实验中心"
# 应找到标题
```

## 8. 开发调试模式

### 8.1 API 调试模式

```bash
# 启动 API（带详细日志）
QUANT_API_DEBUG=true python -m uvicorn services.api.app.main:app \
  --host 127.0.0.1 --port 9011 --reload --log-level debug
```

### 8.2 Web 调试模式

```bash
cd apps/web

# 开发模式（实时重载）
pnpm dev

# 构建并启动（生产模式）
pnpm build
pnpm start
```

### 8.3 前端 Playwright 测试

```bash
cd apps/web

# 运行所有前端测试
QUANT_WEB_BASE_URL=http://127.0.0.1:9012 \
QUANT_API_BASE_URL=http://127.0.0.1:9011 \
pnpm exec playwright test

# 运行单个测试文件
pnpm exec playwright test tests/ui-main-flow.spec.cjs

# 带 UI 的测试
pnpm exec playwright test --ui
```

## 9. 重启与更新流程

### 9.1 标准重启流程

```bash
cd /home/djy/Quant

# 1. 拉取最新代码
git pull origin master

# 2. 重建并重启
docker compose -f infra/deploy/docker-compose.yml up -d --build

# 3. 等待健康检查
sleep 30
docker compose -f infra/deploy/docker-compose.yml ps

# 4. 验证
curl -s http://localhost:9012/evaluation | grep -o "降级模式" | wc -l
```

### 9.2 紧急重启流程

```bash
# 快速重启单个服务
docker compose -f infra/deploy/docker-compose.yml restart web

# 强制重建（解决配置不生效）
docker compose -f infra/deploy/docker-compose.yml up -d --force-recreate web
```

## 10. 相关文档

- 详细部署说明：`docs/deployment-handbook.md`
- 开发指南：`docs/developer-handbook.md`
- 系统架构：`docs/architecture.md`
- 降级模式修复：`docs/2026-04-18-degraded-mode-fix.md`
- API 文档：`docs/api.md`
- Freqtrade 运维：`docs/ops-freqtrade.md`