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
python -m uvicorn services.api.app.main:app --host 127.0.0.1 --port 9011
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

## 5. Docker Compose 统一部署

当前统一部署目录：`infra/deploy`

### 5.1 快速启动

```bash
cd /home/djy/Quant/infra/deploy
docker compose up -d --build
```

访问地址：
- Web 界面：http://localhost:9012
- API 服务：http://localhost:9011
- Freqtrade：http://localhost:9013

### 5.2 配置文件说明

**必需配置：**

1. `infra/deploy/api.env` - API 服务环境变量
   ```bash
   # 数据库配置
   QUANT_DB_USERNAME=quant_admin
   QUANT_DB_PASSWORD=quant_pass_2024
   
   # Freqtrade 连接配置
   QUANT_FREQTRADE_API_URL=http://freqtrade:9013
   QUANT_FREQTRADE_API_USERNAME=Freqtrader
   QUANT_FREQTRADE_API_PASSWORD=your_password_here
   QUANT_FREQTRADE_API_TIMEOUT_SECONDS=10
   
   # 运行模式
   QUANT_RUNTIME_MODE=dry-run
   ```

2. `infra/freqtrade/user_data/config.private.json` - Freqtrade 私有配置
   ```json
   {
     "exchange": {
       "name": "binance",
       "key": "your_api_key",
       "secret": "your_api_secret"
     },
     "api_server": {
       "username": "Freqtrader",
       "password": "your_password_here"
     }
   }
   ```

3. `infra/freqtrade/user_data/config.base.json` - Freqtrade 基础配置
   ```json
   {
     "api_server": {
       "enabled": true,
       "listen_ip_address": "0.0.0.0",
       "listen_port": 9013
     }
   }
   ```

**代理配置（访问 Binance 需要）：**

4. `infra/mihomo/config.yaml` - Mihomo 代理配置
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

5. `infra/freqtrade/user_data/config.proxy.mihomo.json` - Freqtrade 代理配置
   ```json
   {
     "exchange": {
       "ccxt_config": {
         "httpsProxy": null,
         "aiohttp_proxy": "http://mihomo:7890"
       },
       "ccxt_async_config": {
         "httpsProxy": null,
         "aiohttp_proxy": "http://mihomo:7890"
       }
     }
   }
   ```

### 5.3 服务组件

当前部署包含 4 个服务：

- **mihomo**：代理服务，转发 Binance API 请求
- **freqtrade**：交易执行器，连接 Binance 执行交易
- **api**：后端 API 服务，提供数据和业务逻辑
- **web**：前端 Web 界面

### 5.4 常用命令

```bash
# 启动所有服务
docker compose up -d

# 重启单个服务
docker compose restart api

# 强制重建容器（配置变更后必须）
docker compose up -d --force-recreate api

# 查看日志
docker compose logs -f api
docker compose logs -f freqtrade

# 停止所有服务
docker compose down

# 查看服务状态
docker ps --filter "name=quant-"
```

### 5.5 故障排查

**API 无法连接 Freqtrade：**
1. 检查 Freqtrade 是否启动：`docker logs quant-freqtrade`
2. 检查 API 环境变量：`docker exec quant-api env | grep QUANT_FREQTRADE`
3. 测试容器间连接：`docker exec quant-api curl http://freqtrade:9013/api/v1/ping`
4. 如果配置变更，必须重建容器：`docker compose up -d --force-recreate api`

**Freqtrade 无法连接 Binance：**
1. 检查代理配置：`docker logs quant-mihomo`
2. 检查 Freqtrade 日志：`docker logs quant-freqtrade | grep -i binance`
3. 验证代理可达：`docker exec quant-freqtrade curl -x http://mihomo:7890 https://api.binance.com/api/v3/ping`

**配置变更不生效：**
- 重启不会重新加载环境变量，必须使用 `--force-recreate`
- 或者先 `docker compose down` 再 `docker compose up -d`

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

### WSL + Windows 代理配置

如果在 WSL 环境中使用 Windows 主机的代理（如 Clash）：

1. **获取 Windows 主机 IP**
   ```bash
   ip route show | grep default | awk '{print $3}'
   # 通常是 10.255.255.254 或 172.x.x.1
   ```

2. **配置 mihomo 转发到主机代理**
   - 在 `infra/mihomo/config.yaml` 中设置 `server: 10.255.255.254`
   - 端口设置为 Windows Clash 的端口（如 7897）

3. **验证连接**
   ```bash
   curl -x http://localhost:7890 https://api.binance.com/api/v3/ping
   ```

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

1. **容器状态**
   ```bash
   docker ps --filter "name=quant-"
   # 检查所有容器是否 Up 和 healthy
   ```

