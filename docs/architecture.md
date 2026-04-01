# Quant Architecture

## 当前架构结论

系统当前已经进入“真实 dry-run 工作台 + 最小研究闭环”阶段。

主链路是：

`Binance 数据 -> Qlib 研究层 -> 策略判断 -> 风控 -> Freqtrade dry-run -> 订单/持仓/任务/风险 -> WebUI`

第一阶段边界仍然不变：

- 只做 `crypto`
- 只接 `Binance`
- 只接 `Freqtrade`
- 当前不开放真实下单
- `Qlib` 当前只做最小研究层，不做完整实验平台

## 系统分层

### 1. 数据层

- Binance 市场数据
- Binance 账户数据

作用：
- 提供真实行情
- 提供真实余额

### 2. 研究层

当前研究层由 `Qlib` 最小运行入口承担。

作用：

- 准备最小研究样本
- 生成最小特征和标签
- 执行最小训练
- 执行最小推理
- 输出：
  - `signal`
  - `score`
  - `explanation`
  - `model_version`

### 3. 策略层

当前固定两套首批策略：

- `trend_breakout`
- `trend_pullback`

作用：
- 读取图表数据
- 读取研究层最近结果
- 给出当前判断：
  - `signal`
  - `watch`
  - `block`
  - `evaluation_unavailable`
- 当前采用“软门控”：
  - 原策略是主判断源
  - 研究分数只负责确认或压低信号，不单独触发新信号

### 4. 风控层

作用：
- 决定信号能否继续执行
- 把拒绝结果写成风险事件

### 5. 执行层

当前执行器：

- `Freqtrade`

作用：
- 接收控制面动作
- 维护 `demo / dry-run / live` 运行边界
- 当前以 `dry-run` 为主
- 现在已经支持 `memory / rest` 双后端门面
- 当前只有 `dry-run + 已配置 REST` 才会切到真实 Freqtrade 后端
- `demo` 和 `live` 当前不会误碰真实 Freqtrade
- `start / pause / stop` 当前控制的是整台执行器，不是单张策略卡

### 6. 控制平面 API

作用：
- 对外提供统一接口
- 聚合研究、策略、信号、订单、持仓、风险、任务
- 不让前端直接连接交易所或执行器

### 7. WebUI

作用：
- 给个人用户一个统一的操作空间
- 不做主观交易终端
- 当前已经有策略中心、市场页、图表页、信号页、余额页、订单页、持仓页、风险页、任务页
- 页面已经能看到研究状态、研究分数、模型版本和研究解释
- 市场页、单币图表页、策略页现在开始共用统一研究摘要

## 关键模块与职责

### `services/worker/qlib_config.py`

负责：

- 研究层运行目录约束
- 研究层可执行状态判断
- `qlib / qlib-fallback` 后端状态切换

### `services/worker/qlib_features.py`

负责：

- 把 K 线样本转成稳定的最小特征集合

### `services/worker/qlib_labels.py`

负责：

- 把 K 线样本转成最小训练标签

### `services/worker/qlib_runner.py`

负责：

- 执行最小训练
- 执行最小推理
- 写入最近一次训练和推理结果

### `services/api/app/services/research_service.py`

负责：

- 触发研究训练和研究推理
- 读取最近一次研究结果
- 把研究结果转换成控制平面可消费结构

### `services/api/app/services/research_cockpit_service.py`

负责：

- 把研究结果、软门控状态和图表标记收敛成统一研究摘要
- 给市场页输出 `research_brief`
- 给单币图表页和策略页输出 `research_cockpit`
- 对缺研究结果、异常分数和空标记做统一降级

### `services/api/app/services/strategy_catalog.py`

负责：
- 固定白名单
- 固定两套首批策略
- 统一输出默认参数

### `services/api/app/services/strategy_engine.py`

负责：
- `trend_breakout` 最小判断
- `trend_pullback` 最小判断

### `services/api/app/services/strategy_workspace_service.py`

负责：
- 聚合策略中心页面所需数据
- 输出：
  - 执行器运行摘要
  - 研究层总览
  - 两套策略卡片
  - 白名单摘要
  - 最近信号
  - 最近执行结果
  - 当前判断
  - 研究分数和解释摘要
  - 判断信心和研究门控状态

### `services/api/app/services/signal_service.py`

负责：
- 最小信号流水线
- 生成和保存标准化信号

### `services/api/app/services/risk_service.py`

负责：
- 基础风控判断
- 风险事件记录

### `services/api/app/services/execution_service.py`

负责：
- 把信号转换为执行动作
- 交给执行适配器

### `services/api/app/services/sync_service.py`

负责：
- 同步执行器返回的订单、持仓、策略状态
- 输出统一的执行器运行快照，给策略页、订单页、持仓页共用

### `services/api/app/adapters/binance`

负责：
- 读取 Binance 市场数据
- 读取 Binance 账户数据

### `services/api/app/adapters/freqtrade/client.py`

负责：
- 统一选择 `memory` 或 `rest` 后端
- 返回策略状态、订单、持仓快照

### `services/api/app/adapters/freqtrade/rest_client.py`

负责：
- 连接真实 Freqtrade REST API
- 读取策略状态、订单、持仓
- 执行 `start / pause / stop`

## 页面结构

### 市场页

当前有：
- 白名单市场列表
- 更适合哪套策略
- 趋势状态
- 研究倾向
- 推荐下一步
- 单币入口

### 单币图表页

当前有：
- K 线数据
- 最小指标摘要
- 策略解释
- 突破 / 回调判断
- 入场参考
- 止损参考
- 研究门控
- 研究倾向
- 研究状态
- 研究分数
- 模型版本
- 研究解释
- Freqtrade 准备情况
- 下一步动作

下一步要补：
- 把信号点、入场位、止损位做成更直观的图层
- 把 EMA 和关键参考线做成更清晰的展示

### 策略页

当前已经升级为策略中心，展示：
- 执行器状态
- 研究状态
- 两套策略卡片
- 当前判断
- 白名单摘要
- 最近信号
- 最近执行结果
- 控制动作区
- 每张策略卡片里的研究倾向、判断信心、研究门控、模型版本和研究解释

### 信号页

当前已经能展示：

- 最近信号
- 最近研究结果
- 研究训练入口
- 研究推理入口

## 当前数据真相源

- 行情：`Binance`
- 研究输出：`Qlib / qlib-fallback`
- 余额：`Binance`
- 订单与持仓：
  - `dry-run` 下默认仍以 `Freqtrade` 为真相源
  - 如果配置了真实 REST 后端，会显式显示 `freqtrade-rest-sync`
- 策略目录：`strategy_catalog`
- 页面聚合：`Control Plane API`

## 运行入口

- API：`services/api/app/main.py`
- WebUI：`apps/web/app`
- 演示脚本：`infra/scripts/demo_flow.ps1`

## 当前下一步

下一步不是再补一堆新模块，而是继续收口现有两条主线：

- `Freqtrade` 继续推进真实执行层
- `Qlib` 后续再从最小研究层升级到真实依赖和更完整实验能力
- 市场页补策略视角
- 图表页补信号点和止损线
