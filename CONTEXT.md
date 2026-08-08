# Quant 项目状态文档

> 最后更新：2026-08-08

---

## 当前进度

**状态**：前端重构（3 阶段 15 任务）全部完成并部署验证；数据链路断点修复、新手交互动线重构、Playwright 测试收口

**本次更新（2026-08-08 晚）**：

### 前端数据链路修复与重构（计划：docs/superpowers/plans/2026-08-08-frontend-refactor.md）

**阶段一：数据链路断点修复（6 任务）**
- 会话有效性校验：失效 token 跳登录而非静默显示假数据（新增 session-guard 组件 + session 接口后端校验）
- 降级提示：策略/任务页 API 失败时显示黄色提示条（保留兜底数据但标记 error，不静默）
- openclaw 巡检/审计接口统一 envelope 包裹
- 因子页 IC 摘要指标（mean_ic/ic_std/icir/ic_win_rate）从 ic_series 真实计算（兼容 factory report 嵌套结构）
- 选币页 terminal.metrics 补齐年化/夏普/超额/换手 4 个指标
- 研究页测试样本数 + 训练/验证 AUC 打通

**阶段二：前端重构（4 任务）**
- 首页改为 3 个核心数字卡（持仓盈亏/自动化状态/执行器健康）+ 详情折叠
- 新建 /pipeline 研究流水线页：训练→因子→选币一页走完（新手主入口）
- 空状态区分"已训练但指标缺" vs "未运行"
- 导航分组：研究员工具收进"高级模式"折叠

**阶段三：测试收口**
- 清理 26 个断言旧 UI 的失效 Playwright 测试
- 新建 9 个测试（主链路冒烟/会话过期/降级提示/首页3数字/流水线/空状态/导航分组），**9/9 × 2 轮全过**

