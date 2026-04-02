# Quant

> 面向个人加密量化交易的研究与执行控制平面  
> 当前状态：`Phase A` 已完成，`Phase B` 主体体验已收口，`Qlib` 最小研究层和多周期交易视图已打通，系统已经进入“真实 dry-run 工作台 + 最小研究闭环”阶段；`live` 安全门和 live 容器骨架已就绪，并已完成首笔真实 `Binance Spot` 买单验收。

## 这是什么

`Quant` 不是做全市场、全资产、全功能的大平台。  
第一阶段先把个人加密量化交易最关键的一条链路做通：

`市场数据 -> 信号 -> 风控 -> 执行 -> 账户/订单/持仓/任务/风险可见`

对应的英文主链路是：

`signal -> risk -> execution -> monitoring`

当前范围仍然严格收敛在：

- 只做 `crypto`
- 只接 `Binance`
- 只接 `Freqtrade`
- 执行模式当前仍以 `dry-run` 为主

## 现在已经做到哪里

### 已完成

- `Phase A` 全部完成
- 真实 Binance 行情已接入
- 真实 Binance 余额已接入
- `Qlib` 最小研究闭环已接入
- WebUI 已能查看：
  - 市场
  - 单币图表
  - 余额
  - 订单
  - 持仓
  - 风险
  - 任务
- `dry-run` 主链路已打通
  - 登录
  - 生成信号
  - 风控判断
  - 启动策略
  - 派发信号
  - 生成 dry-run 订单和持仓
- `Phase B` 已完成前 `5` 个任务
  - 统一白名单和策略目录
  - 图表指标基础
  - `trend_breakout`
  - `trend_pullback`
  - 策略中心
- 市场页已经会显示：
  - 当前更适合哪套策略
  - 当前趋势状态
  - 研究倾向
  - 推荐下一步
- 单币图表页已经会显示：
  - 多周期切换
  - 自绘 SVG K 线主图
  - 信号点、入场参考和止损参考
  - 策略解释
  - 突破 / 回调判断
  - 研究门控和研究倾向
  - 判断信心和主判断
  - Freqtrade 准备情况
- 研究层已经能完成：
  - 最小训练
  - 最小推理
  - 标准化输出研究分数、解释和模型版本
  - 在信号页、单币图表页、策略页展示最近研究结果

### 当前最重要的新能力

- 策略已经不是只有开关了，系统里已有两套首批波段策略：
  - `trend_breakout`
  - `trend_pullback`
- 策略页现在已经收成“执行页”
- 策略页会统一展示：
  - 执行器状态
  - 执行决策
  - 两套策略卡片
  - 默认参数摘要
  - 白名单摘要
  - 最近信号
  - 最近执行结果
- Freqtrade 执行层现在已经从“只会内存假执行”升级成“memory / rest 双后端门面”
- 仓库里现在已经有 `WSL + Docker + Binance Spot + dry-run` 的 Freqtrade 部署骨架
- Freqtrade 这条线现在已经补上明确安全门：
  - `demo` 和 `live` 不会因为残留凭据误碰真实 Freqtrade
  - `dry-run` 会校验远端 Freqtrade 的真实模式
  - 启动、暂停、停止当前明确控制的是整台执行器，不是假装单策略控制
  - `flat` 不再全平所有持仓，只会收敛到当前币种；如果明确给了 `trade_id`，只平那一笔
  - 同一条信号只允许派发一次，重复点击会在控制平面本地直接拦下
  - 成功回执现在优先返回真实 `trade_id / order_id / price / status`
  - Docker 仍用 `host` 网络，但 REST 只监听 `127.0.0.1`
  - `live` 新增了本地安全门：
    - 必须显式允许
    - 必须连上真实 `Freqtrade REST`
    - 远端必须确认 `live + spot`
    - 必须命中 live 白名单
    - 必须满足单笔金额上限
    - 必须满足最大持仓数
    - 必须满足 Binance 最小下单额
- 仓库里现在已经有 `WSL + Docker + Binance Spot + live` 的最小骨架：
  - `infra/freqtrade/user_data/config.live.base.json`
  - 默认只允许 `DOGE/USDT`
  - `stake_amount=1`
  - `max_open_trades=1`
- Qlib 研究层现在已经从“最小 mock 信号来源”升级成“可训练、可推理、可解释的最小研究层”
- Qlib 研究结果现在已经会以“软门控”方式参与策略判断，不再只是展示
- 市场页、单币图表页、策略页现在开始共用统一研究摘要
- 市场页现在已经改成“筛选入口”
- 市场页现在会显示：
  - 多周期状态
  - 研究倾向
  - 推荐策略
  - 判断信心
  - 主判断
