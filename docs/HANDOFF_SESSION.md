# 会话接力文档

## 最近更新：2026-08-17

---

## 当前进行中的工作（新 session 从这里接手）

### 1. 方向做空（合约）观察期（进行中）

**已完成**（08-13 前）：
- ✅ OOS 隔离验证：模型 16 币平均分数 <0.38 时做空 BTC，TEST 段命中率 77.8%、平均收益 +2.58%/次
- ✅ api 市场方向接口：`GET /api/v1/signals/research/market-direction`（返回 avg_score/direction/short_trigger）
- ✅ 方向做空调度服务：`services/api/app/services/direction_short_service.py`（状态机：<0.38 开空、>0.45 平空，状态持久化）
- ✅ 调度接入：openclaw 巡检 cycle_check 时检查方向（`openclaw_patrol_service.py:_check_direction_short`），独立 freqtrade 客户端指向模拟盘 9014（与实盘隔离，`QUANT_DIRECTION_SHORT_FREQTRADE_URL` 可切换）
- ✅ futures 模拟盘容器：`quant-freqtrade-sim`（9014，dry_run，杠杆 1x，独立 sqlite）
- ✅ **首笔空单已开出并被止损平仓**（BTC/USDT:USDT，Short，成交价 63311.7；08-13 止损平仓 -0.53 USDT / -0.84%）

**08-17 完成（方案 A：前端展示模拟做空状态）**：
- ✅ 后端接口 `GET /api/v1/signals/research/direction-short-status`：模型平均分数 + 状态文件 + 模拟盘真实持仓/最近平仓
- ✅ 前端任务页"方向做空（模拟盘）"状态卡（60s 轮询）：平均分数 / 做空状态 / 开空时间 / 模拟盈亏
- ✅ 共用重构：巡检与接口共用 `build_sim_client()`；`market-direction` 提取 `_market_direction_item`
- ✅ **已部署上线**：git push + 服务器重建 api/web；线上接口返回正确、Playwright 真实页面验证通过（显示 0.3696 / 已平仓状态待同步 / -0.53）

**观察期注意**：
- 首笔空单被止损后，状态文件仍 `has_short_position=true`（调度 hold 不会主动同步真实持仓）——若观察期要继续，需人工决策是否让调度同步状态文件（见下）
- 模拟盘实际无持仓；接口已暴露 `position_state_mismatch`，页面会提示"已平仓（状态待同步）"

### 2. ✅ 已完成：前端展示模拟做空状态（方案 A）

- 状态卡在任务页 `/tasks`（登录后可见），含模型平均分数、做空状态、开空时间、模拟盈亏
- 接口以模拟盘真实持仓为准，状态文件不一致时明确提示

### 3. 历史决策回顾（重要，避免重复实验）

| 已尝试 | 结果 |
|--------|------|
| 标签优化（close_only/2%/2-5d） | ✅ 唯一有效（0.532→0.566） |
| walk-forward 数据量提升 | ✅ 采纳 |
| 排序学习/多周期特征/分组训练/横截面特征 | ❌ 全部无提升 |
| 截面选币做空 | ❌ ≈随机 |
| 时序方向做空 | ✅ 有效（做空 BTC） |
| 物理隔离 OOS 考核 | ✅ 已落地（基线 TEST auc=0.5287） |

---

## 环境与操作要点

### 本地开发
- Python 统一用 conda 环境 `quant`：`source /home/djy/miniforge3/etc/profile.d/conda.sh && conda activate quant`
- 禁止本地跑 Docker；部署走 git push + 服务器

### 服务器部署（ssh -i ~/.ssh/id_aliyun_djy djy@39.106.11.65）
```bash
# api/web 更新：
ssh ... "cd ~/Quant && git pull && cd infra/deploy && docker compose build api web && docker compose up -d --no-deps api web"
# 注意：改 api.env 后必须 compose up 重建容器（docker restart 不重新读 env_file）
# 模拟盘更新：
ssh ... "cd ~/Quant/infra/freqtrade && git pull && docker restart quant-freqtrade-sim"
```

### 关键坑（都踩过，别重复）
1. **docker restart 不读 env_file**——改 api.env 后要 compose up -d 重建
2. **ccxt 4.5 代理参数**：aiohttp_proxy 失效，用 `proxies` dict（config.futures.sim.json 已双保险）
3. **期货交易对格式**：BTC/USDT:USDT（`_normalize_symbol` 已支持）
4. **forceenter 超时但订单成交**：需查持仓确认状态（已加容错）
5. **磁盘**：Build Cache 会堆积（曾堆 17GB 导致卡死）——每天 03:00 crontab 自动清理（/home/djy/scripts/disk_maintenance.sh）
6. **py-spy 抓线程栈**：容器重建后需重装；`docker exec --privileged quant-api py-spy dump --pid 1`
7. **VPN 主节点**：香港³（152.175.1.118 白名单）；日本线路对币安不稳
8. **api 卡死历史**：health_monitor 已移出事件循环；rsi-summary 缓存 15 分钟；kline 定时同步 15 分钟

### 测试基线
- 全量测试当前基线失败数：约 70（历史断言问题，非本次引入）
- 改动后对比：`pytest -q | grep -c FAILED` 与基线一致即可

---

## 文档索引（新 session 必读顺序）
1. AGENTS.md（项目规则）
2. CONTEXT.md（完整进度记录，含所有决策）
3. 本文档
4. docs/superpowers/plans/（各期实施计划）
