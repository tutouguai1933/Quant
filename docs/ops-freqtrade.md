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

当前仍然保留的边界：

- `live` 仍不会放开真实执行
- 当前只有 `dry-run + 已配置 REST` 才会切到真实 Freqtrade 后端
- `start / pause / stop` 现在明确控制的是整台执行器
- 真实 Freqtrade 的信号派发参数如果和你部署版本不一致，可能需要微调

## 运行约定

- 所有 Python 相关命令默认先进入 conda 环境 `quant`

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
6. 登录策略页，确认能看到“执行器状态”
7. 点击“启动策略”，确认页面里出现 `running`
8. 点击“派发最新信号”，确认订单页出现 `filled`
9. 打开持仓页，确认能看到 `BTC/USDT` 和 `long`
10. 打开订单页和持仓页，确认都能看到“同步来源”

## 当前风险说明

- 当前最稳的验证路径仍然是 `dry-run`
- 当前已经做过一轮本地真实页面验收，但还没有对接真实 Freqtrade REST 服务完成最终端到端验收
- 如果你的 Freqtrade 版本对 `forceenter / forceexit` 的参数要求不同，需要按实际版本再做微调
