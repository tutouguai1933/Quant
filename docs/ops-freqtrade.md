# Freqtrade 接入说明

## 当前结论

当前控制平面已经支持两种 Freqtrade 后端：

- `memory`
  作为默认回退，用于本地演示和无配置场景
- `rest`
  当提供 Freqtrade REST 配置后启用，用于真实 bot 控制和状态同步

当前阶段已经做通：

- 运行模式读取
- Freqtrade REST 登录
- `start / pause / stop`
- 订单、持仓、策略状态同步
- 策略页展示执行器状态
- 订单页、持仓页展示同步来源
- `demo / dry-run / live` 安全边界
- 远端 dry-run 模式校验
- 仓库内 Spot dry-run Docker 部署骨架
- 一次真实 Spot dry-run 端到端联调
- 本地防重复派发
- `flat` 只收敛到当前币种或当前交易
- 成功执行回执优先使用真实 Freqtrade 返回
- live 本地安全门
- live 容器配置骨架

当前仍然保留的边界：

- `live` 代码路径已经打开，并且已经完成首笔真实成交验收
- `start / pause / stop` 现在明确控制的是整台执行器
- 真实 Freqtrade 的信号派发参数如果和你部署版本不一致，可能需要微调
- 如果还没配 Freqtrade REST 变量，图表页会明确提示 `not_ready`

## 运行约定

- 所有 Python 相关命令默认先进入 conda 环境 `quant`
- 当前推荐的真实接入方式：`WSL + Docker + Binance Spot`，默认先走 `dry-run`
- 日常开发在 `WSL` 做，真实 `dry-run / live` 验证和最终部署放到阿里云服务器
- `GitHub` 私有仓库作为唯一代码基线，服务器从仓库拉代码再部署

```bash
source /home/djy/miniforge3/etc/profile.d/conda.sh
conda activate quant
```

## 环境变量

最小配置：

```bash
export QUANT_RUNTIME_MODE=dry-run
export QUANT_BINANCE_MARKET_BASE_URL='https://api.binance.com'
export QUANT_BINANCE_ACCOUNT_BASE_URL='https://api.binance.com'
export QUANT_BINANCE_TIMEOUT_SECONDS='10'
export QUANT_FREQTRADE_API_URL='http://127.0.0.1:8080'
export QUANT_FREQTRADE_API_USERNAME='Freqtrader'
export QUANT_FREQTRADE_API_PASSWORD='YourPassword'
```

也兼容短变量名：

```bash
export QUANT_FREQTRADE_URL='http://127.0.0.1:8080'
export QUANT_FREQTRADE_USERNAME='Freqtrader'
export QUANT_FREQTRADE_PASSWORD='YourPassword'
```

说明：

- 如果不提供这组配置，系统会自动回退到 `memory`
- 如果只配了一部分，会直接报错，不会半配置运行
- 如果服务器在中国大陆，公开行情建议单独改成：
  - `QUANT_BINANCE_MARKET_BASE_URL='https://data-api.binance.vision'`
- 账户同步和真实下单仍然依赖 `api.binance.com`
- 如果这一段直连超时，需要给服务器补代理，或者改用海外节点

live 安全门最小配置：

```bash
export QUANT_RUNTIME_MODE=live
export QUANT_ALLOW_LIVE_EXECUTION=true
export QUANT_LIVE_ALLOWED_SYMBOLS='DOGEUSDT'
export QUANT_LIVE_MAX_STAKE_USDT='6'
export QUANT_LIVE_MAX_OPEN_TRADES='1'
```

## Docker 骨架

仓库里现在已经提供：

- `infra/freqtrade/docker-compose.yml`
- `infra/freqtrade/.env.example`
- `infra/freqtrade/user_data/config.base.json`
- `infra/freqtrade/user_data/config.live.base.json`
- `infra/freqtrade/user_data/config.private.json.example`

最小命令：

