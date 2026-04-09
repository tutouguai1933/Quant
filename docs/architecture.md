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

当前状态：

- 已有统一研究报告
- 已有实验对比
- 已有研究 / 回测 / 执行对照

关键目录：

- `services/api/app/services/research_factory_service.py`
- `apps/web/app/evaluation`

### 6. 执行层

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

### 7. 自动化层

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

关键目录：

- `services/api/app/services/automation_*`
- `apps/web/app/tasks`

### 8. 控制平面

作用：

- 把研究、执行、自动化、页面交互串起来
- 不让前端直接碰交易所或执行器

当前状态：

- API、WebUI、自动化状态、统一配置中心都在这一层

关键目录：

- `services/api/`
- `apps/web/`

## 前端 6 个工作台

当前前端已经显性化为 6 个工作台：

1. `/data`
2. `/features`
3. `/research`
4. `/backtest`
5. `/evaluation`
6. `/strategies` + `/tasks`

它们对应的是：

- 数据
- 特征
- 研究
- 回测
- 评估
- 执行与自动化

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
