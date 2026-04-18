# Quant 架构说明

这份文档专门回答三件事：

- 这套系统分成哪几层
- 每一层负责什么
- 新 AI 接手时，应该从哪里开始改

## 当前架构结论

系统现在已经不是单页演示，而是一个可运行的个人量化工作台。  
当前主链已经固定成：

`数据 -> 特征 -> 研究 -> 回测 -> 评估 -> dry-run -> 小额 live -> 复盘`

系统边界仍然很明确：

- 只做加密
- 只接 Binance
- 执行器只接 Freqtrade
- 研究器当前以 Qlib 为主
- 研究和执行之间通过控制平面衔接

## 系统分层

### 1. 数据层

作用：

- 拉取市场 K 线
- 拉取账户余额和订单
- 把研究输入整理成统一数据快照

当前状态：

- 已有 `raw / cleaned / feature-ready` 三层数据状态
- 训练、推理、回测和报告会回指同一份数据快照

关键目录：

- `services/api/app/services/`
- `services/worker/`
- `apps/web/app/data`

### 2. 特征层

作用：

- 把价格、波动、成交量等原始数据变成可研究的因子

当前状态：

- 已按五类组织：
  - 趋势
  - 动量
  - 震荡
  - 成交量
  - 波动率
- 已区分主判断因子和辅助因子
- `/features` 现在已经收成“因子工作台”，默认只保留分类、启用、有效性、冗余和总分解释五张摘要卡
- 因子配置、因子说明、研究承接和单因子详情都已下沉到抽屉，不再把大表单和大表格直接铺满首屏

关键目录：

- `services/api/app/services/workbench_config_service.py`
- `services/worker/qlib_runner.py`
- `apps/web/app/features`

### 3. 研究层

作用：

- 训练
- 推理
- 候选筛选
- 统一研究报告

当前状态：

- 支持最小训练和推理
- 支持规则门、验证门、回测门、一致性门
- 支持统一候选池和 `live` 子集

关键目录：

- `services/worker/`
- `services/api/app/services/research_*`
- `apps/web/app/research`
- `apps/web/app/evaluation`

### 4. 回测层

作用：

- 用统一成本模型模拟交易
- 给研究结果提供可比较的净结果

当前状态：

- 已有手续费、滑点、成本模型
- 已显示动作段、买卖切换、回测与执行差异

关键目录：

- `services/worker/qlib_backtest.py`
- `apps/web/app/backtest`

### 5. 评估与复盘层

作用：

- 解释为什么推荐
- 解释为什么淘汰
- 解释研究与执行差异
- 把研究结论和执行状态收成统一仲裁输入

当前状态：

- 已有统一研究报告
- 已有实验对比
- 已有研究 / 回测 / 执行对照
- 已补结构化执行差异码，供仲裁层稳定判断“是该继续研究，还是该先补同步 / dry-run / live”

关键目录：

- `services/api/app/services/research_factory_service.py`
- `services/api/app/services/evaluation_workspace_service.py`
- `apps/web/app/evaluation`

### 6. 研究到执行仲裁层

作用：

- 把研究推荐、执行健康、运行窗口和人工接管压成单一下一步结论

当前状态：

- `tasks/automation` 状态接口已经会返回统一 `arbitration`
- 已能区分继续研究、等待同步、进入 dry-run、进入 live、手动模式、人工接管、冷却窗口和日内等待
- 仲裁层已经有异常回退，不会因为评估层临时失败就把状态接口拖挂

关键目录：

- `services/api/app/services/research_execution_arbitration_service.py`
- `services/api/app/services/automation_workflow_service.py`

### 7. 执行层

作用：

- 把研究结果推进到 `dry-run` 或小额 `live`
- 同步订单、持仓和余额

当前状态：

- `Freqtrade + Binance` 已接通
- `dry-run` 已稳定
- 小额 `live` 已验证
- 统一候选池已经和执行链打通

关键目录：

- `services/api/app/adapters/freqtrade/`
- `services/api/app/services/signal_service.py`
- `infra/freqtrade/`

### 8. 自动化层

作用：

- 定时训练
- 定时推理
- 自动 dry-run
- 小额自动 live
- 健康摘要
- 告警
- 人工接管

当前状态：

- 调度、失败规则、人工接管、`Kill Switch` 已有
- 任务页已经能看到接管时间线和失败原因
- 任务页首屏现在只保留一个主动作区，模式切换、调度动作、告警处理和跨页跳转都通过抽屉展开

关键目录：

- `services/api/app/services/automation_*`
- `apps/web/app/tasks`

### 9. 控制平面

作用：

- 把研究、执行、自动化、页面交互串起来
- 不让前端直接碰交易所或执行器

当前状态：

- API、WebUI、自动化状态、统一配置中心都在这一层

关键目录：

- `services/api/`
- `apps/web/`

## 前端入口结构

当前前端入口已经开始按“摘要优先、细节按需展开”重排成三层：

### 1. 主工作区

1. `/`
2. `/features`
3. `/research`
4. `/evaluation`
5. `/strategies`
6. `/tasks`

