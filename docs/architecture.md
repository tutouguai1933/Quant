# Quant Architecture

## 当前架构结论

系统当前已经进入“真实 dry-run 工作台 + 最小研究闭环”阶段。

当前 `Freqtrade` 已经完成真实 `Spot + dry-run + REST` 接入，控制平面不再只依赖内存态执行。
当前还额外补上了 live 本地安全门和 live 容器骨架，并已完成首笔真实 `DOGE/USDT` 买单验收。
当前 Docker 运行方式保留 `host` 网络，以兼容这台环境的本机代理；但 Freqtrade REST 自身只监听 `127.0.0.1`，不会对外网卡开放。
阿里云统一部署已经成功拉起 `API / WebUI / Freqtrade / Mihomo` 四个容器。
当前这台大陆服务器已经通过固定代理节点恢复公开行情与 Freqtrade 对 Binance 的访问，但签名账户链路仍受 Binance API 白名单限制。
因此系统现在把 Binance 公开行情和签名账户链路拆成了两套可单独配置的地址与超时设置。
当前默认口径是：公开行情优先走 `data-api.binance.vision`，签名账户和真实下单继续走 `api.binance.com`。
控制平面访问 Freqtrade REST 时会显式禁用代理，避免容器内的 `HTTP_PROXY` 误伤内部服务调用。
当前环境分工也已经固定：

- `WSL` 负责日常开发、测试和本地页面联调
- `GitHub` 私有仓库作为唯一代码基线
- 阿里云服务器负责真实 `dry-run / live` 验证和最终部署
- 服务器端口管理沿用“主范围固定、临时 Debug 条目按需申请和回收”的规则
- 本地运行也跟随同一套端口规则：`9011 / 9012 / 9013 / 9014 / 9015`

主链路是：

`Binance 数据 -> Qlib 研究层 -> 策略判断 -> 风控 -> Freqtrade dry-run -> 订单/持仓/任务/风险 -> WebUI`

第一阶段边界仍然不变：

- 只做 `crypto`
- 只接 `Binance`
- 只接 `Freqtrade`
- 已完成首笔真实下单验收
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
- 当前 `dry-run / live + 已配置 REST` 都可以切到真实 Freqtrade 后端
- `demo` 和 `live` 当前不会误碰真实 Freqtrade
- `live` 配置当前允许控制平面手动首单，但默认仍从 `stopped` 开始
- `start / pause / stop` 当前控制的是整台执行器，不是单张策略卡
- `flat` 当前只收敛到当前币种；如果传了 `trade_id`，则只平当前那一笔
- 重复派发会先在控制平面本地拦住，不再把重复错误完全交给远端
- 成功执行回执优先使用真实 Freqtrade 返回，而不是本地硬编码占位
- 首笔真实成交已经验证控制平面、Binance 订单、Binance 持仓和页面读数是一致的
- `live` 模式下的同步任务现在直接使用 Binance 账户同步结果，避免派发后再读 Freqtrade 快照时卡超时
- `live` 同步现在只有在 Binance 账户里确认到“刚刚派发的那一笔订单”时，才会把 signal 推进到 `synced`
- `live` 订单同步范围现在优先跟随 `QUANT_LIVE_ALLOWED_SYMBOLS`，同时会把本次派发的 symbol 临时并入，避免白名单外遗留仓位在平仓时漏单
- sync 任务如果第一次失败，后续重试成功也会把 signal 状态补齐
- live 现在会额外检查：
  - 是否显式允许 live
  - 是否连接到真实 `Freqtrade REST`
  - 远端是否是 `live + spot`
  - 是否命中 live 白名单
  - 是否超过单笔金额上限
  - 是否超过最大持仓数
  - 是否满足 Binance 最小下单额

### 6. 控制平面 API

作用：
- 对外提供统一接口
- 聚合研究、策略、信号、订单、持仓、风险、任务
- 不让前端直接连接交易所或执行器
- 在服务器部署时，作为 WebUI、Freqtrade 和研究层之间的统一入口

### 7. WebUI

