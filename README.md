# Quant

> 面向个人加密量化交易的研究与执行控制平面  
> 当前状态：`Phase A` 已完成，`Phase B` 主体体验已收口，`Qlib` 最小研究层和多周期交易视图已打通，系统已经进入“真实 dry-run 工作台 + 最小研究闭环”阶段；`live` 安全门和 live 容器骨架已就绪。阿里云统一部署已经拉起，并已接入 Mihomo 代理；服务器侧已完成真实 `Binance Spot` 买入、真实卖出可卖部分和执行器清账验证。

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
  - 专业交互式 K 线主图
  - 左右周期切换条
  - 成交量副图
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
  - live 同步现在必须确认“刚刚派发的那一笔订单”已经被 Binance 账户同步看到，才会把 signal 标成 `synced`
  - sync 任务如果第一次没追上，后面重试成功也会把 signal 补成 `synced`
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
  - `stake_amount=6`
  - `max_open_trades=1`
- Qlib 研究层现在已经从“最小 mock 信号来源”升级成“可训练、可推理、可解释的最小研究层”
- Qlib 研究结果现在已经会以“软门控”方式参与策略判断，不再只是展示
- 市场页、单币图表页、策略页现在开始共用统一研究摘要
- 市场页现在已经改成“筛选入口”
- 市场页现在会先出骨架，再补市场数据
- 市场页现在会显示：
  - 多周期状态
  - 研究倾向
  - 推荐策略
  - 判断信心
  - 主判断
- 单币图表页现在已经改成“交易主区”
- 登录状态现在默认保持 7 天
- 单币图表页现在会显示研究解释摘要、研究门控和研究倾向
- 单币图表页现在会把信号点、入场参考、止损参考直接画到专业图表主区里
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
- `live` 模式下派发后的同步任务已经修好，现在会直接走 Binance 账户同步，不再因为 Freqtrade 快照超时而失败
- 真实平仓代码路径已经收紧到“只平当前币种或当前交易”，并已补上更严格的 live 同步确认
- 阿里云服务器上的 API / WebUI / Freqtrade 容器已经成功拉起
- 阿里云服务器上的 Mihomo 代理容器已经接入
- 阿里云外网已经能直接打开 `9012` 的 WebUI 页面
- `OpenClaw` 触发非交易任务还没接入
- 服务器上的 Binance 公开行情与 Freqtrade 现在都通过固定代理节点访问
- 市场接口在代理瞬时失败时会自动回退为空结果，不再直接报错
- 服务器上的订单和持仓接口已经恢复为 `200`，不再因为容器内代理干扰 Freqtrade 而报错
- 服务器上的真实余额、真实订单和真实持仓已经恢复
- 当前服务器上还留着一笔 `DOGE` 未托管现货仓位：Binance 账户里有，但当前 `Freqtrade live` 交易库里没有
- 控制平面现在会明确提示这类“未托管现货仓位”，避免把它误判成普通平仓失败
- 这次又成功发起了一笔新的真实 `DOGE/USDT` 买单，订单号是 `14140438880`
- 这笔新单已经被当前 `Freqtrade live` 正确记录，没有和昨天那笔旧单混在一起
- 这次真实卖出失败的根因已经定位：`1 USDT` 对 `DOGE` 来说会在扣除手续费并按步长取整后低于最小卖出额
- live 安全门现在已经补上“最小可卖出金额”检查，后续会在买入前就拦住这类小仓位
- 服务器上的 live 单笔上限和执行器默认 stake 现在都已经切到 `6 USDT`
- 这次已经按真实账户执行卖出：
  - 新卖单订单号：`14140484509`
  - 实际卖出数量：`23 DOGE`
  - 卖出后 `Freqtrade` 的打开中记录已经清空
  - Binance 账户里还剩 `0.976 DOGE` 零头，这是交易所步长规则留下的尾数，不是系统还在持有一笔打开仓位
