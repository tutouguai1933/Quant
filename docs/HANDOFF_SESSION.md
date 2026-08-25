# 会话接力文档

## 最近更新：2026-08-17

> 08-17 晚：修复首页"数据加载中"——实盘 freqtrade 因 ccxt 4.5.44 异步代理字段变更反复启动失败；已补 `aiohttp_proxy` + 容器代理环境变量，freqtrade 恢复 RUNNING，首页接口与真实页面验证通过。
>
> 08-17 深夜（二次修复）：慢请求（freqtrade/status 676s、entry-conditions 967s、cycle-history 688s）占满 API 线程池导致首页请求排队。已给 freqtrade 代理加 5s 缓存+单飞、执行器状态/入场条件旧值兜底+后台刷新、周期历史与 runtime 加短缓存，前端"数据加载中"最长显示 8s。验证：并发首轮 ≤4.5s、次轮 <2s，真实浏览器首页秒开、控制台 0 错误。

---

## 当前进行中的工作（新 session 从这里接手）

### 最新状态（2026-08-25 补充）

**策略实验全景**（全部 OOS 验证过）：
- ✅ 标签优化 close_only/2%/2-5d（唯一有效：0.532→0.566）
- ❌ 排序学习/多周期特征/分组训练/横截面特征/截面选币做空/方向做空(选币)/波动率突破——全部无样本外正期望
- 脚本留存 scripts/run_*.py，市场环境变化后可重跑
- 波动率突破回测：TRAIN +62% → TEST -59%（典型过拟合，EP004 教训复现）

**合约实战已打通**：
- quant-freqtrade-sim 容器（9014）已升级为合约实盘实例（dry_run=false、真实 key、stake=9 USDT、白名单 ETH/BTC/XRP/DOGE）
- 第一笔真实空单 XRP 已成交并平仓闭环
- 配置坑全记录：期货 pair 格式 BTC/XRP+:USDT、ccxt proxies 参数、市价单需 price_side=other、api_server 认证
- ⚠️ 合约账户余额 ~10 USDT；BTC 最小下单额 81U、ETH 22.8U 超出限制，XRP/DOGE 可以下单

**服务器稳定性**：卡死问题累计闭环 6 个根因（rsi缓存风暴/docker阻塞事件循环/磁盘满/KlineStore重建/AsyncClient反复销毁/logging锁竞争+GIL风暴）。部署必须用守卫脚本 /home/djy/scripts/safe_deploy.sh（内存<500MB 拒绝构建）；磁盘每天 03:00 自动清理。

### 待办清单（按优先级）
1. 方向做空模拟盘观察期收益跟踪（对照预期命中率 77.8%）——数据在 direction_short_state.json + freqtrade-sim trades API
2. 衍生品另类数据积累（采集服务已上线，15分钟/轮，攒够 2-4 周重跑 scripts/run_derivatives_study.py 有效性研究）
3. 前端展示完善：首页方向做空状态卡已上线；任务页同款卡片已有
4. （远期）模型能力提升：链上数据等新信息源调研——OOS 基线 TEST auc=0.5287 是考核标准

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
- ✅ 首笔空单被止损后状态文件残留问题已修复：巡检每轮决策前用在场持仓自动对齐状态文件（`reconcile_with_open_trades`）
- ✅ 已实测闭环：状态文件与在场空仓一致（score=0.3696<0.38，持有 BTC/USDT:USDT 空仓），观察期恢复自动运行
- ⚠️ 踩坑补充：Freqtrade `/trades` 只返回已平仓历史，在场持仓必须走 `/status`（`list_open_trades`）

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
2. **ccxt 4.5.44 代理参数（08-17 已实锤）**：异步客户端只认 `aiohttp_proxy`、不认 `proxies` dict；同步客户端认 `proxies`。两个字段都要配（config.proxy.mihomo.json 已双保险），且 freqtrade 容器已默认注入 HTTP_PROXY/HTTPS_PROXY 环境变量
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
