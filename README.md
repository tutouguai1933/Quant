# Quant

> 面向个人加密量化交易的研究与执行控制平面  
> 当前状态：`Phase A` 已完成，`Phase B` 主体体验已收口，`Qlib` 最小研究层和多周期交易视图已打通；系统补强计划 `Phase 1-7` 也已全部完成，当前已经具备“研究可解释、执行可恢复、自动化可控”的完整主链。`live` 安全门和 live 容器骨架已就绪，阿里云统一部署已经拉起，并已接入 Mihomo 代理；服务器侧已完成真实 `Binance Spot` 买入、真实卖出可卖部分和执行器清账验证。

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
- 下一阶段会按“先自动运维、再自动 `dry-run`、最后小额自动 `live`”推进自动化

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
- `Phase B` 已完成前 `5` 个任务，并继续补完了市场、图表和执行页之间的核心动线
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
  - 进入单币图表页
  - 进入策略中心
- 单币图表页已经会显示：
  - 多周期切换
  - 专业交互式 K 线主图
  - 左右周期切换条
  - 成交量副图
  - `EMA20 / EMA55`
  - 最近图表点摘要
  - 信号点、入场参考和止损参考
  - 策略解释
  - 突破 / 回调判断
  - 研究门控和研究倾向
  - 判断信心和主判断
  - Freqtrade 准备情况
  - 进入策略中心的下一步动作
- 研究层已经能完成：
  - 最小训练
  - 最小推理
  - 标准化输出研究分数、解释和模型版本
  - 明确标出当前数据处在 `raw / cleaned / feature-ready` 哪一层
  - 为训练、推理、回测和报告统一回指同一份数据快照
  - 对重复使用的同一批 K 线给出缓存复用标记和缓存签名
  - 复用同一服务实例里的市场读取缓存，避免训练后紧接着推理又重复拉取一遍同批 K 线
  - 把因子整理成趋势、动量、波动、量能、震荡五类，并区分主判断因子和辅助确认因子
  - 为训练和推理统一输出同一份因子协议、预处理规则和时间周期参数映射
  - 在信号页、单币图表页、策略页展示最近研究结果
- 回测层现在已经能完成：
  - 固定手续费和滑点口径
  - 在回测结果里单独显示成本影响
  - 统计动作段数量和买卖切换次数
  - 在统一复盘里对照“回测假设”和“当前执行结果”
- 评估与复盘层现在已经能完成：
  - 统一输出固定评估指标目录
  - 给研究结果生成统一评估摘要
  - 区分研究复盘、`dry-run` 复盘、`live` 复盘
  - 在统一报告里明确哪些候选被淘汰、为什么被淘汰、下一步该做什么
- 研究层现在进一步补强了：
  - 训练上下文：会记录样本窗口、因子版本、时间周期和回测参数
  - 推理上下文：会记录输入标的、输入周期、输出信号数量和候选摘要
  - 稳定性门：会同时检查训练与验证之间的漂移，不再只看验证和回测
  - 推荐可信度：会结合分数、回测、验证和市场状态给出更稳的推荐说明
- 执行层现在进一步补强了：
  - 固定 `manual / dry-run / live / paused / takeover` 状态机
  - 订单会标出 `pending_entry / pending_exit / filled_entry / filled_exit`
  - 持仓与零头会分开统计，不再都挤在一个“余额”概念里
  - 健康摘要会明确告诉你当前该重试同步、重连执行器、继续观察待平仓，还是处理交易所零头
- 自动化层现在进一步补强了：
  - 固定调度顺序：训练 -> 推理 -> 信号输出 -> 执行 -> 复盘
  - 固定失败规则：训练/推理/信号输出失败就停，执行失败先复盘再决定
  - 每天会累计日报摘要，记录轮数、状态分布和告警数量
  - 支持 `dry-run only`
  - 支持 `Kill Switch`
- 自动化主链已经有了最小可用版本：
  - 自动化模式和全局开关
  - 统一调度入口
  - 自动 `dry-run`
  - 自动小额 `live`
  - 健康摘要和统一复盘
  - 自动化状态会本地持久化，重启后仍能恢复当前模式
- 研究到执行一体化工作台现在已完成第一步：
  - 新增数据工作台 `/data`
  - 新增数据工作台接口 `GET /api/v1/data/workspace`
  - 页面会直接显示数据来源、快照 ID、样本数量、时间范围和 `raw / cleaned / feature-ready`
  - 当样本预览失败时，会直接提示当前预览不可用，而不是假装成功

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
- Qlib 候选现在已经同时经过：
  - 规则门
  - 回测门
  - 训练验证门