- 余额页现在会把资产直接分成“可交易”和“交易所零头”
  - `0.976 DOGE` 这类余额会明确显示成零头资产
  - 页面会同时显示可卖数量和处理提示，避免把零头误看成系统卡仓
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
infra/deploy                阿里云统一部署骨架
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
- 日常开发以 `WSL` 为主，真实联调和最终部署以阿里云服务器为主
- 如果服务器位于中国大陆，公开行情和签名账户接口要分开检查

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
- 当前 live 骨架默认只放 `DOGE/USDT`，且 `stake_amount=6`

### 默认地址

- API：`http://127.0.0.1:8000`
- WebUI：`http://127.0.0.1:3000`
- 管理员账号：`admin / 1933`
- 研究运行目录默认值：`/tmp/quant-qlib-runtime`
- 多 session 并行时建议额外设置：`QUANT_QLIB_SESSION_ID=<你的 session 名>`

## 云服务器部署方式

推荐工作方式：

- `GitHub` 私有仓库作为唯一代码基线
- `WSL`
  - 写代码
  - 跑单元测试
  - 做页面开发
  - 做本地 `demo / dry-run`
- `阿里云服务器`
  - 跑 `Freqtrade`
  - 跑控制平面 API
  - 跑 WebUI
  - 持有真实环境变量
  - 作为 Binance 白名单出口

这样做的目的很简单：

- 本地开发更快
- 真实出口 IP 更稳定
- 真实 `dry-run / live` 问题不会再被校园网出口干扰
- 多 session 和服务器都能基于同一份 GitHub 代码继续推进

### 服务器部署骨架

仓库里现在已经补了这套统一部署骨架：

- `infra/deploy/docker-compose.yml`
- `infra/deploy/.env.example`
- `infra/deploy/api.env.example`
- `services/api/Dockerfile`
- `apps/web/Dockerfile`

最小启动方式：

```bash
cd infra/deploy
cp .env.example .env
cp api.env.example api.env
docker compose up -d --build
```

默认职责：

- `9011`: API
- `9012`: WebUI
- `9013`: Freqtrade REST
- `9016`: Mihomo 代理
- `9017`: Mihomo 控制器

大陆服务器补充说明：

- 公开行情建议单独设置：
  - `QUANT_BINANCE_MARKET_BASE_URL=https://data-api.binance.vision`
- 账户同步和真实下单仍然依赖 `api.binance.com`
- 当前仓库已经提供 `infra/mihomo` 和统一部署里的代理接入位
- 如果签名接口仍返回空结果，需要把当前固定代理节点的出口 IP 加到 Binance API 白名单，而不是只加服务器公网 IP
- 现在 API 已支持这两个地址分开配置，并且 Binance 请求都会按超时收口，不会一直卡住

## 服务器端口管理

服务器端口管理和本地保持同一套规则：

- `Quant` 主应用固定使用自己的主范围
- 如果某个 session 需要临时联调，就新增一个临时条目，命名规则是 `Quant-Debug-N`，例如 `Quant-Debug-1`
- 临时条目占用下一段连续端口，例如 `9021-9030`
- 联调结束后删除临时条目，让后续 session 继续复用

当前主范围约定：

- `9011`: API
- `9012`: WebUI
- `9013`: Freqtrade REST
- `9014`: Qlib
- `9015`: OpenClaw

端口登记文件在：

- `/home/djy/.port-registry.yaml`

### 服务器调试顺序

1. 先确认端口有没有起来
2. 再看容器或服务日志
3. 再看 API 是否返回正确内容
4. 最后才看页面状态

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
- [x] GitHub 基线 + 阿里云统一部署骨架
- [x] 阿里云首轮容器拉起与端口联调
- [x] 阿里云 Mihomo 代理接入与公开行情恢复
- [x] 阿里云 Binance 签名账户链路收口
- [x] live 最小可卖出金额安全门
- [x] 清理服务器上的 `DOGE` 未托管现货仓位和打开中记录
- [x] 余额页标出交易所零头资产
- [ ] 处理服务器上剩余的 `0.976 DOGE` 零头
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