**排查中发现的重大 bug 与修复**：
- **cookie 鉴权失效根因**：next.config.mjs 的 rewrite 规则把 /api/control/* 直接转发后端（不经 route handler），cookie 无法转成 Bearer → 策略页一直显示假数据。移除 rewrite 改由 route handler 统一代理
- **登录页已登录跳转**：window.location.replace 硬跳导致 hydration 不完整（页面 body 只有 websocket 横幅），改 Next router.replace
- **api CPU 100% 堆积**：365 天数据训练耗时 31 分钟，超过 15 分钟周期 → 训练线程堆积。周期改为 60 分钟（QUANT_OPENCLAW_CYCLE_INTERVAL=3600，compose .env），重启 api 清堆积线程后 CPU 0.2%

**当前状态**：服务全绿（api/web/openclaw/freqtrade healthy，api CPU 5%），自动化 auto_dry_run 已恢复（paused=False、failures=0，周期 60 分钟）
- **注意**：图表组件（quantile-net-chart 等）内部默认空状态文案未改，页面层通过数据源判断后自行渲染空状态块替代图表组件，避免改公共组件影响其他页面

### 研究流水线单页贯通（训练→因子→选币）
- **新页面** `/pipeline`：从上到下三步骤卡片（① 训练模型 → ② 因子研究 → ③ 选币回测），每步一个运行按钮 + 结果指标 + 新手向数据说明；复用三个 workspace 接口展示，不重写数据层
- **触发**：步骤按钮调用现有后端 POST（训练=`/signals/research/train`、因子=`/signals/research/infer`、选币=完整流水线 `/signals/pipeline/run`）；完成后轮询刷新并提示"✓ 完成"
- **导航**：侧边栏"研究"组四链接（模型训练/回测训练/选币回测/因子研究）合并为一个"研究流水线"；旧页面仍可访问
- **关键发现**：`/api/control/*` 被 next.config 重写直连后端（不经 route handler），cookie 鉴权无效 → 客户端 POST 改为显式携带会话令牌（query token + Bearer 头）
- **验证**：Playwright 测试通过；三步骤按钮在真实浏览器全部验证（运行中→完成）

### 系统优化：可信训练-回测闭环（4 并行工作流 16 任务）
- **数据量**：训练数据 60→365 天（sample_count 837→8372，10 倍）。修复了 market_service 硬编码 days=30 的隐藏瓶颈（store_days 参数透传 lookback_days）
- **回测**：重写为真实交易模拟（simulate_trades：buy 开仓/止损/止盈/窗口结束平仓/手续费双扣）；run_backtest 字段名兼容，新增 trades_count/final_nav/exit_reasons；max_drawdown_pct 保持负值约定
- **walk-forward**：启用（QUANT_QLIB_ENABLE_WALK_FORWARD=true），预测函数接真 LightGBM（predictor=ml，4 folds），失败降级恒等比例
- **阈值**：standard_gate preset 0.55→0.45（与 env 一致）；回测门最小样本保护（防 2 样本造假指标）；模型视图对齐最新训练（清除 heuristic_v1 残留）
- **验证**：val_auc 0.438→0.525（超过随机线）；回测 120→1263 笔模拟交易
- **遗留**：回测 nav 复利虚高（take_profit 8% 长序列锁定导致），门控因回撤 -91% 拦截不影响决策，后续可调模拟参数；freqtrade 曾因 Binance 签名接口超时进程死亡（代理抖动），已重启恢复

### 服务状态
| 服务 | 状态 |
|------|------|
| quant-api | ✅ Healthy（新代码已部署） |
| quant-freqtrade | ✅ RUNNING（重启恢复） |
| quant-web / openclaw / mihomo | ✅ Healthy |
| 自动化周期 | auto_dry_run，等待冷却窗口结束 |

**本次更新（2026-08-01）**：

### 全系统恢复（停机 5-7 周后重启）
- **卡点确认**：quant-api Exited(137) 5 周前 OOM、quant-freqtrade Exited(2) 3 周前无法访问 Binance、mihomo 全部节点 REALITY 认证失败（配置过期）、GitHub pull 失败（代理失效）
- **mihomo 代理更新**：用户提供新节点配置（`infra/mihomo/config.yaml` 不进 Git），所有旧节点 public-key 已更换；补充 MMDB（jsdelivr 下载）后正常启动
- **出口 IP 白名单匹配**：Binance API key 白名单包含 154.31.113.7（日本¹）和 45.95.212.82（日本⁴），固定 BestSSR 到 **日本¹**（154.31.113.7）
- **行情直连**：`QUANT_BINANCE_MARKET_BASE_URL` 改为 `data-api.binance.vision`（大陆直连 200），compose `NO_PROXY` 加 vision 域名（commit `4888078`）；不再依赖失效代理，账户/交易接口仍走代理
- **quant-api 恢复**：OOM(137) 是 Docker recreate 竞争残留孤儿 uvicorn 占用 9011 导致 bind 失败循环；用 `docker run --pid=host` 清理孤儿进程 + `--force-recreate` 重建容器解决
- **quant-freqtrade 恢复**：代理恢复后启动成功（EnhancedStrategy，1h，stake 10 USDT，dry_run=False 真实模式）
- **自动化恢复**：6/10 连续失败触发的人工接管通过 `/tasks/automation/dry-run-only` 清除（resume 会被 resume_checklist 拦截属正常保护），现为 auto_dry_run 运行中
- **注意**：服务器仅 1.6G 内存，api 容器内存紧张时有 OOM 风险，需要关注

**上次更新（2026-05-27）**：

### 系统 Review 后 P0 改造
- **策略安全门**：ML live gate 改为使用候选自己的 per-symbol validation；当 ML 没有任何买入样本时，回测不再回退到全部样本，避免无信号候选被误包装成可交易
- **OpenClaw 巡检闭环**：OpenClaw 快照补齐 `automation_state` 和 `execution_health`；`automation_dry_run_only` 改为完整调用 dry-run only 恢复逻辑，能清除暂停和人工接管
- **策略页承接**：`/strategies` 增加执行确认动作区，补齐启动策略、暂停策略、停止策略、派发最新信号入口，统一走现有 `/actions` 路由
- **监控与运维口径**：Prometheus 端口统一为 `9091`；host 网络抓取目标改为 localhost；移除默认 Freqtrade scrape 凭据；Freqtrade healthcheck 改为读取私有配置中的 REST 凭据
- **验证结果**：策略定向 unittest 2 个通过；OpenClaw unittest 3 个通过；前端 TypeScript、Playwright `/strategies` 定向测试、`pnpm build` 均通过；配置静态检查通过

### 服务器不可用与自动化失败修复
- **API 卡顿根因**：API 容器请求 Freqtrade 时使用 `172.17.0.1:9013`，但代理直连例外缺少 `172.17.0.1`，部分请求误走 mihomo 代理后超时，导致 Web 代理接口出现 `socket hang up`
- **修复**：Freqtrade 代理路由统一使用 `httpx.AsyncClient(..., trust_env=False)`；部署 `NO_PROXY` 增加 `172.17.0.1`
- **自动化失败根因**：05/26 01:50 推理阶段报 `dictionary changed size during iteration`，触发 `workflow_infer_failed` 并进入人工接管
- **修复**：`QlibRunner` 训练和推理遍历数据前固定 key 快照，避免共享行情字典在遍历期间变化
- **恢复动作**：服务器已部署 commit `b10ca54`，切到 `auto_dry_run` 后触发一轮自动化周期，训练、推理、信号输出、复盘均成功
- **当前结果**：自动化未暂停、未人工接管；本轮候选被门控正常拦下，推荐继续研究（BNBUSDT 最大回撤过大）

**上次更新（2026-05-23）**：

### ML 模型推理修复
- **模型文件路径 Bug**：predictor.py 用字符串拼接检查模型文件（`.model.txt`），但 save 用 `with_suffix` 替换后缀（`.txt`），路径不匹配导致模型加载失败，fallback到启发式评分（全部为 0）
- **类方法丢失 Bug**：`_build_per_symbol_validation` 缩进错误导致它后面的所有类方法脱离 `QlibRunner` class，训练时报 `AttributeError`
- **运行时目录持久化**：添加 `QUANT_QLIB_RUNTIME_ROOT=/app/.runtime/qlib` 确保模型文件不会随容器重建丢失

### 门控逻辑全面修复
- **Backtest Gate**：原回测对全部测试样本求和（无视模型预测），修复为只计入 ML 预测买入（概率≥0.5）的样本
- **Consistency Gate**：原来用全局验证集对比单币回测（数据维度不对等），改为回测内部一致性检查（胜率vs Sharpe、收益vs回撤）
- **Validation Gate**：原来所有候选共用全局验证数据，改为每个币种独立计算 per-symbol 验证指标
- **门控阈值调整**：`dry_run_min_score` 0.55→0.45，`live_min_score` 0.65→0.50，`live_min_ml_probability` 0.55→0.45

### EnhancedStrategy 成交量过滤改进
- **同时段对比**：成交量不再与 SMA20 比，改为对比过去 7 天同一小时的均量，避免凌晨自然低量被误拦
- **阈值调整**：0.8 → 0.6（同时段对比更精准）
- **ROI 同步**：代码中 `minimal_roi` 与 JSON 配置文件保持一致

### RSI 概览改进
- 默认周期 1D → 1H（实时性更好）
- 缓存增加 5 分钟 TTL 过期机制

---

## 系统状态

### 服务状态
| 服务 | 地址 | 状态 |
|------|------|------|
| 服务器API | http://39.106.11.65:9011 | ✅ Healthy |
| 服务器Web | http://39.106.11.65:9012 | ✅ Healthy |
| Freqtrade | EnhancedStrategy | ✅ API可用 |
| mihomo代理 | 127.0.0.1:7890 | ✅ Healthy |
| OpenClaw | 巡检服务 | ✅ Healthy |
| 自动化周期 | auto_dry_run | ✅ 等待下一轮研究 |

---

## 双策略架构

### 1. EnhancedStrategy（RSI策略，Freqtrade）

**入场条件**（4个同时满足）：
1. 1H RSI < 32（超卖区）
2. 4H 价格 > SMA200（长期趋势向上）
3. 4H RSI < 70（不超买）
4. 成交量 > 过去 7 天同一时段均量 × 0.6

| 参数 | 当前值 |
|------|--------|
| rsi_entry_threshold | 32 |
| rsi_exit_threshold | 72 |
| atr_multiplier | 2.0 |
| max_day_loss_pct | 5% |
| stoploss | -8% |
| ROI | 8%/5%/3%/2% (0/30/60/120min) |
| stake_amount | 7 USDT |

### 2. 自动化周期策略（ML策略）

| 参数 | 当前值 |
|------|--------|
| 时间框架 | 4h |
| 回看天数 | 60天 |
| num_leaves | 31 |
| learning_rate | 0.02 |
| reg_alpha/reg_lambda | 0.1 |
| n_estimators | 200 |
| 运行频率 | 15分钟 |

### 门控体系

| Gate | 检查内容 | 关键阈值 |
|------|---------|---------|
| Score Gate | ML 得分 | ≥ 0.45 |
| Rule Gate | EMA趋势/ATR/成交量 | ema20_gap>0, ema55_gap>0 |
| Backtest Gate | 回测指标（只看ML买入样本） | return>0, sharpe≥0.25 |
| Consistency Gate | 回测内部一致性 | 胜率vs Sharpe, 收益vs回撤 |
| Validation Gate | per-symbol 验证质量 | sample≥12, positive_rate≥45% |
| Live Gate | 实盘准入 | score≥0.50, win_rate≥55% |

---

## 已修复的 Bug 列表

| 日期 | Bug | 影响 | 修复 |
|------|-----|------|------|
| 05-27 | ML live gate 使用全局验证 | live 准入可能没有按单币种质量判断 | 改用候选 per-symbol validation |
| 05-27 | ML 无买入样本回测回退全样本 | 无信号候选可能被误算成可交易 | 无买入样本返回空回测样本 |
| 05-27 | OpenClaw 快照缺巡检字段 | 巡检可能读不到执行健康和告警状态 | 快照补齐 automation_state / execution_health |
| 05-27 | OpenClaw dry-run only 只改模式 | 可能未清除暂停/人工接管 | 复用完整 enable_dry_run_only |
| 05-27 | 监控端口和抓取目标不一致 | Prometheus/Grafana 可能误报或空数据 | 端口统一 9091，host 网络目标改 localhost |
| 05-27 | API 没有 `/metrics` 但 Prometheus 默认抓取 | Prometheus 目标持续 404 报红 | 增加轻量 `/metrics`，cAdvisor 改为可选抓取 |
| 05-27 | 未认证接口抛 ASGI 异常 | 日志出现 Traceback，掩盖真实问题 | 全局把 `PermissionError` 转成 401 响应 |
| 05-27 | OpenClaw/策略状态偶发慢响应 | 巡检和页面可能等待完整自动化/同步链路 | 巡检周期后台排队，自动化状态过期缓存快速返回 |
| 05-27 | Freqtrade 请求误走代理 | API 卡顿，Web 代理 `socket hang up` | Freqtrade 代理直连，`NO_PROXY` 加 `172.17.0.1` |
| 05-27 | 推理遍历共享字典时报错 | 自动化 `workflow_infer_failed` 并人工接管 | 遍历前固定 dataset key 快照 |
| 05-23 | predictor 文件路径拼接错误 | 模型无法加载，score=0 | `with_suffix()` 替换字符串拼接 |
| 05-23 | `_build_per_symbol_validation` 缩进错误 | 所有类方法脱离 class | 移到类定义之后 |
| 05-23 | 回测全量样本求和 | 收益永远为负 | 只统计 ML 预测买入样本 |
| 05-23 | Consistency Gate 跨维度对比 | 全局vs单币误拦 | 改为回测内部一致性 |
| 05-23 | Validation Gate 全局复用 | 15个候选共用同份数据 | per-symbol 独立计算 |
| 05-22 | RSI 缓存无过期 | 首页定格在旧数据 | 5分钟 TTL |
| 05-21 | 自动化周期人工接管 | 8天未运行 | 重置状态 |
| 05-20 | 训练超时 | 新参数训练时间超限 | 3处超时配置调整 |

---

## 部署命令速查

```bash
# API
ssh -i ~/.ssh/id_aliyun_djy djy@39.106.11.65 \
  "cd ~/Quant && git pull && cd infra/deploy && docker compose build api && docker compose up -d --no-deps api"

# Freqtrade 重启
ssh -i ~/.ssh/id_aliyun_djy djy@39.106.11.65 \
  "docker stop quant-freqtrade && docker rm quant-freqtrade && cd ~/Quant/infra/freqtrade && docker compose up -d freqtrade"

# 自动化状态重置
ssh -i ~/.ssh/id_aliyun_djy djy@39.106.11.65 \
  "cat ~/Quant/infra/data/runtime/automation_state.json | python3 -c \"
import sys,json; state=json.load(sys.stdin)
state['manual_takeover']=state['paused']=False
state['consecutive_failure_count']=0
print(json.dumps(state,indent=2))
\" > /tmp/as.json && mv /tmp/as.json ~/Quant/infra/data/runtime/automation_state.json"
```