- 统一研究报告现在已经会直接给出：
  - 当前推荐标的
  - 下一步动作
  - 候选排行榜
  - 筛选失败原因汇总
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
- 登录后的信号页和驾驶舱主按钮现在默认直接运行 `Qlib` 信号流水线
- 同时保留“演示信号流水线”，方便重复验证 `dry-run` 成功链路
- WebUI 现在已经切到“专业交易终端 + 决策优先”的双栏布局
- 前端现在统一走 `shadcn/ui v4` 风格的基础组件层，不再混用松散样式
- 首页、信号页、策略页、余额页、订单页、持仓页、登录页都已经完成第一轮终端化重构
- 前端验证现在固定包含：
  - 仓库级测试
  - `pnpm build`
  - Playwright 布局 / 网络 / 控制台 / axe 审计
  - Lighthouse 的 `accessibility / best-practices`
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
- 订单页和持仓页现在会主动提示：
  - 如果列表已经空了，但余额页还有少量币，优先按“交易所零头”理解
  - 不再把“余额尾数”和“系统卡着仓位”混为一谈
- 真实 `Qlib` 依赖和完整实验平台还没接入
- 更深一层的研究筛选已经开始接入，但还没有进入“长期稳定收益”阶段

## 项目结构

```text
apps/web                     Web 界面
services/api/app            控制平面 API、服务、路由、适配器
services/worker             研究层最小运行入口和研究逻辑
packages/db                 数据库结构
docs                        架构、接口、运维说明
infra/scripts               演示脚本

## 系统导览

如果你想先看懂整个系统怎么跑，再去体验页面，先读这份文档：

- [docs/system-flow-guide.md](docs/system-flow-guide.md)

它会用非技术语言解释：

- 研究层在做什么
- 点击 `运行 Qlib 信号流水线` 后系统会发生什么
- `dry-run / live / 复盘` 分别是什么意思
- 自动化工作流是怎么串起来的
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
- `services/api/app/services/validation_workflow_service.py`
  把研究、任务和执行状态整理成统一复盘报告
- `services/api/app/services/automation_service.py`
  保存自动化模式、暂停状态、最近告警和本地持久化状态
- `services/api/app/services/automation_workflow_service.py`
  把训练、推理、自动 dry-run、小额 live 和复盘收成统一自动化流程
- `services/worker/qlib_features.py`
  最小研究特征
- `services/worker/qlib_labels.py`
  最小研究标签
- `apps/web/components/ui`
  前端统一基础组件层
- `apps/web/components/app-shell.tsx`
  终端化页面壳层和主导航
- `apps/web/components/research-candidate-board.tsx`
  候选、回测摘要和失败原因面板
- `apps/web/components/trading-chart-panel.tsx`
  单币主图区和图层展示

## 本地运行

默认约定：

- 所有 Python 相关命令都在 conda 环境 `quant` 中执行
- WebUI 命令仍在 `apps/web` 下单独执行
- 日常开发以 `WSL` 为主，真实联调和最终部署以阿里云服务器为主
- 如果服务器位于中国大陆，公开行情和签名账户接口要分开检查
- 本地运行也统一遵循 `/home/djy/.port-registry.yaml`

### API

```bash
source /home/djy/miniforge3/etc/profile.d/conda.sh
conda activate quant
export QUANT_QLIB_SESSION_ID=main
mkdir -p /tmp/quant-qlib-runtime
set -a
source /home/djy/Quant/.env.quant.local
set +a
uvicorn services.api.app.main:app --host 127.0.0.1 --port 9011
```

### WebUI

```bash
cd apps/web
pnpm start --hostname 127.0.0.1 --port 9012
```

## 搜索记录

- `2026-04-04`
  - 研究对象：`shadcn/ui` 官方开源仓库
  - 参考来源：`https://github.com/shadcn-ui/ui`
  - 结论：
    - 官网精致感主要来自“主题变量 + 页面壳层 + 功能块 + 示例组合”，不是只靠基础组件
    - 最值得直接参考的路径包括：
      - `apps/v4/app/(app)/(root)/page.tsx`
      - `apps/v4/app/(app)/layout.tsx`
      - `apps/v4/components/page-header.tsx`
      - `apps/v4/registry/new-york-v4/blocks/dashboard-01/page.tsx`
      - `apps/v4/registry/new-york-v4/examples/data-table-demo.tsx`
      - `apps/v4/registry/new-york-v4/examples/chart-bar-demo.tsx`
    - 后续如果继续优化 Quant 前端，应优先复用官方“完整页面和功能块思路”，而不是只让 AI 单独拼基础组件

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
- 本地 Freqtrade REST 默认监听 `127.0.0.1:9013`