- 单币图表页现在已经改成“交易主区”
- 单币图表页现在会显示研究解释摘要、研究门控和研究倾向
- 单币图表页现在会把信号点、入场参考、止损参考直接画到主图里
- 策略页现在会显示执行器状态、执行决策和执行建议
- 市场页、单币图表页、策略页现在统一显示：
  - 研究倾向
  - 推荐策略
  - 判断信心
  - 主判断
- 市场页现在会先提示“优先关注 / 高信心 / 多周期状态”
- 单币图表页现在会把“主判断、原因、下一步动作、止损参考”放到同一条交易动线上
- 信号页现在可以直接触发研究训练和研究推理
- 订单页和持仓页现在会显示同步来源
- 当前已经完成一轮真实页面验收：
  - 登录后策略页会显示 `已解锁`
  - 点击“启动策略”后策略页会出现 `running`
  - 点击“派发最新信号”后订单页会出现真实 Freqtrade dry-run 订单状态（当前为 `closed`）
  - 点击“派发最新信号”后持仓页会出现 `BTC/USDT long`
  - 策略页、订单页、持仓页现在都会明确显示 `freqtrade / rest / dry-run`

### 还没做

- 已完成首笔真实 `DOGE/USDT` 买单，控制平面、订单页、持仓页和 Binance 余额都能看到结果
- 当前还留着一个执行层问题：派发后的同步任务这次超时失败，但真实成交结果已经写到 Binance 和页面里
- 高级交互式图表仍然还没做完
- 图表页当前已经是可读的交易视图，但还不是完整交互图层
- `OpenClaw` 触发非交易任务还没接入
- 真实 Freqtrade 的完整实盘放行仍未开放
- 真实 `Qlib` 依赖和完整实验平台还没接入

## 项目结构

```text
apps/web                     Web 界面
services/api/app            控制平面 API、服务、路由、适配器
services/worker             研究层最小运行入口和研究逻辑
packages/db                 数据库结构
docs                        架构、接口、运维说明
infra/scripts               演示脚本
infra/freqtrade             Freqtrade Spot dry-run Docker 骨架
```

## 关键模块

- `apps/web`
  用户看到的控制台和策略中心
- `services/api/app/routes`
  对外接口入口
- `services/api/app/services/signal_service.py`
  信号流水线和信号存储
- `services/api/app/services/risk_service.py`
  基础风控判断
- `services/api/app/services/strategy_catalog.py`
  策略目录和白名单
- `services/api/app/services/strategy_engine.py`
  两套首批策略的最小判断逻辑
- `services/api/app/services/strategy_workspace_service.py`
  策略中心聚合视图
- `services/api/app/adapters/binance`
  Binance 市场和账户读取
- `services/api/app/adapters/freqtrade/client.py`
  Freqtrade 执行适配器
- `infra/freqtrade`
  Freqtrade Spot dry-run Docker 部署骨架
- `services/api/app/services/research_service.py`
  研究结果读取、训练、推理入口
- `services/api/app/services/research_cockpit_service.py`
  统一研究摘要生成
- `services/api/app/services/market_timeframe_service.py`
  图表周期规范和多周期摘要生成
- `services/worker/qlib_runner.py`
  最小训练、最小推理和结果落盘
- `services/worker/qlib_features.py`
  最小研究特征
- `services/worker/qlib_labels.py`
  最小研究标签

## 本地运行

默认约定：

- 所有 Python 相关命令都在 conda 环境 `quant` 中执行
- WebUI 命令仍在 `apps/web` 下单独执行

### API

```bash
source /home/djy/miniforge3/etc/profile.d/conda.sh
conda activate quant
export QUANT_QLIB_SESSION_ID=main
mkdir -p /tmp/quant-qlib-runtime
set -a
source /home/djy/Quant/.env.quant.local
set +a
uvicorn services.api.app.main:app --host 127.0.0.1 --port 8000
```

### WebUI

```bash
cd apps/web
pnpm start --hostname 127.0.0.1 --port 3000
```

### Freqtrade Spot Dry-Run / Live Scaffold

```bash
cd infra/freqtrade
cp .env.example .env
cp user_data/config.private.json.example user_data/config.private.json
docker compose up -d
```

说明：