```bash
cd /home/djy/Quant/infra/freqtrade
cp .env.example .env
cp user_data/config.private.json.example user_data/config.private.json
docker compose up -d
```

预期结果：

- 本机 `127.0.0.1:8080` 会起来一台 Freqtrade REST API
- 控制平面补齐 `QUANT_FREQTRADE_API_URL / USERNAME / PASSWORD` 后，会从 `memory` 切到 `rest`

说明：

- 当前骨架固定为 `Spot`
- Docker 继续使用 `host` 网络
- 但 Freqtrade REST 自己只监听 `127.0.0.1:8080`
- 第一批交易对白名单固定为：
  - `BTC/USDT`
  - `ETH/USDT`
  - `SOL/USDT`
  - `DOGE/USDT`
- 你现在这组只读 Binance Key 可以先用于控制平面侧的真实余额和市场读取
- 后续如果 Freqtrade dry-run 联调需要更完整权限，再换成专用 `Spot Trading` Key
- 如果你本机依赖代理出网，容器里继续使用这台机器的本机代理即可
- 如果要切 live：
  - `.env` 里把 `QUANT_FREQTRADE_PUBLIC_CONFIG` 切到 `config.live.base.json`
  - 当前 live 骨架默认只允许 `DOGE/USDT`
  - 默认 `stake_amount=6`
  - 默认 `max_open_trades=1`

## 服务器端口管理

服务器端口管理和本地使用同一套规则：

- `Quant` 主应用固定用主范围
- 临时联调会话单独新增 `Quant-Debug-N`
- 每个条目默认占 10 个连续端口
- 联调结束后删除临时条目

推荐做法：

- 正式服务固定占用 `9011-9020`
- 临时联调按顺序申请下一段，例如 `9021-9030`
- 所有占用都写进 `/home/djy/.port-registry.yaml`

当前主范围建议：

- `9011`: API
- `9012`: WebUI
- `9013`: Freqtrade REST
- `9014`: Qlib
- `9015`: OpenClaw

## 服务器统一部署

服务器统一部署目录：

- `infra/deploy`

最小启动步骤：

1. 在服务器拉取最新 GitHub 代码
2. 进入 `infra/deploy`
3. 复制 `.env.example` 为 `.env`
4. 复制 `api.env.example` 为 `api.env`
5. 准备好 `../freqtrade/.env` 和 `../freqtrade/user_data/config.private.json`
6. 执行 `docker compose up -d --build`

统一部署后的默认端口：

- `9011`: API
- `9012`: WebUI
- `9013`: Freqtrade REST
- `9016`: Mihomo 代理
- `9017`: Mihomo 控制器

服务器本次联调结果：

- `9011 / 9012 / 9013 / 9016 / 9017` 容器已经成功拉起
- 外网已经可以直接打开 `9012`
- `Mihomo` 已经接入，并固定在单一节点
- 公开行情和 `Freqtrade` 已经能通过代理访问 Binance
- 市场接口在代理偶发抖动时会回退为空结果，不再直接返回 `500`
- 订单和持仓接口已经恢复为 `200`，控制平面访问 Freqtrade REST 时会强制直连
- 签名账户链路目前仍受 Binance 白名单限制

当前代理出口说明：

- Binance 真正看到的是 Mihomo 当前节点的出口 IP，不是阿里云服务器公网 IP
- 当前默认固定在 `香港1`
- 当前 `香港1` 实测出口 IP：`154.3.37.169`
- 如果要恢复余额、订单同步和 live 联调，需要把这个出口 IP 加到 Binance API 白名单

## 服务器调试顺序

服务器上排查问题时，按这个顺序走：

1. 先看端口有没有被正确监听
2. 再看容器或服务日志
3. 再看 API 是否返回预期结果
4. 最后看页面状态是否真的变化

这样做的原因是：

- 先确认服务有没有起来
- 再确认服务本身有没有报错
- 再确认接口是不是通的
- 最后才判断是不是前端问题