### 默认地址

- API：`http://127.0.0.1:9011`
- WebUI：`http://127.0.0.1:9012`
- Freqtrade REST：`http://127.0.0.1:9013`
- 管理员账号：`admin / 1933`
- 研究运行目录默认值：`/tmp/quant-qlib-runtime`
- 多 session 并行时建议额外设置：`QUANT_QLIB_SESSION_ID=<你的 session 名>`

### 本地端口约定

本地运行和服务器运行保持同一套口径：

- `9011`: API
- `9012`: WebUI
- `9013`: Freqtrade REST
- `9014`: Qlib
- `9015`: OpenClaw

如果某个 session 需要单独联调，就新增 `Quant-Debug-N`，联调结束后删除。

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
- 研究层现在已有统一研究报告接口，后续页面和联调优先读这一个汇总出口
- 研究运行目录现在还会留下数据快照和实验账本，方便复盘和多 session 接力
- 数据快照现在按稳定签名命名；同一批数据会复用同一路径，不再每次换一个临时文件名
- 统一研究报告和实验账本现在都会带出快照 ID、快照路径、缓存签名和当前数据层级
- 当前市场读取缓存是服务实例级缓存，进程重启后会重新读取；但数据快照和数据集缓存签名会保留，训练、推理、回测和报告的追溯口径不会变

## Qlib 验证工作流

这条工作流现在固定成同一顺序，不再临时跳步：

1. 先做研究训练
2. 再做研究推理
3. 先看候选排行榜和统一研究报告
4. 只挑“允许进入 `dry-run`”的候选
5. 先跑 `dry-run`
6. `dry-run` 稳定后，才允许进入小额 `live`
7. `live` 完成后，统一回看余额、订单、持仓、任务和风险

补充：

- 现在还可以直接读取统一复盘接口：`GET /api/v1/tasks/validation-review`
- 如果想把当前状态收成一次任务记录，可以调用：`POST /api/v1/tasks/review`
- 研究运行目录里最重要的两个文件是：
  - `dataset/latest_dataset_snapshot.json`
  - `dataset/snapshots/dataset-<cache_signature>.json`
  - `runs/experiment_index.json`

说明：

- 研究推荐只负责告诉你“下一步先看哪个币”
- 它不会绕过 `dry-run` 准入门和已有安全门
- 这条顺序同时适用于本地开发联调和阿里云上的真实验证

## 当前待办

### 当前任务清单

- [x] Task 1：把本地运行和默认地址统一到 `9011-9015`
- [x] Task 2：把真实交易后的账户状态、订单状态、页面状态完全对齐
- [x] Task 3：处理 `0.976 DOGE` 这类交易所零头
- [x] Task 4：把 `Phase B` 最后一段体验链串完整
- [x] Task 5：图表页补 `EMA20 / EMA55`
- [x] Task 6：把最近图表点做得更直观
- [x] Task 7：让市场页、图表页、策略页的动线更顺
- [x] Task 8：本地和服务器统一遵循端口注册表
- [x] Task 9：与 `Qlib` 进行对接和调试
- [x] Qlib 统一研究报告出口
- [x] 固定 `dry-run -> 小额 live -> 复盘` 验证工作流
- [x] Qlib 数据快照与实验账本
- [x] Qlib 数据层补强（`raw / cleaned / feature-ready`、快照标准化、缓存复用）
- [x] Phase 2：因子层独立（分类、预处理、统一输出协议）
- [x] Phase 3：回测层升级（成本口径、动作段统计、回测/执行对照）
- [x] Phase 4：评估与复盘层独立（统一评估指标、统一复盘出口、实验淘汰规则）
- [x] Phase 5：研究层深化（实验元数据、样本外稳定性、推荐可信度）
- [x] Phase 6：执行层工程化（状态机、零头路径、健康与失败恢复）
- [x] Phase 7：自动化系统化（调度中心、告警日报、人工接管与 Kill Switch）
- [x] Qlib 带成本的最小回测
- [x] Qlib 统一复盘接口与执行健康摘要
- [x] 自动化运维与自动买卖设计文档
- [x] 自动化运维与自动买卖实现计划
- [x] 前端终端化设计基线（决策优先 + 双栏交易研究终端）
- [x] 首页 / 信号页 / 策略页第一批终端化重构
- [ ] 研究到执行一体化工作台
  - 设计文档：`docs/superpowers/specs/2026-04-06-research-to-execution-workbench-design.md`
  - 实施计划：`docs/superpowers/plans/2026-04-06-research-to-execution-workbench-implementation.md`
  - [x] Step 1：数据工作台
  - [ ] Step 2：特征工作台
  - [ ] Step 3：策略研究工作台
  - [ ] Step 4：回测工作台
  - [ ] Step 5：评估与实验中心
  - [ ] Step 6：执行与自动化工作台收口

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
- [x] 图表页显示 `EMA20 / EMA55` 和最近图表点
- [x] 市场页和单币图表页补上“进入策略中心”的下一步入口
- [x] 订单页和持仓页补上交易所零头说明
- [x] GitHub 基线 + 阿里云统一部署骨架
- [x] 阿里云首轮容器拉起与端口联调
- [x] 阿里云 Mihomo 代理接入与公开行情恢复
- [x] 阿里云 Binance 签名账户链路收口
- [x] live 最小可卖出金额安全门
- [x] 清理服务器上的 `DOGE` 未托管现货仓位和打开中记录
- [x] 余额页标出交易所零头资产
- [x] 把服务器上剩余的 `0.976 DOGE` 收口为交易所零头处理路径
- [x] 完成 `Phase B` 剩余验收闭环
- [ ] 接入 `OpenClaw` 非交易任务触发
- [ ] 继续完成市场页、单币页和其余结果页的终端化收口

