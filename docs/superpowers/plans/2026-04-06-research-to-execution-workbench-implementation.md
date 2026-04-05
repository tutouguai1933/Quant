# 研究到执行一体化工作台实施计划

关联设计：

- [2026-04-06-research-to-execution-workbench-design.md](/home/djy/Quant/.worktrees/hardening-phase1/docs/superpowers/specs/2026-04-06-research-to-execution-workbench-design.md)

## Scope

- 显性化六个工作台：
  - 数据工作台
  - 特征工作台
  - 策略研究工作台
  - 回测工作台
  - 评估与实验中心
  - 执行与自动化工作台
- 复用现有后端主链，不重做执行器或研究器

## Out of Scope

- 多市场
- 高频
- 新研究框架
- 全自动无人值守实盘

## Step 1：数据工作台（已完成）

目标：

- 把数据来源、时间范围、样本数量、快照 ID、数据状态正式显性化

任务：

- 新增数据工作台 API 聚合入口
- 新增数据工作台页面
- 支持查看：
  - 数据来源
  - 币种
  - 周期
  - 时间范围
  - 样本数量
  - 快照 ID
  - `raw / cleaned / feature-ready`

验收：

- 页面能回答“这次研究到底用了什么数据”

## Step 2：特征工作台（已完成）

目标：

- 把因子层从“后端存在”变成“前端可见”

任务：

- 新增特征工作台 API 聚合入口
- 新增特征工作台页面
- 支持查看：
  - 因子组
  - 主判断因子
  - 辅助确认因子
  - 预处理规则
  - 参数映射
  - 特征版本

验收：

- 页面能回答“当前启用了哪些因子、为什么这么配”

## Step 3：策略研究工作台（已完成）

目标：

- 把训练、推理、标签和实验参数显性化

任务：

- 新增策略研究工作台页面
- 支持查看：
  - 策略模板
  - 标签方式
  - 持有周期
  - 训练/验证/测试窗口
  - 当前模型
  - 当前实验参数
- 第一版先支持最小手动选择：
  - 币种
  - 周期
  - 标签模板
  - 研究模板

验收：

- 页面能回答“这次实验到底在研究什么”

## Step 4：回测工作台（已完成）

目标：

- 把成本、动作段和结果曲线显性化

任务：

- 新增回测工作台 API 聚合入口
- 新增回测工作台页面
- 展示：
  - 收益
  - 净收益
  - 成本影响
  - 回撤
  - Sharpe
  - 动作段
  - 买卖切换次数

验收：

- 页面能回答“回测结果为什么看起来这样”

## Step 5：评估与实验中心

目标：

- 把推荐理由和淘汰理由做成可比较中心

任务：

- 新增评估与实验中心页面
- 展示：
  - 实验排行榜
  - 候选对比
  - 推荐原因
  - 淘汰原因
  - 样本外稳定性
  - 进入 `dry-run` / `live` 的门槛

验收：

- 页面能回答“为什么推荐这个币，为什么淘汰那个币”

## Step 6：执行与自动化工作台收口

目标：

- 继续承接研究结果，不让主路径断开

任务：

- 在执行页和自动化页补上来自研究层和评估层的入口
- 保持：
  - 推荐候选
  - 执行状态机
  - 健康摘要
  - 调度顺序
  - `dry-run only`
  - `Kill Switch`

验收：

- 用户能从研究工作台自然进入执行与自动化工作台

## Validation Commands

```bash
source /home/djy/miniforge3/etc/profile.d/conda.sh
conda activate quant
cd /home/djy/Quant
python -m unittest discover -s services/api/tests -v
python -m unittest discover -s services/worker/tests -v
python -m unittest discover -s tests -v
```

```bash
cd /home/djy/Quant/apps/web
pnpm build
```

## Expected Results

- 后端测试继续通过
- 前端测试继续通过
- 页面新增后仍然保持主链可走通
- 用户能明确看见：
  - 数据
  - 特征
  - 策略研究
  - 回测
  - 评估
  - 执行与自动化