- 默认 `QUANT_FREQTRADE_PUBLIC_CONFIG=config.base.json`，走 `dry-run`
- 如果后面要切 live，可把 `.env` 里的 `QUANT_FREQTRADE_PUBLIC_CONFIG` 改成 `config.live.base.json`
- 当前 live 骨架默认只放 `DOGE/USDT`，且 `stake_amount=1`

### 默认地址

- API：`http://127.0.0.1:8000`
- WebUI：`http://127.0.0.1:3000`
- 管理员账号：`admin / 1933`
- 研究运行目录默认值：`/tmp/quant-qlib-runtime`
- 多 session 并行时建议额外设置：`QUANT_QLIB_SESSION_ID=<你的 session 名>`

## 运行模式

- `demo`
  纯本地演示
- `dry-run`
  读取真实 Binance 数据，但执行仍是 dry-run
- `live`
  代码路径和安全门已具备，并已完成首笔真实 `DOGE/USDT` 买单；默认环境已经切回 `dry-run`

## 测试命令

默认约定：

- 先进入 conda 环境 `quant`
- 所有后端测试和脚本都在这个环境中执行

```bash
source /home/djy/miniforge3/etc/profile.d/conda.sh
conda activate quant
python -m unittest discover -s services/api/tests -v
python -m unittest discover -s services/worker/tests -v
python -m unittest discover -s tests -v
cd apps/web && pnpm exec tsc --noEmit && pnpm build
```

说明：

- 依赖本地 socket 的个别 API 测试在当前沙箱里可能被系统权限拦住
- `Qlib` 这条线本轮已经通过 worker 测试、研究服务测试、前端测试和真实页面验收
- 研究训练和研究推理现在需要管理员登录后再触发

## 当前待办

- [x] 目录骨架和基础文档
- [x] 统一契约和数据库模型
- [x] 控制平面 API 骨架
- [x] WebUI 骨架
- [x] 最小信号流水线
- [x] 执行适配器和同步链路
- [x] 基础风控与任务系统
- [x] 单管理员鉴权
- [x] 最小演示与验收流程
- [x] Binance 真实行情
- [x] Binance 真实余额
- [x] 两套首批波段策略最小版
- [x] 策略中心
- [x] Qlib 最小研究层
- [x] Freqtrade Spot dry-run Docker 骨架
- [x] 市场页显示策略适配与趋势状态
- [x] 图表页显示策略解释和止损参考
- [x] 图表页把信号点和止损线做成更直观的图层
- [ ] 完成 `Phase B` 剩余验收闭环
- [ ] 接入 `OpenClaw` 非交易任务触发

## 最小演示与验收

- 演示脚本：`infra/scripts/demo_flow.ps1`
- 运维说明：`docs/ops.md`

## 文档入口

- [plan.md](/home/djy/Quant/plan.md)
- [architecture.md](/home/djy/Quant/docs/architecture.md)
- [api.md](/home/djy/Quant/docs/api.md)
- [ops.md](/home/djy/Quant/docs/ops.md)
- [ops-qlib.md](/home/djy/Quant/docs/ops-qlib.md)
- [2026-04-02-platform-architecture-restoration-design.md](/home/djy/Quant/docs/superpowers/specs/2026-04-02-platform-architecture-restoration-design.md)
- [2026-04-02-freqtrade-real-integration-implementation.md](/home/djy/Quant/docs/superpowers/plans/2026-04-02-freqtrade-real-integration-implementation.md)
- [2026-04-02-qlib-minimal-research-layer-implementation.md](/home/djy/Quant/docs/superpowers/plans/2026-04-02-qlib-minimal-research-layer-implementation.md)
- [2026-04-02-qlib-trading-view-flow-design.md](/home/djy/Quant/docs/superpowers/specs/2026-04-02-qlib-trading-view-flow-design.md)
- [2026-04-02-qlib-trading-view-flow-implementation.md](/home/djy/Quant/docs/superpowers/plans/2026-04-02-qlib-trading-view-flow-implementation.md)
- [2026-04-02-platform-extension-slots-implementation.md](/home/djy/Quant/docs/superpowers/plans/2026-04-02-platform-extension-slots-implementation.md)
- [ops-freqtrade.md](/home/djy/Quant/docs/ops-freqtrade.md)
- [2026-04-01-live-trading-phase-b-design.md](/home/djy/Quant/docs/superpowers/specs/2026-04-01-live-trading-phase-b-design.md)
- [2026-04-01-live-trading-phase-b-implementation.md](/home/djy/Quant/docs/superpowers/plans/2026-04-01-live-trading-phase-b-implementation.md)
