# 合约实战打通 + 另类数据接入 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ①合约方向做空打通实战（真实账户、最小仓位、完整风控）；②接入币安衍生品另类数据（持仓量/多空比/主动买卖比）并实验其对收益的预测价值。

**Architecture:** 合约线：复用 quant-freqtrade-sim 容器升级为 futures 实盘（dry_run=false + 真实 key + 小仓位风控），api 侧 direction_short 调度链路不变（已指向 9014）。数据线：新增 binance_derivatives_service 定时拉取 4 类衍生品数据存本地，实验脚本验证其与未来收益的相关性，有效则集成特征管线并过 OOS 考核。

**Tech Stack:** freqtrade（futures 模式）+ 币安 fapi 公共数据端点 + lightgbm 实验框架

---

## ⚠️ 安全红线（全程遵守）

- 合约实盘初始参数锁定：**杠杆 1x、逐仓（isolated）、单笔 20 USDT、只交易 BTCUSDT、max_open_trades=1**
- API key/secret 只存服务器文件，不入 git、不出现在对话和日志
- 提现权限绝不开启；key 绑定 IP 白名单（8 个 VPN 出口 IP，用户已配）
- 每个实战步骤先验证再推进；任何异常立即暂停并汇报

## 用户前置条件（已完成）

- ✅ 币安合约账户开通
- ✅ API key 创建（权限：读取+现货+合约；IP 白名单 8 个 VPN 出口 IP）
- ⏳ key/secret 待放置：`~/quant_futures_key.txt`（两行：`key=...` `secret=...`）

---

## 阶段一：合约实战打通（Task 1-3）

### Task 1: 合约 key 配置 + futures 实盘配置 + 连通性验证

**Files:**
- Create: `infra/freqtrade/user_data/config.futures.live.json`（从 sim 配置复制修改：dry_run=false、真实 key 引用、db 改名）
- Modify: `infra/freqtrade/docker-compose.yml`（freqtrade-sim 容器的 command 切换到 live 配置；或新增环境变量开关）
- Create: `scripts/verify_contract_live.py`（连通性验证脚本）

- [ ] **Step 1: 读取用户 key 并生成 live 配置**

```bash
ssh ... "cat ~/quant_futures_key.txt"   # 读 key= / secret=
```
- 用 python 把 key/secret 写入 `config.private.futures.json`（git 必须忽略，加 .gitignore 规则）
- 生成 `config.futures.live.json`：
  - `dry_run: false`
  - `trading_mode: futures`、`margin_mode: isolated`
  - `stake_amount: 20`、`max_open_trades: 1`
  - `pair_whitelist: ["BTC/USDT:USDT"]`（只留 BTC）
  - `exchange.key/secret` 从 private 文件注入（freqtrade 支持 `--config` 多文件覆盖，private 放最后）
  - db: `tradesv3.futures.sqlite`

- [ ] **Step 2: .gitignore 加规则**

```
infra/freqtrade/user_data/config.private.futures.json
infra/freqtrade/user_data/tradesv3.futures.sqlite*
```

- [ ] **Step 3: 切换容器到 live 配置并启动**

```bash
# compose 里 freqtrade-sim 的 command 增加 --config config.private.futures.json（放最后覆盖）
docker compose up -d freqtrade-sim   # recreate
```

- [ ] **Step 4: 连通性验证脚本**

`scripts/verify_contract_live.py`（在 freqtrade-sim 容器内运行或通过 api）：
1. freqtrade API ping（9014）
2. 通过 freqtrade `/api/v1/balance` 验证真实账户读取成功（返回合约余额）
3. 记录初始余额

Expected: balance 返回真实 USDT 余额数字

- [ ] **Step 5: 测试 + 提交**

```bash
python3 -m pytest services/api/tests/test_direction_short_service.py -q   # 回归
git add -A && git commit -m "feat: 合约实盘配置与连通性验证"
```

### Task 2: 最小仓位实战验证（一笔开空+平仓）

- [ ] **Step 1: 手动开一笔最小空单**

通过 freqtrade API（9014）forceenter short BTC/USDT:USDT（20 USDT，1x 杠杆）

- [ ] **Step 2: 验证真实成交**

- freqtrade status 显示 short 持仓
- 币安 APP 上能看到对应合约仓位（让用户肉眼确认一次，建立信任）

- [ ] **Step 3: 手动平仓**

forceexit → 确认平仓成交、盈亏结算正确