它们对应的是：

- 总览
- 因子
- 研究
- 决策
- 执行
- 运维

当前首页 `/` 已先收成一个“首页主动作区”：

- 研究动作
- 执行入口
- 异常入口
- 工具跳转

这四类入口都统一从抽屉展开，不再在首页首屏并列摆多组按钮。

首页默认内容也已经进一步收成 6 张主工作台卡：

- 当前推荐
- 当前研究状态
- 当前执行状态
- 当前风险与告警
- 当前下一步动作
- 最近结果回看

每张卡都只保留一句摘要和“查看详情”抽屉，默认不再把明细直接铺满首页。

`/features` 现在已经收成“因子工作台”：

- 因子分类总览
- 当前启用因子
- 因子有效性摘要
- 因子冗余摘要
- 总分解释入口

因子配置、因子说明、研究承接和因子详情都已经下沉到抽屉；首屏不再默认铺开因子配置表单和明细表。

`/evaluation` 现在也已经收成 5 张判断摘要卡：

- 当前推荐
- 当前阻塞
- 当前下一步动作
- 推荐摘要
- 淘汰摘要

评估配置、门控细节、研究执行差异和实验对比都已经下沉到详情抽屉或弹窗，不再默认铺在首屏。

`/tasks` 现在已经收成 5 张运维摘要卡：

- 当前自动化模式
- 当前头号告警
- 当前人工接管状态
- 当前恢复建议
- 最近工作流摘要

告警历史、恢复清单、失败规则、长期运行参数、调度顺序和工作流细节都已经下沉到详情抽屉。

`/strategies` 现在已经收成 4 张执行摘要卡：

- 当前执行器状态
- 当前候选可推进性
- 当前执行模式
- 当前账户收口摘要

候选池、研究执行差异、账户回填、执行安全门配置和最近执行结果都已经下沉到详情抽屉；执行器控制动作继续保留在策略主动作区里。

### 2. 工具入口

1. `/market`
2. `/balances`
3. `/positions`
4. `/orders`
5. `/risk`

这些页面负责查明细，不再和主线页面争抢第一层注意力。

### 3. 补充入口

1. `/data`
2. `/backtest`
3. `/signals`

这些页面继续保留，但在当前信息架构里属于补充查看，不再作为默认主线入口。

## 当前最关键的设计决定

### 研究池和执行池不再完全断开

当前改成：

- 研究和 `dry-run` 共用一组更大的候选池
- `live` 再使用更严格的小子集

原因：

- 避免“研究推荐出来了，但不能继续执行”的断链

### GitHub 是唯一代码基线

原因：

- 本地、云上、不同会话要基于同一套版本推进

### 服务器是最终部署环境

当前默认分工：

- `WSL`：开发与本地验证
- GitHub：代码基线
- 阿里云服务器：最终部署、真实 dry-run / live 验证

### Binance 公开行情和签名链路分离

当前默认：

- 公开行情优先走 `data-api.binance.vision`
- 签名账户和真实下单继续走 `api.binance.com`

这样做是为了兼容当前服务器代理和白名单环境。

### 前端主入口先收口再扩展

当前默认：

- 左侧先展示主工作区
- 工具页降级成工具入口
- 数据、回测、信号保留为补充入口
- 首页、研究页、评估页、策略页、任务页都先收成单一主动作区
- 研究页默认只保留研究运行状态和 `当前状态 / 当前配置摘要 / 当前产物` 三张摘要卡，完整配置、说明和实验细节通过抽屉或弹窗展开

这样做是为了先把“现在该看什么、下一步去哪”说清楚，再逐步补详情抽屉和弹窗层。

## 新 AI 最该先读哪些文件

1. [CONTEXT.md](/home/djy/Quant/CONTEXT.md)
2. [README.md](/home/djy/Quant/README.md)
3. [docs/roadmap.md](/home/djy/Quant/docs/roadmap.md)
4. [docs/developer-handbook.md](/home/djy/Quant/docs/developer-handbook.md)
5. [docs/system-flow-guide.md](/home/djy/Quant/docs/system-flow-guide.md)

## 当前最重要的后续方向

### phase2

- 把工作台补成更完整可配置
- 把实验对比和研究 / 执行差异讲清楚
- 把长期运行能力继续收紧

### phase3

- 多模板研究与执行仲裁
- 候选池进一步扩大但保持可控
- 让推荐结果更稳定进入 `dry-run / live`

### phase4

- 更稳定的服务器运行
- 更稳定的自动化调度
- 更少人工干预

## 相关文档

- 使用动线：  
  [docs/user-handbook.md](/home/djy/Quant/docs/user-handbook.md)
- 系统流程解释：  
  [docs/system-flow-guide.md](/home/djy/Quant/docs/system-flow-guide.md)
- 开发手册：  
  [docs/developer-handbook.md](/home/djy/Quant/docs/developer-handbook.md)
- 部署手册：  
  [docs/deployment-handbook.md](/home/djy/Quant/docs/deployment-handbook.md)
