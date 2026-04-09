# 研究到执行一体化工作台设计

## 1. Summary

把 `Quant` 从“后端主链已打通、前端只能看到部分结果”的系统，升级成一套前端可见、可操作、可比较的研究到执行一体化工作台。

这样做的原因很直接：当前系统已经具备 `Qlib + Freqtrade + Control Plane` 主链，但用户还看不见完整的 `数据 -> 特征 -> 策略 -> 回测 -> 评估 -> 可视化 -> 工具 -> 实盘` 路线，研究过程和执行过程之间仍然存在明显断层。

## 2. Goals / Non-goals

### Goals

- 让前端正式显化 `数据层 / 特征层 / 策略研究层 / 回测层 / 评估层 / 执行与自动化层` 六个工作台。
- 让用户能明确看到“当前研究到底用了什么数据、什么因子、什么标签、什么回测口径”。
- 让用户能手动选择研究输入，而不只是被动查看结果。
- 让研究结果、回测结果、评估结果和执行结果形成一条清晰路径。
- 保留现有 `Qlib + Freqtrade + Control Plane` 主链，不推倒重来。

### Non-goals

- 这一轮不引入多市场、多资产、多券商主链。
- 这一轮不做高频系统。
- 这一轮不做新的研究框架替换 `Qlib`。
- 这一轮不先做全自动无人值守实盘。
- 这一轮不优先做视觉大换肤，先把工作台层次显性化。

## 3. Current State & Constraints

### Current State

- 当前系统已经具备：
  - `Qlib` 最小训练、推理、候选筛选、研究报告
  - `Freqtrade` 执行链
  - 自动化、复盘、健康摘要
  - 市场、单币、策略、任务、余额、订单、持仓页面
- 当前系统的问题不是“没有逻辑”，而是：
  - 数据层不显性
  - 特征层不显性
  - 回测层不显性
  - 评估与实验对比不显性
  - 用户无法在前端清楚回答“本次研究用了什么、为什么推荐、为什么淘汰”

关键文件：

- [README.md](/home/djy/Quant/README.md)
- [CONTEXT.md](/home/djy/Quant/CONTEXT.md)
- [docs/architecture.md](/home/djy/Quant/docs/architecture.md)
- [docs/system-flow-guide.md](/home/djy/Quant/docs/system-flow-guide.md)
- [docs/superpowers/plans/2026-04-06-quant-system-hardening-implementation.md](/home/djy/Quant/docs/superpowers/plans/2026-04-06-quant-system-hardening-implementation.md)

### Constraints

- 当前主链仍然只做 `crypto + Binance + Freqtrade + Qlib`。
- 当前研究主目标仍然是 `BTC / ETH / SOL / DOGE` 的单币择时，持有周期 `1-3 天`。
- 不能破坏现有 `dry-run / live / 复盘` 主链。
- 不能自动安装新依赖或修改锁文件，除非用户明确允许。
- 前端所有新页面和交互都必须做真实页面验证，不只是代码检查。

## 4. Requirements

### P0

- 提供可见的数据工作台。
- 提供可见的特征工作台。
- 提供可配置的策略研究工作台。
- 提供可配置的回测工作台。
- 提供统一的评估与实验对比中心。
- 让执行与自动化页继续承接研究结果，而不是另起一套口径。

### P1

- 支持在前端手动选择：
  - 币种
  - 时间周期
  - 时间窗口
  - 因子组
  - 标签方式
  - 成本模型
  - 筛选门开关
- 支持前端直接查看：
  - 数据快照
  - 特征协议
  - 训练上下文
  - 推理上下文
  - 候选对比
  - 淘汰原因

### P2

- 支持实验结果排序、筛选和进入 `dry-run` 的手动确认。
- 支持把某个研究实验一键送入后续验证链。

### Non-functional

- 前端必须让“当前在哪一步、下一步是什么”清晰可见。
- 新增页面要优先复用现有控制平面 API 和研究报告，不造第二套口径。
- 所有工作台都必须能回到同一条主链：
  `数据 -> 特征 -> 研究 -> 回测 -> 评估 -> 执行 -> 自动化/复盘`

## 5. Design

### Overall approach

采用“后端继续复用现有主链，前端显性化六个工作台”的方案。

后端保持当前层次：

- `Data`
- `Analysis`
- `Research`
- `Backtest`
- `Evaluation`
- `Execution`
- `Automation`
- `Control Plane`

前端则显性化成六个工作台：

1. 数据工作台
2. 特征工作台
3. 策略研究工作台
4. 回测工作台
5. 评估与实验中心
6. 执行与自动化工作台

这样做的关键不是再造一套后端，而是把已经存在的后端能力，以“工作台”的方式显性化。

### Data Workspace

回答的问题：

