# 当前进度

- 当前正在做：`Phase3` 的 `A2` 已完成，下一步进入 `A3` 模板适配解释。
- 上次停留位置：`A2` 的研究模板已经补到训练 / 推理产物、研究工作台和手动流水线记录，研究页也能直接看出“当前配置模板”和“最近实际运行模板”是否对齐。

# 关键决定

- `Phase2` 视为已完成，路线图已切到 `Phase3`。
- `Phase3` 主线固定为三段：
  - 多模板研究与统一候选池
  - 研究到执行仲裁层
  - 多候选优先级、恢复与长期运行收紧
- `Phase3` 细化待办固定写在：
  - [docs/phase3-execution-todo.md](/home/djy/Quant/docs/phase3-execution-todo.md)
- `Phase3` 默认执行方式固定为：
  - 每项任务优先拆成后端、前端、review / test 三路 subagent
  - 每项做完立刻做定向回归
  - reviewer 超时由主 agent 补 review
- `A1` 新增的关键收口：
  - `live` 子集如果和候选池脱节，会落成单独状态，不再伪装成正常 `ready`
  - 评估层推荐阶段会真正受统一候选范围契约约束，不能再越过 `live` 子集直接推荐 `live`
  - 策略页在候选池为空时不再回退旧白名单，而是直接进入空态说明
- `A2` 新增的关键收口：
  - `QlibRunner` 的训练 / 推理顶层结果已经显式写出 `research_template`
  - 研究工作台新增 `artifact_templates`，能直接说明训练模板、推理模板、当前配置模板和对齐状态
  - 手动 `pipeline` 写入自动化周期时，会一起带上 `research_template` 和 `strategy_template`
  - 研究页新增“模板产物对齐”卡片，不用再猜当前看到的是不是旧模板产物

# 下一步

- 进入 `A3`：
  - 给多模板结果补“模板适配解释”
