# UI 优化待办清单 V2

> 生成时间：2026-05-06
> 审阅范围：全部 21 个页面 + 共享组件
> 审阅方式：HTTP 检查 + API验证 + 代码扫描
> 最后更新：2026-05-06 19:50

---

## 修复完成状态

### ✅ 已修复问题

| # | 问题 | 修复方案 | 状态 |
|---|------|----------|------|
| 1 | `/hyperopt` 404 | 重新构建并部署到正确位置 `/app/apps/web/.next` | ✅ 已修复 |
| 2 | `/factor-knowledge` 404 | 重新构建并部署到正确位置 `/app/apps/web/.next` | ✅ 已修复 |
| 3 | `scoring-display.tsx` 样式 | 改用 `bg-[var(--terminal-muted)]` | ✅ 已修复 |

### 验证结果
```bash
/hyperopt: 200 ✅
factor-knowledge: 200 ✅
scoring-display.tsx: 已改用CSS变量
```

---

## 一、HTTP 页面状态

| 页面 | HTTP | 状态 |
|------|------|------|
| `/` 首页 | 200 | ✅ |
| `/login` 登录 | 200 | ✅ |
| `/strategies` 策略 | 200 | ✅ |
| `/balances` 余额 | 200 | ✅ |
| `/positions` 持仓 | 200 | ✅ |
| `/orders` 订单 | 200 | ✅ |
| `/risk` 风险 | 200 | ✅ |
| `/research` 研究 | 200 | ✅ |
| `/backtest` 回测 | 200 | ✅ |
| `/evaluation` 评估 | 200 | ✅ |
| `/features` 因子 | 200 | ✅ |
| `/ops` 运维 | 200 | ✅ |
| `/tasks` 任务 | 200 | ✅ |
| `/analytics` 分析 | 200 | ✅ |
| `/data` 数据 | 200 | ✅ |
| `/market` 市场 | 200 | ✅ |
| `/market/BTCUSDT` 详情 | 200 | ✅ |
| `/signals` 信号 | 200 | ✅ |
| `/hyperopt` 参数优化 | 200 | ✅ 已修复 |
| `/config` 配置 | 200 | ✅ |
| `/factor-knowledge` 知识库 | 200 | ✅ 已修复 |

**总结**: 21/21 页面全部正常 ✅

---

### 1.2 /market/[symbol] Tab功能验证

| Tab | 状态 | 数据 |
|-----|------|------|
| 图表 | ✅ 正常 | K线数据正常 (5条4h) |
| RSI历史 | ✅ 正常 | 1D周期16条记录 |
| 交易历史 | ✅ API正常 | 当前无数据(dry-run) |

**结论**: Tab功能已完整实现

---

### 1.3 API 验证结果

| 端点 | 状态 | 数据 |
|------|------|------|
| `/api/v1/health` | ✅ 200 | 容器健康 |
| `/api/v1/market` | ✅ 200 | 16个币种 |
| `/api/v1/market/BTCUSDT/chart` | ✅ 200 | K线正常 |
| `/api/v1/market/BTCUSDT/rsi-history` | ✅ 200 | RSI历史(1D周期16条) |
| `/api/v1/trade-log/history` | ✅ 200 | API正常 |
| `/api/v1/balances` | ✅ 200 | dry-run返回空 |
| `/api/v1/analytics` | ✅ 200 | ready状态 |
| `/api/v1/positions` | ⚠️ 200 | dry-run返回空 |

---

### 1.4 样式问题

| 文件 | 行号 | 问题 | 状态 |
|------|------|------|------|
| `scoring-display.tsx` | 188, 272 | 使用 `bg-gray-500` 而非CSS变量 | ✅ 已修复 |

---

### 1.5 容器状态

```
quant-api:       ✅ Up (healthy)
quant-web:       ✅ Up (healthy)
quant-freqtrade: ✅ Up (healthy)
quant-mihomo:    ✅ Up (healthy)
```

---

## 二、修复完成清单

### ✅ 全部问题已修复

| # | 问题 | 修复方案 | 状态 |
|---|------|----------|------|
| 1 | `/hyperopt` 404 | 重新构建并部署到 `/app/apps/web/.next` | ✅ 已修复 |
| 2 | `/factor-knowledge` 404 | 重新构建并部署到 `/app/apps/web/.next` | ✅ 已修复 |
| 3 | `scoring-display.tsx` 样式 | 改用 `bg-[var(--terminal-muted)]` | ✅ 已修复 |

---

## 三、修复任务 (已完成)

### ✅ 任务 1: 修复 hyperopt 页面 404
```
状态: ✅ 已完成
页面: /hyperopt
修复: 重新构建并部署到 /app/apps/web/.next
验证: HTTP 200
```

### ✅ 任务 2: 修复 factor-knowledge 页面 404
```
状态: ✅ 已完成
页面: /factor-knowledge
修复: 重新构建并部署到 /app/apps/web/.next
验证: HTTP 200
```

### ✅ 任务 3: 修复 scoring-display.tsx 样式
```
状态: ✅ 已完成
文件: apps/web/components/scoring-display.tsx
行号: 188, 272
修复: bg-gray-500 → bg-[var(--terminal-muted)]
```

---

## 四、已确认正常的功能

- ✅ RSI 历史表格 Tab
- ✅ 交易历史详细 Tab
- ✅ 选币流水线结果展示 (研究侧卡)
- ✅ 市场列表数据
- ✅ 图表数据
- ✅ API服务正常运行
- ✅ 终端风格样式
- ✅ 所有21个页面HTTP正常

---

## 五、最终状态

### UI审查完成 ✅

所有问题已修复，系统正常运行：
- 21/21 页面正常
- RSI/交易历史Tab已实现
- API服务正常
- 终端风格统一
- 容器健康