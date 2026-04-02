# Phase A 运行说明

## `dry-run` 和 `live` 的差别

- `dry-run` 会走完整的下单链路，但仍保持当前阶段的受控执行方式，方便观察信号、订单和持仓变化。
- `live` 代表进入真实执行前的最后保护边界。当前阶段已经会走真实执行路径，但会先过本地安全门，再决定是否放行。
- 当前阶段的 `FreqtradeClient.get_runtime_snapshot()` 会明确返回运行模式，`mode` 只能是 `demo`、`dry-run` 或 `live`。

## 当前阶段建议

- 目前推荐只跑 `dry-run`。
- `demo` 仍保留现有的内存假执行，适合开发和回归检查。
- `live` 现在已经有真实执行路径，但当前首笔真实单仍未验收通过。
- 所有 Python 相关命令默认先进入 conda 环境 `quant`。

## 你需要准备

1. Binance 主账号
2. 身份认证
3. 2FA
4. Quant 专用 API Key / Secret
5. 小额测试资金
6. 运行环境

## 一条龙验收路径

1. 配置 `QUANT_RUNTIME_MODE=dry-run`
2. 配置 Binance API Key / Secret
3. 启动 API
4. 启动 WebUI
5. 打开市场页确认真实行情
6. 打开单币图表页确认真实 K 线
7. 打开余额 / 订单 / 持仓页确认同步状态：余额来自 Binance，订单 / 持仓仍以 Freqtrade dry-run 为准
8. 启动策略并确认仍在 dry-run

## 切到 `live` 前必须检查的内容

1. `QUANT_RUNTIME_MODE=live` 已明确设置，并且程序读到的快照里确实显示为 `live`。
2. `QUANT_ALLOW_LIVE_EXECUTION=true` 已显式开启。
3. Binance 凭据已配置并可用。
4. 已确认信号、仓位、订单和风控结果都符合预期。
5. 已在 `dry-run` 下完成一次完整验证，没有异常告警。
6. 真实 Freqtrade REST 已经接通，并且远端明确处于 `live + spot`。
7. `QUANT_LIVE_ALLOWED_SYMBOLS / QUANT_LIVE_MAX_STAKE_USDT / QUANT_LIVE_MAX_OPEN_TRADES` 已配置。

## 说明

- 如果没有设置 `QUANT_ALLOW_LIVE_EXECUTION=true`，`ExecutionService.dispatch_signal()` 在 `live` 模式下会直接拒绝执行。
- 即使已经设置确认开关，当前仍必须满足：真实 REST、`spot`、白名单、单笔金额上限、最大持仓数和 Binance 最小下单额。
- 当前首笔真实单没有打出去的原因是 Binance key 返回 `401 / -2015`，不是控制平面代码没有放行。