## 当前页面上会看到什么

### 策略页

会新增一块“执行器状态”，显示：

- 当前执行器
- 当前后端是 `memory` 还是 `rest`
- 当前模式是 `demo / dry-run / live`
- 当前连接状态

### 订单页和持仓页

会新增“同步来源”区块，显示：

- `source`
- `truth source`

用来判断现在看到的是：

- `freqtrade-sync`
- 或 `freqtrade-rest-sync`

## 最小验收步骤

1. 进入 conda 环境 `quant`
2. 配置 `QUANT_RUNTIME_MODE`
3. 如果要接真实 Freqtrade，补齐 Freqtrade REST 环境变量
4. 启动 API
5. 启动 WebUI
6. 打开市场页，确认能看到“推荐策略”和“趋势状态”
7. 打开单币图表页，确认能看到“策略解释”“止损参考”和“Freqtrade 准备情况”
8. 登录策略页，确认能看到“执行器状态”
9. 点击“启动策略”，确认页面里出现 `running`
10. 点击“派发最新信号”，确认订单页出现真实 dry-run 订单状态（当前通常是 `closed`）
11. 打开持仓页，确认能看到 `BTC/USDT` 和 `long`
12. 打开订单页和持仓页，确认都能看到“同步来源”

## 当前风险说明

- 当前最稳的验证路径仍然是 `dry-run`
- 当前已经做过一轮本地真实页面验收，市场页和图表页也已经能明确提示下一步
- 当前已经完成一次真实 `Freqtrade REST + Binance Spot + dry-run` 联调
- 当前已经完成首笔真实 `DOGE/USDT` 买单：
  - 真实成交金额约 `1.08216 USDT`
  - 真实成交数量约 `12 DOGE`
  - 订单状态为 `FILLED`
  - 持仓页和订单页都能读到真实结果
- `live` 模式下的 `sync_task` 现在已经改成直接使用 Binance 账户同步
- 已经做过一次真实 `/tasks/sync` 验证，返回成功，并带回真实余额、订单和持仓
- live 同步现在只会在 Binance 账户同步里确认到“刚刚派发的那一笔订单”时，才把 signal 标成 `synced`
- 如果首次同步失败，后续重试成功也会把 signal 状态补齐
- 当前阿里云上的真实余额同步已经恢复，签名账户链路可用
- 当前服务器上还留着一笔 `DOGE` 未托管现货仓位：
  - Binance 账户里能看到真实 `DOGE`
  - 但当前 `Freqtrade live` 的 `/api/v1/status` 和 `/api/v1/trades` 都为空
  - 所以 `forceexit` 无法直接平这笔仓位
- 控制平面现在会明确返回“账户里仍有现货余额，但当前 Freqtrade 没有打开交易记录，无法直接平仓”
- 今天又成功发起了一笔新的真实 `DOGE/USDT` 买单：
  - 新订单号是 `14140438880`
  - 这笔新单已被当前 `Freqtrade live` 正确记录
  - 真实卖出失败的根因不是接口，而是最小卖出额
- 当前已经补上 live 买前检查：
  - 会结合最小成交额、交易步长、手续费和最新价格
  - 如果这笔单后面大概率卖不出去，就会在买入前直接拦住
- 服务器上的 live 单笔上限和执行器默认 stake 现在都已经切到 `6 USDT`
- 当前卡住的仍然是那笔历史上已经开的 `1 USDT` 小仓位，不是新的 `6 USDT` 配置
- 当前订单页看到的状态可能是 `closed`，这是 Freqtrade 当前版本在 dry-run 下返回的真实状态
- 如果你的 Freqtrade 版本对 `forceenter / forceexit` 的参数要求不同，需要按实际版本再做微调
- 如果 bot 里已经有同币种历史 dry-run 交易，当前 `flat` 会按当前币种或当前 `trade_id` 收敛，不会全平全部仓位