作用：
- 给个人用户一个统一的操作空间
- 当前已经有策略中心、市场页、图表页、信号页、余额页、订单页、持仓页、风险页、任务页
- 页面已经能看到研究状态、研究分数、模型版本和研究解释
- 登录后的信号页主按钮和驾驶舱主按钮现在都直接走 `Qlib` 信号流水线
- 市场页、单币图表页、策略页现在开始共用统一研究摘要
- 市场页现在先承担“筛选入口”
- 单币图表页现在承担“交易主区”
- 策略页现在承担“执行页”
- 单币图表页现在已经有客户端多周期切换、专业 K 线主图、成交量副图和研究图层
- 单币图表页现在会把 `EMA20 / EMA55` 和“最近图表点”直接放到主图区摘要里
- 市场页和单币图表页现在都内置“进入策略中心”的下一步入口
- 图表页现在通过前端同源代理读取市场数据，避免浏览器直接跨端口请求 API
- 登录状态现在默认保持 7 天，页面可见性只依赖 cookie，受保护动作继续走服务端校验
- 三个页面现在统一使用“研究倾向 / 推荐策略 / 判断信心 / 主判断”这套口径
- 订单页和持仓页现在会把“列表已空”和“余额里还有交易所零头”明确区分开

## 部署与调试约定

- 本地开发环境默认是 `WSL`
- 云服务器环境默认承担：
  - 真实执行器
  - 真实控制平面 API
  - 真实 WebUI
- 服务器部署默认通过 `infra/deploy/docker-compose.yml` 统一拉起
- 服务器调试顺序固定为：
  - 先看端口
  - 再看服务日志
  - 再看接口返回
  - 最后看页面状态

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
- 统一消费 `qlib_dataset` 的训练/验证/测试切分结果
- 在候选输出前真实执行 `qlib_rule_gate` 规则门
- 输出统一实验对比摘要
- 写入最近一次训练和推理结果

### `services/api/app/services/research_service.py`

负责：

- 触发研究训练和研究推理
- 读取最近一次研究结果
- 把研究结果转换成控制平面可消费结构
- 输出统一研究报告，收口训练、推理、候选和实验摘要

### `services/api/app/services/research_factory_service.py`

负责：

- 把研究结果整理成统一候选快照
- 复用 worker 的统一实验摘要，给控制平面输出统一研究报告
- 给单币页和策略页输出可直接消费的候选摘要

### `services/api/app/services/strategy_workspace_service.py`

负责：

- 聚合策略页总览、策略卡片、账户状态和最近信号
- 输出当前研究推荐候选，告诉页面“下一步更适合先看哪个币”

### `services/api/app/services/signal_service.py`

负责：

- 保存和读取信号
- 控制信号能否进入派发
- 对通用 `Qlib` 研究信号按“当前推荐候选优先”做认领排序

### `services/api/app/services/research_cockpit_service.py`

负责：

- 把研究结果、软门控状态和图表标记收敛成统一研究摘要
- 给市场页输出 `research_brief`
- 给单币图表页和策略页输出 `research_cockpit`
- 给单币图表页补 `overlay_summary`
- 对缺研究结果、异常分数和空标记做统一降级

### `services/api/app/services/market_timeframe_service.py`

负责：

- 统一图表可选周期
- 对非法周期做默认兜底
- 输出多周期摘要所需的统一周期顺序

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
  - 执行建议
  - 推荐策略

### `apps/web/components/trading-chart-panel.tsx`

负责：
- 输出单币页主图
- 组织图表头部、左右周期条和图表壳层
- 在专业图表不可用时退回 SVG 兜底
- 展示信号点、入场线、止损线和当前价格

### `apps/web/components/timeframe-tabs.tsx`

负责：

- 输出贴在图表左右两侧的周期切换入口
- 区分快周期和高周期

### `apps/web/components/research-sidecard.tsx`

负责：

- 输出研究侧卡
- 展示研究倾向、研究门控、主判断、入场参考和止损参考

### `apps/web/components/multi-timeframe-summary.tsx`

负责：

- 输出单币页多周期摘要
- 展示不同周期下的研究倾向、推荐策略和判断强度

