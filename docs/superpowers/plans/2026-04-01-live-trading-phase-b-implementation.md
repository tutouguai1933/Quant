# Phase B Implementation

关联规格：
- [2026-04-01-live-trading-phase-b-design.md](/home/djy/Quant/docs/superpowers/specs/2026-04-01-live-trading-phase-b-design.md)

## 当前进度

`Phase B` 当前已经完成前 `5` 个任务。

### 已完成

1. 统一白名单和策略目录
2. 图表指标基础
3. `trend_breakout`
4. `trend_pullback`
5. 策略中心

## 已落地结果

### Task 1

- 默认白名单已经固定
- 策略目录已经集中管理

### Task 2

- 图表接口已经有最小指标摘要
- 返回结构已统一为 `items + overlays + markers`

### Task 3

- `trend_breakout` 已可运行

### Task 4

- `trend_pullback` 已可运行

### Task 5

- 策略页已经升级成策略中心
- 已能展示：
  - 两套策略卡片
  - 当前判断
  - 白名单摘要
  - 最近信号
  - 最近执行结果

## 剩余执行顺序

### Task 6：市场页补策略视角

- 在市场页显示更适合哪套策略
- 显示趋势状态

### Task 7：图表页补策略解释

- 显示策略解释卡片
- 显示信号点
- 显示止损线

### Task 8：Phase B 验收闭环

- 从市场页进入图表页
- 从图表页进入策略中心
- 从策略中心进入 dry-run 派发
- 在订单、持仓、任务、风险页看见完整反馈

## 当前执行边界

- 仍只做 `Spot USDT + dry-run`
- 不开放真实下单
- 不开放在线参数编辑
- 不扩到多市场和研究平台