- 这次研究用了什么数据？
- 当前数据是否完整？
- 当前数据属于 `raw / cleaned / feature-ready` 哪一层？

应展示：

- 数据来源
- 币种
- 周期
- 时间范围
- 样本数量
- 快照 ID
- 数据状态
- 坏行/缺失摘要

### Feature Workspace

回答的问题：

- 当前启用了哪些因子？
- 哪些是主判断因子？
- 哪些是辅助确认因子？
- 当前参数是否适配 `1-3 天` 持有周期？

应展示：

- 因子分组
- 因子说明
- 参数
- 预处理规则
- 特征版本

### Strategy Research Workspace

回答的问题：

- 当前到底在研究什么策略？
- 训练窗口、验证窗口、标签定义是什么？
- 当前模型和实验参数是什么？

应展示：

- 策略模板
- 标签方式
- 持有周期
- 训练/验证/测试窗口
- 模型
- 当前实验元数据

### Backtest Workspace

回答的问题：

- 这套策略历史上到底表现怎样？
- 收益是不是被成本吃掉了？
- 动作段是不是太碎？

应展示：

- 手续费和滑点假设
- 收益、净收益、成本影响
- 回撤
- Sharpe
- 动作段数量
- 买卖切换次数

### Evaluation Workspace

回答的问题：

- 哪个实验最好？
- 为什么推荐这个币？
- 为什么别的候选被淘汰？

应展示：

- 实验排行榜
- 候选对比
- 淘汰原因
- 样本外稳定性
- 研究复盘

### Execution + Automation Workspace

回答的问题：

- 当前执行到了哪一步？
- 现在是 `manual / dry-run / live / paused / takeover` 哪种状态？
- 下一步该继续研究、继续 dry-run、继续 live，还是停机？

应展示：

- 当前推荐候选
- 执行状态机
- 健康摘要
- 调度顺序
- 告警
- 日报
- `dry-run only`
- `Kill Switch`

### Key decisions

- 不把后端重新拆一套，只把现有层次显性化。
- 前端先显性化“工作台”而不是追求复杂交互。
- 用户必须能在前端手动挑选研究输入。
- 页面设计继续沿用当前终端风格，但信息结构改成“工作台 + 主路径”。

### Alternatives

方案 A：继续维持当前后台式页面，只在现有页面补更多字段。  
优点是快；缺点是用户仍然看不清研究过程。

方案 B：做成研究到执行一体化工作台。  
优点是最符合当前项目；缺点是需要重新组织前端结构。

方案 C：先把研究平台完全独立出来，再接回执行。  
优点是研究侧更纯；缺点是会割裂现在已经打通的执行链。

推荐方案仍是 **B**。

## 6. Acceptance Criteria

- 用户能在前端直接看到数据状态、快照、时间范围和样本数量。
- 用户能在前端直接看到因子分组、主判断因子、辅助确认因子和预处理规则。
- 用户能在前端手动选择研究输入，而不是只能被动看结果。
- 用户能在回测页看到收益、净收益、成本影响、回撤、Sharpe、动作段统计。
- 用户能在评估页明确看到推荐原因和淘汰原因。
- 用户能在执行与自动化页继续沿着同一条主链往下走，不需要跳出研究链。

## 7. Validation Strategy

候选命令：

```bash
source /home/djy/miniforge3/etc/profile.d/conda.sh
conda activate quant
cd /home/djy/Quant
python -m unittest discover -s services/api/tests -v
python -m unittest discover -s services/worker/tests -v
python -m unittest discover -s tests -v
```

前端候选命令：

```bash
cd /home/djy/Quant/apps/web
pnpm build
```

真实页面验证候选：

- 验证数据工作台是否出现数据来源、快照 ID、数据状态
- 验证特征工作台是否出现因子分组和参数
- 验证回测工作台是否出现成本影响和动作段统计
- 验证评估中心是否出现推荐原因和淘汰原因
- 验证执行与自动化页是否继续保持原有主链可用

## 8. Risks & Rollback

风险：

- 前端页面会明显增多，导航和结构需要重新收。
- 如果工作台之间口径不统一，反而会让用户更困惑。
- 如果前端直接拼后端结果，容易重复造口径。

回滚：

- 新工作台按页面和组件逐步加，不直接替换老接口。
- 每个工作台独立提交，必要时可按页面回退。

## 9. Open Questions

- 第一版数据工作台是否要支持“手动刷新数据”按钮。
- 第一版特征工作台是否允许前端直接改因子开关，还是先只做“只读 + 手动选择研究模板”。

## 10. References

- [2026-04-06-quant-system-hardening-implementation.md](/home/djy/Quant/docs/superpowers/plans/2026-04-06-quant-system-hardening-implementation.md)
- [system-flow-guide.md](/home/djy/Quant/docs/system-flow-guide.md)