### `infra/deploy/docker-compose.yml`

负责：

- 在阿里云服务器统一启动 API、WebUI 和 Freqtrade
- 把默认服务端口固定到 `9011-9013`
- 让控制平面默认通过容器服务名访问 Freqtrade

### `services/api/Dockerfile`

负责：

- 构建控制平面 API 镜像
- 在服务器上用统一命令启动 `9011`

### `apps/web/Dockerfile`

负责：

- 构建 WebUI 镜像
- 在服务器上用统一命令启动 `9012`

### `apps/web/components/pro-kline-chart.tsx`

负责：

- 用 `lightweight-charts` 渲染专业 K 线主图
- 叠加成交量、副图摘要、研究标记和悬浮信息
- 提供拖拽、缩放、横纵坐标和十字光标

### `apps/web/components/market-symbol-workspace.tsx`

负责：

- 在客户端接管单币页周期切换
- 用短缓存复用已经拉过的图表结果
- 把主图区、研究侧卡、多周期摘要和执行准备串成一条交易动线

### `apps/web/components/market-snapshot-workspace.tsx`

负责：

- 让市场页先显示骨架，再补市场表格
- 在前端复用 30 秒短缓存，减少回到市场页时的等待

### `apps/web/app/api/control/[...path]/route.ts`

负责：

- 给前端客户端组件提供同源市场代理
- 避免浏览器直接跨端口请求控制面 API

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

补充：
- 公开行情和签名账户现在可以分开配置基础地址
- 所有 Binance 请求都会按统一超时收口
- 这样大陆服务器至少可以先跑通公开行情，不会把账户链路一起拖死

### `services/api/app/adapters/freqtrade/client.py`

负责：
- 统一选择 `memory` 或 `rest` 后端
- 返回策略状态、订单、持仓快照

### `services/api/app/adapters/freqtrade/rest_client.py`

负责：
- 连接真实 Freqtrade REST API
- 读取策略状态、订单、持仓
- 执行 `start / pause / stop`

### `infra/freqtrade`

负责：
- 提供 `WSL + Docker + Binance Spot + dry-run` 的最小部署骨架
- 把公开配置和私密配置拆开，避免把密钥写进仓库
- 给控制平面保留稳定的本机 REST 接入位

## 页面结构

### 市场页

当前有：
- 白名单市场列表
- 筛选入口
- 加载骨架
- 前端市场快照工作区
- 重点关注卡
- 多周期状态
- 研究倾向
- 推荐策略
- 判断信心
- 主判断
- 单币入口

### 单币图表页

当前有：
- 图表左右两侧的周期切换条
- 专业交互式 K 线主图
- 成交量副图
- `EMA20 / EMA55`
- 最近图表点摘要
- 信号点、入场线和止损线
- 研究侧卡
- 多周期摘要
- 当前判断
- 突破 / 回调判断
- 入场参考
- 止损参考
- 研究门控
- 研究倾向
- 判断信心
- 研究状态
- 研究分数
- 模型版本
- 研究解释
- Freqtrade 准备情况
- 下一步动作
- 进入策略中心

### 策略页

当前已经收成执行页，展示：
- 执行器状态
- 执行决策
- 研究状态
- 两套策略卡片
- 当前判断
- 执行建议
- 白名单摘要
- 最近信号
- 最近执行结果
- 控制动作区
- 每张策略卡片里的推荐策略、执行建议、参数摘要和最近信号
- 当前页面骨架已改成“左判断 / 右执行”的双栏终端结构

### 信号页

当前已经能展示：

- 最近信号
- 最近研究结果
- 研究训练入口
- 研究推理入口
- 当前页面骨架已改成“左候选 / 右统一研究报告”的双栏终端结构

### 首页与终端壳层

当前已经新增：

- 深色终端化壳层
- “当前工作区”摘要条
- 首页决策入口页
- 左侧推荐动作区
- 右侧当前决策板
- 统一的双栏主区规则

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
- 图表页后续再补高级交互能力
- 等待执行层和研究层做最终联调验收
- 前端后续继续把市场页、单币页和其余结果页按终端规则收口
