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

```bash
source /home/djy/miniforge3/etc/profile.d/conda.sh
conda activate quant
```

## 环境变量

最小配置：

```bash
export QUANT_RUNTIME_MODE=dry-run
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

live 安全门最小配置：

```bash
export QUANT_RUNTIME_MODE=live
export QUANT_ALLOW_LIVE_EXECUTION=true
export QUANT_LIVE_ALLOWED_SYMBOLS='DOGEUSDT'
export QUANT_LIVE_MAX_STAKE_USDT='1'
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
  - 默认 `stake_amount=1`
  - 默认 `max_open_trades=1`

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
- 当前剩余问题不是下单失败，而是派发后那次 `sync_task` 超时失败，需要后续继续修
- 当前订单页看到的状态可能是 `closed`，这是 Freqtrade 当前版本在 dry-run 下返回的真实状态
- 如果你的 Freqtrade 版本对 `forceenter / forceexit` 的参数要求不同，需要按实际版本再做微调
- 如果 bot 里已经有同币种历史 dry-run 交易，当前 `flat` 会按当前币种或当前 `trade_id` 收敛，不会全平全部仓位
