# 自动化运维与自动买卖实现计划

关联设计文档：

- [2026-04-04-automation-ops-and-auto-trading-design.md](/home/djy/Quant/docs/superpowers/specs/2026-04-04-automation-ops-and-auto-trading-design.md)

## 范围

- 先落自动化运维、自动 `dry-run`、小额自动 `live` 的主流程。
- 保留当前手动模式和现有 `live` 安全门。

## 不在本轮范围

- `Lean / vn.py`
- 多市场自动交易
- 高频策略
- 完全无人值守模式

## Task 1：自动化模式和全局开关

- [ ] 增加统一自动化模式：
  - 手动
  - 自动 `dry-run`
  - 自动小额 `live`
- [ ] 增加全局自动化停机开关
- [ ] 增加人工接管入口

验收：

- [ ] 页面可看见当前自动化模式
- [ ] 页面可手动暂停自动化

## Task 2：统一调度入口

- [ ] 增加统一调度器，串起训练、推理、同步、复盘
- [ ] 明确每类任务的串行关系和失败重试规则
- [ ] 在任务页展示调度结果

验收：

- [ ] 能在不人工点击的情况下完成一轮训练、推理、同步、复盘

## Task 3：自动 `dry-run`

- [ ] 候选通过研究门后自动进入 `dry-run`
- [ ] 只允许当前推荐候选进入自动执行
- [ ] 自动记录 `dry-run` 结果到复盘

验收：

- [ ] 候选通过后不需要人工点派发，也能进入 `dry-run`
- [ ] 任务页和复盘页能看到本次自动 `dry-run`

## Task 4：自动小额 `live`

- [ ] 在保留现有安全门的前提下，允许自动进入小额 `live`
- [ ] 自动 `live` 只允许：
  - 白名单币种
  - 单笔限额内
  - 最大持仓数内
- [ ] 自动 `live` 后自动同步和复盘

验收：

- [ ] 自动 `live` 不会绕过现有 `live` 限制
- [ ] 自动 `live` 后页面、任务和复盘都能看到结果

## Task 5：告警和健康摘要

- [ ] 训练失败告警
- [ ] 推理失败告警
- [ ] 执行失败告警
- [ ] 同步失败告警
- [ ] 自动化健康摘要

验收：

- [ ] 失败时任务页和健康页能看到明确错误
- [ ] 页面能看见最近一次自动化是否健康

## Task 6：自动化复盘

- [ ] 把自动训练、自动推理、自动 `dry-run`、自动 `live` 收成统一复盘
- [ ] 输出下一步动作：
  - 继续研究
  - 继续 `dry-run`
  - 保留小额 `live`
  - 停机

验收：

- [ ] 复盘能回答“做了什么、结果是什么、下一步是什么”

## Task 7：页面入口与运维说明

- [ ] 在页面上加入自动化模式、停机入口和下一步动作
- [ ] 更新运维文档
- [ ] 更新 `README.md`、`CONTEXT.md`、`plan.md`

验收：

- [ ] 新会话只看文档即可知道自动化怎么工作

## 验证命令

本轮优先使用现有环境验证，不自动安装新依赖。

候选命令：

```bash
source /home/djy/miniforge3/etc/profile.d/conda.sh
conda activate quant
cd /home/djy/Quant
python -m unittest discover -s services/api/tests -v
python -m unittest discover -s services/worker/tests -v
python -m unittest discover -s tests -v
```

预期结果：

- API、Worker、文档和页面相关测试全部通过

页面验证候选命令：

```bash
cd /home/djy/Quant/apps/web
pnpm build
pnpm exec playwright test --reporter=line
```

预期结果：

- 页面构建通过
- 关键交互和页面审计通过