- [ ] **Step 4: Review 1（安全审查）**

检查点：实际杠杆=1x、实际仓位金额≈20 USDT、只动了 BTCUSDT、无其他币种交易记录

### Task 3: 自动调度对接实盘 + 风控收紧

**Files:**
- Modify: `services/api/app/services/openclaw_patrol_service.py`（direction_short 的 env 默认值保持 9014 即可，容器已是实盘）
- Modify: `services/api/app/services/direction_short_service.py`（如需补充状态字段）

- [ ] **Step 1: 确认调度链路指向实盘容器**

direction_short 客户端默认 URL=9014（该容器现在是合约实盘）✓ 无需改代码

- [ ] **Step 2: 风控参数确认**

- SHORT_TRIGGER_SCORE=0.38 / FLAT_TRIGGER_SCORE=0.45（OOS 验证值，不改）
- 单日最大开空次数保护（防反复触发）：在 decide() 加"当日开仓次数 ≤2"限制 + 测试

- [ ] **Step 3: 测试 + 提交**

回归 test_direction_short_service.py + 新增当日次数限制测试

---

## 阶段二：另类数据接入（Task 4-6）

### Task 4: 币安衍生品数据采集服务

**Files:**
- Create: `services/api/app/services/binance_derivatives_service.py`
- Test: `services/api/tests/test_binance_derivatives_service.py`

数据端点（fapi.binance.com，公共无需 key，已验证可用）：
- `futures/data/openInterestHist`（持仓量）
- `futures/data/topLongShortPositionRatio`(大户持仓多空比)
- `futures/data/globalLongShortAccountRatio`（散户多空比）
- `futures/data/takerlongshortRatio`（主动买卖比）

- [ ] **Step 1: 服务实现（TDD）**

功能：
- `fetch(symbol, period, limit)` 拉取各端点
- `store()` 存 `.runtime/derivatives/{symbol}_{endpoint}.jsonl`（增量追加，去重按 timestamp）
- `latest_features(symbol)` 输出最新特征行：oi_change_pct（持仓量变化率）、ls_ratio_zscore（多空比 z-score）、taker_ratio_ma（主动买卖比均值）

- [ ] **Step 2: 定时采集**

挂到现有 kline_sync_scheduler 循环（每 15 分钟顺带同步衍生品数据，BTCUSDT 起）

- [ ] **Step 3: 测试 + 提交**

mock httpx 响应测试解析/去重逻辑；py_compile；提交

### Task 5: 衍生品数据有效性实验

**Files:**
- Create: `scripts/run_derivatives_study.py`

- [ ] **Step 1: 实验设计**

1. 采集 BTCUSDT 全历史衍生品数据（4h，尽可能长）
2. 对齐 K 线未来收益（2-5 天标签，同线上配置）
3. 分析每个衍生品指标的分桶胜率（类似分数校准表）：
   - 持仓量大增 + 价格跌 → 后续走势？（多头挤兑信号）
   - 多空比极端值（>2 或 <0.5）→ 反向信号？
   - taker 买卖比极端值 → 短期反转？
4. 输出各指标的分桶胜率表，识别胜率 ≥60% 的信号区间

- [ ] **Step 2: 服务器执行 + 分析**

- [ ] **Step 3: 结论评审（Review 2）**

- 有 ≥1 个指标在 TEST 段稳定 ≥60% 胜率 → 进入 Task 6 特征集成
- 全部无效 → 记录结论，另类数据方向暂停

### Task 6:（条件执行）衍生品特征集成 + OOS 考核

- 有效指标加入 `qlib_features.py` FACTOR_DEFINITIONS（auxiliary 角色）
- 数据管道：build_feature_rows 支持外部特征合并
- **必须过 OOS 考核**：`run_oos_benchmark.py` TEST auc 提升 ≥0.01 才部署

---

## 部署与验收

- [ ] 阶段一完成后：合约实盘自动调度上线（观察期 1 周，每天检查持仓/盈亏）
- [ ] Task 5 结论出来后：向用户汇报另类数据的可行性判断
- [ ] 全程更新 CONTEXT.md

## 注意事项

- 实盘初期任何异常（下单失败/重复下单/异常盈亏）→ 先停 direction_short 调度再排查
- freqtrade-sim 容器名字虽叫 sim，升级后即为合约实盘实例（改名风险大，保留名字，在 bot_name 区分）
- 币安衍生品端点限频：每分钟 ~1200 次权重，采集频率 15 分钟远低于限制