## 最小演示与验收

- 演示脚本：`infra/scripts/demo_flow.ps1`
- 运维说明：`docs/ops.md`

## 文档入口

- [docs/system-flow-guide.md](/home/djy/Quant/docs/system-flow-guide.md)
- [docs/superpowers/plans/2026-04-06-quant-system-hardening-implementation.md](/home/djy/Quant/docs/superpowers/plans/2026-04-06-quant-system-hardening-implementation.md)
- [plan.md](/home/djy/Quant/plan.md)
- [architecture.md](/home/djy/Quant/docs/architecture.md)
- [api.md](/home/djy/Quant/docs/api.md)
- [ops.md](/home/djy/Quant/docs/ops.md)
- [ops-qlib.md](/home/djy/Quant/docs/ops-qlib.md)
- [2026-04-02-platform-architecture-restoration-design.md](/home/djy/Quant/docs/superpowers/specs/2026-04-02-platform-architecture-restoration-design.md)
- [2026-04-02-freqtrade-real-integration-implementation.md](/home/djy/Quant/docs/superpowers/plans/2026-04-02-freqtrade-real-integration-implementation.md)
- [2026-04-02-qlib-minimal-research-layer-implementation.md](/home/djy/Quant/docs/superpowers/plans/2026-04-02-qlib-minimal-research-layer-implementation.md)
- [2026-04-02-qlib-trading-view-flow-design.md](/home/djy/Quant/docs/superpowers/specs/2026-04-02-qlib-trading-view-flow-design.md)
- [2026-04-04-decision-first-terminal-ui-design.md](/home/djy/Quant/docs/superpowers/specs/2026-04-04-decision-first-terminal-ui-design.md)
- [2026-04-04-decision-first-terminal-ui-implementation.md](/home/djy/Quant/docs/superpowers/plans/2026-04-04-decision-first-terminal-ui-implementation.md)
- [2026-04-04-automation-ops-and-auto-trading-design.md](/home/djy/Quant/docs/superpowers/specs/2026-04-04-automation-ops-and-auto-trading-design.md)
- [2026-04-04-automation-ops-and-auto-trading-implementation.md](/home/djy/Quant/docs/superpowers/plans/2026-04-04-automation-ops-and-auto-trading-implementation.md)
- [2026-04-06-quant-system-hardening-implementation.md](/home/djy/Quant/docs/superpowers/plans/2026-04-06-quant-system-hardening-implementation.md)
- [2026-04-02-qlib-trading-view-flow-implementation.md](/home/djy/Quant/docs/superpowers/plans/2026-04-02-qlib-trading-view-flow-implementation.md)
- [2026-04-02-platform-extension-slots-implementation.md](/home/djy/Quant/docs/superpowers/plans/2026-04-02-platform-extension-slots-implementation.md)
- [ops-freqtrade.md](/home/djy/Quant/docs/ops-freqtrade.md)
- [2026-04-01-live-trading-phase-b-design.md](/home/djy/Quant/docs/superpowers/specs/2026-04-01-live-trading-phase-b-design.md)
- [2026-04-01-live-trading-phase-b-implementation.md](/home/djy/Quant/docs/superpowers/plans/2026-04-01-live-trading-phase-b-implementation.md)