2. **端口监听**
   ```bash
   ss -ltnp | grep ':9011 '  # API
   ss -ltnp | grep ':9012 '  # Web
   ss -ltnp | grep ':9013 '  # Freqtrade
   ```

3. **服务健康检查**
   ```bash
   curl -s http://localhost:9011/health
   curl -s http://localhost:9013/api/v1/ping
   curl -s http://localhost:9012/ | head -c 100
   ```

4. **容器间连接**
   ```bash
   docker exec quant-api curl -s http://freqtrade:9013/api/v1/ping
   ```

5. **环境变量验证**
   ```bash
   docker exec quant-api env | grep QUANT_FREQTRADE
   ```

6. **服务日志**
   ```bash
   docker logs quant-api --tail 50
   docker logs quant-freqtrade --tail 50
   ```

7. **页面功能测试**
   - 访问 http://localhost:9012
   - 检查是否有"降级模式"或"API 不可用"提示
   - 测试 /orders、/positions、/strategies 等页面

## 9. 常见问题与解决方案

### 问题 1：API 报告 "无法连接 Freqtrade REST"

**症状：**
- `/api/v1/orders` 返回 `status: unavailable`
- 错误信息：`Connection refused` 或 `timeout`

**排查步骤：**
1. 检查 Freqtrade 容器状态：`docker ps | grep freqtrade`
2. 检查 API 配置的 URL：`docker exec quant-api env | grep QUANT_FREQTRADE_API_URL`
3. 测试容器间连接：`docker exec quant-api curl http://freqtrade:9013/api/v1/ping`

**常见原因：**
- Freqtrade 的 `listen_ip_address` 设置为 `127.0.0.1`（应改为 `0.0.0.0`）
- API 配置的端口错误（应为 9013）
- API 配置的密码错误
- 配置变更后未重建容器

**解决方法：**
```bash
# 1. 修改 infra/freqtrade/user_data/config.base.json
#    "listen_ip_address": "0.0.0.0"

# 2. 修改 infra/deploy/api.env
#    QUANT_FREQTRADE_API_URL=http://freqtrade:9013
#    QUANT_FREQTRADE_API_PASSWORD=正确的密码

# 3. 重建容器
docker compose up -d --force-recreate api freqtrade
```

### 问题 2：Freqtrade 无法连接 Binance API

**症状：**
- Freqtrade 日志显示 `ExchangeNotAvailable`
- 错误信息：`Connection timeout` 或 `Name resolution failed`

**排查步骤：**
1. 检查代理配置：`docker logs quant-mihomo | grep -i error`
2. 测试代理连接：`docker exec quant-freqtrade curl -x http://mihomo:7890 https://api.binance.com/api/v3/ping`
3. 检查 mihomo 日志：`docker logs quant-mihomo | grep DIRECT`

**常见原因：**
- mihomo 未配置上游代理，使用 DIRECT 模式直连
- mihomo 只监听 127.0.0.1，容器无法访问
- Freqtrade 配置了多个代理导致冲突

**解决方法：**
```bash
# 1. 配置 mihomo 使用主机代理
# 编辑 infra/mihomo/config.yaml，添加：
#   bind-address: "*"
#   allow-lan: true
#   proxies:
#     - name: "host-vpn"
#       server: 10.255.255.254
#       port: 7897

# 2. 配置 Freqtrade 使用 mihomo
# 编辑 infra/freqtrade/user_data/config.proxy.mihomo.json
#   "httpsProxy": null
#   "aiohttp_proxy": "http://mihomo:7890"

# 3. 重启服务
docker compose restart mihomo freqtrade
```

### 问题 3：配置变更不生效

**症状：**
- 修改了 `.env` 或配置文件
- 重启容器后仍使用旧配置

**原因：**
- `docker compose restart` 不会重新加载环境变量
- 容器在创建时就固化了环境变量

**解决方法：**
```bash
# 必须使用 --force-recreate 重建容器
docker compose up -d --force-recreate <service_name>

# 或者先停止再启动
docker compose down
docker compose up -d
```

### 问题 4：首页显示"降级模式"

**症状：**
- 首页提示"部分数据加载失败"或"降级模式"

**排查步骤：**
1. 检查 API 连接：`curl http://localhost:9012/api/control/orders`
2. 查看 meta 信息中是否有 `status: unavailable`

**常见原因：**
- API 服务未启动或不健康
- Freqtrade 连接失败（参考问题 1）
- 网络问题导致前端无法访问后端

**解决方法：**
- 按问题 1 的步骤修复 Freqtrade 连接
- 检查所有服务状态：`docker ps --filter "name=quant-"`

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
